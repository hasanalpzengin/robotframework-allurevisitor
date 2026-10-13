"""Real robotframework-browser run -> Playwright traces in Allure 2 and Allure 3 reports.

Needs the optional ``browser`` dependency group (``uv sync --group browser``,
then ``rfbrowser init``). Skips when the Browser library or its browsers are
unavailable, so the default test run never depends on Playwright.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys

import pytest
from allure_cli import GENERATORS, generate_report
from conftest import load_containers

from robotframework_allurevisitor.visitor import generate

TRACE_MIME = "application/vnd.allure.playwright-trace"

PER_TEST_SUITE = """\
*** Settings ***
Library          Browser
Test Setup       New Context    tracing=True
Test Teardown    Close Context

*** Test Cases ***
Per Test Context
    New Page    data:text/html,<h1>one</h1>
    Get Text    h1    ==    one
"""

SHARED_SUITE = """\
*** Settings ***
Library           Browser
Suite Setup       New Context    tracing=True
Suite Teardown    Close Context

*** Test Cases ***
Shared Context A
    New Page    data:text/html,<h1>a</h1>
    Get Text    h1    ==    a

Shared Context B
    New Page    data:text/html,<h1>b</h1>
    Get Text    h1    ==    b
"""

# Failure messages meaning "Browser is installed but cannot run here".
_UNAVAILABLE_HINTS = ("Executable doesn't exist", "rfbrowser init", "Could not connect")


def _run_browser_suites(work, extra_args=()):
    if importlib.util.find_spec("Browser") is None:
        pytest.skip("robotframework-browser is not installed (uv sync --group browser)")
    suites = work / "suites"
    suites.mkdir()
    (suites / "per_test.robot").write_text(PER_TEST_SUITE)
    (suites / "shared.robot").write_text(SHARED_SUITE)
    out = work / "out"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(out),
            "--name",
            "Browser",
            *extra_args,
            str(suites),
        ],
        capture_output=True,
        text=True,
    )
    output_xml = out / "output.xml"
    log = output_xml.read_text() if output_xml.is_file() else completed.stdout
    if completed.returncode != 0:
        if any(hint in log for hint in _UNAVAILABLE_HINTS):
            pytest.skip("Browser library is installed but its browsers are not available")
        pytest.fail(f"Browser suite failed:\n{completed.stdout[-3000:]}")
    return output_xml


@pytest.fixture(scope="module")
def browser_run(tmp_path_factory):
    work = tmp_path_factory.mktemp("browser")
    output_xml = _run_browser_suites(work)
    results_dir = work / "allure-results"
    generate(output_xml, results_dir, clean=True)
    return work, results_dir


@pytest.fixture(scope="module")
def browser_listener_run(tmp_path_factory):
    """Same suites with the live listener: traces are only written at Close Context."""
    work = tmp_path_factory.mktemp("browser-listener")
    results_dir = work / "allure-results"
    _run_browser_suites(
        work, ["--listener", f"robotframework_allurevisitor.Listener:{results_dir}"]
    )
    return work, results_dir


def _trace_names(items):
    return [
        a["name"] for item in items for a in item.get("attachments", []) if a["type"] == TRACE_MIME
    ]


@pytest.mark.browser
def test_traces_attached_in_results(browser_run):
    _, results_dir = browser_run
    containers = {c["name"]: c for c in load_containers(results_dir)}

    # Per-test context: New Context is the test [Setup] -> trace on that test's fixture.
    per_test = _trace_names(containers["Per Test Context"]["befores"])
    # Suite-level context: New Context is the Suite Setup -> trace on the suite fixture.
    shared = _trace_names(containers["Shared"]["befores"])

    assert len(per_test) == 1 and per_test[0].startswith("trace_context=")
    assert len(shared) == 1 and shared[0].startswith("trace_context=")
    assert per_test != shared


@pytest.mark.browser
@pytest.mark.parametrize("generator", GENERATORS)
def test_traces_in_reports(browser_run, generator):
    work, results_dir = browser_run
    report = generate_report(generator, results_dir, work / f"report-{generator}")

    for case in report.test_cases():
        setup_types = [a["type"] for fixture in case["setup"] for a in fixture["attachments"]]
        assert TRACE_MIME in setup_types, f"{case['name']}: no trace in setup ({generator})"


@pytest.mark.browser
def test_listener_captures_traces(browser_listener_run):
    _, results_dir = browser_listener_run
    containers = {c["name"]: c for c in load_containers(results_dir)}
    assert len(_trace_names(containers["Per Test Context"]["befores"])) == 1
    # Suite-level context: the zip appears only at Suite Teardown's Close Context.
    assert len(_trace_names(containers["Shared"]["befores"])) == 1
    for name in ("Per Test Context", "Shared"):
        for attachment in containers[name]["befores"][0]["attachments"]:
            assert (results_dir / attachment["source"]).is_file()


@pytest.mark.browser
@pytest.mark.parametrize("generator", GENERATORS)
def test_listener_traces_in_reports(browser_listener_run, generator):
    work, results_dir = browser_listener_run
    report = generate_report(generator, results_dir, work / f"report-{generator}")
    for case in report.test_cases():
        setup_types = [a["type"] for fixture in case["setup"] for a in fixture["attachments"]]
        assert TRACE_MIME in setup_types, f"{case['name']}: no trace in setup ({generator})"
