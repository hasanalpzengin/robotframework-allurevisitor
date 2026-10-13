"""CLI options: broken heuristic, environment.properties, executor.json."""

from __future__ import annotations

import json

import pytest
from conftest import load_results

from robotframework_allurevisitor._convert import properties_text
from robotframework_allurevisitor.cli import main

SUITE = "*** Test Cases ***\nMissing Keyword\n    No Keyword With This Name\n"


def test_broken_heuristic_flag(robot, tmp_path):
    output_xml = robot(SUITE)
    results_dir = tmp_path / "allure-results"

    assert main([str(output_xml), "-o", str(results_dir), "--clean"]) == 0
    assert [r["status"] for r in load_results(results_dir)] == ["failed"]

    assert main([str(output_xml), "-o", str(results_dir), "--clean", "--broken-heuristic"]) == 0
    assert [r["status"] for r in load_results(results_dir)] == ["broken"]


def test_environment_and_executor(robot, tmp_path):
    output_xml = robot(SUITE)
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()
    (results_dir / "stale-result.json").write_text("{}")
    executor = {"name": "GitHub Actions", "type": "github", "buildName": "#42"}

    main(
        [
            str(output_xml),
            "-o",
            str(results_dir),
            "--clean",
            "--environment",
            "Browser=chromium",
            "--environment",
            "Stage=qa",
            "--executor",
            json.dumps(executor),
        ]
    )

    assert not (results_dir / "stale-result.json").exists()
    properties = (results_dir / "environment.properties").read_text(encoding="latin-1")
    assert properties.splitlines() == ["Browser=chromium", "Stage=qa"]
    assert json.loads((results_dir / "executor.json").read_text()) == executor


def test_executor_from_file(robot, tmp_path):
    output_xml = robot(SUITE)
    executor_file = tmp_path / "executor.json"
    executor_file.write_text('{"name": "Jenkins", "buildOrder": 7}')
    results_dir = tmp_path / "allure-results"

    main([str(output_xml), "-o", str(results_dir), "--executor", str(executor_file)])

    assert json.loads((results_dir / "executor.json").read_text())["buildOrder"] == 7


def test_no_metadata_by_default(robot, tmp_path):
    results_dir = tmp_path / "allure-results"
    main([str(robot(SUITE)), "-o", str(results_dir)])
    assert not (results_dir / "environment.properties").exists()
    assert not (results_dir / "executor.json").exists()


@pytest.mark.parametrize("bad", [["--environment", "novalue"], ["--executor", "[1, 2]"]])
def test_invalid_options_are_rejected(tmp_path, bad):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "output.xml"), *bad])


def test_properties_escaping():
    text = properties_text({"a key=x": "C:\\path", "multi": "1\n2", "uni": "ü✓😀"})
    assert text.splitlines() == [
        "a\\ key\\=x=C:\\\\path",
        "multi=1\\n2",
        "uni=ü\\u2713\\ud83d\\ude00",
    ]
