# robotframework-allurevisitor

[![PyPI version](https://img.shields.io/pypi/v/robotframework-allurevisitor.svg)](https://pypi.org/project/robotframework-allurevisitor/)
[![Python versions](https://img.shields.io/pypi/pyversions/robotframework-allurevisitor.svg)](https://pypi.org/project/robotframework-allurevisitor/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/manykarim/robotframework-allurevisitor/blob/main/LICENSE)

Generate [Allure](https://allurereport.org/) results from Robot Framework, for
Allure 2 and Allure 3. Two entry points share one Robot → Allure mapping and
write the same `*-result.json` / `*-container.json` / `*-attachment.*` files via
the official `allure-python-commons` engine:

- **`rf-allure`** post-processes an existing `output.xml` (from CI, a rerun, or a
  pabot run) — no re-run needed.
- **`robotframework_allurevisitor.Listener`** writes results during a run and also
  records runtime-only data (`allure.attach`, `allure.dynamic.*`, `allure.step`).
  It replaces the `allure-robotframework` listener; see the
  [migration guide](https://github.com/manykarim/robotframework-allurevisitor/blob/main/docs/migration-from-allure-robotframework.md).

## Installation

```bash
pip install robotframework-allurevisitor
```

This installs the `rf-allure` console script (with `allurevisitor` as an alias).
Rendering the report additionally requires an Allure report generator — either
**Allure 3** (`npm install -g allure`, needs Node) or **Allure 2**
(`npm install -g allure-commandline`, needs Node and Java). Both are tested.

## Requirements

- Python `>=3.13`
- [uv](https://docs.astral.sh/uv/) for working on the project from source

## From source

```bash
uv sync
```

## Usage

Command line (`rf-allure`, with `allurevisitor` as an alias):

```bash
uv run rf-allure path/to/output.xml -o allure-results --clean
```

Then render the report with either generator:

```bash
# Allure 3
npx allure generate allure-results -o allure-report
npx allure open allure-report

# Allure 2
npx allure-commandline generate --clean -o allure-report allure-results
npx allure-commandline open allure-report
```

Programmatic:

```python
from robotframework_allurevisitor import generate

generate("output.xml", "allure-results", clean=True)
```

### Live listener

```bash
robot --listener robotframework_allurevisitor.Listener tests/           # -> output/allure
robot --listener robotframework_allurevisitor.Listener:build/allure tests/
```

Options follow the directory as `name=value`: `clean=True` empties the directory
first; `broken_heuristic=True` reports library/syntax/import/timeout failures as
`broken`. With the listener active, Python libraries can use the `allure` API and
suites can use the keyword library:

```robotframework
*** Settings ***
Library    robotframework_allurevisitor.AllureLibrary

*** Test Cases ***
Example
    Attach         some text    name=note    attachment_type=TEXT
    Attach File    ${OUTPUT DIR}/data.json    attachment_type=JSON
```

Select tests from an Allure test plan with
`ALLURE_TESTPLAN_PATH=plan.json robot --prerunmodifier robotframework_allurevisitor.testplan …`.
Coming from `allure-robotframework`? See the
[migration guide](https://github.com/manykarim/robotframework-allurevisitor/blob/main/docs/migration-from-allure-robotframework.md).

### CLI options

| Option | Description |
|---|---|
| `sources` | One or more `output.xml` files or globs (positional). |
| `-o, --output` | Results directory (default `allure-results`). |
| `--clean` | Remove existing files in the results directory first. |
| `--thread` | Thread label, e.g. a pabot worker id (drives the Timeline view). |
| `--issue-pattern` | Pattern turning issue tags into Allure issue links. |
| `--link-pattern` | Pattern turning link tags into Allure links. |
| `--broken-heuristic` | Report library/syntax/import/timeout failures as `broken` instead of `failed`. |
| `--environment KEY=VALUE` | Environment entry shown in the report (repeatable); writes `environment.properties`. |
| `--executor JSON` | Executor info (inline JSON or a JSON file path); writes `executor.json`. |

The same options are keyword arguments of `generate()` (`broken_heuristic=True`,
`environment={...}`, `executor={...}`).

## What gets converted

The output matches the official `allure-robotframework` listener wherever the
difference would only be presentation, so reports look the same as with the
listener.

- **Suites → containers**, with Suite Setup/Teardown as the container's
  `befores`/`afters`. **Each test also gets its own container** carrying the
  test's `[Setup]`/`[Teardown]`, so both show up as *Set up* / *Tear down*.
- **Tests → results**, with `parentSuite`/`suite`/`subSuite` labels from the test
  full name (same rules as the listener), `framework`/`language`/`host` (and
  optional `thread`) labels, and a stable `historyId = md5(full_name)`.
- **Tags → labels and links** via `allure_commons.mapping.parse_tag`:
  `allure.label.<name>:…`, `allure.epic|feature|story|severity|id:…`,
  `allure.issue|tms|link:…`, bare severities (`critical`, …), plus the legacy
  `issue:[name]url`, `tms:[name]url`, and `link:[name]url` forms. Other tags
  become `tag` labels; a `skipped` tag forces status `skipped`.
- **Keywords and control structures (FOR/IF/WHILE/TRY/GROUP/VAR/…) → nested
  steps**, with keyword assignment in the step name and arguments as step
  parameters `arg1..N`.
- **Status**: `PASS→passed`, `SKIP`/`NOT RUN`/`NOT SET→skipped`, `FAIL→failed`.
  With `--broken-heuristic`, library/import/syntax/timeout errors → `broken`.
- **Timestamps** come from the result data (epoch ms), never wall-clock, so
  conversion is reproducible.
- **Log messages → one `Keyword Log` HTML attachment per step** (FAIL/ERROR in
  red; plain-text messages are HTML-escaped). Set `ALLURE_MAX_STEP_MESSAGE_COUNT=N`
  to show steps with at most N messages as message sub-steps instead.
- **Screenshots** embedded in log messages (`<img src=…>`, e.g. from SeleniumLibrary
  or Browser) → image attachments, resolved relative to the `output.xml` folder.
- **Playwright traces** from [robotframework-browser](https://robotframework-browser.org/)
  (`New Context    tracing=True`) → trace attachments
  (`application/vnd.allure.playwright-trace`) that open in the Playwright Trace
  Viewer from Allure 2 (2.35+) and Allure 3. Traces are found from Browser's
  `trace file will be saved to: …` log message and attached to the keyword or
  setup that opened the context — including contexts opened in Suite Setup. If
  the run's output folder was moved (e.g. a downloaded CI artifact), traces are
  looked up in `browser/traces/` next to `output.xml`.

### What cannot be converted

`output.xml` only contains what Robot Framework logged. These features happen at
runtime, so only the [live listener](#live-listener) records them; `rf-allure`
cannot recover them from `output.xml`:

- `AllureLibrary` keywords (`Attach`, `Attach File`, `Global Attach`, …) and
  `allure.attach(...)` / `allure.attach.file(...)` from Python libraries;
- `allure.dynamic.*` (labels, links, title, description) and `@allure.step` /
  `with allure.step(...)` from Python code;
- test-plan filtering (`ALLURE_TESTPLAN_PATH`), which changes what runs.

Anything a library *logs* (screenshots, links, HTML) is converted.

### Changes in 0.2.0

0.2.0 aligns the output with `allure-robotframework` and changes some results
compared with 0.1.0: test setup/teardown are fixtures instead of steps, log
messages are aggregated per step, step parameters are `arg1..N` instead of
`arg0..N`, deep suite hierarchies label like the listener, and failures are
`failed` unless `--broken-heuristic` is given. See [CHANGELOG.md](CHANGELOG.md).

## Reruns, merges, and pabot

Passing multiple sources combines them; because `historyId` is stable, repeated
runs of the same test are grouped by Allure as **retries** with the latest
attempt (by stop time) as the headline:

```bash
uv run rf-allure original.xml rerun.xml -o allure-results --clean
```

For a single, deduplicated last-wins result, pre-merge with Robot's own tooling
and convert the merged file:

```bash
rebot --merge original.xml rerun.xml --output merged.xml
uv run rf-allure merged.xml -o allure-results --clean
```

For **pabot**, either convert the single merged `output.xml`, or convert each
worker's file with a distinct `--thread` — but never both into the same results
directory (identical `historyId` would inflate counts).

## History and categories: Allure 2 vs Allure 3

Both generators read the same results; they differ in how trends and categories
are configured. The stable `historyId`/`testCaseId` this tool writes is what lets
either one link runs together.

- **Allure 2**: copy the previous report's `history/` directory into
  `allure-results` before `allure generate`. Categories come from a
  `categories.json` file in `allure-results`.
- **Allure 3**: history is a file configured in `allurerc.mjs` and appended on
  every `generate`; categories are also configured there (a `categories.json`
  in the results is ignored by the default report).

```js
// allurerc.mjs (Allure 3)
export default {
  name: "Robot Framework",
  historyPath: "./history.jsonl",
};
```

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

### End-to-end tests

The `e2e` tests run the whole pipeline — Robot Framework → the packaged
`rf-allure` CLI → real reports from **both Allure 2 and Allure 3** — and check
each report's own data (Allure 2: `widgets/summary.json`, `data/test-cases/`;
Allure 3: `summary.json`, `data/test-results/`): status counts, labels, links,
description, fixtures, steps, screenshots, `Keyword Log`, and environment.

```bash
uv run pytest -m e2e          # only the end-to-end tests
uv run pytest -m "not e2e"    # skip them (hermetic fast lane)
```

Generators are resolved per major version: an `allure` executable on `PATH` of
that version, else `npx allure` (Allure 3, needs Node) or
`npx allure-commandline` (Allure 2, needs Node and Java). Versions are pinned via
`ALLURE3_VERSION` / `ALLURE2_VERSION` (defaults 3.20.1 / 2.46.1). An unavailable
generator **skips** its tests; a generator that runs but fails **fails** them.
CI sets `ALLURE_REQUIRE_GENERATORS=1` so an unavailable generator fails as well.

The `browser` tests run real robotframework-browser suites with tracing and
check the traces in both reports. They need the optional dependency group:

```bash
uv sync --group browser
uv run --group browser rfbrowser init chromium
uv run --group browser pytest -m browser
```

See [AGENTS.md](AGENTS.md) for architecture and contribution notes.
