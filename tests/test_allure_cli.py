"""The report readers normalise Allure 2 and Allure 3 data to the same shape.

Uses a fixed, hand-written results directory (independent of the converter) so a
reader bug cannot be masked by a converter change.
"""

from __future__ import annotations

import json

import pytest
from allure_cli import GENERATORS, generate_report, walk

RESULT = {
    "uuid": "11111111-1111-1111-1111-111111111111",
    "name": "Fixed Test",
    "fullName": "Suite.Fixed Test",
    "historyId": "h1",
    "testCaseId": "h1",
    "status": "failed",
    "statusDetails": {"message": "boom"},
    "description": "Fixed description",
    "start": 1000,
    "stop": 2000,
    "labels": [{"name": "suite", "value": "Suite"}, {"name": "feature", "value": "F"}],
    "links": [{"type": "issue", "url": "https://tracker/1", "name": "ISSUE-1"}],
    "steps": [
        {
            "name": "Outer",
            "status": "passed",
            "start": 1000,
            "stop": 1500,
            "parameters": [{"name": "arg1", "value": "x"}],
            "steps": [
                {
                    "name": "Inner",
                    "status": "passed",
                    "start": 1100,
                    "stop": 1200,
                    "attachments": [
                        {"name": "note", "source": "a1-attachment.txt", "type": "text/plain"}
                    ],
                }
            ],
        }
    ],
}

CONTAINER = {
    "uuid": "22222222-2222-2222-2222-222222222222",
    "children": [RESULT["uuid"]],
    "befores": [{"name": "Prepare", "status": "passed", "start": 900, "stop": 950}],
    "afters": [{"name": "Cleanup", "status": "passed", "start": 2050, "stop": 2100}],
}


@pytest.mark.e2e
@pytest.mark.parametrize("generator", GENERATORS)
def test_readers_normalise_report_data(tmp_path, generator):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / f"{RESULT['uuid']}-result.json").write_text(json.dumps(RESULT))
    (results_dir / f"{CONTAINER['uuid']}-container.json").write_text(json.dumps(CONTAINER))
    (results_dir / "a1-attachment.txt").write_text("hello")
    (results_dir / "environment.properties").write_text("Stage=qa\n")

    report = generate_report(generator, results_dir, tmp_path / "report")

    assert report.stats() == {
        "passed": 0,
        "failed": 1,
        "broken": 0,
        "skipped": 0,
        "unknown": 0,
        "total": 1,
    }
    case = report.test_case("Fixed Test")
    assert case["status"] == "failed"
    assert ("feature", "F") in case["labels"]
    assert {"name": "ISSUE-1", "url": "https://tracker/1", "type": "issue"} in case["links"]
    assert "Fixed description" in case["description"]
    assert [fixture["name"] for fixture in case["setup"]] == ["Prepare"]
    assert [fixture["name"] for fixture in case["teardown"]] == ["Cleanup"]

    (outer,) = case["steps"]
    assert outer["name"] == "Outer"
    assert outer["parameters"] == {"arg1": "x"}
    inner = next(node for node in walk(case["steps"]) if node["name"] == "Inner")
    assert inner["attachments"] == [{"name": "note", "type": "text/plain"}]

    assert report.environment() == {"Stage": ["qa"]}
