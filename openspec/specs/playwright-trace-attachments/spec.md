# playwright-trace-attachments Specification

## Purpose

Attach Playwright trace archives produced by robotframework-browser (`tracing=True`) to the Allure results so they can be opened in the Playwright Trace Viewer from both Allure 2 and Allure 3 reports.

## Requirements

### Requirement: Traces are discovered from the result log

The system SHALL discover Playwright trace files from robotframework-browser log messages of the form `... trace file will be saved to: <path>` contained in the result tree, and SHALL NOT discover traces by scanning directories or by comparing timestamps.

#### Scenario: Per-test context trace is attached
- **WHEN** a test's `[Setup]` runs `New Context    tracing=True` and the test closes the context in `[Teardown]`
- **THEN** the trace archive logged by that `New Context` is attached exactly once to that test's results

#### Scenario: Suite-level context trace is attached
- **WHEN** `New Context    tracing=True` runs in `Suite Setup` and the context is closed in `Suite Teardown`
- **THEN** the trace archive is attached to the suite setup fixture of the suite's container
- **AND** it is not silently dropped

#### Scenario: No tracing configured
- **WHEN** no log message announces a trace file
- **THEN** no trace attachment is produced and no error is raised

### Requirement: Trace attachment type and placement

Each discovered trace SHALL be copied into the results directory as a `.zip` attachment with MIME type `application/vnd.allure.playwright-trace`, named after the trace file, and attached to the step or fixture of the keyword that logged the announcement.

#### Scenario: Trace has the Playwright MIME type
- **WHEN** a trace is attached
- **THEN** the attachment `type` is `application/vnd.allure.playwright-trace` and its source file ends with `.zip`

#### Scenario: Trace is viewable in both generators
- **WHEN** a report is generated from the results with Allure 2 or Allure 3
- **THEN** the report data contains the trace attachment with the Playwright-trace content type

### Requirement: Relocated output tolerance

When the logged absolute trace path does not exist at conversion time, the system SHALL look for a file with the same name in `browser/traces/` next to the `output.xml` being converted, and SHALL skip the trace without failing when neither location exists.

#### Scenario: Output directory moved after the run
- **WHEN** a CI artifact containing `output.xml` and `browser/traces/` is downloaded to a different path and converted
- **THEN** the trace is attached from the relocated `browser/traces/` directory

#### Scenario: Trace file missing
- **WHEN** neither the logged path nor the relocated path exists
- **THEN** conversion succeeds without a trace attachment for that context
