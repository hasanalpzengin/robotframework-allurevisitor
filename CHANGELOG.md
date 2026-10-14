# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-13

pabot, re-executed tests, and both together, with Browser screenshots and traces,
verified end to end for the converter and the listener on Allure 2 and Allure 3.

### Changed
- **BREAKING (identity):** multiple sources (`rf-allure original.xml rerun.xml`)
  are converted one by one instead of under a combined `A & B` root suite. Names,
  suite labels, and `historyId` now equal a single-source conversion, so Allure
  history lines up across runs. Results from earlier multi-source conversions
  have a different `historyId`.
- Each source resolves screenshots and traces against its own directory, not the
  first source's.
- Robot `*HTML*` status messages (e.g. `rebot --merge` notes) become plain text.
  A passed test keeps its message (`Pass Execution`, merge notes).

### Added
- `rf-allure --merge` / `generate(..., merge=True)`: merge like `rebot --merge`
  (last wins, one result per test), with every test keeping its own run's
  screenshots and traces.
- Warnings for screenshots that cannot be found (with a hint about pabot's
  `--artifactsinsubfolders`), and for relative screenshots of re-executed tests
  in a `rebot --merge` file.
- Trace lookup in pabot layouts: prefixed `--artifacts` copies and
  `pabot_results/<n>/browser/traces/`.
- README section "Parallel runs and re-execution"; `robotframework-pabot` joins
  the `browser` dependency group and its workflow tests.

## [0.3.0] - 2026-10-13

A live listener that replaces `allure-robotframework`, sharing the converter's
mapping.

### Added
- `robotframework_allurevisitor.Listener` (Robot listener API v3):
  `robot --listener robotframework_allurevisitor.Listener[:DIR]` (default
  `output/allure`), with `clean=True` and `broken_heuristic=True` options.
  Its results equal converting the same run's `output.xml` with `rf-allure`.
- Runtime data from Python libraries while the listener runs: `allure.attach`,
  `allure.attach.file`, `allure.dynamic.*` (labels, links, title, description,
  parameters), `allure.step` (failed for `AssertionError`, broken otherwise), and
  global attachments/errors — each placed on the keyword step that made the call.
- `robotframework_allurevisitor.AllureLibrary` keywords: `Attach`, `Attach File`,
  `Global Attach`, `Global Attach File`, `Global Error`.
- `--prerunmodifier robotframework_allurevisitor.testplan`
  (`ALLURE_TESTPLAN_PATH`, select by `allure.id` or full name).
- pabot `thread` labels, a warning when the upstream listener is also active, and
  a [migration guide](https://github.com/manykarim/robotframework-allurevisitor/blob/main/docs/migration-from-allure-robotframework.md).
- Final statuses are applied the way `log.html` shows them: a failing suite
  setup/teardown also fails finished tests, including tests of child suites.

## [0.2.0] - 2026-10-13

Allure 3 support, output parity with the `allure-robotframework` listener, and
Playwright trace attachments.

### Breaking
Results now match the official `allure-robotframework` listener. Reports built
from 0.1.0 and 0.2.0 results therefore differ:
- Test `[Setup]`/`[Teardown]` are fixtures on a per-test container (shown as
  *Set up* / *Tear down*) instead of steps of the test body.
- Log messages of a step are combined into one `Keyword Log` HTML attachment
  (FAIL/ERROR in red; plain text HTML-escaped) instead of one attachment per
  message. `ALLURE_MAX_STEP_MESSAGE_COUNT=N` shows small message sets as sub-steps.
- Step parameters are named `arg1..N` (was `arg0..N`).
- A Robot `FAIL` is `failed`. The library/syntax/import/timeout -> `broken`
  guess is now opt-in via `--broken-heuristic` / `broken_heuristic=True`.
- Suites nested three or more levels deep are labelled like the listener
  (`A.B.C.D.Test` -> `parentSuite=A`, `suite=B`, `subSuite=C.D`).

### Added
- Allure 3 support, verified alongside Allure 2: the e2e tests generate real
  reports with both (pinned to 3.20.1 / 2.46.1) and check each report's own data,
  and CI runs both.
- Playwright trace attachments for robotframework-browser `tracing=True`
  contexts, including contexts opened in Suite Setup, with
  `application/vnd.allure.playwright-trace` for the Trace Viewer in Allure 2
  (2.35+) and Allure 3. Based on the idea and MIME handling from
  [#1](https://github.com/manykarim/robotframework-allurevisitor/pull/1) by
  @hasanalpzengin, reworked to find traces from Browser's log instead of by
  timestamp.
- `--environment KEY=VALUE` and `--executor JSON` (and `environment=` /
  `executor=` in `generate()`) to write `environment.properties` / `executor.json`.
- A `skipped` tag forces status `skipped`; `NOT SET` maps to `skipped`.
- Legacy link tags `issue:[name]url`, `tms:[name]url`, `link:[name]url`.
- Optional `browser` dependency group and `browser` pytest marker for real
  robotframework-browser trace tests.

### Fixed
- Plain-text log messages containing `<` or `&` no longer corrupt the HTML log
  attachment.
- Duplicate labels from repeated tags are collapsed.

## [0.1.0] - 2026-06-04

Initial release.

### Added
- `AllureResultVisitor`, a stack-based Robot Framework `ResultVisitor` that
  converts an `output.xml` into Allure result files using the official
  `allure-python-commons` model and file logger.
- Mapping of suites to containers (with suite setup/teardown as
  `befores`/`afters`), tests to results, and keywords plus control structures
  (FOR/IF/WHILE/TRY/GROUP/VAR) to nested steps.
- Status mapping (`passed`/`failed`/`skipped`/`broken`), data-derived
  timestamps, `parentSuite`/`suite`/`subSuite` and tag/link labels, stable
  `historyId`, and message/screenshot attachments.
- `generate()` API and the `rf-allure` (alias `allurevisitor`) console script,
  supporting multiple sources, `--clean`, `--thread`, and issue/link patterns.
- Unit tests plus an end-to-end test that runs the full
  Robot → `rf-allure` → Allure report pipeline.

[0.3.0]: https://github.com/manykarim/robotframework-allurevisitor/releases/tag/v0.3.0
[0.2.0]: https://github.com/manykarim/robotframework-allurevisitor/releases/tag/v0.2.0
[0.1.0]: https://github.com/manykarim/robotframework-allurevisitor/releases/tag/v0.1.0
