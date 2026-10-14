## Why

Teams that use Robot Framework with robotframework-browser usually also run tests in parallel with pabot and re-execute failed tests (`--rerunfailed`, then `rebot --merge`). Reproducing these workflows showed that the live listener already handles every combination. The `rf-allure` converter does not:

- **pabot**: when pabot runs without `--artifactsinsubfolders`, the merged `output.xml` references screenshots as `browser/screenshot/fail-screenshot-1.png`, relative to the final output directory. The files actually sit in `pabot_results/<n>/`, and each process uses the same names. All screenshots are dropped silently: they end up as text inside the `Keyword Log`. If the output directory moves, traces are lost too, because the relocation fallback only looks in `<dir>/browser/traces/<name>`. With `--artifactsinsubfolders`, pabot stores the files under prefixed names (`<timestamp>-<n>-trace_context=….zip`).
- **Re-execution**: Browser deletes `browser/{screenshot,traces,…}` in its output directory at the start of every run. So a rerun into the same `--outputdir` destroys the first run's artifacts, and a rerun has to use its own directory. But:
  - Passing `original.xml rerun.xml` as two sources nests both under a combined root named `Suites & Suites`. That changes every `fullName`, `historyId`, and suite label compared with a single-run conversion, which breaks Allure history across CI runs.
  - All sources resolve files against the first source's directory, so the rerun's screenshots can silently resolve to the first run's file of the same name.
- **rebot-merged output**: `rebot --merge` does not rewrite relative paths, so one side's screenshots point to the wrong directory. The merged test message is raw Robot HTML (`*HTML* <span class="merge">…`), which Allure shows verbatim.

## What Changes

- **Multi-source conversion fixed (BREAKING for identity)**:
  - Each source is converted as its own result tree. Without the synthetic `A & B` root, `fullName`, `historyId`, and suite labels match a single-run conversion. Repeated tests still share a `historyId` and show as Allure retries.
  - Each source resolves screenshots and traces against its own `output.xml` directory.
  - Results from earlier multi-source conversions get a different `historyId`, so their history does not line up with new results.
- **New `rf-allure --merge` / `generate(..., merge=True)`**:
  - Merges the sources with Robot's own merger (the same last-wins semantics and merge message as `rebot --merge`) and emits one result per test.
  - Unlike a `rebot`-merged file, it resolves every test's attachments against the directory of the source that test came from.
- **rebot-merged `output.xml` accepted**: a merged test's Robot HTML message becomes readable plain text, keeping the "re-executed and merged", new status, and old status/message parts.
- **pabot artifact resolution**:
  - Traces are found in pabot layouts (`pabot_results/<n>/browser/traces/` and pabot's prefixed `--artifacts` copies), including after the output directory has moved.
  - A referenced screenshot that cannot be resolved produces a warning that names the file and suggests `--artifactsinsubfolders`, instead of being dropped silently.
- **Documented, tested workflows** for both front ends, each with Browser screenshots and traces on Allure 2 and Allure 3:
  - pabot
  - rerun + merge
  - pabot + rerun + merge

  Also a README "Parallel runs and re-execution" section.
- CI: robotframework-pabot joins the `browser` dependency group, so the `browser` job runs the pabot and rerun workflows.

## Capabilities

### New Capabilities
- `execution-workflows`: supported, tested end-to-end workflows for pabot, re-execution with retries or merge, and pabot + re-execution, each with Browser artifacts, for both the converter and the listener.

### Modified Capabilities
- `allure-conversion-cli`: multi-source conversion gives per-source identity and per-source attachment resolution; new `--merge` option.
- `allure-result-generation`: merged-test messages become plain text; an unresolvable screenshot reference warns instead of being dropped silently.
- `playwright-trace-attachments`: relocation fallback covers pabot result layouts and prefixed artifact copies.
- `e2e-report-verification`: the `browser` e2e suite covers pabot, rerun, and pabot + rerun on both generators; pabot is part of the `browser` group.

## Impact

- Code: `visitor.py` (`generate()`: a visit per source, `merge` mode, per-test source directory), `_mapping.py` (per-test source directory, trace search paths, unresolved-image warning, merge-message conversion), `cli.py` (`--merge`).
- Listener: no behaviour change; it is covered by the new workflow tests.
- Dependencies: `robotframework-pabot` added to the `browser` dependency group (dev-only).
- Docs: README workflows section, CHANGELOG, AGENTS.md (the "Multiple sources combine" rule changes).
- Compatibility: `historyId` changes only for multi-source conversions, which previously carried the synthetic root prefix. Single-source conversions are unchanged.
