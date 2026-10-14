## MODIFIED Requirements

### Requirement: Convert one or more output.xml sources

The system SHALL provide a programmatic `generate(sources, results_dir, ...)` function and a console-script CLI that accept one or more `output.xml` sources (paths or globs) and write Allure result files into a target directory.

When multiple sources are given without merge, the system SHALL:
- convert each source as its own result tree, so each test's `fullName`, `historyId`, and suite labels are identical to those of a single-source conversion;
- resolve each source's screenshots and traces relative to that source's own directory.

Repeated runs of the same test therefore share a `historyId`, and Allure groups them as retries with the latest attempt (by stop time) as the headline.

#### Scenario: Single source conversion
- **WHEN** the CLI is run with one `output.xml` and a results directory
- **THEN** Allure result files for that run are written into the results directory

#### Scenario: Multiple sources are combined and grouped as retries
- **WHEN** the CLI is run with `original.xml` (a test fails) and `rerun.xml` (the same test passes)
- **THEN** both attempts are emitted as results sharing the same `historyId`
- **AND** the attempt with the latest stop time has status `passed`, so Allure shows the passing result as the headline with the earlier failure as a retry

#### Scenario: Multi-source identity matches single-source identity
- **WHEN** `original.xml` is converted alone, and separately together with `rerun.xml`
- **THEN** a test present in both conversions has the same `fullName`, `historyId`, and `parentSuite`/`suite`/`subSuite` labels in both

#### Scenario: Attachments resolved per source
- **WHEN** `out/output.xml` and `out/rerun/output.xml` both reference `browser/screenshot/robotframework-browser-screenshot-1.png` and are converted together
- **THEN** each attempt's attachment is the file from its own source's directory

#### Scenario: Pre-merged source yields a single result
- **WHEN** sources are merged upstream with `rebot --merge` and the merged `output.xml` is converted
- **THEN** a single result per test is written with the last-wins status

#### Scenario: Glob expansion
- **WHEN** a source argument is a glob that matches several files
- **THEN** all matching files are included as sources

## ADDED Requirements

### Requirement: Merge re-executed sources

The CLI SHALL accept a `--merge` flag, and `generate()` a `merge` argument, that merges the sources in the given order with the same last-wins semantics and merge messages as `rebot --merge`, and emits one result per test. Each test's screenshots and traces, and those of each suite setup and teardown, SHALL be resolved relative to the directory of the source that item came from. As in `rebot --merge`, a re-executed suite takes its setup and teardown from the later source.

#### Scenario: Merge keeps the latest attempt
- **WHEN** `rf-allure --merge original.xml rerun.xml` is run and a test failed in `original.xml` and passed in `rerun.xml`
- **THEN** exactly one result is written for that test, with status `passed` and a message saying that it was re-executed and merged

#### Scenario: Tests not re-executed are kept
- **WHEN** a test passed in `original.xml` and is absent from `rerun.xml`
- **THEN** its result is written from `original.xml` with its original attachments

#### Scenario: Merged attachments come from their own run
- **WHEN** both sources reference a screenshot with the same relative name in their own directories
- **THEN** the re-executed test carries the rerun directory's file and a test kept from the original carries the original directory's file
