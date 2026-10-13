# Migrating from `allure-robotframework`

`robotframework-allurevisitor` ships a live listener that replaces the
`allure-robotframework` listener, plus its `AllureLibrary` keywords and test-plan
pre-run modifier. Python code that uses `import allure` (`allure.attach`,
`allure.dynamic.*`, `allure.step`) keeps working unchanged.

The listener uses the same Robot → Allure mapping as the `rf-allure` converter,
so a live run and a later conversion of its `output.xml` produce the same results
(except for runtime-only data, which only the listener sees).

## 1. Swap the packages

```bash
pip uninstall allure-robotframework
pip install robotframework-allurevisitor
```

Do not run both listeners in one run. Both receive every `allure.attach` /
`allure.step` call, so runtime data would be recorded twice. If both are active,
this listener logs a warning.

## 2. Change the entry points

| What | `allure-robotframework` | `robotframework-allurevisitor` |
|---|---|---|
| Listener | `--listener allure_robotframework` | `--listener robotframework_allurevisitor.Listener` |
| Listener with results dir | `--listener allure_robotframework:build/allure` | `--listener robotframework_allurevisitor.Listener:build/allure` |
| Keyword library | `Library    AllureLibrary` | `Library    robotframework_allurevisitor.AllureLibrary` |
| Test-plan selection | `--prerunmodifier allure_robotframework.testplan` | `--prerunmodifier robotframework_allurevisitor.testplan` |
| Python libraries | `import allure` | unchanged |
| `ALLURE_MAX_STEP_MESSAGE_COUNT` | log messages as sub-steps up to N | unchanged |
| `ALLURE_TESTPLAN_PATH` | path of the test-plan JSON | unchanged |
| Default results directory | `output/allure` | `output/allure` (unchanged) |
| pabot | same `--listener` option | same `--listener` option; same `thread` label |

The `AllureLibrary` keywords keep their names and arguments: `Attach`,
`Attach File`, `Global Attach`, `Global Attach File`, `Global Error`.
`attachment_type` takes an Allure type name (`PNG`, `TEXT`, `JSON`, …) or a
literal MIME type.

Example:

```bash
robot --listener robotframework_allurevisitor.Listener tests/
npx allure generate output/allure -o allure-report        # Allure 3
npx allure-commandline generate --clean -o allure-report output/allure   # Allure 2
```

### Listener options

Options follow the results directory as `name=value`:

```bash
robot --listener "robotframework_allurevisitor.Listener:output/allure:clean=True:broken_heuristic=True" tests/
```

| Option | Effect |
|---|---|
| `clean=True` | Empty the results directory first. Do not use with pabot (workers share the directory). |
| `broken_heuristic=True` | Report library/syntax/import/timeout failures as `broken` instead of `failed`. |

## 3. Differences you may notice

The output follows `allure-robotframework` (labels, tags, links, fixtures,
`Keyword Log` attachments, `arg1..N` parameters, `failed` for every Robot
failure, the `skipped` tag). These differences remain:

- **Timestamps come from Robot's result data**, not the wall clock at listener
  callbacks, so they match `log.html` and a later conversion exactly.
  `allure.step` steps still use wall-clock time (Robot does not record them).
- **Control structures** (`FOR`, `IF`, `WHILE`, `TRY`, `GROUP`, `VAR`, …) appear
  as nested steps.
- **Plain-text log messages are HTML-escaped** in the `Keyword Log` attachment,
  so `<` and `&` show up as written. Messages logged with `html=True` are kept
  as HTML.
- **`broken` is opt-in** (`broken_heuristic=True`); upstream never reports `broken`
  for Robot failures either, so the default matches.
- **Screenshots** logged as `<img src=…>` become image attachments instead of
  staying inside the log HTML.
- **Playwright traces** from robotframework-browser (`New Context    tracing=True`)
  are attached and open in the Trace Viewer, including contexts opened in Suite
  Setup.
- **`allure.dynamic.title`, `description`, `description_html`, and `parameter`**
  take effect; upstream's Robot listener ignores them.
- **A failing parent suite setup/teardown** marks tests of child suites as failed,
  as `log.html` does (upstream only updates tests of the suite itself).

## 4. Results without the listener

To build a report from an existing `output.xml` (from CI, a rerun, or a merged
pabot run), use the converter instead. It produces the same results, minus the
runtime-only data listed in the README:

```bash
rf-allure output.xml -o allure-results --clean
```
