# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## What this project is

`robotframework-allurevisitor` generates [Allure](https://allurereport.org/) input
files from Robot Framework results. It is an **alternative to the
`allure-robotframework` listener**: rather than hooking into a live test run, it
post-processes an existing Robot Framework `output.xml` using Robot Framework's
`ResultVisitor` API and writes Allure `*-result.json` files into a results
directory.

Use it when you have a Robot `output.xml` (e.g. from CI, a rerun, or a merged
run) and want an Allure report without re-running the tests.

## Tech stack & layout

- **Python** `>=3.13`, packaged with **hatchling**, `src/` layout.
- **Environment & dependencies are managed by [uv](https://docs.astral.sh/uv/).**
- Runtime deps: `robotframework` (the `ResultVisitor`/`ExecutionResult` API) and
  `allure-python-commons` (the Allure model + file logger).
- Dev deps (in the `dev` dependency group): `pytest`, `ruff`. Optional `browser`
  group: `robotframework-browser` (only for the `browser` trace tests).

```
src/robotframework_allurevisitor/
  __init__.py     # public API: AllureResultVisitor, generate
  visitor.py      # stack-based ResultVisitor (traversal only) + generate()
  _mapping.py     # Mapper: Robot node -> Allure object; AttachmentSink; messages, traces
  _convert.py     # timing (to_ms), status (status_of), identity, properties_text
  _labels.py      # suite_labels(), tag_labels_and_links() (parse_tag + legacy links)
  cli.py          # `rf-allure` / `allurevisitor` console entry point
tests/
  conftest.py              # run_robot()/load_results()/load_containers() helpers
  allure_cli.py            # Allure 2/3 generator resolution + normalised report readers
  test_visitor.py          # runs real Robot suites, asserts the emitted Allure JSON
  test_labels.py           # suite labels, tag/link mapping
  test_traces.py           # Playwright trace detection (no Browser needed)
  test_cli.py              # CLI options, environment/executor files
  test_allure_cli.py       # readers agree on a fixed results dir (`e2e`)
  test_e2e_report.py       # status counts on Allure 2 + 3 (`e2e`)
  test_e2e_capabilities.py # every capability on Allure 2 + 3 (`e2e`)
  test_e2e_browser.py      # real robotframework-browser traces (`browser`)
```

## Environment setup

The environment is **uv-managed** — do not use bare `pip`, `venv`, or edit
`pyproject.toml` dependency tables by hand.

```bash
uv sync                       # create .venv and install all deps + dev group
uv add <package>              # add a runtime dependency
uv add --dev <package>        # add a dev dependency (dev group)
uv remove <package>           # remove a dependency
```

`uv add`/`uv remove` update `pyproject.toml` and `uv.lock` together — always go
through them so the lockfile stays in sync.

## Common commands

```bash
uv run pytest                 # run the test suite
uv run ruff check .           # lint
uv run ruff format .          # format
uv run rf-allure OUTPUT_XML... -o RESULTS_DIR [--clean] [--thread ID] \
    [--broken-heuristic] [--environment K=V]... [--executor JSON]       # generate
```

Programmatic use:

```python
from robotframework_allurevisitor import generate
generate("output.xml", "allure-results", clean=True)
```

## How the visitor maps Robot -> Allure

Output deliberately matches the upstream `allure-robotframework` listener where
the difference is presentation only (fixtures, Keyword Log, `arg1..N`, suite
labels, FAIL->failed, `skipped` tag); it keeps data-derived timestamps.

- **Suites -> `TestResultContainer`** (`<uuid>-container.json`); Suite
  Setup/Teardown become the container's `befores`/`afters`. Child containers and
  tests are linked via `children`. **Each test also gets its own container**
  (`children=[test uuid]`) holding its `[Setup]`/`[Teardown]` as befores/afters.
- **Tests -> `TestResult`** (`<uuid>-result.json`).
- **Keywords and control structures (FOR/IF/WHILE/TRY/GROUP/VAR/…) -> nested
  `TestStepResult`**, kept correctly nested via a traversal stack (`_steps`).
  Keyword assignment is folded into the step name; arguments become step
  parameters `arg1..N`.
- Status (`status_of` in `_convert.py`): `PASS->passed`,
  `SKIP`/`NOT RUN`/`NOT SET->skipped`, `FAIL->failed`; library/import/syntax/timeout
  errors -> `broken` only with `broken_heuristic`. A `skipped` tag forces skipped.
- Times come from the result data via `to_ms` (epoch ms), **never** wall-clock —
  conversion is reproducible. RF 7 `datetime` and legacy RF 4-6 strings both work.
- `historyId`/`testCaseId = md5(full_name)` (`history_id`) so Allure groups runs
  across reruns/CI.
- Labels (`_labels.py`): `parentSuite`/`suite`/`subSuite` from the full name
  (upstream `get_allure_suites` rules), `framework`/`language`/`host`, optional
  `thread`, plus tag labels/links via `parse_tag` and the legacy
  `issue:`/`tms:`/`link:` tags, de-duplicated with `labels_set`.
- Log messages are buffered per stack frame and flushed at frame end as one
  `Keyword Log` HTML attachment (or sub-steps, `ALLURE_MAX_STEP_MESSAGE_COUNT`);
  plain text is HTML-escaped. Embedded screenshots -> image attachments resolved
  relative to the `output.xml` directory.
- Playwright traces: Browser's `trace file will be saved to: <zip>` message ->
  `application/vnd.allure.playwright-trace` attachment on the owning frame;
  fallback `<output.xml dir>/browser/traces/<name>`. Never timestamp matching.
- All attachment files go through `AttachmentSink` (immediate copy here; a live
  front end can defer copies).

## Key behaviors to preserve

- **Fixture detection** in `start_keyword`: `kw.type in (SETUP, TEARDOWN)` and
  either no test is active (suite fixture -> suite container) or the test is on
  top of the stack (test fixture -> per-test container). A user keyword's own
  `[Teardown]` has its keyword on top and stays a step.
- **Control structures use `type`/attributes for labels, not `.name`** — `For.name`
  and `If.name` are deprecated and warn in RF 8.
- **Multiple sources combine, they do NOT last-wins merge.**
  `ExecutionResult(*sources)` nests each source as a sibling sub-suite; identical
  `historyId` makes Allure group them as retries. For a single deduplicated
  result, pre-merge with `rebot --merge`.
- **Partial output**: `generate()` wraps parse+visit so a truncated `output.xml`
  warns instead of crashing. `ExecutionResult` parses eagerly, so an unparseable
  file recovers nothing — by design.

## Conventions for changes

- Keep mapping logic in `visitor.py`; keep conversion helpers in `_convert.py` /
  `_labels.py`; keep `cli.py` thin.
- Robot model objects are duck-typed across RF versions — prefer `getattr(...)`
  with sensible fallbacks over hard attribute access.
- Add/adjust a test in `tests/` for any behavior change. Tests run real Robot
  suites via `python -m robot` (see `conftest.py`), so they are self-contained —
  no committed `output.xml` fixtures.
- Run `uv run ruff check .` and `uv run pytest` before declaring work done.
- Target line length is 100 (`tool.ruff` in `pyproject.toml`).

## End-to-end tests (`e2e` / `browser` markers)

The e2e tests run Robot → the packaged `rf-allure` CLI (subprocess, so the entry
point is exercised) → real **Allure 2 and Allure 3** reports, parametrised over
`GENERATORS` in `tests/allure_cli.py`.

- Select/deselect with `uv run pytest -m e2e` / `-m "not e2e"`.
- `resolve_command()` picks an `allure` on `PATH` of the right major version,
  else `npx allure@$ALLURE3_VERSION` / `npx allure-commandline@$ALLURE2_VERSION`.
  Each generator is called with its own syntax (Allure 3 has no `--clean`).
- Unresolvable generator -> **skip** (or fail with `ALLURE_REQUIRE_GENERATORS=1`,
  as CI does); a resolved generator that exits non-zero -> **fail**.
- Assert through `Report.stats()` / `test_cases()` / `environment()`, which
  normalise Allure 2 (`widgets/summary.json`, `data/test-cases/`) and Allure 3
  (`summary.json`, `data/test-results/`) data. Assert on data, never HTML.
- `browser` tests need `uv sync --group browser` + `rfbrowser init chromium`
  and skip when the Browser library or its browsers are unavailable.
