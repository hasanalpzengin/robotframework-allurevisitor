"""Live Robot Framework listener (API v3) writing Allure results.

Usage::

    robot --listener robotframework_allurevisitor.Listener[:RESULTS_DIR] tests/

Each test is converted from its complete result subtree when it ends, by the
same visitor and mapping ``rf-allure`` uses, so live and post-processed results
match. Results are written when their suite ends, after Robot has assigned final
statuses (a failing suite setup/teardown changes the status of tests that
already finished). Calls made through ``allure-python-commons`` while tests run
(``allure.attach``, ``allure.dynamic.*``, ``allure.step``) are recorded by
keyword and added to the matching step.
"""

from __future__ import annotations

import json
from pathlib import Path

import allure_commons
from allure_commons.logger import AllureFileLogger
from allure_commons.utils import uuid4
from robot.api import logger as robot_logger
from robot.libraries.BuiltIn import BuiltIn

from robotframework_allurevisitor._mapping import DeferredAttachmentSink
from robotframework_allurevisitor._runtime import Overlay, RuntimeHooks
from robotframework_allurevisitor.visitor import AllureResultVisitor

DEFAULT_RESULTS_DIR = "output/allure"

# Thread label outside pabot, like allure-robotframework: one value per process.
_DEFAULT_THREAD = f"default-{uuid4()}"


class _Collector:
    """Logger stand-in that holds a converted test's result and container."""

    def __init__(self, logger: AllureFileLogger) -> None:
        self._logger = logger
        self.buffering = False
        self.items: list = []

    def report_result(self, result) -> None:  # noqa: ANN001
        if self.buffering:
            self.items.append(result)
        else:
            self._logger.report_result(result)

    def report_container(self, container) -> None:  # noqa: ANN001
        if self.buffering:
            self.items.append(container)
        else:
            self._logger.report_container(container)

    def drain(self) -> list:
        items, self.items = self.items, []
        return items


class Listener:
    """Robot Framework listener producing Allure results during a run."""

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(
        self,
        results_dir: str = DEFAULT_RESULTS_DIR,
        broken_heuristic: bool = False,
        clean: bool = False,
    ) -> None:
        self._results_dir = Path(results_dir)
        self._logger = AllureFileLogger(str(self._results_dir), clean=clean)
        self._collector = _Collector(self._logger)
        self._sink = DeferredAttachmentSink(self._logger, warn=robot_logger.warn)
        self._overlay = Overlay()
        self._visitor = AllureResultVisitor(
            self._collector,
            broken_heuristic=broken_heuristic,
            sink=self._sink,
            overlay=self._overlay,
        )
        self._keywords: list[str] = []  # result ids of running keywords
        self._scopes: list[str] = []  # result ids of running suites / test
        self._test_id: str | None = None
        self._pending: list[list[tuple]] = []  # per running suite: (rf id, result, container)
        # rf test id -> (result uuid, status, message) of tests already written.
        self._written: dict[str, tuple[str, str, str | None]] = {}
        self._configured = False
        self._warned_upstream = False
        self._hooks = RuntimeHooks(
            self._logger, self._overlay, self._current_key, self._current_test
        )
        allure_commons.plugin_manager.register(self._hooks)
        self._warn_if_upstream_active()

    # ------------------------------------------------------------- suites
    def start_suite(self, data, result) -> None:  # noqa: ANN001
        if not self._configured:
            self._configure()
        self._scopes.append(result.id)
        self._pending.append([])
        self._visitor.start_suite(result)

    def end_suite(self, data, result) -> None:  # noqa: ANN001
        # Suite fixtures keep their bodies until here (test bodies are already gone).
        if result.has_setup:
            result.setup.visit(self._visitor)
        if result.has_teardown:
            result.teardown.visit(self._visitor)

        pending = self._pending.pop()
        self._reconcile(result, pending)
        self._sink.flush()
        for rf_id, test_result, container in pending:
            self._logger.report_result(test_result)
            self._logger.report_container(container)
            message = test_result.statusDetails.message if test_result.statusDetails else None
            self._written[rf_id] = (test_result.uuid, test_result.status, message)
        self._visitor.end_suite(result)
        self._scopes.pop()

    # -------------------------------------------------------------- tests
    def start_test(self, data, result) -> None:  # noqa: ANN001
        self._scopes.append(result.id)
        self._test_id = result.id

    def end_test(self, data, result) -> None:  # noqa: ANN001
        self._collector.buffering = True
        try:
            result.visit(self._visitor)
        finally:
            self._collector.buffering = False
        test_result, container = self._collector.drain()
        self._pending[-1].append((result.id, test_result, container))
        self._scopes.pop()
        self._test_id = None

    # ----------------------------------------------------------- keywords
    def start_keyword(self, data, result) -> None:  # noqa: ANN001
        self._keywords.append(result.id)

    def end_keyword(self, data, result) -> None:  # noqa: ANN001
        if self._keywords:
            self._keywords.pop()

    def close(self) -> None:
        self._sink.flush()
        allure_commons.plugin_manager.unregister(self._hooks)

    # ---------------------------------------------------------- internals
    def _configure(self) -> None:
        """Read run-level settings once Robot's variables exist (first suite start)."""
        builtin = BuiltIn()
        options = self._visitor.mapper.options
        output_dir = builtin.get_variable_value("${OUTPUT DIR}")
        options.source_dir = Path(output_dir) if output_dir else None
        pool = builtin.get_variable_value("${PABOTEXECUTIONPOOLID}")
        caller = builtin.get_variable_value("${CALLER_ID}")
        options.thread = f"{pool}-{caller}" if pool and caller else _DEFAULT_THREAD
        self._configured = True
        self._warn_if_upstream_active()

    def _current_key(self) -> str | None:
        if self._keywords:
            return self._keywords[-1]
        return self._scopes[-1] if self._scopes else None

    def _current_test(self) -> str | None:
        return self._test_id

    def _reconcile(self, suite, pending: list[tuple]) -> None:
        """Apply the final statuses Robot assigns at suite end.

        A failing suite setup/teardown fails tests that already finished, including
        tests of child suites that were written earlier; those are patched in place.
        """
        mapper = self._visitor.mapper
        by_id = {rf_id: test_result for rf_id, test_result, _ in pending}
        to_patch: dict[str, tuple[str, str | None]] = {}
        for test in suite.all_tests:
            status, details = mapper.test_status(test)
            message = details.message if details else None
            if test.id in by_id:
                by_id[test.id].status = status
                by_id[test.id].statusDetails = details
            elif test.id in self._written:
                uuid, old_status, old_message = self._written[test.id]
                if (old_status, old_message) != (status, message):
                    to_patch[uuid] = (status, message)
                    self._written[test.id] = (uuid, status, message)
        if to_patch:
            self._patch_written(to_patch)

    def _patch_written(self, to_patch: dict[str, tuple[str, str | None]]) -> None:
        # AllureFileLogger names files with a random uuid, so match on the content.
        for path in self._results_dir.glob("*-result.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("uuid") not in to_patch:
                continue
            status, message = to_patch[data["uuid"]]
            data["status"] = status
            details = data.get("statusDetails") or {}
            if message:
                details["message"] = message
            if details:
                data["statusDetails"] = details
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _warn_if_upstream_active(self) -> None:
        if self._warned_upstream:
            return
        upstream = any(
            type(plugin).__module__.startswith("allure_robotframework")
            for plugin in allure_commons.plugin_manager.get_plugins()
        )
        if upstream:
            self._warned_upstream = True
            robot_logger.warn(
                "Both the allure_robotframework listener and "
                "robotframework_allurevisitor.Listener are active: runtime attachments, "
                "steps, and labels will be recorded twice. Use only one of them."
            )
