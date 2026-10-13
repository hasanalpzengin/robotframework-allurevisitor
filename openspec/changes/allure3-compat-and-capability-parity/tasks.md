## 1. Test harness for both generators

- [x] 1.1 Add generator resolution to `tests/allure_cli.py` (PATH `--version` probe, npx fallbacks with `ALLURE2_VERSION`/`ALLURE3_VERSION` pins, per-version `generate` syntax; skip on unresolvable, `pytest.fail` on run failure) and verify by running `uv run pytest -m e2e -rs` with and without Node on `PATH`
- [x] 1.2 Add report readers normalising Allure 2 (`widgets/summary.json`, `data/test-cases/`) and Allure 3 (`summary.json` with missing keys = 0, `data/test-results/`) into `stats()` / `test_cases()`; verify with a unit test against reports generated from a fixed results directory
- [x] 1.3 Parametrise `test_e2e_report.py` over `allure2`/`allure3` and verify both variants pass on the current code (status counts, one case per test)

## 2. Mapping core refactor

- [x] 2.1 Extract per-node builders from `visitor.py` into `_mapping.py` with an `AttachmentSink` (immediate copy) and verify the existing `tests/test_visitor.py` passes unchanged
- [x] 2.2 Add per-frame message buffers and the `Keyword Log` / sub-step flush (escaping, `<br>`, red FAIL/ERROR, `ALLURE_MAX_STEP_MESSAGE_COUNT`); verify with tests for aggregation, highlighting, sub-step mode, and that image messages are not duplicated

## 3. Parity behaviours

- [x] 3.1 Emit per-test containers with test `[Setup]`/`[Teardown]` as befores/afters; verify container `children` and absence from `steps` in `test_visitor.py`
- [x] 3.2 Rename step parameters to `arg1..N`; verify the assignment/arguments test
- [x] 3.3 Make FAIL→failed default, add `broken_heuristic` to `status_of`/`generate()`/visitor, add NOT SET, apply `skipped` tag override; verify with status tests for default, heuristic-on, and `skipped` tag
- [x] 3.4 Port upstream suite-label algorithm and legacy `issue:`/`tms:`/`link:` tags with `labels_set` de-duplication; verify with tests for 1-, 2-, 3-, 4-level names and `issue:[Bug 7]https://tracker/7`

## 4. Playwright traces

- [x] 4.1 Detect `trace file will be saved to:` messages, resolve path (logged → `<source_dir>/browser/traces/<name>` → skip), attach with `application/vnd.allure.playwright-trace`; verify with unit tests that synthesise the log message and a dummy zip for: per-test, suite setup, relocated, and missing cases
- [x] 4.2 Add registered `browser` pytest marker and `tests/test_e2e_browser.py` running real Browser suites (per-test and suite-level context) that skips when robotframework-browser/browsers are unavailable; verify locally with `PLAYWRIGHT_BROWSERS_PATH` set and both generators showing the trace attachments

## 5. CLI and metadata

- [x] 5.1 Add `--broken-heuristic`, repeatable `--environment KEY=VALUE`, and `--executor` (file or inline JSON) to `cli.py` and `generate()`, writing `environment.properties`/`executor.json` after `--clean`; verify with CLI tests asserting file contents

## 6. Capability e2e

- [x] 6.1 Add a capability suite (labels, links, description, suite+test fixtures, nested steps, screenshot, Keyword Log, environment) to the e2e tests and assert each capability through the normalised readers for both generators; verify `uv run pytest -m e2e` passes for allure2 and allure3

## 7. CI, docs, release

- [ ] 7.1 Update `.github/workflows/ci.yml` with setup-node, setup-java, npm cache, and an optional browser job; verify the workflow on a branch push shows both generator variants passed (not skipped)
- [x] 7.2 Update README (Allure 2 vs 3 usage, `historyPath`, config categories, runtime-only features list, breaking changes) and AGENTS.md mapping section; verify links and commands by running them
- [x] 7.3 Bump version to 0.2.0, add CHANGELOG entry with Breaking section and credit to @hasanalpzengin for PR #1; verify `uv build` and `twine check` succeed
- [ ] 7.4 Commit trace work with `Co-authored-by: hasanalpzengin <hasalp38@gmail.com>`, close PR #1 with a comment linking this change; verify the trailer in `git log` and PR state
- [x] 7.5 Run `uv run ruff check .`, `uv run ruff format --check .`, and full `uv run pytest -rs` and confirm no e2e variant is skipped on a machine with Node+Java
