"""Several sources: per-source identity and files (retries) and the converter merge."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import load_containers, load_results, run_robot

from robotframework_allurevisitor.cli import main
from robotframework_allurevisitor.visitor import generate

# Every run writes its own shot.png (content = the run name) next to its output.xml,
# so an attachment's content tells which run's directory it was resolved from.
SUITE = """\
*** Settings ***
Library        OperatingSystem
Suite Setup    Shoot    setup

*** Test Cases ***
Flaky
    Shoot    flaky
    Should Be Equal    %{RESULT}    pass

Stable
    Shoot    stable

*** Keywords ***
Shoot
    [Arguments]    ${what}
    Create File    ${OUTPUT DIR}/${what}.png    %{RUN}
    Log    <img src="${what}.png">    html=True
"""


def _run(tmp_path: Path, name: str, result: str, *args: str) -> Path:
    work = tmp_path / name
    work.mkdir()
    return run_robot(SUITE, work, env={"RESULT": result, "RUN": name}, args=list(args))


def _two_runs(tmp_path: Path) -> tuple[Path, Path]:
    original = _run(tmp_path, "original", "fail")
    rerun = _run(tmp_path, "rerun", "pass", "--rerunfailed", str(original))
    return original, rerun


def _images(results_dir: Path, item: dict) -> list[str]:
    """Contents of the image attachments anywhere below ``item``."""
    found = []
    for attachment in item.get("attachments", []):
        if attachment["type"] == "image/png":
            found.append((results_dir / attachment["source"]).read_text())
    for step in item.get("steps", []):
        found.extend(_images(results_dir, step))
    return found


def _identity(result: dict) -> tuple:
    suites = sorted(
        (label["name"], label["value"])
        for label in result["labels"]
        if label["name"] in ("parentSuite", "suite", "subSuite")
    )
    return result["fullName"], result["historyId"], tuple(suites)


def test_multisource_identity_matches_single_source(tmp_path):
    original, rerun = _two_runs(tmp_path)
    single, combined = tmp_path / "single", tmp_path / "combined"
    generate(original, single)
    generate([original, rerun], combined)

    single_ids = {r["name"]: _identity(r) for r in load_results(single)}
    for result in load_results(combined):
        assert _identity(result) == single_ids[result["name"]]
    assert sorted(r["name"] for r in load_results(combined)) == ["Flaky", "Flaky", "Stable"]


def test_multisource_resolves_files_per_source(tmp_path):
    original, rerun = _two_runs(tmp_path)
    results_dir = tmp_path / "allure"
    generate([original, rerun], results_dir)

    flaky = {r["status"]: r for r in load_results(results_dir) if r["name"] == "Flaky"}
    assert _images(results_dir, flaky["failed"]) == ["original"]
    assert _images(results_dir, flaky["passed"]) == ["rerun"]


def test_merge_keeps_latest_attempt_with_its_own_files(tmp_path):
    original, rerun = _two_runs(tmp_path)
    results_dir = tmp_path / "allure"
    generate([original, rerun], results_dir, merge=True)

    results = {r["name"]: r for r in load_results(results_dir)}
    assert sorted(results) == ["Flaky", "Stable"]  # one result per test
    flaky, stable = results["Flaky"], results["Stable"]
    assert flaky["status"] == "passed"
    assert "re-executed and results merged" in flaky["statusDetails"]["message"]
    assert _images(results_dir, flaky) == ["rerun"]
    # Not re-executed: kept from the original run, with the original run's file.
    assert stable["status"] == "passed"
    assert _images(results_dir, stable) == ["original"]
    # Robot's merge takes the re-executed suite's setup from the rerun.
    (suite,) = [c for c in load_containers(results_dir) if c.get("name") == "Suite"]
    assert _images(results_dir, suite["befores"][0]) == ["rerun"]


def test_cli_merge_flag(tmp_path):
    original, rerun = _two_runs(tmp_path)
    merged, retries = tmp_path / "merged", tmp_path / "retries"
    assert main([str(original), str(rerun), "-o", str(merged), "--merge"]) == 0
    assert main([str(original), str(rerun), "-o", str(retries)]) == 0
    assert sorted(r["name"] for r in load_results(merged)) == ["Flaky", "Stable"]
    assert sorted(r["name"] for r in load_results(retries)) == ["Flaky", "Flaky", "Stable"]


def test_broken_source_does_not_stop_the_others(tmp_path, capsys):
    original, rerun = _two_runs(tmp_path)
    broken = tmp_path / "broken.xml"
    broken.write_text("<robot><suite")
    results_dir = tmp_path / "allure"
    generate([broken, original], results_dir)

    assert "stopped early" in capsys.readouterr().err
    assert sorted(r["name"] for r in load_results(results_dir)) == ["Flaky", "Stable"]


def test_rebot_merged_message_is_plain_text(tmp_path):
    original = _run(tmp_path, "original", "fail")
    rerun = _run(tmp_path, "rerun", "still <failing> & bad", "--rerunfailed", str(original))
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [sys.executable, "-m", "robot.rebot", "--merge", "--output", str(merged)]
        + ["--log", "NONE", "--report", "NONE", str(original), str(rerun)],
        check=False,
        capture_output=True,
    )
    results_dir = tmp_path / "allure"
    generate(merged, results_dir)

    (flaky,) = [r for r in load_results(results_dir) if r["name"] == "Flaky"]
    message = flaky["statusDetails"]["message"]
    assert flaky["status"] == "failed"
    assert "<span" not in message and "*HTML*" not in message
    assert message.splitlines() == [
        "Test has been re-executed and results merged.",
        "New status: FAIL",
        "New message: still <failing> & bad != pass",
        "Old status: FAIL",
        "Old message: fail != pass",
    ]


def test_pass_execution_message_is_kept(robot, tmp_path):
    output_xml = robot("*** Test Cases ***\nDone Early\n    Pass Execution    nothing to do\n")
    results_dir = tmp_path / "allure"
    generate(output_xml, results_dir)
    (result,) = load_results(results_dir)
    assert result["status"] == "passed"
    assert result["statusDetails"]["message"] == "nothing to do"


MISSING_IMAGE_SUITE = """\
*** Test Cases ***
Screens
    Log    <img src="browser/screenshot/fail-screenshot-1.png">    html=True
    Log    <img src="https://example.com/logo.png">    html=True
"""


def test_missing_screenshot_warns_and_stays_in_log(robot, tmp_path, capsys):
    output_xml = robot(MISSING_IMAGE_SUITE)
    results_dir = tmp_path / "allure"
    generate(output_xml, results_dir)

    err = capsys.readouterr().err
    assert "browser/screenshot/fail-screenshot-1.png" in err
    assert "--artifactsinsubfolders" in err
    assert "example.com" not in err  # remote images are not files: no warning
    (result,) = load_results(results_dir)
    log = next(a for s in result["steps"] for a in s.get("attachments", []))
    assert "fail-screenshot-1.png" in (results_dir / log["source"]).read_text()


def test_rebot_merged_relative_screenshot_warns(tmp_path, capsys):
    # A rerun into its own directory: rebot --merge keeps the relative path, which
    # then resolves next to merged.xml, i.e. against the original run's files.
    original, rerun = _two_runs(tmp_path)
    merged = tmp_path / "original" / "merged.xml"
    subprocess.run(
        [sys.executable, "-m", "robot.rebot", "--merge", "--output", str(merged)]
        + ["--log", "NONE", "--report", "NONE", str(original), str(rerun)],
        check=False,
        capture_output=True,
    )
    generate(merged, tmp_path / "allure")
    err = capsys.readouterr().err
    assert "'Flaky' was merged by rebot --merge" in err
    assert "rf-allure --merge" in err
    assert "'Stable'" not in err  # not re-executed: its paths are its own

    # Our own merge knows where every test came from: no such warning.
    generate([original, rerun], tmp_path / "own-merge", merge=True)
    assert "rebot --merge" not in capsys.readouterr().err
