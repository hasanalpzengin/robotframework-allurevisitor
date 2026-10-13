## Why

Allure 3 (npm `allure`, 3.20.x) is now the current Allure generator alongside Allure 2 (2.46.x). Both consume our result files, but the e2e test only proves Allure 2: with Allure 3 on `PATH` it passes `--clean` (rejected by Allure 3) and asserts on Allure 2's report layout, so an Allure 3 regression would surface as a silent *skip*. At the same time the project's output differs from the official `allure-robotframework` listener in several user-visible ways (test fixtures, log attachments, parameter names, `broken` heuristics, deep suite labels), and Playwright trace support has been proposed in PR #1 using a timestamp heuristic that drops traces from contexts opened in Suite Setup. This change makes the converter verifiably work with both generators, aligns its output with the upstream listener, and adds robust trace support — the foundation for the follow-up `add-allure-listener` change, which must produce identical output.

## What Changes

- **Dual-generator e2e**: the e2e test resolves Allure 2 and Allure 3 independently, invokes each with its own CLI syntax, and asserts on each generator's native machine-readable report data (Allure 2: `widgets/summary.json`, `data/test-cases/`; Allure 3: `summary.json`, `data/test-results/`). An available-but-failing generator fails the test instead of skipping. CI runs both.
- **Upstream-parity output** (policy: match upstream where it is a presentation choice; keep data-derived behavior where upstream is constrained by being live):
  - **BREAKING** Test setup/teardown become `befores`/`afters` on a per-test container (previously ordinary steps).
  - **BREAKING** Log messages of a keyword are aggregated into one `Keyword Log` HTML attachment per step (FAIL/ERROR in red), instead of one attachment per message; `ALLURE_MAX_STEP_MESSAGE_COUNT` switches to per-message sub-steps like upstream. Embedded screenshots stay first-class image attachments.
  - **BREAKING** Step parameters are named `arg1..N` (previously `arg0..N`).
  - **BREAKING** `FAIL` maps to `failed` by default; the message-heuristic `broken` classification becomes opt-in (`--broken-heuristic` / `broken_heuristic=True`).
  - **BREAKING** Suite labels for deep hierarchies follow upstream (`parentSuite`=root, `suite`=second level, `subSuite`=remaining levels joined by `.`).
  - A `skipped` tag forces status `skipped`; legacy RF link tag syntax (`issue:[name]url`, `tms:...`, `link:...`) is supported.
- **Playwright traces** (folded from PR #1, credit @hasanalpzengin): trace zips announced by robotframework-browser's `New Context` log message (`trace file will be saved to: <path>`) are attached with MIME `application/vnd.allure.playwright-trace` to the owning step/fixture, with a fallback to `<output.xml dir>/browser/traces/<name>` when the logged absolute path no longer exists. No timestamp matching.
- **Report metadata**: optional CLI/API inputs to write `environment.properties` and `executor.json`.
- **Docs**: README section on Allure 2 vs 3 usage (history via `historyPath`, categories from config), and an explicit list of runtime-only listener features that cannot be recovered from `output.xml`.
- Version bump to `0.2.0` with CHANGELOG notes on the breaking output changes.

## Capabilities

### New Capabilities
- `playwright-trace-attachments`: discovering robotframework-browser trace files from the result log and attaching them as Playwright-trace attachments.

### Modified Capabilities
- `allure-result-generation`: fixture mapping for test setup/teardown, message aggregation, parameter naming, default status mapping and opt-in broken heuristic, deep suite labels, `skipped` tag and legacy link tags.
- `allure-conversion-cli`: new `--broken-heuristic`, `--environment`, `--executor` options.
- `e2e-report-verification`: dual Allure 2 / Allure 3 resolution, per-generator native assertions, no silent skip on generator failure, broader capability suite.

## Impact

- Code: `visitor.py` (fixtures, messages, traces, status option), `_convert.py` (status default), `_labels.py` (suite labels, legacy link tags), `cli.py` (options), `tests/` (conftest generator resolution, e2e, visitor tests), `.github/workflows/ci.yml` (both generators).
- Output contract: breaking changes to result JSON shape for existing 0.1.0 users → `0.2.0`.
- Supersedes PR #1 (to be closed with credit and a link to this change).
- No new runtime dependencies. CI requires Node (Allure 3, Allure 2 via npx) and Java (Allure 2).
