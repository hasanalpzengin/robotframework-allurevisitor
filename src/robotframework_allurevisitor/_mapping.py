"""Per-node construction of Allure model objects from Robot result objects.

The visitor owns the traversal; this module owns *what* each Robot node becomes
(test result, fixture, step, attachment), so the same mapping can be driven by
another front end such as a live listener.
"""

from __future__ import annotations

import html
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from allure_commons.model2 import (
    Attachment,
    Label,
    Parameter,
    Status,
    TestAfterResult,
    TestBeforeResult,
    TestResult,
    TestResultContainer,
    TestStepResult,
)
from allure_commons.types import LabelType
from allure_commons.utils import host_tag, platform_label, uuid4

from robotframework_allurevisitor._convert import history_id, status_of, to_ms
from robotframework_allurevisitor._labels import suite_labels, tag_labels_and_links

# Matches an <img src="..."> reference inside a Robot log message.
_IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)

# Image sources that are not files on disk (nothing to attach, nothing to warn about).
_NON_FILE_SRC = re.compile(r"^(?:https?:|data:)", re.IGNORECASE)

# robotframework-browser announces trace archives in `New Context`:
# "Successfully created context and trace file will be saved to: <path>.zip"
_TRACE_RE = re.compile(r"trace file will be saved to:\s*(?P<path>.+?\.zip)\s*$", re.IGNORECASE)
PLAYWRIGHT_TRACE_MIME = "application/vnd.allure.playwright-trace"

_LOG_FORMAT = "<p><b>[{level}]</b>&nbsp;{message}</p>"
_FAIL_LOG_FORMAT = '<p style="color: red"><b>[{level}]</b>&nbsp;{message}</p>'
_CRITICAL_LEVELS = ("FAIL", "ERROR")

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


class AttachmentSink:
    """Writes attachment content into the results directory via the file logger.

    Files are copied immediately. A front end that sees attachments before their
    files exist (e.g. a live listener) can subclass this and defer the copy.
    """

    def __init__(self, logger) -> None:  # noqa: ANN001 - AllureFileLogger
        self._logger = logger

    def attach_data(self, owner, body: str, *, name: str, mime: str, extension: str) -> None:  # noqa: ANN001
        file_name = f"{uuid4()}-attachment{extension}"
        self._logger.report_attached_data(body, file_name)
        owner.attachments.append(Attachment(name=name, source=file_name, type=mime))

    # Whether files are copied later, so they need not exist when attached.
    defers_files = False

    def attach_file(self, owner, path: Path, *, name: str, mime: str) -> None:  # noqa: ANN001
        file_name = f"{uuid4()}-attachment{path.suffix.lower()}"
        attachment = Attachment(name=name, source=file_name, type=mime)
        owner.attachments.append(attachment)
        self._copy(path, file_name, owner, attachment)

    def _copy(self, path: Path, file_name: str, owner, attachment: Attachment) -> None:  # noqa: ANN001
        self._logger.report_attached_file(str(path), file_name)

    def flush(self) -> None:
        """Copy any deferred files. Nothing is deferred here."""


class DeferredAttachmentSink(AttachmentSink):
    """Records file copies and performs them on :meth:`flush`.

    A live run sees some attachments before their files exist (a Playwright trace
    is written only when its context closes). Files still missing at flush time
    are dropped from their owner, with a warning, instead of leaving a dangling
    attachment.
    """

    defers_files = True

    def __init__(self, logger, warn=None) -> None:  # noqa: ANN001
        super().__init__(logger)
        self._warn = warn or (lambda message: None)
        self._pending: list[tuple[Path, str, object, Attachment]] = []

    def _copy(self, path: Path, file_name: str, owner, attachment: Attachment) -> None:  # noqa: ANN001
        self._pending.append((path, file_name, owner, attachment))

    def flush(self) -> None:
        pending, self._pending = self._pending, []
        for path, file_name, owner, attachment in pending:
            if path.is_file():
                self._logger.report_attached_file(str(path), file_name)
            else:
                owner.attachments.remove(attachment)
                self._warn(f"Allure attachment skipped, file not found: {path}")


@dataclass
class MappingOptions:
    """Settings that influence how Robot nodes are mapped."""

    source_dir: Path | None = None
    host: str | None = None
    thread: str | None = None
    issue_pattern: str | None = None
    link_pattern: str | None = None
    broken_heuristic: bool = False
    # Like allure-robotframework: items with more messages than this get one
    # "Keyword Log" attachment; items with this many or fewer get message sub-steps.
    max_step_messages: int = field(
        default_factory=lambda: int(os.environ.get("ALLURE_MAX_STEP_MESSAGE_COUNT", "0") or 0)
    )
    # Where conversion warnings go (the listener routes them to Robot's log).
    warn: Callable[[str], None] = field(default=lambda message: print(message, file=sys.stderr))


class Mapper:
    """Build Allure model objects for individual Robot result nodes."""

    def __init__(self, sink: AttachmentSink, options: MappingOptions | None = None) -> None:
        self.sink = sink
        self.options = options or MappingOptions()
        # Name of the running test when rebot --merge took it from another output.xml:
        # its relative screenshot paths point into that run's directory, not ours.
        self.merged_from_elsewhere: str | None = None
        self._host = self.options.host or host_tag()
        self._platform = platform_label()

    def status(self, item):  # noqa: ANN001, ANN201
        return status_of(item, broken_heuristic=self.options.broken_heuristic)

    def test_status(self, test):  # noqa: ANN001, ANN201
        """Status of a test, including the listener's ``skipped`` tag override."""
        status, details = self.status(test)
        if any(str(tag).lower() == "skipped" for tag in test.tags):
            status = Status.SKIPPED
        return status, details

    # ---------------------------------------------------------- containers
    def suite_container(self, suite) -> TestResultContainer:  # noqa: ANN001
        return TestResultContainer(
            uuid=uuid4(),
            name=suite.name,
            start=to_ms(suite.start_time),
            stop=to_ms(suite.end_time),
        )

    def test_container(self, test, result: TestResult) -> TestResultContainer:  # noqa: ANN001
        """A container holding only ``result``, carrying the test's own setup/teardown."""
        return TestResultContainer(
            uuid=uuid4(),
            name=test.name,
            children=[result.uuid],
            start=result.start,
            stop=result.stop,
        )

    def finish_container(self, container: TestResultContainer, suite) -> None:  # noqa: ANN001
        """Refresh times once the suite has ended (a live run starts without an end)."""
        container.start = to_ms(suite.start_time)
        container.stop = to_ms(suite.end_time)

    # --------------------------------------------------------------- tests
    def test_result(self, test) -> TestResult:  # noqa: ANN001
        full_name = getattr(test, "full_name", None) or test.longname
        labels = suite_labels(full_name)
        tag_labels, links = tag_labels_and_links(
            test.tags, self.options.issue_pattern, self.options.link_pattern
        )
        labels += tag_labels
        labels += [
            Label(name=LabelType.FRAMEWORK, value="robotframework"),
            Label(name=LabelType.LANGUAGE, value=self._platform),
            Label(name=LabelType.HOST, value=self._host),
        ]
        if self.options.thread:
            labels.append(Label(name=LabelType.THREAD, value=self.options.thread))

        status, details = self.test_status(test)
        return TestResult(
            uuid=uuid4(),
            name=test.name,
            fullName=full_name,
            testCaseId=history_id(full_name),
            historyId=history_id(full_name),
            status=status,
            statusDetails=details,
            description=test.doc or None,
            start=to_ms(test.start_time),
            stop=to_ms(test.end_time),
            labels=labels,
            links=links,
            titlePath=full_name.split(".")[:-1],
        )

    # ------------------------------------------------------ fixtures/steps
    def fixture(self, kw) -> TestBeforeResult | TestAfterResult:  # noqa: ANN001
        factory = TestBeforeResult if kw.type == "SETUP" else TestAfterResult
        status, details = self.status(kw)
        return factory(
            name=kw.name,
            status=status,
            statusDetails=details,
            start=to_ms(kw.start_time),
            stop=to_ms(getattr(kw, "end_time", None)),
        )

    def keyword_step(self, kw) -> TestStepResult:  # noqa: ANN001
        step = self.control_step(kw, self._keyword_name(kw))
        for index, arg in enumerate(getattr(kw, "args", ()) or (), start=1):
            step.parameters.append(Parameter(name=f"arg{index}", value=str(arg)))
        return step

    def control_step(self, item, name: str) -> TestStepResult:  # noqa: ANN001
        status, details = self.status(item)
        return TestStepResult(
            name=name,
            status=status,
            statusDetails=details,
            start=to_ms(getattr(item, "start_time", None)),
            stop=to_ms(getattr(item, "end_time", None)),
        )

    @staticmethod
    def _keyword_name(kw) -> str:  # noqa: ANN001
        name = kw.name
        assign = getattr(kw, "assign", None)
        if assign:
            name = f"{', '.join(assign)} = {name}"
        return name

    # ------------------------------------------------------------ messages
    def message(self, owner, message, buffer: list) -> None:  # noqa: ANN001
        """Attach embedded images and announced traces on ``owner``; buffer the rest."""
        if message.html and self._attach_images(owner, message.message):
            return
        self._attach_trace(owner, message.message)
        buffer.append(message)

    def _attach_trace(self, owner, text: str) -> None:  # noqa: ANN001
        match = _TRACE_RE.search(text or "")
        if match is None:
            return
        logged = Path(match.group("path"))
        # Path(...).name would not split a Windows path on POSIX; split on both separators.
        name = re.split(r"[\\/]", str(logged))[-1]
        # A deferring sink copies later: the trace is only written when its context closes.
        if logged.is_file() or self.sink.defers_files:
            trace = logged
        else:
            trace = self._relocated_trace(name)
        if trace is not None:
            self.sink.attach_file(owner, trace, name=name, mime=PLAYWRIGHT_TRACE_MIME)

    def _relocated_trace(self, name: str) -> Path | None:
        """Find a trace whose logged path no longer exists (moved output, pabot layouts)."""
        if self.options.source_dir is None:
            return None
        traces = self.options.source_dir / "browser" / "traces"
        candidate = traces / name
        if candidate.is_file():
            return candidate
        # pabot --artifacts copies traces as "<timestamp>-<n>-<name>", and without it
        # they stay in pabot_results/<n>/. Names hold a uuid, so matches are unambiguous.
        searches = (
            (traces, f"*-{name}"),
            (self.options.source_dir / "pabot_results", f"*/browser/traces/{name}"),
        )
        for base, pattern in searches:
            for match in sorted(base.glob(pattern)):
                if match.is_file():
                    return match
        return None

    def flush_messages(self, owner, buffer: list) -> None:  # noqa: ANN001
        """Emit buffered messages as one ``Keyword Log`` attachment or as sub-steps."""
        if not buffer:
            return
        if len(buffer) > self.options.max_step_messages:
            body = "".join(_log_line(message) for message in buffer)
            self.sink.attach_data(
                owner, body, name="Keyword Log", mime="text/html", extension=".html"
            )
            return
        for message in buffer:
            timestamp = to_ms(getattr(message, "timestamp", None))
            owner.steps.append(
                TestStepResult(
                    name=message.message,
                    status=Status.FAILED if message.level in _CRITICAL_LEVELS else Status.PASSED,
                    start=timestamp,
                    stop=timestamp,
                )
            )

    def _attach_images(self, owner, html_text: str) -> bool:  # noqa: ANN001
        attached = False
        for src in _IMG_RE.findall(html_text):
            resolved = self._resolve(src)
            if resolved is None:
                self._warn_missing_image(src)
                continue
            if self.merged_from_elsewhere and not Path(src).is_absolute():
                self.options.warn(
                    f"warning: '{self.merged_from_elsewhere}' was merged by rebot --merge from "
                    f"another output; its relative screenshots were resolved against "
                    f"{self.options.source_dir} and may belong to a different run. "
                    "Convert the original outputs with `rf-allure --merge` instead."
                )
                self.merged_from_elsewhere = None  # once per test
            mime = _IMAGE_MIME.get(resolved.suffix.lower(), "application/octet-stream")
            self.sink.attach_file(owner, resolved, name=resolved.name, mime=mime)
            attached = True
        return attached

    def _warn_missing_image(self, src: str) -> None:
        if _NON_FILE_SRC.match(src):
            return
        message = f"warning: screenshot not found, kept in the Keyword Log: {src}"
        if not Path(src).is_absolute():
            message += (
                f" (looked in {self.options.source_dir}; for pabot output, "
                "run pabot with --artifactsinsubfolders)"
            )
        self.options.warn(message)

    def _resolve(self, src: str) -> Path | None:
        if _NON_FILE_SRC.match(src):
            return None
        path = Path(src)
        if not path.is_absolute() and self.options.source_dir is not None:
            path = self.options.source_dir / path
        try:
            return path if path.is_file() else None
        except OSError:  # e.g. ENAMETOOLONG
            return None


def rebot_merged(test) -> bool:  # noqa: ANN001
    """Whether ``rebot --merge`` re-executed or added ``test`` from a later output."""
    message = getattr(test, "message", "") or ""
    return message.startswith("*HTML*") and (
        'class="merge"' in message or "added from merged output" in message
    )


def _log_line(message) -> str:  # noqa: ANN001
    text = message.message if message.html else html.escape(message.message)
    template = _FAIL_LOG_FORMAT if message.level in _CRITICAL_LEVELS else _LOG_FORMAT
    return template.format(level=message.level, message=text.replace("\n", "<br>"))
