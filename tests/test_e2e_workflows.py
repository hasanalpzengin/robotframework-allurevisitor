"""pabot, re-execution, and both together, with real robotframework-browser artifacts.

Every workflow runs once (module fixtures) with the live listener attached, and its
``output.xml`` files are then converted with ``rf-allure``. The listener resolves
screenshots against each process's own ``${OUTPUT DIR}``, so its attempts are the
ground truth the converter is compared with, by screenshot content.

Each test's page shows the test name and run, so every attempt's screenshots have
distinct content: a screenshot resolved from the wrong directory shows up as a
mismatch. Needs the ``browser`` dependency group (Browser + pabot).
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from allure_cli import GENERATORS, generate_report, walk
from conftest import load_containers, load_results

pytestmark = pytest.mark.browser

TRACE_MIME = "application/vnd.allure.playwright-trace"

SUITE = """\
*** Settings ***
Library          Browser
Library          OperatingSystem
Test Setup       New Context    tracing=True
Test Teardown    Close Context

*** Test Cases ***
Flaky {name}
    Show And Shoot
    # Fails on the first attempt only: the flag file exists on the rerun.
    ${{rerun}}=    Run Keyword And Return Status    File Should Exist    ${{FLAGS}}/${{TEST NAME}}
    Create File    ${{FLAGS}}/${{TEST NAME}}
    Should Be True    ${{rerun}}    first attempt fails

Stable {name}
    Show And Shoot

*** Keywords ***
Show And Shoot
    New Page    data:text/html,<h1>${{TEST NAME}} ${{RUN}}</h1>
    Take Screenshot
"""

TESTS = ["Flaky A", "Flaky B", "Stable A", "Stable B"]

# Failure messages meaning "Browser is installed but cannot run here".
_UNAVAILABLE_HINTS = ("Executable doesn't exist", "rfbrowser init", "Could not connect")


# ----------------------------------------------------------------- running
@dataclass
class Workflow:
    work: Path
    listener: Path  # the listener's results directory (all runs)
    outputs: list[Path]  # output.xml per run: original, then rerun


def _require_tools() -> None:
    if importlib.util.find_spec("Browser") is None:
        pytest.skip("robotframework-browser is not installed (uv sync --group browser)")
    if importlib.util.find_spec("pabot") is None:
        pytest.skip("robotframework-pabot is not installed (uv sync --group browser)")


def _suites(work: Path) -> Path:
    suites = work / "suites"
    suites.mkdir()
    for name in ("A", "B"):
        (suites / f"{name.lower()}.robot").write_text(SUITE.format(name=name))
    return suites


def _run(work: Path, runner: list[str], outdir: Path, run: str, *extra: str) -> Path:
    listener = f"robotframework_allurevisitor.Listener:{work / 'listener'}"
    completed = subprocess.run(
        [
            sys.executable,
            *runner,
            "--outputdir",
            str(outdir),
            "--variable",
            f"RUN:{run}",
            "--variable",
            f"FLAGS:{work / 'flags'}",
            "--listener",
            listener,
            *extra,
            str(work / "suites"),
        ],
        capture_output=True,
        text=True,
        cwd=work,  # pabot writes .pabotsuitenames into its working directory
    )
    output_xml = outdir / "output.xml"
    log = output_xml.read_text() if output_xml.is_file() else completed.stdout
    if any(hint in log for hint in _UNAVAILABLE_HINTS):
        pytest.skip("Browser library is installed but its browsers are not available")
    if not output_xml.is_file():
        pytest.fail(f"run produced no output.xml:\n{completed.stdout[-3000:]}")
    return output_xml


ROBOT = ["-m", "robot"]
PABOT = ["-m", "pabot.pabot", "--processes", "2", "--artifacts", "png,zip"]
PABOT += ["--artifactsinsubfolders"]


def _workflow(tmp_path_factory, name: str, runner: list[str], rerun: bool) -> Workflow:
    _require_tools()
    work = tmp_path_factory.mktemp(name)
    _suites(work)
    outputs = [_run(work, runner, work / "out", "original")]
    if rerun:
        # Browser wipes browser/ in its output directory at start: rerun elsewhere.
        outputs.append(
            _run(work, runner, work / "out" / "rerun", "rerun", "--rerunfailed", str(outputs[0]))
        )
    return Workflow(work, work / "listener", outputs)


@pytest.fixture(scope="module")
def pabot_run(tmp_path_factory) -> Workflow:
    return _workflow(tmp_path_factory, "pabot", PABOT, rerun=False)


@pytest.fixture(scope="module")
def rerun_run(tmp_path_factory) -> Workflow:
    return _workflow(tmp_path_factory, "rerun", ROBOT, rerun=True)


@pytest.fixture(scope="module")
def pabot_rerun_run(tmp_path_factory) -> Workflow:
    return _workflow(tmp_path_factory, "pabot-rerun", PABOT, rerun=True)


def _convert(workflow: Workflow, name: str, *args: str, sources=None) -> tuple[Path, str]:  # noqa: ANN001
    results = workflow.work / name
    completed = subprocess.run(
        [sys.executable, "-m", "robotframework_allurevisitor.cli"]
        + [str(s) for s in (sources or workflow.outputs)]
        + ["-o", str(results), "--clean", *args],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return results, completed.stderr


# --------------------------------------------------------------- attempts
@dataclass(frozen=True)
class Attempt:
    name: str
    status: str
    history_id: str
    images: frozenset[str]  # screenshot content hashes
    traces: frozenset[str]  # trace attachment names (uuid-named by Browser)
    thread: str | None


def _attachments(item: dict):  # noqa: ANN202
    yield from item.get("attachments", [])
    for step in item.get("steps", []):
        yield from _attachments(step)


def _attempts(results_dir: Path) -> list[Attempt]:
    containers = load_containers(results_dir)
    attempts = []
    for result in load_results(results_dir):
        befores = [
            before
            for container in containers
            if container.get("children") == [result["uuid"]]
            for before in container.get("befores", [])
        ]
        images = {
            hashlib.sha256((results_dir / a["source"]).read_bytes()).hexdigest()
            for a in _attachments(result)
            if a["type"] == "image/png"
        }
        traces = {a["name"] for b in befores for a in _attachments(b) if a["type"] == TRACE_MIME}
        labels = {label["name"]: label["value"] for label in result["labels"]}
        attempts.append(
            Attempt(
                result["name"],
                result["status"],
                result["historyId"],
                frozenset(images),
                frozenset(traces),
                labels.get("thread"),
            )
        )
    return attempts


def _by_name_and_status(attempts: list[Attempt]) -> dict[tuple[str, str], Attempt]:
    keyed = {(a.name, a.status): a for a in attempts}
    assert len(keyed) == len(attempts), "two attempts of one test with the same status"
    return keyed


def _assert_own_artifacts(attempts: list[Attempt]) -> None:
    """Every attempt has a screenshot and a trace, and shares neither with another."""
    for attempt in attempts:
        assert attempt.images, f"{attempt.name} ({attempt.status}): no screenshot"
        assert len(attempt.traces) == 1, f"{attempt.name} ({attempt.status}): {attempt.traces}"
    images = [image for attempt in attempts for image in attempt.images]
    traces = [trace for attempt in attempts for trace in attempt.traces]
    assert len(images) == len(set(images)), "a screenshot is attached to two attempts"
    assert len(traces) == len(set(traces)), "a trace is attached to two attempts"


def _assert_retries(attempts: list[Attempt]) -> None:
    """Flaky tests failed then passed (one historyId); stable tests ran once."""
    assert sorted((a.name, a.status) for a in attempts) == [
        ("Flaky A", "failed"),
        ("Flaky A", "passed"),
        ("Flaky B", "failed"),
        ("Flaky B", "passed"),
        ("Stable A", "passed"),
        ("Stable B", "passed"),
    ]
    for name in ("Flaky A", "Flaky B"):
        assert len({a.history_id for a in attempts if a.name == name}) == 1


def _latest(attempts: list[Attempt]) -> dict[str, Attempt]:
    """The attempt `rebot --merge` keeps: the passed one where a test was re-executed."""
    latest: dict[str, Attempt] = {}
    for attempt in attempts:
        if attempt.name not in latest or attempt.status == "passed":
            latest[attempt.name] = attempt
    return latest


def _without_thread(attempts) -> set[Attempt]:  # noqa: ANN001
    return {Attempt(a.name, a.status, a.history_id, a.images, a.traces, None) for a in attempts}


# ------------------------------------------------------------------- pabot
def test_pabot_listener(pabot_run):
    attempts = _attempts(pabot_run.listener)
    assert sorted(a.name for a in attempts) == TESTS
    _assert_own_artifacts(attempts)
    pools = {a.thread.split("-", 1)[0] for a in attempts}
    assert len(pools) == 2, f"expected two pabot processes, got threads {pools}"


def test_pabot_converter_matches_listener(pabot_run):
    results, _ = _convert(pabot_run, "converted")
    attempts = _attempts(results)
    _assert_own_artifacts(attempts)
    assert _without_thread(attempts) == _without_thread(_attempts(pabot_run.listener))


# ------------------------------------------------------------------ rerun
@pytest.fixture(scope="module", params=["rerun", "pabot-rerun"])
def rerun_workflow(request) -> Workflow:
    fixture = "rerun_run" if request.param == "rerun" else "pabot_rerun_run"
    return request.getfixturevalue(fixture)


def test_rerun_listener_records_retries(rerun_workflow):
    attempts = _attempts(rerun_workflow.listener)
    _assert_retries(attempts)
    _assert_own_artifacts(attempts)


def test_rerun_converter_retries_match_listener(rerun_workflow):
    results, _ = _convert(rerun_workflow, "retries")
    attempts = _attempts(results)
    _assert_retries(attempts)
    _assert_own_artifacts(attempts)
    assert _without_thread(attempts) == _without_thread(_attempts(rerun_workflow.listener))


def test_rerun_converter_merge_keeps_latest_attempts(rerun_workflow):
    results, _ = _convert(rerun_workflow, "merged", "--merge")
    attempts = _attempts(results)
    assert sorted(a.name for a in attempts) == TESTS
    assert {a.status for a in attempts} == {"passed"}
    expected = _latest(_attempts(rerun_workflow.listener))
    for attempt in attempts:
        listener = expected[attempt.name]
        assert (attempt.images, attempt.traces) == (listener.images, listener.traces)


def test_rerun_rebot_merged_output(rerun_workflow):
    original, rerun = rerun_workflow.outputs
    merged = original.parent / "merged.xml"
    subprocess.run(
        [sys.executable, "-m", "robot.rebot", "--merge", "--output", str(merged)]
        + ["--log", "NONE", "--report", "NONE", str(original), str(rerun)],
        capture_output=True,
        check=False,
    )
    results, stderr = _convert(rerun_workflow, "rebot-merged", sources=[merged])

    by_name = {r["name"]: r for r in load_results(results)}
    assert sorted(by_name) == TESTS
    assert {r["status"] for r in by_name.values()} == {"passed"}
    for name in ("Flaky A", "Flaky B"):
        message = by_name[name]["statusDetails"]["message"]
        assert message.startswith("Test has been re-executed and results merged.")
        assert "<" not in message
    # The rerun's relative screenshot paths now resolve next to merged.xml. With
    # Browser's per-run names they hit the original run's files (warned as possibly
    # foreign); pabot's prefixed copies are unique, so they are missing (warned too).
    if rerun_workflow.work.name.startswith("pabot"):
        assert "screenshot not found" in stderr
    else:
        for name in ("Flaky A", "Flaky B"):
            assert f"'{name}' was merged by rebot --merge" in stderr
    assert "'Stable" not in stderr


# ----------------------------------------------------------------- reports
REPORT_SOURCES = {
    "converter": lambda w: _convert(w, "report-converted")[0],
    "merge": lambda w: _convert(w, "report-merged", "--merge")[0],
    "listener": lambda w: w.listener,
}
WORKFLOWS = {"pabot": "pabot_run", "rerun": "rerun_run", "pabot-rerun": "pabot_rerun_run"}


# A single pabot run has nothing to merge.
REPORT_CASES = [
    (workflow, source)
    for workflow in WORKFLOWS
    for source in REPORT_SOURCES
    if not (workflow == "pabot" and source == "merge")
]


@pytest.mark.parametrize("generator", GENERATORS)
@pytest.mark.parametrize(("workflow_name", "source"), REPORT_CASES)
def test_reports(request, workflow_name, source, generator):
    workflow = request.getfixturevalue(WORKFLOWS[workflow_name])
    results = REPORT_SOURCES[source](workflow)
    report = generate_report(generator, results, workflow.work / f"report-{source}-{generator}")
    reran = len(workflow.outputs) > 1
    context = f"({workflow_name}, {source}, {generator})"

    cases = {case["name"]: case for case in report.test_cases()}
    assert sorted(cases) == TESTS, context
    for name, case in cases.items():
        flaky = name.startswith("Flaky")
        expected_status = "failed" if flaky and not reran else "passed"
        assert case["status"] == expected_status, f"{name} {context}"
        # Retries mode and the listener keep the failed attempt; merge drops it.
        expected_retries = 1 if flaky and reran and source != "merge" else 0
        assert case["retries"] == expected_retries, f"{name} retries {context}"
        images = [a for node in walk(case["steps"]) for a in node["attachments"]]
        assert any(a["type"] == "image/png" for a in images), f"{name}: no screenshot {context}"
        setup = [a["type"] for fixture in case["setup"] for a in fixture["attachments"]]
        assert TRACE_MIME in setup, f"{name}: no trace {context}"
