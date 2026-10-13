"""Playwright traces announced by robotframework-browser become trace attachments.

The Browser library is not needed here: each test logs the same announcement
`New Context` logs, pointing at a dummy zip.
"""

from __future__ import annotations

import zipfile

from conftest import load_containers, load_results

from robotframework_allurevisitor.visitor import generate

TRACE_MIME = "application/vnd.allure.playwright-trace"
ANNOUNCE = "Successfully created context and trace file will be saved to: "


def _zip(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("trace.trace", "{}")
    return path


def _traces(item):
    found = [a for a in item.get("attachments", []) if a["type"] == TRACE_MIME]
    for step in item.get("steps", []):
        found += _traces(step)
    return found


def _all_traces(results_dir):
    items = load_results(results_dir)
    for container in load_containers(results_dir):
        items += container.get("befores", []) + container.get("afters", [])
    return [trace for item in items for trace in _traces(item)]


def test_per_test_and_suite_setup_traces(robot, tmp_path):
    per_test = _zip(tmp_path / "elsewhere" / "trace_context=test.zip")
    suite = _zip(tmp_path / "elsewhere" / "trace_context=suite.zip")
    output_xml = robot(
        f"""\
*** Settings ***
Suite Setup    Log    {ANNOUNCE}{suite}

*** Test Cases ***
Traced
    [Setup]    Log    {ANNOUNCE}{per_test}
    No Operation
"""
    )
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    containers = load_containers(results_dir)
    (result,) = load_results(results_dir)
    (test_container,) = [c for c in containers if c["name"] == result["name"]]
    (suite_container,) = [c for c in containers if c["name"] == "Suite"]

    (test_trace,) = _traces(test_container["befores"][0])
    assert test_trace["name"] == "trace_context=test.zip"
    assert test_trace["source"].endswith(".zip")
    assert (results_dir / test_trace["source"]).read_bytes() == per_test.read_bytes()

    (suite_trace,) = _traces(suite_container["befores"][0])
    assert suite_trace["name"] == "trace_context=suite.zip"

    # Each trace is attached exactly once, and the announcement stays in the log.
    assert len(_all_traces(results_dir)) == 2
    assert [a["name"] for a in test_container["befores"][0]["attachments"]].count(
        "Keyword Log"
    ) == 1


def test_relocated_output_directory(robot, tmp_path):
    _zip(tmp_path / "browser" / "traces" / "trace_context=moved.zip")
    _zip(tmp_path / "browser" / "traces" / "trace_context=win.zip")
    output_xml = robot(
        f"""\
*** Test Cases ***
Moved
    Log    {ANNOUNCE}/ci/run/42/browser/traces/trace_context=moved.zip
    Log    {ANNOUNCE}C:\\\\Users\\\\John Doe\\\\out\\\\browser\\\\traces\\\\trace_context=win.zip
"""
    )
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    names = sorted(trace["name"] for trace in _all_traces(results_dir))
    assert names == ["trace_context=moved.zip", "trace_context=win.zip"]


def test_missing_trace_is_skipped(robot, tmp_path):
    output_xml = robot(
        f"*** Test Cases ***\nGone\n    Log    {ANNOUNCE}/nowhere/trace_context=gone.zip\n"
    )
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"
    assert _all_traces(results_dir) == []


def test_no_tracing_configured(robot, tmp_path):
    output_xml = robot("*** Test Cases ***\nPlain\n    Log    nothing to see\n")
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)
    assert _all_traces(results_dir) == []
