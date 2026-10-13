## Context

`AllureResultVisitor` (`visitor.py`) is a single stack-based `ResultVisitor` that writes results and containers through `AllureFileLogger`. Observations from the explore session (RF 7.4.2, Allure 2.46.1, Allure 3.20.1):

- Both generators already read our results correctly: labels, links, container fixtures (Allure 3 maps them to `setup`/`teardown` on each child test), nested steps, image attachments, and the `application/vnd.allure.playwright-trace` type (Allure 2 since 2.35, Allure 3 `web-awesome`).
- Allure 3 `generate` has no `--clean` and its default (awesome) report writes `summary.json` + `data/test-results/` instead of Allure 2's `widgets/summary.json` + `data/test-cases/`. `summary.json` omits zero counts.
- Upstream `allure-robotframework` (master, `listener/allure_listener.py`, `utils.py`) defines the parity target: per-test containers with test setup/teardown as fixtures, a `Keyword Log` HTML attachment per item (or sub-steps via `ALLURE_MAX_STEP_MESSAGE_COUNT`), `arg1..N`, FAIL→failed, `skipped` tag, `get_allure_suites`, legacy `issue:`/`tms:`/`link:` tags.
- robotframework-browser logs `Successfully created context and trace file will be saved to: <abs path>.zip` (INFO) inside `New Context`; the zip only exists after `Close Context`.
- The follow-up change `add-allure-listener` will drive the same mapping from a live listener, so the mapping must not assume it owns the whole traversal.

## Goals / Non-Goals

**Goals:**
- One mapping implementation whose units (test, fixture, keyword/control step, message flush, attachments) can be driven by both the post-processing visitor and a future listener.
- Byte-for-byte parity in *shape* with the upstream listener for the items listed in the proposal.
- Generator-agnostic e2e harness that fails loudly when a resolved generator breaks.

**Non-Goals:**
- The listener itself, runtime hooks (`allure.attach`, `allure.dynamic`), AllureLibrary, test plan — all in `add-allure-listener`.
- Configuring Allure 3 history/categories for users (documented only).
- Supporting Allure 3's experimental `allure2`/`classic` plugins in tests.

## Decisions

### D1. Split mapping from traversal
Extract the per-node construction (test result + labels, per-test container, fixture, step, message flush, attachment helpers) into a `_mapping.py` builder that operates on RF result objects and an explicit "current owner" passed in. `AllureResultVisitor` keeps the traversal stack and calls the builder. *Alternative*: keep everything in the visitor and subclass it in the listener — rejected because the listener receives `end_test` with a complete subtree but `end_suite` without bodies (see `add-allure-listener` design), so it needs to call "convert this test subtree" directly rather than replay a full traversal.

### D2. Per-test containers
At `start_test` the visitor creates a test container (`children=[test uuid]`) in addition to adding the test uuid to the enclosing suite container. `start_keyword` with `type in (SETUP, TEARDOWN)` now routes to the *innermost* container — the test container while a test is active, the suite container otherwise. The test container is reported at `end_test` after the result. This keeps the existing "suite fixture detection" rule intact and generalises it. *Alternative*: put test fixtures on the suite container — rejected: Allure would then apply them to every test of the suite.

### D3. Buffered message flush
Each stack frame (test, fixture, step) gets a message buffer. `visit_message` resolves image references immediately (screenshots and traces become attachments on the frame) and buffers everything else. On frame end, the buffer is flushed either as one `Keyword Log` HTML attachment or, if `0 < count <= ALLURE_MAX_STEP_MESSAGE_COUNT`, as zero-duration sub-steps — mirroring upstream's `_report_messages`. Non-HTML messages are HTML-escaped before embedding (upstream does not escape; we treat that as a bug, not a parity target, since raw `<`/`&` in log text otherwise corrupts the attachment). Newlines become `<br>`.

### D4. Status policy
`status_of(item, *, broken_heuristic=False)`; the `_ERROR_HINTS` heuristic only runs when enabled. NOT SET joins SKIP/NOT RUN. The `skipped`-tag override is applied in the test builder, not in `status_of`, because it is test-level.

### D5. Suite labels and legacy link tags
Port `get_allure_suites` semantics into `_labels.suite_labels`, and add the `issue:`/`tms:`/`link:` legacy parser to `tag_labels_and_links`, de-duplicating labels with `allure_commons.mapping.labels_set`. `--issue-pattern`/`--link-pattern` continue to apply to `allure.*` link tags via `parse_tag`.

### D6. Playwright traces from the log
A regex `trace file will be saved to:\s*(?P<path>\S+\.zip)` on buffered/visited messages yields a trace path; resolution order: logged absolute path → `<source_dir>/browser/traces/<basename>` → skip. The attachment is placed on the frame that logged it (the `New Context` step, or the setup fixture for suite/test setup). File copying goes through a small `AttachmentSink` with `attach_file(owner, path, name, mime)`; the visitor's sink copies immediately. The listener in `add-allure-listener` will supply a deferring sink because the zip is only written at `Close Context`. *Alternative considered*: PR #1's wallTime matching against test windows — rejected (drops Suite Setup contexts, timezone-sensitive, O(tests × traces) zip opens). PR #1's MIME constant and `.zip` naming are kept; @hasanalpzengin is credited via `Co-authored-by:` on the implementing commit and in CHANGELOG, and PR #1 is closed with a pointer to this change.

### D7. Environment and executor
Written directly as `environment.properties` (`key=value`, properties-escaped) and `executor.json` into the results directory by `generate()`; `AllureFileLogger` has no API for them. `--clean` removal happens before they are written.

### D8. Generator abstraction in tests
`tests/allure_cli.py` describes each generator by major version: how to resolve it (PATH + `--version` probe, else npx with pinned `ALLURE2_VERSION`/`ALLURE3_VERSION` defaulting to 2.46.1 / 3.20.1), how to invoke `generate` (`generate --clean -o OUT RESULTS` vs `generate RESULTS -o OUT`), and readers that normalise report data into a common shape: `stats()`, `test_cases()` → list of `{name, labels, links, description, setup, teardown, steps, attachments}`. Tests are parametrised over `["allure2", "allure3"]`. Resolution failures skip; run failures `pytest.fail`. *Alternative*: use Allure 3's `allure2` plugin to get one layout — rejected; it is experimental and would not test what users run.

### D9. CI
`ci.yml` adds `actions/setup-node` and `actions/setup-java` and caches the npm cache dir so both npx generators run; a separate optional job installs robotframework-browser (`rfbrowser init chromium`) and runs `-m browser`.

## Risks / Trade-offs

- [Breaking output for 0.1.0 users] → bump to 0.2.0, CHANGELOG "Breaking" section, README migration note; `--broken-heuristic` restores the old status behaviour.
- [Allure 3 report data is an internal format and may change] → pin generator versions in tests; readers isolate format knowledge in one place.
- [Browser log message text could change upstream] → regex tolerant of the prefix; browser e2e test catches it; fallback is "no trace", never a crash.
- [Per-test containers double the file count] → matches upstream; acceptable.
- [Escaping diverges from upstream] → documented; only affects messages not logged with `html=True`.

## Migration Plan

Release as 0.2.0. Users needing the old `broken` behaviour pass `--broken-heuristic`. No rollback steps beyond pinning `robotframework-allurevisitor<0.2`.
