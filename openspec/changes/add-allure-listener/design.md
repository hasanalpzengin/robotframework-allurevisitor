## Context

Builds on `allure3-compat-and-capability-parity`, which introduces a mapping core (`_mapping.py`: test/fixture/step builders, buffered message flush, `AttachmentSink`) driven by the post-processing visitor. Spike results on RF 7.4.2 (explore session):

1. With listener API v3, `end_test(data, result)` receives the test's complete result subtree; keyword, control-structure, message, and embedded-image counts matched the same test loaded from `output.xml`.
2. At `end_suite(data, result)` the suite's tests have **empty bodies** but carry the **final** status/message (e.g. `FAIL`, `Parent suite teardown failed:\nteardown boom` where `end_test` had reported `PASS`). The suite's `setup`/`teardown` still have their bodies.
3. `allure_commons` hooks fire synchronously inside library keywords; recording `result.id` from `start_keyword(data, result)` on a stack identified the running keyword (`s1-t1-k2-k1`), and that id matches the result tree.
4. Without a registered plugin, `allure.attach` etc. are no-ops — which is why the converter can't recover them.

Upstream reference: `allure-python/allure-robotframework` master (`robot_listener.py`, `allure_listener.py`, `library/allure_library.py`, `allure_testplan.py`).

## Goals / Non-Goals

**Goals:**
- One mapping for live and offline modes; listener-specific code limited to event capture, buffering, and reconciliation.
- Drop-in *capability* replacement for upstream under our own names.

**Non-Goals:**
- Module-name compatibility (`allure_robotframework`, `AllureLibrary` top-level names) — decided against in explore session; covered by the migration guide.
- Listener API v2 support or RF < 7.
- A sidecar file that lets `rf-allure` recover runtime attachments later (possible future change).
- Live streaming of each test before its suite ends (blocked by status reconciliation).

## Decisions

### D1. Convert at `end_test`, write at `end_suite`
```
start_suite  -> push SuiteFrame(container uuid, pending=[])
start_test   -> push TestFrame(test uuid, overlay buckets)
start_kw     -> push result.id on kw-id stack
end_kw       -> pop kw-id stack
end_test     -> TestResult + test container = mapping.build_test(result, overlay)
                append to SuiteFrame.pending   (not written yet)
end_suite    -> for each pending: copy final status/message from result.tests[id]
                suite fixtures = mapping.build_fixtures(result.setup/teardown, overlay)
                sink.flush(); write results, test containers, suite container
                link container into parent SuiteFrame
close        -> flush remaining sink, unregister hook plugin
```
Using result-model times keeps listener output equal to converter output (spec "Output equivalence"). *Alternative*: port upstream's lifecycle-per-event model — rejected: duplicates mapping and diverges in times and control structures.

### D2. Overlay keyed by keyword id
A `RuntimeHooks` plugin (registered with `allure_commons.plugin_manager`) records events into an `Overlay` keyed by the current keyword id (top of the stack), or by the owning test/suite fixture id when no keyword is running. `allure.step` hooks open nested `RuntimeStep` nodes inside the current key so attachments inside them nest correctly. The mapping core gets one extension point: after building the step for a keyword with id X, call `overlay.apply(X, step)`; after building a test, `overlay.apply_test(test_result)` for labels, links, title, description, and parameters. Keyword ids are unique within a run and match the result tree (spike 3). *Alternative*: match by keyword name and position — rejected as ambiguous for repeated keywords.

### D3. Status reconciliation by test id
`end_suite` looks up each pending test by `result.tests` id and overwrites `status`/`statusDetails.message` when they differ, using the same `status_of` (incl. `skipped` tag, `broken_heuristic`). This reproduces what `ExecutionResult` gives the converter.

### D4. Deferring sink
The listener's `AttachmentSink` records `(owner attachment, source path, target name)` and copies on `end_suite` of the owning container (or `close`). Files missing at flush time are skipped with a Robot warning. This gives Close-Context traces and late screenshots a chance to exist.

### D5. Thread label and pabot
Read `${PABOTEXECUTIONPOOLID}` and `${CALLER_ID}` via `BuiltIn().get_variable_value` at `start_suite` (upstream's formula), else `default-<uuid4>` per process. Uniqueness of files across processes comes from uuid file names, as in the converter.

### D6. Library and test plan
`AllureLibrary` is a thin module calling `allure.attach`/`attach.file`/`global_attach`/`global_error` (upstream's code shape, including `_attachment_type` name→enum fallback to literal). `testplan` is a `SuiteVisitor` using `allure_commons.utils.get_testplan` and our `tag_labels_and_links` to read `allure.id`. Globals are written via the `report_globals` developer hook of `AllureFileLogger`.

### D7. Coexistence detection
At listener init, inspect `allure_commons.plugin_manager.get_plugins()` for an instance whose class module starts with `allure_robotframework`; also check again at first `start_suite` (registration order is unspecified). Emit a single `logger.warn`.

### D8. Equivalence test as the guard rail
A test runs a capability suite once with the listener and converts the produced `output.xml` with `generate()`, normalises both result sets (uuid → stable path keys, attachment sources → content hashes, drop `thread`), and asserts equality. This test protects the "one mapping" promise when either side changes.

## Risks / Trade-offs

- [Memory: a suite's converted tests are held until suite end] → same as upstream; converted results are much smaller than the RF tree, which RF already releases.
- [RF internals: bodies dropped before `end_suite`, ids format] → covered by listener tests on the pinned RF version; CI matrix can add the minimum supported RF.
- [Hook calls from threads/background tasks have no keyword context] → attach to the current test (or suite fixture) and document.
- [Wall-clock times for `allure.step` vs result times elsewhere] → unavoidable (RF does not record them); steps are still ordered correctly inside their keyword.
- [Default directory `output/allure` differs from the CLI default `allure-results`] → chosen for migration ease; documented in the guide.

## Migration Plan

Ship as a minor release after 0.2.0. Users replace `--listener allure_robotframework[:dir]` with `--listener robotframework_allurevisitor.Listener[:dir]`, `Library AllureLibrary` with `Library robotframework_allurevisitor.AllureLibrary`, and `--prerunmodifier allure_robotframework.testplan` with `--prerunmodifier robotframework_allurevisitor.testplan`, then uninstall `allure-robotframework`.
