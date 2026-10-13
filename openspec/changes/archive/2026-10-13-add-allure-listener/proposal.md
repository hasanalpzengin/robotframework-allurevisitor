## Why

Teams using the official `allure-robotframework` listener get runtime-only features (`allure.attach`, `allure.dynamic.*`, `allure.step`, AllureLibrary keywords, test plans) that a post-processor of `output.xml` can never recover, while this project offers better data-derived mapping (result timestamps, control structures, screenshots, Playwright traces, Allure 3 verification). Offering a listener that drives the *same* mapping as `rf-allure` lets this package fully replace `allure-robotframework`, with one consistent output whether results are produced live or after the run. Depends on `allure3-compat-and-capability-parity` (shared mapping core, parity policy, deferred attachment sink).

## What Changes

- New Robot Framework listener (API v3) under this project's own names: `--listener robotframework_allurevisitor.Listener[:RESULTS_DIR]` (default `output/allure`, like upstream).
  - Converts each test from its complete result subtree at test end using the shared mapping core; writes tests, per-test containers, and the suite container at suite end after applying Robot's final statuses (e.g. suite-teardown failure).
  - Captures `allure_commons` runtime hooks (`allure.attach`/`attach.file`, `allure.dynamic` labels/links/title/description/parameters, `allure.step`, global attachments/errors) during execution and places them on the keyword step that was running, keyed by Robot's keyword id.
  - `thread` label from the pabot pool id, else a per-process default — like upstream.
  - Defers copying attachment files until the owning container is written, so traces written at `Close Context` are captured.
  - Warns when the upstream `allure-robotframework` listener is also active.
- New keyword library `robotframework_allurevisitor.AllureLibrary` with upstream-compatible keywords `Attach`, `Attach File`, `Global Attach`, `Global Attach File`, `Global Error`.
- New pre-run modifier `robotframework_allurevisitor.testplan` honouring `ALLURE_TESTPLAN_PATH` (select by `allure.id` or full-name selector).
- Migration guide from `allure-robotframework` (before/after table for listener, library, prerunmodifier, environment variables, known differences).
- No changes to `rf-allure` behaviour; listener and converter produce equivalent results for the same run.

## Capabilities

### New Capabilities
- `allure-listener`: live Robot Framework listener producing Allure results through the shared mapping, including runtime-hook overlay, status reconciliation, pabot thread labels, and coexistence rules.
- `allure-runtime-library`: Robot keyword library for attachments and global attachments/errors during a run.
- `allure-testplan`: pre-run modifier selecting tests from an Allure test plan.

### Modified Capabilities
- `package-distribution`: release documentation must include the migration guide from `allure-robotframework`.

## Impact

- Code: new `listener.py`, `AllureLibrary.py` (or package), `testplan.py`; `__init__.py` exports; small extensions to the mapping core (runtime overlay hook point, deferring sink).
- Docs: `docs/migration-from-allure-robotframework.md`, README listener section, AGENTS.md layout.
- Tests: listener tests running real Robot suites with `--listener`, converter/listener equivalence test, runtime-hook tests with a helper Python library, testplan tests, e2e on both generators.
- Dependencies: none new (`allure-python-commons` already provides `allure` and hooks).
- Version: minor release after 0.2.0 (e.g. 0.3.0).
