## MODIFIED Requirements

### Requirement: Optional browser trace end-to-end test

The project SHALL include end-to-end tests, marked `browser`, that:
- run a robotframework-browser suite with tracing enabled (one per-test context and one suite-level context), convert it, and assert that each trace is attached with the Playwright-trace MIME type and appears in both generators' report data;
- run the pabot, re-execution (retries and merge), and pabot + re-execution workflows with Browser screenshots and traces, through both the converter and the listener, and assert each test's attachments and status in both generators' report data.

The tests SHALL be skipped when robotframework-browser or its browsers are unavailable. robotframework-pabot SHALL be part of the `browser` dependency group. `browser` SHALL be a registered pytest marker.

#### Scenario: Browser traces end to end
- **WHEN** the browser test runs with robotframework-browser installed
- **THEN** both the per-test and the suite-level trace are attached and present in the generated reports

#### Scenario: Workflow tests end to end
- **WHEN** the `browser` tests run with the `browser` dependency group installed
- **THEN** the pabot, rerun, and pabot + rerun workflows are verified for both front ends on Allure 2 and Allure 3

#### Scenario: Browser library unavailable
- **WHEN** robotframework-browser is not installed
- **THEN** the browser end-to-end tests are skipped
