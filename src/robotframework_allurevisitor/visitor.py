"""Stack-based Robot Framework ``ResultVisitor`` that emits Allure files.

The visitor walks ``robot.api.ExecutionResult`` depth-first and reports each
container at ``end_suite`` and each test result at ``end_test``, so peak memory
is bounded by the current suite/keyword depth rather than the whole run.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import (
    TestAfterResult,
    TestBeforeResult,
    TestResult,
    TestResultContainer,
)
from robot.api import ExecutionResult, ResultVisitor
from robot.result.merger import Merger

from robotframework_allurevisitor._convert import properties_text
from robotframework_allurevisitor._mapping import (
    AttachmentSink,
    Mapper,
    MappingOptions,
    rebot_merged,
)
from robotframework_allurevisitor._runtime import Overlay


class AllureResultVisitor(ResultVisitor):
    """Convert a Robot Framework result tree into Allure result files."""

    def __init__(
        self,
        logger: AllureFileLogger,
        *,
        source_dir: str | Path | None = None,
        host: str | None = None,
        thread: str | None = None,
        issue_pattern: str | None = None,
        link_pattern: str | None = None,
        broken_heuristic: bool = False,
        sink: AttachmentSink | None = None,
        overlay: Overlay | None = None,
        source_dir_for: Callable[[object], Path | None] | None = None,
    ) -> None:
        self._logger = logger
        # Directory of the output.xml a test or suite fixture came from, when the
        # tree mixes several sources (converter merge); None keeps ``source_dir``.
        self._source_dir_for = source_dir_for
        self._saved_source_dirs: list[Path | None] = []
        # Runtime items from a live run (listener only); None when post-processing.
        self._overlay = overlay
        self._mapper = Mapper(
            sink or AttachmentSink(logger),
            MappingOptions(
                source_dir=Path(source_dir) if source_dir else None,
                host=host,
                thread=thread,
                issue_pattern=issue_pattern,
                link_pattern=link_pattern,
                broken_heuristic=broken_heuristic,
            ),
        )
        self._containers: list = []  # stack of suite TestResultContainer
        self._steps: list = []  # stack of ExecutableItem (test / fixture / keyword / control)
        self._messages: list[list] = []  # buffered log messages, parallel to _steps
        self._test: TestResult | None = None
        self._test_container: TestResultContainer | None = None

    @property
    def mapper(self) -> Mapper:
        """The node mapper (options are adjustable, e.g. by the live listener)."""
        return self._mapper

    # ----------------------------------------------------------------- suites
    def start_suite(self, suite) -> None:  # noqa: ANN001
        self._containers.append(self._mapper.suite_container(suite))

    def end_suite(self, suite) -> None:  # noqa: ANN001
        container = self._containers.pop()
        self._mapper.finish_container(container, suite)
        if self._containers:
            self._containers[-1].children.append(container.uuid)
        self._logger.report_container(container)

    # ------------------------------------------------------------------ tests
    def start_test(self, test) -> None:  # noqa: ANN001
        self._enter_source(test)
        # Our own merge knows each test's directory; a rebot-merged file does not.
        if self._source_dir_for is None and rebot_merged(test):
            self._mapper.merged_from_elsewhere = test.name
        result = self._mapper.test_result(test)
        self._test = result
        self._test_container = self._mapper.test_container(test, result)
        self._push(result)
        if self._containers:
            self._containers[-1].children.append(result.uuid)

    def end_test(self, test) -> None:  # noqa: ANN001
        if self._overlay is not None:
            self._overlay.apply_test(test.id, self._test)
        self._pop()
        self._logger.report_result(self._test)
        self._logger.report_container(self._test_container)
        self._test = None
        self._test_container = None
        self._mapper.merged_from_elsewhere = None
        self._leave_source()

    # -------------------------------------------------------------- keywords
    def start_keyword(self, kw) -> None:  # noqa: ANN001
        # Suite and test setup/teardown arrive as SETUP/TEARDOWN keywords owned
        # directly by the suite (no test active) or by the test (test on top of
        # the stack). They become container befores/afters, not steps. A user
        # keyword's own [Teardown] has its keyword on top and stays a step.
        is_fixture = getattr(kw, "type", None) in ("SETUP", "TEARDOWN") and (
            self._test is None or self._steps[-1] is self._test
        )
        if is_fixture:
            if self._test is None:
                self._enter_source(kw)
            self._push(self._mapper.fixture(kw))
            return
        step = self._mapper.keyword_step(kw)
        self._attach(step)
        self._push(step)

    def end_keyword(self, kw) -> None:  # noqa: ANN001
        if self._overlay is not None:
            self._overlay.apply(kw.id, self._steps[-1])
        item = self._pop()
        container = self._test_container if self._test is not None else self._containers[-1]
        if isinstance(item, TestBeforeResult):
            container.befores.append(item)
        elif isinstance(item, TestAfterResult):
            container.afters.append(item)
        if self._test is None and isinstance(item, (TestBeforeResult, TestAfterResult)):
            self._leave_source()

    # ------------------------------------------------------- control structures
    def start_for(self, item) -> None:  # noqa: ANN001
        flavor = getattr(item, "flavor", "IN")
        assign = ", ".join(getattr(item, "assign", ()) or ())
        self._push_control(item, f"FOR {assign} {flavor}".strip())

    def end_for(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_for_iteration(self, item) -> None:  # noqa: ANN001
        assign = getattr(item, "assign", None) or {}
        label = ", ".join(f"{k}={v}" for k, v in assign.items()) or "iteration"
        self._push_control(item, label)

    def end_for_iteration(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_if(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "IF")

    def end_if(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_if_branch(self, item) -> None:  # noqa: ANN001
        condition = getattr(item, "condition", None) or ""
        self._push_control(item, f"{item.type} {condition}".strip())

    def end_if_branch(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_while(self, item) -> None:  # noqa: ANN001
        condition = getattr(item, "condition", None) or ""
        self._push_control(item, f"WHILE {condition}".strip())

    def end_while(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_while_iteration(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "iteration")

    def end_while_iteration(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_try(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "TRY")

    def end_try(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_try_branch(self, item) -> None:  # noqa: ANN001
        patterns = " ".join(getattr(item, "patterns", ()) or ())
        self._push_control(item, f"{item.type} {patterns}".strip())

    def end_try_branch(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_group(self, item) -> None:  # noqa: ANN001
        self._push_control(item, f"GROUP {getattr(item, 'name', '') or ''}".strip())

    def end_group(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_var(self, item) -> None:  # noqa: ANN001
        self._push_control(item, f"VAR {getattr(item, 'name', '') or ''}".strip())

    def end_var(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def _leaf_control(self, item, label) -> None:  # noqa: ANN001
        # RETURN / BREAK / CONTINUE / ERROR have no nested body; emit and unwind.
        self._push_control(item, label)
        self._pop_control()

    def start_return(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "RETURN")

    def start_break(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "BREAK")

    def start_continue(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "CONTINUE")

    def start_error(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "ERROR")

    # ------------------------------------------------------------- messages
    def visit_message(self, message) -> None:  # noqa: ANN001
        if self._steps:
            self._mapper.message(self._steps[-1], message, self._messages[-1])

    # ------------------------------------------------------------- internals
    def _enter_source(self, item) -> None:  # noqa: ANN001
        if self._source_dir_for is None:
            return
        options = self._mapper.options
        self._saved_source_dirs.append(options.source_dir)
        options.source_dir = self._source_dir_for(item) or options.source_dir

    def _leave_source(self) -> None:
        if self._source_dir_for is not None and self._saved_source_dirs:
            self._mapper.options.source_dir = self._saved_source_dirs.pop()

    def _push_control(self, item, name: str) -> None:  # noqa: ANN001
        step = self._mapper.control_step(item, name)
        self._attach(step)
        self._push(step)

    def _pop_control(self) -> None:
        self._pop()

    def _push(self, item) -> None:  # noqa: ANN001
        self._steps.append(item)
        self._messages.append([])

    def _pop(self):  # noqa: ANN202
        item = self._steps.pop()
        self._mapper.flush_messages(item, self._messages.pop())
        return item

    def _attach(self, step) -> None:  # noqa: ANN001
        parent = self._steps[-1] if self._steps else self._test
        if parent is not None:
            parent.steps.append(step)


def generate(
    sources,  # noqa: ANN001 - str | Path | sequence thereof
    results_dir: str | Path,
    *,
    clean: bool = False,
    thread: str | None = None,
    issue_pattern: str | None = None,
    link_pattern: str | None = None,
    broken_heuristic: bool = False,
    environment: Mapping[str, str] | None = None,
    executor: Mapping | None = None,
    merge: bool = False,
) -> None:
    """Convert one or more Robot ``output.xml`` sources into Allure results.

    Each source is converted on its own, so names and ``historyId`` match a
    single-source conversion and attachments resolve against that source's
    directory; tests repeated across sources (e.g. a ``--rerunfailed`` run) become
    Allure retries. With ``merge`` the sources are merged like ``rebot --merge``
    (last wins) into one result per test, each test keeping its own run's files.
    ``broken_heuristic`` reports library/syntax/import/timeout failures as
    ``broken`` instead of ``failed``. ``environment`` is written to
    ``environment.properties`` and ``executor`` to ``executor.json``, both shown by
    Allure 2 and 3. A truncated ``output.xml`` is tolerated: whatever was completed
    is still flushed, and the other sources are still converted.
    """
    if isinstance(sources, (str, Path)):
        sources = [sources]
    paths = [Path(s) for s in sources]

    logger = AllureFileLogger(str(results_dir), clean=clean)
    # Written after the logger's clean so --clean does not remove them.
    _write_metadata(Path(results_dir), environment, executor)

    def new_visitor(source_dir: Path, source_dir_for=None) -> AllureResultVisitor:  # noqa: ANN001
        return AllureResultVisitor(
            logger,
            source_dir=source_dir,
            thread=thread,
            issue_pattern=issue_pattern,
            link_pattern=link_pattern,
            broken_heuristic=broken_heuristic,
            source_dir_for=source_dir_for,
        )

    if merge:
        _generate_merged(paths, new_visitor)
        return
    for path in paths:
        # A fresh visitor per source: a failure in one source leaves no stale stack.
        _convert_tolerantly(path, new_visitor(_dir_of(path)))


def _generate_merged(paths: Sequence[Path], new_visitor) -> None:  # noqa: ANN001
    """Merge like ``rebot --merge`` and remember which source each item came from."""
    results = []
    source_dirs: dict[int, Path] = {}
    for path in paths:
        try:
            result = ExecutionResult(str(path))
        except Exception as error:  # noqa: BLE001 - tolerate truncated/corrupt output.xml
            _warn_stopped(path, error)
            continue
        directory = _dir_of(path)
        # Robot's Merger moves these objects into the first tree unchanged
        # (tests replace or join tests, suite fixtures replace fixtures).
        for item in _source_items(result.suite):
            source_dirs[id(item)] = directory
        results.append((path, result))
    if not results:
        return
    first_path, merged = results[0]
    merger = Merger(merged, rpa=merged.rpa)
    for _, other in results[1:]:
        merger.merge(other)
    # ``results`` keeps every source tree alive, so the ids above stay unique.
    visitor = new_visitor(_dir_of(first_path), lambda item: source_dirs.get(id(item)))
    _convert_tolerantly(first_path, visitor, merged)


def _source_items(suite):  # noqa: ANN001, ANN202
    yield suite.setup
    yield suite.teardown
    yield from suite.tests
    for child in suite.suites:
        yield from _source_items(child)


def _convert_tolerantly(path: Path, visitor: AllureResultVisitor, result=None) -> None:  # noqa: ANN001
    try:
        (result if result is not None else ExecutionResult(str(path))).visit(visitor)
    except Exception as error:  # noqa: BLE001 - tolerate truncated/corrupt output.xml
        # Results/containers completed before the failure are already flushed by
        # the file logger; warn rather than abort so CI still gets a partial report.
        _warn_stopped(path, error)


def _warn_stopped(path: Path, error: Exception) -> None:
    print(f"warning: stopped early while converting {str(path)!r}: {error}", file=sys.stderr)


def _dir_of(path: Path) -> Path:
    return path.resolve().parent


def _write_metadata(results_dir: Path, environment, executor) -> None:  # noqa: ANN001
    if environment:
        (results_dir / "environment.properties").write_text(
            properties_text(dict(environment)), encoding="latin-1"
        )
    if executor:
        (results_dir / "executor.json").write_text(
            json.dumps(dict(executor), ensure_ascii=False, indent=2), encoding="utf-8"
        )
