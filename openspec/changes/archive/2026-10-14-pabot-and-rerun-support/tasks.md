## 1. Setup

- [x] 1.1 Run `uv add --group browser robotframework-pabot` and verify that `uv run --group browser python -m pabot.pabot --version` prints the version and `uv.lock` is updated
- [x] 1.2 Verify `uv run pytest` and `uv run ruff check .` are green on main before starting

## 2. Per-source conversion

- [x] 2.1 Change `generate()` to parse and visit each source separately, setting `mapper.options.source_dir` to that source's directory and keeping partial-output tolerance per source (a broken source warns; later sources still convert). Verify with a test that converting `original.xml` alone and `original.xml` + `rerun.xml` gives the same `fullName`, `historyId`, and suite labels for a shared test
- [x] 2.2 Verify per-source attachment resolution: two sources in different directories each reference `screenshot.png` with different content, and each attempt carries the file from its own directory (content hash)
- [x] 2.3 Update the multi-source tests in `test_visitor.py`/`test_cli.py` that assumed the combined root (none needed changes: they assert the shared `historyId` and the latest status, not names); verify the full suite passes

## 3. Converter merge

- [x] 3.1 Add a per-test source-directory hook to the visitor, switching `source_dir` at `start_test` and restoring it at `end_test`. Verify that `test_equivalence.py` still passes, which shows the listener is unaffected
- [x] 3.2 Implement `generate(..., merge=True)` with Robot's `Merger` and a `{id(test): source_dir}` map. Verify with a test that a re-executed test gives exactly one `passed` result with the "re-executed and merged" message and the rerun directory's screenshot, while a test that was not re-executed keeps the original directory's screenshot
- [x] 3.3 Add `--merge` to `rf-allure`; verify with a CLI test that `--merge` gives one result per test and that, without `--merge`, both attempts are emitted

## 4. Mapping robustness

- [x] 4.1 Convert `*HTML*` status messages to plain text (prefix removed, `<br>`/`<hr>` → newlines, tags removed, entities decoded). Verify with a `rebot --merge` output in which a test failed twice: the message has no `<` tags and contains "re-executed", the new status, and the old message
- [x] 4.2 Warn on an unresolvable `<img src>` file reference (stderr; the message names the file and mentions `--artifactsinsubfolders` for relative paths), with no warning for `http(s):`/`data:` sources. Verify with a test that removes the screenshot file before conversion: the warning is emitted, conversion succeeds, and the message remains in the `Keyword Log`
- [x] 4.3 Extend the trace relocation search (`browser/traces/<name>`, `browser/traces/*-<name>`, `pabot_results/*/browser/traces/<name>`). Verify with unit tests in `test_traces.py` that build each layout in a temporary directory without Browser and assert the trace is attached

## 5. Workflow end-to-end tests (`browser`)

- [x] 5.1 Create `tests/test_e2e_workflows.py` with the two-suite flaky Browser fixture. Each test's page shows its name and its run, so every screenshot has unique content. Add module-scoped runners for pabot, rerun (separate `--outputdir`), and pabot + `pabot --rerunfailed`, each with and without the listener; skip when Browser or pabot is unavailable. Run pabot with the temporary directory as its working directory, so `.pabotsuitenames` stays out of the repo. Verify that the fixture alone runs green under `pytest -m browser`
- [x] 5.2 pabot: verify that converter output (with `--artifactsinsubfolders`) and listener output attach each test's own screenshot (by hash) and trace, and that listener results carry two distinct pool-id thread prefixes
- [x] 5.3 Rerun: verify that converter retries mode, converter `--merge`, `rebot --merge` conversion, and the listener (same results dir) give the expected attempts, statuses, shared `historyId`, and per-attempt screenshot and trace
- [x] 5.4 pabot + rerun: verify that converter retries mode and `--merge` (with `--artifactsinsubfolders`), and the listener across both pabot runs, give the expected attempts and per-attempt attachments
- [x] 5.5 Generate Allure 2 and Allure 3 reports for the retries, merge, and listener outputs. Verify that each test's status and attachments appear in `Report` data. Make `Report.test_cases()` hide retry entries (Allure 2 `retry`, Allure 3 `isRetry`) and give each case a `retries` count (Allure 2 `extra.retries`, Allure 3 `retries`). Verify that the flaky test shows one retry on both generators

## 6. Docs and release

- [x] 6.1 README: add a "Parallel runs and re-execution" section with the commands for each workflow and both front ends, plus the three constraints (separate rerun `--outputdir`, `--artifactsinsubfolders`, prefer `rf-allure --merge` over `rebot --merge`). Verify by running each documented converter command against the e2e fixture output
- [x] 6.2 Update AGENTS.md (per-source visit rule, `--merge`, workflow tests) and CHANGELOG 0.4.0 (with a BREAKING note on multi-source `historyId`), and bump the version to 0.4.0. Verify that `uv build` succeeds
- [x] 6.3 Run `uv run ruff check .`, `uv run pytest`, and `uv run --group browser pytest -m "e2e or browser"`, and verify all are green with only the expected skips
