"""AllureLibrary keywords and the testplan pre-run modifier."""

from __future__ import annotations

import json

from conftest import find_step, load_results
from robot.api import ExecutionResult

LISTENER = "robotframework_allurevisitor.Listener"

LIBRARY_SUITE = """\
*** Settings ***
Library        robotframework_allurevisitor.AllureLibrary
Suite Setup    Global Attach    build-info    name=build

*** Test Cases ***
Keywords
    Attach    hello    name=greeting    attachment_type=TEXT
    Attach File    ${CURDIR}/trace.zip    name=trace
    ...    attachment_type=application/vnd.allure.playwright-trace    extension=zip
    Global Error    env down
"""


def _run_library_suite(robot, tmp_path, args):
    (tmp_path / "trace.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    return robot(LIBRARY_SUITE, args=args)


def test_library_keywords_with_listener(robot, tmp_path):
    _run_library_suite(robot, tmp_path, ["--listener", LISTENER])
    results_dir = tmp_path / "output" / "allure"

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"
    (greeting,) = find_step(result["steps"], "Attach")["attachments"]
    assert greeting["name"] == "greeting" and greeting["type"] == "text/plain"
    assert (results_dir / greeting["source"]).read_text() == "hello"

    trace = next(
        a for a in find_step(result["steps"], "Attach File")["attachments"] if a["name"] == "trace"
    )
    assert trace["type"] == "application/vnd.allure.playwright-trace"
    assert trace["source"].endswith(".zip")

    globals_items = [json.loads(f.read_text()) for f in results_dir.glob("*-globals.json")]
    attachments = [a["name"] for g in globals_items for a in g.get("attachments", [])]
    errors = [e["message"] for g in globals_items for e in g.get("errors", [])]
    assert attachments == ["build"] and errors == ["env down"]


def test_library_keywords_without_listener(robot, tmp_path):
    output_xml = _run_library_suite(robot, tmp_path, [])

    assert ExecutionResult(str(output_xml)).suite.status == "PASS"
    assert not (tmp_path / "output").exists()


PLAN_SUITE = """\
*** Test Cases ***
A
    [Tags]    allure.id:42
    Log    a
B
    Log    b
C
    Log    c
"""


def _executed(output_xml):
    return sorted(test.name for test in ExecutionResult(str(output_xml)).suite.all_tests)


def _run_with_plan(robot, tmp_path, plan):
    env = {}
    if plan is not None:
        (tmp_path / "plan.json").write_text(json.dumps({"version": "1.0", "tests": plan}))
        env["ALLURE_TESTPLAN_PATH"] = str(tmp_path / "plan.json")
    return robot(
        PLAN_SUITE,
        env=env,
        args=["--prerunmodifier", "robotframework_allurevisitor.testplan"],
    )


def test_testplan_selects_by_allure_id(robot, tmp_path):
    assert _executed(_run_with_plan(robot, tmp_path, [{"id": "42"}])) == ["A"]


def test_testplan_selects_by_full_name(robot, tmp_path):
    assert _executed(_run_with_plan(robot, tmp_path, [{"selector": "Suite.B"}])) == ["B"]


def test_testplan_without_plan_runs_everything(robot, tmp_path):
    assert _executed(_run_with_plan(robot, tmp_path, None)) == ["A", "B", "C"]
