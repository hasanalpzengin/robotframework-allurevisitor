"""Listener output -> real Allure 2 and Allure 3 reports, including runtime-only data."""

from __future__ import annotations

import subprocess
import sys

import pytest
from allure_cli import GENERATORS, generate_report, walk

LIBRARY = """
import allure


def python_step():
    allure.dynamic.feature("Live Feature")
    with allure.step("inner python step"):
        allure.attach("runtime body", name="runtime-note")
"""

SUITE = """\
*** Settings ***
Library    Runtime.py
Library    robotframework_allurevisitor.AllureLibrary

*** Test Cases ***
Live
    [Tags]    allure.severity:critical
    Python Step
    Attach    from keyword    name=keyword-note    attachment_type=TEXT

Live Failure
    Fail    expected failure
"""


@pytest.fixture(scope="module")
def listener_results(tmp_path_factory):
    work = tmp_path_factory.mktemp("listener")
    (work / "Runtime.py").write_text(LIBRARY)
    (work / "suite.robot").write_text(SUITE)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(work),
            "--pythonpath",
            str(work),
            "--listener",
            f"robotframework_allurevisitor.Listener:{work / 'allure-results'}",
            str(work / "suite.robot"),
        ],
        cwd=work,
        capture_output=True,
        check=False,
    )
    return work, work / "allure-results"


@pytest.mark.e2e
@pytest.mark.parametrize("generator", GENERATORS)
def test_listener_results_in_report(listener_results, generator):
    work, results_dir = listener_results
    report = generate_report(generator, results_dir, work / f"report-{generator}")

    stats = report.stats()
    assert (stats["passed"], stats["failed"], stats["total"]) == (1, 1, 2)

    case = report.test_case("Live")
    labels = set(case["labels"])
    assert {("feature", "Live Feature"), ("severity", "critical")} <= labels
    inner = next(n for n in walk(case["steps"]) if n["name"] == "inner python step")
    assert inner["attachments"][0]["name"] == "runtime-note"
    attachments = [a for node in walk(case["steps"]) for a in node["attachments"]]
    assert {"name": "keyword-note", "type": "text/plain"} in attachments
