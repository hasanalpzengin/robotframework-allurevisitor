## MODIFIED Requirements

### Requirement: Status is mapped with details

The system SHALL map Robot statuses to Allure statuses: PASS → passed; SKIP, NOT RUN, and NOT SET → skipped; and FAIL → failed. A test carrying a `skipped` tag (case-insensitive) SHALL be reported as skipped regardless of its Robot status. Only when the broken heuristic is explicitly enabled SHALL a FAIL whose message indicates a library, syntax, import, variable-resolution, or timeout error map to broken.

When a test or step has a message, the system SHALL populate `StatusDetails.message`. This includes a passed test whose message comes from `Pass Execution` or from a merge note. A message in Robot's HTML format (prefixed `*HTML*`, as written by a result merge) SHALL be converted to readable plain text: tags removed, entities decoded, and the merge note, new status, and old status and message kept on separate lines.

#### Scenario: Passing test
- **WHEN** a test status is PASS and it has no message
- **THEN** the result status is `passed` and `statusDetails` is empty

#### Scenario: Passing test with a message
- **WHEN** a test passes through `Pass Execution    nothing to do`
- **THEN** the result status is `passed` and `statusDetails.message` is `nothing to do`

#### Scenario: Assertion failure
- **WHEN** a test fails with an assertion message
- **THEN** the result status is `failed` and `statusDetails.message` contains the failure message

#### Scenario: Library or syntax error
- **WHEN** a test fails because a keyword could not be found and the broken heuristic is not enabled
- **THEN** the result status is `failed`

#### Scenario: Library or syntax error with broken heuristic enabled
- **WHEN** a test fails because a keyword could not be found and the broken heuristic is enabled
- **THEN** the result status is `broken`

#### Scenario: Skipped test
- **WHEN** a test is skipped
- **THEN** the result status is `skipped`

#### Scenario: skipped tag forces skipped status
- **WHEN** a test that passed carries the tag `skipped`
- **THEN** the result status is `skipped`

#### Scenario: Merged test message is plain text
- **WHEN** a test re-executed and merged by `rebot --merge` failed in both runs
- **THEN** its result status is `failed` and `statusDetails.message` contains no HTML tags and includes "re-executed", the new status, and the old status and message

### Requirement: Messages and screenshots become attachments

The system SHALL aggregate the log messages owned by a keyword, fixture, or test into a single HTML attachment named `Keyword Log` on that item. Each message SHALL be rendered as `[LEVEL] message`, with newlines as line breaks and FAIL/ERROR messages highlighted in red.

When the environment variable `ALLURE_MAX_STEP_MESSAGE_COUNT` is set to N and an item has N or fewer messages, the system SHALL instead emit each message as a zero-duration sub-step (failed for FAIL/ERROR, passed otherwise).

Messages that embed image references to files on disk SHALL be resolved, relative to the directory of the `output.xml` the test came from, to first-class binary attachments with the correct image MIME type via `report_attached_file`. They SHALL NOT be duplicated into the `Keyword Log`. When a referenced image cannot be found, the system SHALL:
- emit a warning naming the missing file, which for a relative reference suggests pabot's `--artifactsinsubfolders`;
- keep the message in the `Keyword Log`.

#### Scenario: Log message folded into the owning step
- **WHEN** a keyword logs three INFO messages
- **THEN** the keyword's step has exactly one `text/html` attachment named `Keyword Log` containing all three messages with their levels

#### Scenario: Failure messages highlighted
- **WHEN** a keyword logs a FAIL message
- **THEN** that message is rendered in red within the `Keyword Log` attachment

#### Scenario: Messages as sub-steps
- **WHEN** `ALLURE_MAX_STEP_MESSAGE_COUNT=5` and a keyword logs two messages
- **THEN** the keyword's step contains two zero-duration sub-steps named after the messages and no `Keyword Log` attachment

#### Scenario: Screenshot becomes a binary attachment
- **WHEN** a log message embeds an image reference to a file on disk
- **THEN** an image attachment is emitted via `report_attached_file` with an image MIME type
- **AND** the image message is not repeated inside the `Keyword Log` attachment

#### Scenario: Missing screenshot warns
- **WHEN** a pabot-merged `output.xml` produced without `--artifactsinsubfolders` references `browser/screenshot/fail-screenshot-1.png` and that file does not exist next to it
- **THEN** conversion succeeds, a warning names the missing file and mentions `--artifactsinsubfolders`, and the message stays in the `Keyword Log`
