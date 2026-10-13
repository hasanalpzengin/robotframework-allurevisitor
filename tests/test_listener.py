"""The live listener: entry point, status reconciliation, thread label, runtime hooks."""

from __future__ import annotations

import importlib.util
import subprocess
import sys

from conftest import load_containers, load_results

LISTENER = "robotframework_allurevisitor.Listener"

THREE_TESTS = """\
*** Test Cases ***
One
    Log    1
Two
    Log    2
Three
    Fail    3
"""


def test_default_results_directory(robot, tmp_path):
    robot(THREE_TESTS, args=["--listener", LISTENER])

    results = load_results(tmp_path / "output" / "allure")
    assert sorted(r["name"] for r in results) == ["One", "Three", "Two"]
    assert {r["name"]: r["status"] for r in results}["Three"] == "failed"
    # One suite container plus one container per test.
    assert len(load_containers(tmp_path / "output" / "allure")) == 4


def test_custom_results_directory(robot, tmp_path):
    robot(THREE_TESTS, args=["--listener", f"{LISTENER}:build/allure"])

    assert len(load_results(tmp_path / "build" / "allure")) == 3
    assert not (tmp_path / "output" / "allure").exists()


def test_suite_teardown_failure_fails_finished_tests(robot, tmp_path):
    suite = (
        "*** Settings ***\nSuite Teardown    Fail    teardown boom\n\n"
        "*** Test Cases ***\nLooks Fine\n    Log    ok\n"
    )
    robot(suite, args=["--listener", LISTENER])

    (result,) = load_results(tmp_path / "output" / "allure")
    assert result["status"] == "failed"
    message = result["statusDetails"]["message"]
    assert "Parent suite teardown failed" in message and "teardown boom" in message


def test_parent_teardown_failure_patches_written_child_results(tmp_path):
    """A parent suite's teardown fails tests of child suites written earlier."""
    root = tmp_path / "root"
    (root / "child").mkdir(parents=True)
    (root / "__init__.robot").write_text(
        "*** Settings ***\nSuite Teardown    Fail    parent boom\n"
    )
    (root / "child" / "tests.robot").write_text("*** Test Cases ***\nNested\n    Log    ok\n")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(tmp_path),
            "--listener",
            LISTENER,
            str(root),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    (result,) = load_results(tmp_path / "output" / "allure")
    assert result["status"] == "failed"
    assert "parent boom" in result["statusDetails"]["message"]


def _threads(results):
    return {label["value"] for r in results for label in r["labels"] if label["name"] == "thread"}


def test_thread_label_default_and_pabot_variables(robot, tmp_path):
    robot(THREE_TESTS, args=["--listener", LISTENER])
    (default,) = _threads(load_results(tmp_path / "output" / "allure"))
    assert default.startswith("default-")

    robot(
        THREE_TESTS,
        args=[
            "--listener",
            f"{LISTENER}:pabot-results",
            "--variable",
            "PABOTEXECUTIONPOOLID:3",
            "--variable",
            "CALLER_ID:abc",
        ],
    )
    assert _threads(load_results(tmp_path / "pabot-results")) == {"3-abc"}


def test_pabot_run_has_one_result_per_test_and_two_threads(tmp_path):
    pytest = __import__("pytest")
    if importlib.util.find_spec("pabot") is None:
        pytest.skip("robotframework-pabot is not installed")
    suites = tmp_path / "suites"
    suites.mkdir()
    for index in range(4):
        (suites / f"s{index}.robot").write_text(
            f"*** Test Cases ***\nTest {index}\n    Sleep    0.3s\n"
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pabot.pabot",
            "--processes",
            "2",
            "--outputdir",
            str(tmp_path / "out"),
            "--listener",
            f"{LISTENER}:{tmp_path / 'allure'}",
            str(suites),
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    results = load_results(tmp_path / "allure")
    assert sorted(r["name"] for r in results) == [f"Test {i}" for i in range(4)]
    # Like allure-robotframework: "<pool id>-<caller id>"; pabot gives each executed
    # suite its own CALLER_ID, so the pool id identifies the worker process.
    assert {thread.split("-")[0] for thread in _threads(results)} == {"0", "1"}


def test_warns_when_upstream_listener_also_active(tmp_path):
    pytest = __import__("pytest")
    if importlib.util.find_spec("allure_robotframework") is None:
        pytest.skip("allure-robotframework is not installed")
    (tmp_path / "suite.robot").write_text("*** Test Cases ***\nBoth\n    Log    hi\n")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--outputdir",
            str(tmp_path),
            "--listener",
            f"allure_robotframework:{tmp_path / 'upstream'}",
            "--listener",
            f"{LISTENER}:{tmp_path / 'ours'}",
            str(tmp_path / "suite.robot"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "allure_robotframework" in completed.stdout + completed.stderr
    assert "robotframework_allurevisitor.Listener" in completed.stdout + completed.stderr
    assert len(load_results(tmp_path / "ours")) == 1  # ours keeps working
