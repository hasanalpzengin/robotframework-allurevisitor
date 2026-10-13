"""Runtime calls from Python libraries land where they were made (live listener only)."""

from __future__ import annotations

import json

import pytest
from conftest import find_step, load_containers, load_results

LISTENER = "robotframework_allurevisitor.Listener"

HOOKS_LIBRARY = """
import allure


def attach_config():
    allure.attach("cfg", name="config")


def attach_note():
    allure.attach("body", name="note")


def attach_text_file(path):
    allure.attach.file(path, name="file", attachment_type=allure.attachment_type.TEXT)


def dynamic_meta():
    allure.dynamic.feature("F")
    allure.dynamic.tag("dyn-tag")
    allure.dynamic.link("https://x", name="x")
    allure.dynamic.title("Renamed Test")
    allure.dynamic.description("Dynamic description")
    allure.dynamic.parameter("p", 42)


def python_step():
    with allure.step("inner"):
        allure.attach("y", name="inner-att")


def step_statuses():
    for error in (AssertionError("bad value"), ValueError("boom")):
        try:
            with allure.step(f"raises {type(error).__name__}"):
                raise error
        except Exception:
            pass


def report_global_error():
    allure.global_error("env down")
"""

SUITE = """\
*** Settings ***
Library        Hooks.py
Suite Setup    Attach Config

*** Test Cases ***
Runtime
    Wrapper
    Attach Text File    ${CURDIR}/note.txt
    Dynamic Meta
    Python Step
    Step Statuses
    Report Global Error

*** Keywords ***
Wrapper
    Attach Note
"""


@pytest.fixture
def runtime_results(robot, tmp_path):
    (tmp_path / "Hooks.py").write_text(HOOKS_LIBRARY)
    (tmp_path / "note.txt").write_text("file body")
    robot(SUITE, args=["--pythonpath", str(tmp_path), "--listener", LISTENER])
    return tmp_path / "output" / "allure"


def _attachment(results_dir, item, name):
    (attachment,) = [a for a in item.get("attachments", []) if a["name"] == name]
    return attachment, (results_dir / attachment["source"]).read_text()


def test_attachment_on_running_keyword(runtime_results):
    (result,) = load_results(runtime_results)
    wrapper = find_step(result["steps"], "Wrapper")
    (attach_note,) = wrapper["steps"]
    assert attach_note["name"] == "Attach Note"
    _, body = _attachment(runtime_results, attach_note, "note")
    assert body == "body"

    attach_file = find_step(result["steps"], "Attach Text File")
    attachment, body = _attachment(runtime_results, attach_file, "file")
    assert attachment["type"] == "text/plain" and body == "file body"


def test_dynamic_test_metadata(runtime_results):
    (result,) = load_results(runtime_results)
    labels = {(label["name"], label["value"]) for label in result["labels"]}
    assert {("feature", "F"), ("tag", "dyn-tag")} <= labels
    assert {"type": "link", "url": "https://x", "name": "x"} in result["links"]
    assert result["name"] == "Renamed Test"
    assert result["fullName"] == "Suite.Runtime"  # identity is unchanged
    assert result["description"] == "Dynamic description"
    assert {"name": "p", "value": "42"} in result["parameters"]


def test_python_step_nests_its_attachment(runtime_results):
    (result,) = load_results(runtime_results)
    keyword = find_step(result["steps"], "Python Step")
    (inner,) = keyword["steps"]
    assert inner["name"] == "inner" and inner["status"] == "passed"
    assert inner["start"] <= inner["stop"]
    _, body = _attachment(runtime_results, inner, "inner-att")
    assert body == "y"


def test_step_status_by_exception(runtime_results):
    """allure.step: AssertionError -> failed, any other exception -> broken."""
    (result,) = load_results(runtime_results)
    keyword = find_step(result["steps"], "Step Statuses")
    statuses = {step["name"]: step["status"] for step in keyword["steps"]}
    assert statuses == {"raises AssertionError": "failed", "raises ValueError": "broken"}
    failed = next(s for s in keyword["steps"] if s["status"] == "failed")
    assert "bad value" in failed["statusDetails"]["message"]


def test_suite_setup_hook_goes_to_fixture(runtime_results):
    (suite,) = [c for c in load_containers(runtime_results) if c["name"] == "Suite"]
    (fixture,) = suite["befores"]
    assert fixture["name"] == "Attach Config"
    _, body = _attachment(runtime_results, fixture, "config")
    assert body == "cfg"


def test_global_error_written(runtime_results):
    (globals_file,) = runtime_results.glob("*-globals.json")
    errors = json.loads(globals_file.read_text())["errors"]
    assert [error["message"] for error in errors] == ["env down"]
