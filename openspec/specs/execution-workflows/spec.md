# execution-workflows Specification

## Purpose

Guarantee that the common ways of running Robot Framework at scale (parallel runs with pabot, re-execution of failed tests, and both together) produce correct Allure results with Browser screenshots and Playwright traces, through both the `rf-allure` converter and the live listener, on Allure 2 and Allure 3.

## Requirements

### Requirement: Parallel runs with pabot

The system SHALL produce one result per executed test, with its screenshots and traces attached, for a pabot run of robotframework-browser suites in both of these ways:
- **Converter**: converting the `output.xml` that pabot merges, when pabot was run with `--artifactsinsubfolders`.
- **Listener**: every pabot process runs the listener against a shared results directory. Each result carries the `thread` label of its pabot process.

#### Scenario: Converter on pabot output
- **WHEN** two Browser suites run under `pabot --processes 2 --artifacts png,zip --artifactsinsubfolders`, each test taking a screenshot and recording a trace, and the merged `output.xml` is converted
- **THEN** every test has its own screenshot (not another process's file of the same name) and its trace attached

#### Scenario: Listener under pabot
- **WHEN** the same suites run under pabot with `--listener robotframework_allurevisitor.Listener:<dir>`
- **THEN** every test has its screenshot and trace attached, and the results carry thread labels from two different pabot processes

### Requirement: Re-executed tests as retries

When the original run and a rerun of its failed tests (`--rerunfailed`, written to a separate output directory) are converted together, or when both runs use the listener with the same results directory, the system SHALL emit every attempt.

Each attempt SHALL resolve its own screenshots and traces. Attempts of the same test SHALL share a `historyId` equal to the one a single-run conversion produces, so Allure shows the latest attempt with the earlier ones as retries.

#### Scenario: Converter with original and rerun outputs
- **WHEN** a Browser test fails in `out/output.xml`, passes in `out/rerun/output.xml`, and both files are passed to `rf-allure`
- **THEN** the results contain a failed and a passed attempt of that test with the same `historyId` as in a conversion of `out/output.xml` alone
- **AND** each attempt carries the screenshot written by its own run
- **AND** the Allure 2 and Allure 3 reports show the test as passed with one retry

#### Scenario: Listener across original run and rerun
- **WHEN** the original run and the rerun both use the listener with the same results directory
- **THEN** the results contain both attempts with a shared `historyId` and each attempt's own screenshot and trace

### Requirement: Re-executed tests merged into one result

The system SHALL support a single last-wins result per test in two ways:
- **Converter merge**: converting the original and rerun outputs with merge enabled. Each test's attachments SHALL come from the run that produced it.
- **`rebot --merge` output**: converting an `output.xml` produced by `rebot --merge`. A merged file does not record which run's directory a relative screenshot path belongs to, and the same name can exist in both runs. So for every test that rebot re-executed or added, the system SHALL warn when it resolves a relative screenshot path: the file may belong to a different run, and `rf-allure --merge` is the recommended alternative. Missing files SHALL be reported with a warning.

#### Scenario: Converter merge with Browser artifacts
- **WHEN** `rf-allure --merge out/output.xml out/rerun/output.xml` converts a run in which a Browser test failed and then passed in the rerun
- **THEN** one result per test is written; the re-executed test is `passed` and carries the rerun's screenshot and trace
- **AND** a test that passed in the original run keeps the original run's screenshot and trace

#### Scenario: rebot-merged output
- **WHEN** the output of `rebot --merge out/output.xml out/rerun/output.xml` is converted
- **THEN** one result per test is written with the merged status and a readable merge message
- **AND** a warning names each re-executed test whose relative screenshots were resolved and recommends `rf-allure --merge`

### Requirement: pabot combined with re-execution

The workflows above SHALL also hold when both the original run and the rerun are pabot runs (`pabot --rerunfailed`):
- **Converter**: retries mode and merge mode.
- **Listener**: both pabot runs write to the same results directory.

#### Scenario: Converter on pabot original and pabot rerun
- **WHEN** a pabot run (with `--artifactsinsubfolders`) has a failing Browser test, a pabot rerun into a separate output directory passes it, and both merged outputs are converted
- **THEN** the test has a failed and a passed attempt sharing a `historyId`, each with its own screenshot and trace
- **AND** converting the same outputs with `--merge` yields one `passed` result with the rerun's screenshot and trace

#### Scenario: Listener on pabot original and pabot rerun
- **WHEN** both pabot runs use the listener with the same results directory
- **THEN** the results contain both attempts of the re-executed test with each attempt's screenshot and trace

### Requirement: Workflow documentation

The README SHALL document the supported commands for each workflow, with both front ends:
- pabot
- rerun with retries
- rerun with merge
- pabot + rerun

It SHALL state the constraints that the workflows depend on:
- A rerun needs its own `--outputdir`, because Browser deletes its artifacts in the output directory at the start of a run.
- Converting pabot output needs `--artifactsinsubfolders` for screenshots.
- A `rebot --merge` file cannot locate both runs' relative screenshots, so `rf-allure --merge` is the recommended way to merge.

#### Scenario: README covers workflows
- **WHEN** the README is inspected
- **THEN** it contains the commands for pabot, rerun with retries, rerun with merge, and pabot + rerun, and states the separate-output-directory and `--artifactsinsubfolders` requirements
