## Context

The following was reproduced on 2026-10-13 with Robot Framework 7.4.2, robotframework-browser 20.6.0 and robotframework-pabot 5.2.2, using two Browser suites. Each suite had one flaky test (with `Take Screenshot` and an automatic failure screenshot) and one stable test, and every test used a tracing context.

| Workflow | Listener | Converter today |
|---|---|---|
| pabot, no `--artifactsinsubfolders` | all screenshots and traces (process output dir = `pabot_results/<n>`) | 4/4 screenshots silently dropped: relative `src` is resolved against the final dir; traces OK via absolute path |
| pabot `--artifacts png,zip --artifactsinsubfolders` | — | OK: pabot copies to `browser/…/<ts>-<n>-<name>` and rewrites `src` |
| rerun, same `--outputdir` | OK (copies at suite end) | first run's artifacts gone: Browser `_start_suite` removes `browser/{screenshot,video,traces,state,coverage}` once per run |
| rerun, separate `--outputdir`, two sources | — | names become `Suites & Suites.Suites.A.Flaky A`, so `historyId` and suite labels differ from a single run; every source resolves against the first source's dir |
| `rebot --merge` | n/a | message is raw `*HTML* <span class="merge">…`; relative `src` of one side resolves against the wrong directory, and can pick a different file with the same name |
| pabot + `pabot --rerunfailed`, listener, same results dir | 6/6 screenshots, 6/6 traces, retries grouped by `historyId`, thread labels | — |

Robot's `Merger` (used by `ExecutionResult(..., merge=True)`) keeps object identity. It assigns `tests[index] = new_test` and appends new suites whole, so a test object from a merged-in source survives in the merged tree.

## Goals / Non-Goals

**Goals**

- The converter gives correct identity and the correct per-run attachments for:
  - pabot,
  - multi-source reruns,
  - its own merge,
  - pabot + rerun.
- A `rebot --merge` file converts to a readable result. Any attachment the converter cannot place produces a warning and is never silently replaced by another run's file.
- Every workflow is verified end to end with Browser, on both generators, for both front ends.

**Non-Goals**

- Recovering screenshots from pabot output produced without `--artifactsinsubfolders`. File names collide across processes, and the merged XML does not say which process ran a test. Robot's own `log.html` is broken the same way. We warn and document instead.
- Rewriting paths inside `rebot --merge` output.
- A converter-side `thread` label for pabot (the merged XML does not record the pool id). The listener already provides one.
- Deduplicating retries in the listener. Allure's retry model is the intended presentation.

## Decisions

### D1. One visit per source instead of `ExecutionResult(*sources)`

`generate()` loops over the sources. For each one it:

1. parses it with `ExecutionResult(source)`;
2. sets `mapper.options.source_dir` to that source's directory;
3. visits the tree with the same visitor.

Without the synthetic combined root, names and labels equal those of a single-source run. Peak memory stays per source.

Alternatives:

- Strip the combined root's prefix from names. This is fragile: suites may have the same name, and the root may be a real one.
- Keep the root. This is what breaks history.

The partial-output tolerance applies per source: a broken source warns and the remaining sources are still converted. This is a BREAKING identity change for multi-source users, and the CHANGELOG will say so.

### D2. `--merge` uses Robot's merger plus a per-item source map

`generate(..., merge=True)`:

1. Parses every source with `ExecutionResult(source)`.
2. Records `{id(item): source_dir}` for every test and every suite setup/teardown of each source, and keeps the trees alive (holding the result objects is enough).
3. Merges into the first result with `robot.result.merger.Merger(first, rpa=first.rpa).merge(other)`, in order.
4. Visits the merged tree.

The visitor gets an optional `source_dir_for(item)` hook. The mapper's `source_dir` is switched when a test or a suite fixture starts, and restored when it ends.

Robot's `Merger` keeps object identity: `tests[index] = new_test` replaces a test, new suites are appended whole, and `old.setup = suite.setup` reuses the fixture object (`create_fixture` only reconfigures it). So a re-executed suite's setup and teardown come from the later source, and they resolve against that source's directory.

Reusing Robot's merger gives exact `rebot --merge` semantics: last wins, new tests and suites are added, and the merge messages match. Writing our own last-wins logic would drift from Robot's.

Memory: merging needs all source trees at once, the same as `rebot --merge`, and this is documented.

### D3. Per-test source directory in the mapper

Today `MappingOptions.source_dir` is read in `_resolve` (images) and `_relocated_trace`. D1 and D2 only change *what* `source_dir` holds while a test is being visited. Mapping code is unchanged and the listener is unaffected: its `source_dir` is `${OUTPUT DIR}` and it has no hook. This keeps `test_equivalence.py` green.

### D4. Robot HTML messages become plain text

In `Mapper.status`:

- If a message starts with `*HTML*`, remove the prefix.
- Turn `<br>` and `<hr>` into newlines.
- Remove the remaining tags with a small regex.
- Decode entities with `html.unescape`.
- Collapse blank-line runs.

A passed item's message is kept as well. Robot sets one only for `Pass Execution` and merge notes, and without it a merged passing test would lose its merge note.

The result reads, for example:

```
Test has been re-executed and results merged.
New status: PASS
Old status: FAIL
Old message: Text 'a' (str) should be 'x' (str)
```

This applies to every `*HTML*` failure message, not only merge messages. A user's own `Fail    *HTML* <b>x</b>` therefore also becomes plain text. That is acceptable, because Allure renders `statusDetails.message` as plain text and would otherwise show the tags. The listener sees the same messages, so equivalence holds.

### D5. Trace search order

`_relocated_trace(name)` checks these locations under `source_dir`, in order:

1. `browser/traces/<name>`
2. `browser/traces/*-<name>` (pabot prefix; the trace name holds a uuid, so it is unique)
3. `pabot_results/*/browser/traces/<name>`

The first existing file wins.

### D6. Unresolved images warn

In `_attach_images`, an `<img src>` that does not resolve to a file triggers a warning, sent to stderr through the mapper's `warn` callable (the same one the deferred sink uses). The warning names the file. For a relative path it adds: "if this came from pabot, run pabot with --artifactsinsubfolders".

The message continues to the `Keyword Log`, as it does today. Remote `http(s):` and `data:` sources are ignored silently, because they are not files.

A missing file is never resolved by guessing among same-named files in other directories, because that is exactly how the wrong image gets attached.

A `rebot --merge` file creates the opposite problem. A re-executed test's relative path can resolve to the *other* run's file of the same name (Browser restarts numbering in every run), and the converter cannot tell. Tests that rebot re-executed or added carry its merge note. For those tests only, and only when no per-item source map exists (a rebot-merged file rather than our own `--merge`), the mapper warns once per test when it resolves a relative screenshot, and recommends `rf-allure --merge`.

### D7. Workflow tests share fixtures

A new `tests/test_e2e_workflows.py` (`browser` marker) builds the two-suite flaky fixture. A flag file flips the flaky test from failing to passing on the rerun, and each test's page text includes its name and the run, so every screenshot has unique content. Tests assert attachments by content hash, not by name.

Module-scoped fixtures run each workflow once:

- `pabot`
- `rerun` (separate output dir)
- `pabot_rerun`
- the listener variants of each

Converter assertions cover:

- retries, merge, `rebot --merge`;
- reports on Allure 2 and Allure 3 (status `passed`, retries count where the reader exposes it, attachments present).

The `Report` reader gains `retries(name)`, which reads `extra.retries` in Allure 2 and `retries`/history in Allure 3. Its exact field is confirmed while implementing (task 6.1), and the assertion is skipped for a generator that does not expose it.

pabot is invoked as `sys.executable -m pabot.pabot`; the tests skip when pabot is not importable.

### D8. Dependencies and CI

`uv add --group browser robotframework-pabot`. The CI `browser` job already syncs that group, so it picks up the workflow tests without further changes. The default `test` job stays without pabot. The existing listener pabot test keeps skipping there, as it does today.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Multi-source `historyId` change breaks history for existing multi-source users | One-time break. It makes multi-source identity match single runs, which is what history needs. Called out as BREAKING in the CHANGELOG. |
| `Merger` internals change between RF versions | Use only its public use, `Merger(result, rpa=...).merge(other)`, as `ExecutionResult(merge=True)` does. A unit test checks that a re-executed test resolves its file from the rerun directory. |
| pabot or Browser output changes (prefix format, cleanup) | Workflow tests in the CI `browser` job catch it. The suffix match (`*-<name>`) does not depend on the prefix format. |
| Browser workflows make the `browser` job slower | Module-scoped fixtures run each workflow once, with 2 suites × 2 tests. |
| `*HTML*` stripping loses formatting the user intended | Allure would show the raw tags instead. Plain text is the better default. |

## Migration Plan

- Release as 0.4.0.
- CHANGELOG: list the BREAKING identity note for multi-source, and the `--merge` flag.
- README: "Parallel runs and re-execution" section.
- AGENTS.md: replace the "Multiple sources combine, they do NOT last-wins merge" rule with the per-source visit rule and `--merge`.

## Open Questions

- ~~Which field exposes retries in Allure 3?~~ Resolved: Allure 3 marks earlier attempts `isRetry: true` and lists them in the headline's `retries`. Allure 2 marks them `retry: true` and lists them in `extra.retries`.
