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
- Robot Framework `>=7.4.2`
- [uv](https://docs.astral.sh/uv/) for working on the project from source

## From source

```bash
uv sync
```

## Usage

Command line (`rf-allure`, with `allurevisitor` as an alias):

```bash
rf-allure path/to/output.xml -o allure-results --clean
```

(From a source checkout, prefix it with `uv run`.)

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
| `--merge` | Merge the sources like `rebot --merge` (last wins) into one result per test; without it, repeated tests become retries. See [re-execution](#re-executing-failed-tests). |
| `--thread` | Thread label, e.g. a pabot worker id (drives the Timeline view). |
| `--issue-pattern` | Pattern turning issue tags into Allure issue links. |
| `--link-pattern` | Pattern turning link tags into Allure links. |
| `--broken-heuristic` | Report library/syntax/import/timeout failures as `broken` instead of `failed`. |
| `--environment KEY=VALUE` | Environment entry shown in the report (repeatable); writes `environment.properties`. |
| `--executor JSON` | Executor info (inline JSON or a JSON file path); writes `executor.json`. |

The same options are keyword arguments of `generate()` (`merge=True`,
`broken_heuristic=True`, `environment={...}`, `executor={...}`).

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
  The status message is kept as plain text (Robot `*HTML*` messages, such as
  `rebot --merge` notes, are converted), also for passed tests (`Pass Execution`).
- **Timestamps** come from the result data (epoch ms), never wall-clock, so
  conversion is reproducible.
- **Log messages → one `Keyword Log` HTML attachment per step** (FAIL/ERROR in
  red; plain-text messages are HTML-escaped). Set `ALLURE_MAX_STEP_MESSAGE_COUNT=N`
  to show steps with at most N messages as message sub-steps instead.
- **Screenshots** embedded in log messages (`<img src=…>`, e.g. from SeleniumLibrary
  or Browser) → image attachments, resolved relative to the `output.xml` folder.
  A screenshot file that cannot be found is reported as a warning and stays in the
  `Keyword Log`.
- **Playwright traces** from [robotframework-browser](https://robotframework-browser.org/)
  (`New Context    tracing=True`) → trace attachments
  (`application/vnd.allure.playwright-trace`) that open in the Playwright Trace
  Viewer from Allure 2 (2.35+) and Allure 3. Traces are found from Browser's
  `trace file will be saved to: …` log message and attached to the keyword or
  setup that opened the context — including contexts opened in Suite Setup. If
  the run's output folder was moved (e.g. a downloaded CI artifact), traces are
  looked up next to `output.xml` in `browser/traces/`, in pabot's prefixed
  `--artifacts` copies there, and in `pabot_results/*/browser/traces/`.

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

### Upgrading

**0.4.0**: several sources (`rf-allure original.xml rerun.xml`) are converted one
by one instead of under a combined `Suites & Suites` root. Names, suite labels, and
`historyId` now equal a single-run conversion, so results from earlier multi-source
conversions do not line up in history with new ones. Single-source conversions are
unchanged. See [Parallel runs and re-execution](#parallel-runs-and-re-execution).

**0.2.0** aligns the output with `allure-robotframework` and changes some results
compared with 0.1.0: test setup/teardown are fixtures instead of steps, log
messages are aggregated per step, step parameters are `arg1..N` instead of
`arg0..N`, deep suite hierarchies label like the listener, and failures are
`failed` unless `--broken-heuristic` is given. See [CHANGELOG.md](CHANGELOG.md).

## Parallel runs and re-execution

These workflows are tested end to end with robotframework-browser screenshots and
Playwright traces, on Allure 2 and Allure 3, for both the converter and the listener.

Constraints these workflows depend on:

- **Rerun into its own `--outputdir`.** Browser deletes `browser/` (screenshots,
  traces) in its output directory at the start of every run, so a rerun into the
  same directory destroys the first run's artifacts.
- **Run pabot with `--artifactsinsubfolders`** when you convert its output. Without
  it, pabot's merged `output.xml` points at screenshots that stay in
  `pabot_results/<n>/`, and Robot's `log.html` breaks the same way. The converter
  warns about every screenshot it cannot find. Traces are found either way.
- **Merge with `rf-allure --merge`, not `rebot --merge`.** A rebot-merged file
  cannot say which run's directory a relative screenshot path belongs to. Both runs
  use the same file names, so the converter warns for every re-executed test.

### pabot

```bash
# Listener: every process writes to one results directory, with a thread label per process.
pabot --listener robotframework_allurevisitor.Listener:allure-results tests/

# Converter
pabot --artifacts png,zip --artifactsinsubfolders --outputdir out tests/
rf-allure out/output.xml -o allure-results --clean
```

### Re-executing failed tests

```bash
robot --outputdir out tests/
robot --rerunfailed out/output.xml --outputdir out/rerun tests/
```

The tests that failed in `out/` and passed in `out/rerun/` can be reported in two ways:

```bash
# Retries (recommended): every attempt is kept. Allure shows the latest attempt and
# lists the earlier ones as retries. historyId matches a single run, so history works.
rf-allure out/output.xml out/rerun/output.xml -o allure-results --clean

# Merged: one result per test, last wins, like `rebot --merge`, but each test keeps
# the screenshots and traces of the run it came from.
rf-allure --merge out/output.xml out/rerun/output.xml -o allure-results --clean
```

With the listener, pass the same results directory to both runs (and no
`clean=True`). The attempts appear as retries:

```bash
robot --listener robotframework_allurevisitor.Listener:allure-results --outputdir out tests/
robot --listener robotframework_allurevisitor.Listener:allure-results \
      --rerunfailed out/output.xml --outputdir out/rerun tests/
```

A file merged by `rebot --merge` converts too: the merge note becomes plain text.
It is still better to give `rf-allure` the original outputs, because of the
screenshot paths described above.

### pabot and re-execution together

```bash
pabot --artifacts png,zip --artifactsinsubfolders --outputdir out tests/
pabot --artifacts png,zip --artifactsinsubfolders \
      --rerunfailed out/output.xml --outputdir out/rerun tests/
rf-allure out/output.xml out/rerun/output.xml -o allure-results --clean           # retries
rf-allure --merge out/output.xml out/rerun/output.xml -o allure-results --clean   # merged
```

The listener works the same way: give both pabot runs the same
`--listener robotframework_allurevisitor.Listener:allure-results`.

Each source is converted on its own, so a test's name, suite labels, and
`historyId` are the same whether a file is converted alone or with others.
Converting each pabot worker's own `pabot_results/<n>/output.xml` with a distinct
`--thread` also works. Never convert both the worker files and the merged file into
one results directory: the same tests would be counted twice.

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
screenshots, under pabot, with re-execution, and with both, and check each
attempt's screenshots and traces in both reports, for both the converter and the
listener. They need the optional dependency group (Browser and pabot):

```bash
uv sync --group browser
uv run --group browser rfbrowser init chromium
uv run --group browser pytest -m browser
```

See [AGENTS.md](AGENTS.md) for architecture and contribution notes.
