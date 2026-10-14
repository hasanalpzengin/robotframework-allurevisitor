# allure-conversion-cli Specification

## Purpose

A command-line and programmatic interface to convert one or more `output.xml` sources into an Allure results directory, supporting native multi-source merge, clean output, thread labelling, issue/link patterns, and tolerance of partial output.

## Requirements

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

### Requirement: Streaming, single-pass generation

The system SHALL convert results in a single depth-first traversal, emitting each test result at test end and each container at suite end, so peak memory is bounded by current suite depth rather than the whole run.

#### Scenario: Large output is converted without loading all results in memory
- **WHEN** a large `output.xml` is converted
- **THEN** result and container files are flushed incrementally during traversal

### Requirement: Output directory controls

The CLI SHALL default the results directory and SHALL support a `--clean` flag that removes existing files in the results directory before writing. Without `--clean`, the system SHALL append to the directory, relying on uuid filenames to avoid collisions.

#### Scenario: Clean run replaces previous results
- **WHEN** the CLI is run with `--clean` against a non-empty results directory
- **THEN** prior files are removed before the new results are written

#### Scenario: Appending across invocations
- **WHEN** the CLI is run twice without `--clean` against the same directory
- **THEN** both runs' result files coexist without overwriting each other

### Requirement: Labelling and link configuration options

The CLI SHALL accept a `--thread` option to set the thread label (e.g. a pabot worker id) and `--issue-pattern`/`--link-pattern` options forwarded to tag parsing so issue and link tags become Allure links.

#### Scenario: Thread label applied for pabot worker
- **WHEN** the CLI is run with `--thread worker-2`
- **THEN** every result produced by that invocation carries a `thread=worker-2` label

#### Scenario: Issue pattern produces links
- **WHEN** the CLI is run with an `--issue-pattern` and a test has a matching issue tag
- **THEN** the result has a corresponding issue link

### Requirement: Tolerance of partial output

The system SHALL tolerate a truncated or partially-written `output.xml`: it SHALL NOT abort with an unhandled exception, SHALL emit a warning, and SHALL flush whatever results were produced. Because `ExecutionResult` parses the source eagerly, an unparseable truncation yields no results; a source the parser can still read yields all results it recovers.

#### Scenario: Truncated output does not crash the converter
- **WHEN** the CLI converts a truncated `output.xml` from a killed run
- **THEN** the command exits without raising an unhandled exception and emits a warning
- **AND** any results the parser was able to recover are written to the output directory

### Requirement: Opt-in broken classification

The CLI SHALL accept a `--broken-heuristic` flag, and `generate()` a `broken_heuristic` argument, that enables classifying library, syntax, import, variable-resolution, and timeout failures as `broken`. Without it, every Robot FAIL is reported as `failed`.

#### Scenario: Default conversion reports failed
- **WHEN** the CLI converts a run in which a test fails with `No keyword with name 'X' found.`
- **THEN** that result's status is `failed`

#### Scenario: Flag enables broken
- **WHEN** the CLI converts the same run with `--broken-heuristic`
- **THEN** that result's status is `broken`

### Requirement: Report metadata files

The CLI SHALL accept repeatable `--environment KEY=VALUE` options that are written to `environment.properties` in the results directory, and an `--executor` option pointing to a JSON file (or inline JSON) written as `executor.json`. `generate()` SHALL accept equivalent `environment` (mapping) and `executor` (mapping) arguments. Without these options no such files are written.

#### Scenario: Environment properties written
- **WHEN** the CLI is run with `--environment Browser=chromium --environment Stage=qa`
- **THEN** the results directory contains `environment.properties` with `Browser=chromium` and `Stage=qa`
- **AND** both Allure 2 and Allure 3 reports list those environment entries

#### Scenario: Executor written
- **WHEN** the CLI is run with `--executor '{"name":"GitHub Actions","type":"github","buildName":"#42"}'`
- **THEN** the results directory contains `executor.json` with those fields

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
