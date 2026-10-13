"""End-to-end tests for the Allure result visitor."""

from __future__ import annotations

import subprocess
import sys

from allure_commons.utils import md5
from conftest import find_step, load_containers, load_results, step_names

from robotframework_allurevisitor.visitor import generate

BASIC_SUITE = """\
*** Test Cases ***
Passing Test
    [Documentation]    A passing test.
    [Tags]    smoke    allure.severity:critical
    Log    hello
    Should Be Equal    1    1

Failing Test
    Should Be Equal    1    2
"""


def test_basic_parity(robot, tmp_path):
    """6.2 Golden-file parity: statuses, labels, step tree, stable historyId."""
    output_xml = robot(BASIC_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    results = {r["name"]: r for r in load_results(results_dir)}
    assert set(results) == {"Passing Test", "Failing Test"}

    passing = results["Passing Test"]
    assert passing["status"] == "passed"
    assert passing["fullName"] == "Suite.Passing Test"
    assert passing["historyId"] == md5("Suite.Passing Test")
    assert step_names(passing["steps"]) == ["Log", "Should Be Equal"]

    labels = {(label["name"], label["value"]) for label in passing["labels"]}
    assert ("suite", "Suite") in labels
    assert ("framework", "robotframework") in labels
    assert ("severity", "critical") in labels
    assert ("tag", "smoke") in labels

    failing = results["Failing Test"]
    assert failing["status"] == "failed"
    assert failing["statusDetails"]["message"]


CONTROL_SUITE = """\
*** Test Cases ***
Control Flow
    ${x} =    Set Variable    1
    FOR    ${i}    IN    a    b
        Log    ${i}
    END
    IF    ${x} == 1
        Log    yes
    ELSE
        Log    no
    END
    WHILE    ${x} > 1
        Log    never
    END
    TRY
        Fail    boom
    EXCEPT    boom
        Log    caught
    END
"""


def test_control_structures(robot, tmp_path):
    """6.3 FOR/IF/WHILE/TRY appear as steps with correct nesting and status."""
    output_xml = robot(CONTROL_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"

    for_step = find_step(result["steps"], "FOR")
    assert for_step is not None
    # FOR has two iterations, each containing a Log step.
    assert len(for_step["steps"]) == 2
    assert find_step(for_step["steps"], "Log") is not None

    if_step = find_step(result["steps"], "IF")
    assert if_step is not None

    try_step = find_step(result["steps"], "TRY")
    assert try_step is not None
    assert find_step(try_step["steps"], "EXCEPT") is not None


SETUP_TEARDOWN_SUITE = """\
*** Settings ***
Suite Setup    Log    suite-setup
Suite Teardown    Log    suite-teardown

*** Test Cases ***
Skipped Test
    [Tags]    robot:skip
    Log    never

Broken Test
    This Keyword Does Not Exist
"""


def test_setup_teardown_skip_and_broken(robot, tmp_path):
    """Suite setup/teardown -> container befores/afters; skip, failed, opt-in broken."""
    output_xml = robot(SETUP_TEARDOWN_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (container,) = [c for c in load_containers(results_dir) if c["name"] == "Suite"]
    assert len(container["befores"]) == 1
    assert container["befores"][0]["name"] == "Log"
    assert len(container["afters"]) == 1

    results = {r["name"]: r for r in load_results(results_dir)}
    assert results["Skipped Test"]["status"] == "skipped"
    # Like allure-robotframework, a missing keyword is a plain failure by default...
    assert results["Broken Test"]["status"] == "failed"

    # ...and broken only when the heuristic is enabled.
    generate(output_xml, results_dir, clean=True, broken_heuristic=True)
    results = {r["name"]: r for r in load_results(results_dir)}
    assert results["Broken Test"]["status"] == "broken"
    assert results["Skipped Test"]["status"] == "skipped"


FLAKY_SUITE = """\
*** Test Cases ***
Flaky
    Should Be Equal    %{RESULT}    pass
"""


def test_multisource_combine_retry(robot, tmp_path):
    """6.5 Combining sources groups attempts by historyId; latest stop wins headline."""
    run1 = robot(FLAKY_SUITE, output="run1.xml", env={"RESULT": "fail"})
    run2 = robot(FLAKY_SUITE, output="run2.xml", env={"RESULT": "pass"})

    results_dir = tmp_path / "allure-results"
    generate([run1, run2], results_dir, clean=True)

    flaky = [r for r in load_results(results_dir) if r["name"] == "Flaky"]
    assert len(flaky) == 2
    # Both attempts share one stable historyId (md5 of the same full name) so
    # Allure groups them as retries of a single logical test.
    assert len({r["historyId"] for r in flaky}) == 1
    # The latest attempt (by stop time) is the passing one -> last-wins headline.
    latest = max(flaky, key=lambda r: r["stop"])
    assert latest["status"] == "passed"


def test_premerged_source_is_deduplicated(robot, tmp_path):
    """6.5 A rebot --merge source yields a single last-wins result."""
    run1 = robot(FLAKY_SUITE, output="run1.xml", env={"RESULT": "fail"})
    run2 = robot(FLAKY_SUITE, output="run2.xml", env={"RESULT": "pass"})
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "robot.rebot",
            "--merge",
            "--output",
            str(merged),
            "--outputdir",
            str(tmp_path),
            str(run1),
            str(run2),
        ],
        check=False,
    )

    results_dir = tmp_path / "allure-results"
    generate(merged, results_dir, clean=True)

    flaky = [r for r in load_results(results_dir) if r["name"] == "Flaky"]
    assert len(flaky) == 1
    assert flaky[0]["status"] == "passed"


TEMPLATE_SUITE = """\
*** Test Cases ***
Addition
    [Template]    Should Be Equal As Numbers
    ${1 + 1}    2
    ${3 + 4}    7
"""


def test_templated_rows_become_parameterised_steps(robot, tmp_path):
    """6.6 Templated rows are distinct steps carrying their args as parameters."""
    output_xml = robot(TEMPLATE_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"
    assert result["historyId"] == md5("Suite.Addition")

    rows = [s for s in result["steps"] if s["name"] == "Should Be Equal As Numbers"]
    assert len(rows) == 2
    # Each row carries its own arguments as step parameters -> distinct identity.
    row_args = [tuple(p["value"] for p in row["parameters"]) for row in rows]
    assert ("2",) in [args[1:] for args in row_args]
    assert all(len(row["parameters"]) == 2 for row in rows)


def test_determinism(robot, tmp_path):
    """6.7 Two conversions of the same output.xml produce identical historyId/timings."""
    output_xml = robot(BASIC_SUITE)
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(output_xml, first, clean=True)
    generate(output_xml, second, clean=True)

    def identity(results_dir):
        return sorted(
            (r["fullName"], r["historyId"], r["start"], r["stop"])
            for r in load_results(results_dir)
        )

    assert identity(first) == identity(second)


def test_partial_output_tolerance(robot, tmp_path):
    """6.8 A truncated output.xml degrades gracefully without an unhandled error."""
    output_xml = robot(BASIC_SUITE)
    truncated = tmp_path / "truncated.xml"
    data = output_xml.read_bytes()
    truncated.write_bytes(data[: len(data) // 2])

    results_dir = tmp_path / "allure-results"
    # Must not raise; recovers whatever the parser could read (possibly nothing).
    generate(truncated, results_dir, clean=True)
    assert results_dir.is_dir()


MESSAGES_SUITE = """\
*** Test Cases ***
Messages
    Three Messages
    Log    <img src="shot.png">    html=True

Failing Message
    Fail    went <wrong>

*** Keywords ***
Three Messages
    Log    first
    Log    second <b>&</b>
    Log    third\\nline    WARN
"""


def _attachment_text(results_dir, attachment):
    return (results_dir / attachment["source"]).read_text()


def test_messages_aggregated_into_keyword_log(robot, tmp_path):
    """Messages of a keyword become one escaped Keyword Log; images are not duplicated."""
    (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    output_xml = robot(MESSAGES_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    results = {r["name"]: r for r in load_results(results_dir)}
    wrapper = find_step(results["Messages"]["steps"], "Three Messages")
    # The user keyword owns no messages itself; each inner Log owns one.
    logs = [s for s in wrapper["steps"] if s["name"] == "Log"]
    assert len(logs) == 3
    for log in logs:
        (attachment,) = log["attachments"]
        assert attachment["name"] == "Keyword Log"
        assert attachment["type"] == "text/html"
    second = _attachment_text(results_dir, logs[1]["attachments"][0])
    assert "<b>[INFO]</b>" in second
    assert "second &lt;b&gt;&amp;&lt;/b&gt;" in second  # plain text is escaped
    third = _attachment_text(results_dir, logs[2]["attachments"][0])
    assert "<b>[WARN]</b>" in third and "third<br>line" in third

    image_step = results["Messages"]["steps"][-1]
    assert [a["type"] for a in image_step["attachments"]] == ["image/png"]

    fail_step = find_step(results["Failing Message"]["steps"], "Fail")
    (attachment,) = fail_step["attachments"]
    text = _attachment_text(results_dir, attachment)
    assert 'style="color: red"' in text and "<b>[FAIL]</b>" in text
    assert "went &lt;wrong&gt;" in text


def test_keyword_log_collects_all_messages_of_one_keyword(robot, tmp_path):
    """Several messages logged by one keyword end up in a single attachment."""
    output_xml = robot("*** Test Cases ***\nMany\n    Log Many    one    two    three\n")
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    (step,) = result["steps"]
    (attachment,) = step["attachments"]
    text = _attachment_text(results_dir, attachment)
    assert all(word in text for word in ("one", "two", "three"))


def test_messages_as_substeps(robot, tmp_path, monkeypatch):
    """ALLURE_MAX_STEP_MESSAGE_COUNT turns small message sets into sub-steps."""
    monkeypatch.setenv("ALLURE_MAX_STEP_MESSAGE_COUNT", "5")
    output_xml = robot("*** Test Cases ***\nMany\n    Log Many    one    two\n")
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    (step,) = result["steps"]
    assert step.get("attachments", []) == []
    assert step_names(step["steps"]) == ["one", "two"]
    assert all(s["start"] == s["stop"] for s in step["steps"])


TEST_FIXTURE_SUITE = """\
*** Test Cases ***
With Fixtures
    [Setup]    Log    test-setup
    Wrapped
    [Teardown]    Log    test-teardown

Without Fixtures
    Log    body

*** Keywords ***
Wrapped
    Log    inside
    [Teardown]    Log    keyword-teardown
"""


def test_test_setup_teardown_become_per_test_fixtures(robot, tmp_path):
    """Test [Setup]/[Teardown] -> befores/afters of a container owning only that test."""
    output_xml = robot(TEST_FIXTURE_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    results = {r["name"]: r for r in load_results(results_dir)}
    containers = load_containers(results_dir)
    with_fixtures = results["With Fixtures"]

    (own,) = [c for c in containers if c.get("children") == [with_fixtures["uuid"]]]
    assert step_names(own["befores"]) == ["Log"]
    assert step_names(own["afters"]) == ["Log"]
    assert "test-setup" in (results_dir / own["befores"][0]["attachments"][0]["source"]).read_text()

    # The fixtures are not steps of the test body...
    assert step_names(with_fixtures["steps"]) == ["Wrapped"]
    # ...but a user keyword's own [Teardown] stays a step of that keyword.
    assert step_names(with_fixtures["steps"][0]["steps"]) == ["Log", "Log"]

    # Every test gets its own container; the suite container lists both tests.
    (suite,) = [c for c in containers if c["name"] == "Suite"]
    assert set(suite["children"]) == {r["uuid"] for r in results.values()}
    (bare,) = [c for c in containers if c.get("children") == [results["Without Fixtures"]["uuid"]]]
    assert bare.get("befores", []) == [] and bare.get("afters", []) == []


def test_assignment_and_arguments(robot, tmp_path):
    """Assignment is in the step name; arguments are parameters arg1..N."""
    output_xml = robot("*** Test Cases ***\nAssign\n    ${x} =    Catenate    first    second\n")
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    (step,) = result["steps"]
    assert step["name"] == "${x} = Catenate"
    assert step["parameters"] == [
        {"name": "arg1", "value": "first"},
        {"name": "arg2", "value": "second"},
    ]


def test_skipped_tag_forces_skipped(robot, tmp_path):
    """A test tagged `skipped` is reported as skipped even though it passed."""
    output_xml = robot("*** Test Cases ***\nTagged\n    [Tags]    Skipped\n    Log    ran\n")
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "skipped"
