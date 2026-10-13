## ADDED Requirements

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
