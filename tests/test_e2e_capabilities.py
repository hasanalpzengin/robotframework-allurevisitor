"""Every documented Robot -> Allure capability is visible in Allure 2 and Allure 3 reports.

Runs a capability suite through the packaged ``rf-allure`` CLI and checks each
capability in the generator's own report data (via the normalised readers).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from allure_cli import GENERATORS, generate_report, walk

# 1x1 PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db40000000049454e44ae426082"
)

CAPABILITY_SUITE = """\
*** Settings ***
Suite Setup       Set Suite Variable    ${READY}    yes
Suite Teardown    Log    suite done

*** Test Cases ***
Capabilities
    [Documentation]    Capability description
    [Tags]    allure.epic:Reporting    allure.feature:Conversion    allure.story:Capabilities
    ...       allure.severity:critical    allure.label.owner:qa-team    allure.id:1001
    ...       allure.issue:ISSUE-1    allure.tms:TMS-2    allure.link:https://example.com
    ...       smoke
    [Setup]    No Operation
    Outer Keyword
    Log    <img src="shot.png">    html=True
    [Teardown]    Comment    cleanup

*** Keywords ***
Outer Keyword
    ${joined} =    Catenate    left    right
    Log    joined ${joined}
"""


def _rf_allure() -> str:
    found = shutil.which("rf-allure") or str(Path(sys.executable).parent / "rf-allure")
    if not Path(found).exists():
        pytest.skip("rf-allure console script is not installed.")
    return found


@pytest.fixture(scope="module")
def capability_results(tmp_path_factory):
    work = tmp_path_factory.mktemp("capabilities")
    (work / "suite.robot").write_text(CAPABILITY_SUITE)
    (work / "shot.png").write_bytes(PNG)
    subprocess.run(
        [sys.executable, "-m", "robot", "--outputdir", str(work), str(work / "suite.robot")],
        capture_output=True,
        check=True,
    )
    results_dir = work / "allure-results"
    subprocess.run(
        [
            _rf_allure(),
            str(work / "output.xml"),
            "-o",
            str(results_dir),
            "--clean",
            "--environment",
            "Browser=chromium",
            "--environment",
            "Stage=qa",
        ],
        check=True,
    )
    return work, results_dir


@pytest.mark.e2e
@pytest.mark.parametrize("generator", GENERATORS)
def test_capabilities_in_report(capability_results, generator):
    work, results_dir = capability_results
    report = generate_report(generator, results_dir, work / f"report-{generator}")
    case = report.test_case("Capabilities")

    labels = set(case["labels"])
    for expected in [
        ("epic", "Reporting"),
        ("feature", "Conversion"),
        ("story", "Capabilities"),
        ("severity", "critical"),
        ("owner", "qa-team"),
        ("as_id", "1001"),
        ("tag", "smoke"),
        ("suite", "Suite"),
        ("framework", "robotframework"),
    ]:
        assert expected in labels, f"{expected} missing ({generator})"

    links = {(link["type"], link["name"]) for link in case["links"]}
    assert {("issue", "ISSUE-1"), ("tms", "TMS-2"), ("link", "https://example.com")} <= links

    assert "Capability description" in case["description"]

    setup = {fixture["name"] for fixture in case["setup"]}
    teardown = {fixture["name"] for fixture in case["teardown"]}
    assert {"Set Suite Variable", "No Operation"} <= setup
    assert {"Log", "Comment"} <= teardown

    assert [step["name"] for step in case["steps"]] == ["Outer Keyword", "Log"]
    catenate = next(n for n in walk(case["steps"]) if n["name"] == "${joined} = Catenate")
    assert catenate["parameters"] == {"arg1": "left", "arg2": "right"}

    attachments = [a for node in walk(case["steps"]) for a in node["attachments"]]
    assert {"name": "shot.png", "type": "image/png"} in attachments
    assert {"name": "Keyword Log", "type": "text/html"} in attachments

    assert report.environment() == {"Browser": ["chromium"], "Stage": ["qa"]}
