## 1. Prerequisites

- [ ] 1.1 Confirm `allure3-compat-and-capability-parity` is applied (mapping core, `AttachmentSink`, parity behaviours) and verify `uv run pytest` is green on main before starting

## 2. Mapping core extension points

- [ ] 2.1 Add `Overlay` hook points to the mapping core (`apply(kw_id, step)`, `apply_test(test_result)`, fixture keys) with a no-op default for the converter; verify the existing converter tests still pass unchanged
- [ ] 2.2 Add a deferring `AttachmentSink` (record now, copy on flush, warn on missing file); verify with a unit test that a file created after recording is copied on flush

## 3. Listener

- [ ] 3.1 Implement `robotframework_allurevisitor.Listener` (API v3) with suite/test frames, keyword-id stack, convert-at-`end_test`, write-at-`end_suite`, and `close`; export from `__init__.py`; verify with a test that runs a real suite via `--listener` and finds one result per test in `output/allure` and in a custom directory
- [ ] 3.2 Implement status reconciliation at `end_suite`; verify with the suite-teardown-failure test (`failed`, message contains `Parent suite teardown failed`)
- [ ] 3.3 Add the thread label (pabot pool id / `default-<uuid>`); verify with a test that sets `PABOTEXECUTIONPOOLID`/`CALLER_ID` variables and with a pabot run when pabot is available (skip otherwise)
- [ ] 3.4 Add coexistence detection; verify a warning appears when `allure-robotframework` is installed in a scratch venv and both listeners are passed (skip when not installable)

## 4. Runtime hooks

- [ ] 4.1 Implement the `RuntimeHooks` plugin (attach data/file, labels, links, title, description(_html), parameters, steps, globals, global error) recording into `Overlay`; verify with a helper Python test library exercising each hook and asserting placement (keyword step, nested `allure.step`, test-level labels/links, suite fixture)
- [ ] 4.2 Verify `allure.step` status mapping (`failed` for `AssertionError`, `broken` otherwise) with a test library raising both

## 5. Library and test plan

- [ ] 5.1 Implement `robotframework_allurevisitor.AllureLibrary` keywords (`Attach`, `Attach File`, `Global Attach`, `Global Attach File`, `Global Error`); verify with Robot suites run with and without the listener
- [ ] 5.2 Implement `robotframework_allurevisitor.testplan` pre-run modifier; verify selection by `allure.id`, by selector, and no-plan behaviour

## 6. Equivalence and end-to-end

- [ ] 6.1 Add the listener/converter equivalence test with normalisation (uuids, attachment hashes, `thread`); verify it passes on the capability suite from change A
- [ ] 6.2 Extend the e2e tests to generate Allure 2 and Allure 3 reports from listener output, including runtime attachments and a Browser suite-level trace (browser marker); verify `uv run pytest -m "e2e or browser"` passes for both generators

## 7. Documentation and release

- [ ] 7.1 Write `docs/migration-from-allure-robotframework.md` (before/after table, env vars, default dir, known differences, do-not-run-both note) and link it from README with a listener usage section; verify all commands in the guide by running them against a sample suite
- [ ] 7.2 Update AGENTS.md layout/behaviour sections and CHANGELOG for the minor release; verify `uv build` and `twine check` succeed
- [ ] 7.3 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -rs`; confirm no listener or e2e variant is unexpectedly skipped
