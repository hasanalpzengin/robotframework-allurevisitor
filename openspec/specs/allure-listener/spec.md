# allure-listener Specification

## Purpose

Provide a live Robot Framework listener that writes Allure results during execution through the same mapping as the `rf-allure` converter, adding runtime-only features so the package can replace the `allure-robotframework` listener.

## Requirements

### Requirement: Listener entry point

The package SHALL provide a Robot Framework listener usable as `--listener robotframework_allurevisitor.Listener` with an optional first argument naming the results directory (default `output/allure`) and optional `name=value` arguments `broken_heuristic` and `clean`. The listener SHALL require no configuration beyond the results directory.

#### Scenario: Default results directory
- **WHEN** `robot --listener robotframework_allurevisitor.Listener suite.robot` runs in a working directory
- **THEN** Allure result and container files are written to `output/allure`

#### Scenario: Custom results directory
- **WHEN** the listener is given `robotframework_allurevisitor.Listener:build/allure`
- **THEN** results are written to `build/allure`

### Requirement: Output equivalence with the converter

For the same Robot run, the listener's results SHALL be equivalent to converting that run's `output.xml` with `rf-allure` using the same options, apart from uuids, attachment file names, and items produced only by runtime hooks. Equivalence covers result/container structure, names, statuses and details, timestamps, labels (excluding `thread`), links, parameters, step trees, fixtures, and attachment names and types.

#### Scenario: Listener and converter agree
- **WHEN** a suite without runtime hook calls runs with the listener and its `output.xml` is also converted with `rf-allure`
- **THEN** after normalising uuids, attachment file names, and `thread` labels, the two result sets are equal

### Requirement: Final status reconciliation

The listener SHALL write test results only after their enclosing suite has finished, applying the final status and message Robot assigns at suite end, so a failing suite setup or teardown is reflected on its tests exactly as in the converter.

#### Scenario: Suite teardown failure
- **WHEN** a test passes and its suite teardown then fails with `teardown boom`
- **THEN** the written result has status `failed` and its message contains `Parent suite teardown failed` and `teardown boom`

#### Scenario: Interrupted run
- **WHEN** a run is interrupted after some suites have finished
- **THEN** results and containers for every finished suite have already been written

### Requirement: Runtime hook overlay

While the listener is active, calls made through `allure-python-commons` during a keyword (`allure.attach`, `allure.attach.file`, `allure.dynamic.label`/`tag`/`severity`/`epic`/`feature`/`story`/`suite`/`id`/`link`/`issue`/`testcase`/`title`/`description`/`description_html`/`parameter`, and `allure.step` context managers or decorators) SHALL be applied to the result: attachments and steps to the step of the keyword that was running (nested inside any open `allure.step`), and labels, links, title, description, and parameters to the current test. Calls made during suite setup or teardown SHALL apply to the corresponding container fixture. `allure.step` steps SHALL carry wall-clock start/stop, their parameters, and status `failed` for assertion errors or `broken` for other exceptions.

#### Scenario: Attachment from a Python library
- **WHEN** a library keyword called inside user keyword `Wrapper` calls `allure.attach("body", name="note")`
- **THEN** the step for that library keyword, nested under the `Wrapper` step, has an attachment named `note` whose content is `body`

#### Scenario: Dynamic labels and links
- **WHEN** a keyword calls `allure.dynamic.feature("F")` and `allure.dynamic.link("https://x", name="x")`
- **THEN** the test result has a `feature=F` label and a link `x` to `https://x`

#### Scenario: Python step with attachment
- **WHEN** a keyword runs `with allure.step("inner"): allure.attach("y", name="inner-att")`
- **THEN** the keyword's step contains a step `inner` which has the `inner-att` attachment

#### Scenario: Hook call in suite setup
- **WHEN** a keyword in Suite Setup calls `allure.attach("cfg", name="config")`
- **THEN** the suite container's setup fixture has the `config` attachment

### Requirement: Global attachments and errors

`allure.global_attach`, `allure.global_attach.file`, and `allure.global_error` calls SHALL be written as Allure globals files in the results directory.

#### Scenario: Global error recorded
- **WHEN** a library calls `allure.global_error("env down")`
- **THEN** a `*-globals.json` file containing that error message is written

### Requirement: Deferred attachment files

Attachment files referenced by log messages (screenshots, Playwright traces) SHALL be copied when their owning container is written or when the run closes, not when the message is logged, so files created later in the run (for example a trace written by `Close Context` in Suite Teardown) are captured.

#### Scenario: Suite-level trace captured live
- **WHEN** a Browser context with `tracing=True` is opened in Suite Setup and closed in Suite Teardown while the listener is active
- **THEN** the trace is attached with MIME type `application/vnd.allure.playwright-trace`

### Requirement: Parallel execution thread label

The listener SHALL add a `thread` label whose value is `<PABOTEXECUTIONPOOLID>-<CALLER_ID>` when running under pabot, and a per-process `default-<uuid>` value otherwise. Results from concurrent pabot processes writing to the same results directory SHALL NOT overwrite each other.

#### Scenario: pabot workers
- **WHEN** a suite set runs with pabot using two processes and the listener
- **THEN** every test has exactly one result file and the `thread` labels start with two distinct pool ids (`0-`, `1-`); like `allure-robotframework`, the `CALLER_ID` part differs per executed suite

### Requirement: Coexistence with the upstream listener

When the `allure-robotframework` listener is also active in the same run, the listener SHALL emit a Robot warning stating that runtime attachments will be duplicated, and SHALL continue to work.

#### Scenario: Both listeners registered
- **WHEN** a run uses both `--listener allure_robotframework` and `--listener robotframework_allurevisitor.Listener`
- **THEN** a warning naming both listeners appears in the Robot log and console

### Requirement: Migration guide

The project SHALL document migration from `allure-robotframework` with a before/after table covering the listener option, the `AllureLibrary` import, the test-plan pre-run modifier, `ALLURE_MAX_STEP_MESSAGE_COUNT` and `ALLURE_TESTPLAN_PATH`, the default results directory, and the known output differences (data-derived timestamps, control-structure steps, escaped log text, opt-in broken heuristic).

#### Scenario: Guide covers every replaced entry point
- **WHEN** the migration guide is read
- **THEN** it lists the upstream and replacement form for the listener, the library, and the pre-run modifier, and the list of known differences
