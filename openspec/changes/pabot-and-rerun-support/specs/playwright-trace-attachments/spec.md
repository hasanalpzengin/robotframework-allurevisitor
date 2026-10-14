## MODIFIED Requirements

### Requirement: Relocated output tolerance

When the logged absolute trace path does not exist at conversion time, the system SHALL look for the trace by file name, in this order, relative to the directory of the `output.xml` the trace was logged in:
1. `browser/traces/<name>`
2. a file in `browser/traces/` whose name ends with `-<name>` (pabot `--artifacts` copies)
3. `pabot_results/*/browser/traces/<name>`

The system SHALL skip the trace without failing when none of these exists.

#### Scenario: Output directory moved after the run
- **WHEN** a CI artifact containing `output.xml` and `browser/traces/` is downloaded to a different path and converted
- **THEN** the trace is attached from the relocated `browser/traces/` directory

#### Scenario: Moved pabot output with copied artifacts
- **WHEN** a pabot output directory produced with `--artifacts png,zip --artifactsinsubfolders` is moved and converted
- **THEN** each trace is attached from its prefixed copy in `browser/traces/`

#### Scenario: Moved pabot output without copied artifacts
- **WHEN** a pabot output directory containing `pabot_results/` is moved and converted
- **THEN** each trace is attached from `pabot_results/<n>/browser/traces/`

#### Scenario: Trace file missing
- **WHEN** none of the search locations contains the trace
- **THEN** conversion succeeds without a trace attachment for that context
