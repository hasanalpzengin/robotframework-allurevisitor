## MODIFIED Requirements

### Requirement: Suites map to containers with setup and teardown

The system SHALL map each Robot Framework suite to a `TestResultContainer`, nesting child suites and tests via the container `children` list, and SHALL record suite setup as a `before` and suite teardown as an `after` on the owning container. The system SHALL additionally emit one container per test whose `children` contains only that test, and SHALL record the test's `[Setup]` as a `before` and `[Teardown]` as an `after` on that per-test container, so test setup/teardown appear as fixtures rather than as steps of the test body.

#### Scenario: Nested suites form a container tree
- **WHEN** a suite contains a child suite and tests
- **THEN** the parent container's `children` includes the child container's uuid and each test's uuid

#### Scenario: Suite setup and teardown are captured
- **WHEN** a suite defines a Suite Setup and Suite Teardown
- **THEN** the suite's container records the setup keyword under `befores` and the teardown keyword under `afters`

#### Scenario: Test setup and teardown become per-test fixtures
- **WHEN** a test defines `[Setup]` and `[Teardown]`
- **THEN** a container whose `children` is exactly that test's uuid records the setup under `befores` and the teardown under `afters`
- **AND** neither keyword appears in the test result's `steps`

#### Scenario: Fixtures are visible in both generators
- **WHEN** a report is generated with Allure 2 or Allure 3 from such results
- **THEN** the test's report data lists the suite and test setup fixtures as setup and the teardown fixtures as teardown

### Requirement: Keywords and control structures map to nested steps

The system SHALL map keywords to nested `TestStepResult` items and SHALL represent control structures (FOR, FOR iteration, IF, IF branch, WHILE, TRY, TRY branch, GROUP, VAR) as labelled steps, preserving Robot's nesting via a traversal stack. Keyword assignment SHALL be reflected in the step name, and keyword arguments SHALL be recorded as step parameters named `arg1`, `arg2`, ... `argN` in argument order, matching the `allure-robotframework` listener.

#### Scenario: Nested keywords preserve hierarchy
- **WHEN** a test calls a keyword that calls another keyword
- **THEN** the outer step contains the inner step in its `steps` list

#### Scenario: Control structures are represented as steps
- **WHEN** a test body contains a FOR loop with iterations and an IF block
- **THEN** the FOR, its iterations, the IF, and its branches appear as labelled steps in the step tree

#### Scenario: Assignment and arguments are surfaced
- **WHEN** a keyword `${x} = Some Keyword    first    second` runs
- **THEN** the step name includes the assignment
- **AND** the step parameters are `arg1=first` and `arg2=second`

### Requirement: Status is mapped with details

The system SHALL map Robot statuses to Allure statuses: PASS → passed; SKIP, NOT RUN, and NOT SET → skipped; and FAIL → failed. A test carrying a `skipped` tag (case-insensitive) SHALL be reported as skipped regardless of its Robot status. Only when the broken heuristic is explicitly enabled SHALL a FAIL whose message indicates a library, syntax, import, variable-resolution, or timeout error map to broken. When a failure or skip message exists, the system SHALL populate `StatusDetails.message`.

#### Scenario: Passing test
- **WHEN** a test status is PASS
- **THEN** the result status is `passed` and `statusDetails` is empty

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

### Requirement: Labels, tags, links, and stable identity

The system SHALL derive suite labels from the test `full_name` exactly as the `allure-robotframework` listener does: for `S1.T` → `suite=S1`; for `S1.S2.T` → `suite=S1`, `subSuite=S2`; for three or more suite levels → `parentSuite`=first level, `suite`=second level, and `subSuite`=all remaining suite levels joined by `.`. It SHALL add `framework`, `language`, and `host` labels, and add a `thread` label when one is supplied. It SHALL map Robot tags to Allure labels and links using `allure_commons.mapping.parse_tag` (including severity and `allure.*` tags), SHALL de-duplicate labels the same way the listener does, and SHALL additionally accept the legacy Robot link-tag syntax `issue:[name]url`, `tms:[name]url`, and `link:[name]url` (the `[name]` part optional). It SHALL set `testCaseId` and `historyId` to `md5(full_name [+ sorted parameter values])` so identity is stable across reruns.

#### Scenario: Suite hierarchy becomes suite labels
- **WHEN** a test full name is `Root.Mid.Leaf.My Test`
- **THEN** the result has `parentSuite=Root`, `suite=Mid`, and `subSuite=Leaf` labels

#### Scenario: Deep suite hierarchy matches the listener
- **WHEN** a test full name is `A.B.C.D.My Test`
- **THEN** the result has `parentSuite=A`, `suite=B`, and `subSuite=C.D` labels

#### Scenario: Tags become labels and links
- **WHEN** a test has tags `allure.severity:critical` and `allure.issue:ABC-1`
- **THEN** a severity label and an issue link are present on the result

#### Scenario: Legacy link tag syntax
- **WHEN** a test has the tag `issue:[Bug 7]https://tracker/7`
- **THEN** the result has an issue link named `Bug 7` with url `https://tracker/7`

#### Scenario: historyId is stable across runs
- **WHEN** the same test (same full name and parameters) is converted from two different runs
- **THEN** both results have the same `historyId`

### Requirement: Messages and screenshots become attachments

The system SHALL aggregate the log messages owned by a keyword, fixture, or test into a single HTML attachment named `Keyword Log` on that item, rendering each message as `[LEVEL] message` with newlines as line breaks and FAIL/ERROR messages highlighted in red. When the environment variable `ALLURE_MAX_STEP_MESSAGE_COUNT` is set to N and an item has N or fewer messages, the system SHALL instead emit each message as a zero-duration sub-step (failed for FAIL/ERROR, passed otherwise). Messages that embed image references to files on disk SHALL be resolved (relative to the `output.xml` directory) to first-class binary attachments with the correct image MIME type via `report_attached_file`, and SHALL NOT be duplicated into the `Keyword Log`.

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
