"""Runtime items recorded while tests run (the live listener's overlay).

Calls made through ``allure-python-commons`` during a run (``allure.attach``,
``allure.dynamic.*``, ``allure.step``) are recorded here keyed by the Robot
result id of the keyword (or test) that was running, then applied when that
keyword's step or that test's result is built.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from allure_commons import hookimpl
from allure_commons.model2 import (
    ATTACHMENT_PATTERN,
    Attachment,
    GlobalAttachment,
    GlobalError,
    Globals,
    Label,
    Link,
    Parameter,
    Status,
    StatusDetails,
    TestStepResult,
)
from allure_commons.types import AttachmentType
from allure_commons.utils import format_exception, format_traceback, now, represent, uuid4


@dataclass
class _Bucket:
    attachments: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    links: list = field(default_factory=list)
    parameters: list = field(default_factory=list)
    title: str | None = None
    description: str | None = None
    description_html: str | None = None


class Overlay:
    """Runtime items keyed by Robot result id (``s1-t1-k2-k1``, ``s1-t1``, ...)."""

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}

    def bucket(self, key: str) -> _Bucket:
        return self._buckets.setdefault(key, _Bucket())

    def apply(self, key: str, item) -> None:  # noqa: ANN001 - step or fixture
        """Add attachments and steps recorded under ``key`` to ``item``."""
        bucket = self._buckets.pop(key, None)
        if bucket is not None:
            item.attachments.extend(bucket.attachments)
            item.steps.extend(bucket.steps)

    def apply_test(self, key: str, result) -> None:  # noqa: ANN001 - TestResult
        """Add everything recorded for test ``key`` (outside keywords, or test-level)."""
        bucket = self._buckets.pop(key, None)
        if bucket is None:
            return
        result.attachments.extend(bucket.attachments)
        result.steps.extend(bucket.steps)
        result.labels.extend(bucket.labels)
        result.links.extend(link for link in bucket.links if link not in result.links)
        result.parameters.extend(bucket.parameters)
        if bucket.title:
            result.name = bucket.title
        if bucket.description:
            result.description = bucket.description
        if bucket.description_html:
            result.descriptionHtml = bucket.description_html


class RuntimeHooks:
    """``allure_commons`` plugin recording runtime calls into an :class:`Overlay`.

    ``current_key`` returns the result id of the running keyword (or of the test /
    suite when no keyword runs); ``current_test`` returns the running test's id
    or None. Attachment files are written right away; their references wait in
    the overlay until the owning step is built.
    """

    def __init__(self, logger, overlay: Overlay, current_key, current_test) -> None:  # noqa: ANN001
        self._logger = logger
        self._overlay = overlay
        self._current_key = current_key
        self._current_test = current_test
        self._steps: list[TestStepResult] = []  # open allure.step steps

    # ------------------------------------------------------------- targets
    def _target(self):  # noqa: ANN202 - an open step or the current bucket
        return self._steps[-1] if self._steps else self._overlay.bucket(self._current_key())

    def _test_bucket(self) -> _Bucket | None:
        test = self._current_test()
        return self._overlay.bucket(test) if test else None

    # --------------------------------------------------------- attachments
    @hookimpl
    def attach_data(self, body, name, attachment_type, extension) -> None:  # noqa: ANN001
        file_name, mime = _attachment_file(attachment_type, extension)
        self._logger.report_attached_data(body=body, file_name=file_name)
        self._target().attachments.append(Attachment(name=name, source=file_name, type=mime))

    @hookimpl
    def attach_file(self, source, name, attachment_type, extension) -> None:  # noqa: ANN001
        file_name, mime = _attachment_file(attachment_type, extension)
        self._logger.report_attached_file(source=str(source), file_name=file_name)
        self._target().attachments.append(Attachment(name=name, source=file_name, type=mime))

    # ------------------------------------------------------ test metadata
    @hookimpl
    def add_label(self, label_type, labels) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            bucket.labels.extend(Label(name=label_type, value=value) for value in labels)

    @hookimpl
    def add_link(self, url, link_type, name) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            bucket.links.append(Link(type=link_type, url=url, name=name))

    @hookimpl
    def add_title(self, test_title) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            bucket.title = test_title

    @hookimpl
    def add_description(self, test_description) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            bucket.description = test_description

    @hookimpl
    def add_description_html(self, test_description_html) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            bucket.description_html = test_description_html

    @hookimpl
    def add_parameter(self, name, value, excluded, mode) -> None:  # noqa: ANN001
        bucket = self._test_bucket()
        if bucket is not None:
            mode_value = getattr(mode, "value", mode)
            bucket.parameters.append(
                Parameter(name=name, value=represent(value), excluded=excluded, mode=mode_value)
            )

    # --------------------------------------------------------------- steps
    @hookimpl
    def start_step(self, uuid, title, params) -> None:  # noqa: ANN001
        step = TestStepResult(
            name=title,
            start=now(),
            parameters=[Parameter(name=key, value=value) for key, value in params.items()],
        )
        self._target().steps.append(step)
        self._steps.append(step)

    @hookimpl
    def stop_step(self, uuid, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        if not self._steps:
            return
        step = self._steps.pop()
        step.stop = now()
        if exc_val is None:
            step.status = Status.PASSED
            return
        step.status = Status.FAILED if isinstance(exc_val, AssertionError) else Status.BROKEN
        step.statusDetails = StatusDetails(
            message=format_exception(exc_type, exc_val), trace=format_traceback(exc_tb)
        )

    # ------------------------------------------------------------- globals
    @hookimpl
    def global_attach_data(self, body, name, attachment_type, extension) -> None:  # noqa: ANN001
        file_name, mime = _attachment_file(attachment_type, extension)
        self._logger.report_attached_data(body=body, file_name=file_name)
        self._report_global_attachment(file_name, name, mime)

    @hookimpl
    def global_attach_file(self, source, name, attachment_type, extension) -> None:  # noqa: ANN001
        file_name, mime = _attachment_file(attachment_type, extension)
        self._logger.report_attached_file(source=str(source), file_name=file_name)
        self._report_global_attachment(file_name, name, mime)

    @hookimpl
    def global_error(self, message, trace) -> None:  # noqa: ANN001
        self._logger.report_globals(
            Globals(errors=[GlobalError(message=message, trace=trace, timestamp=now())])
        )

    def _report_global_attachment(self, file_name: str, name, mime) -> None:  # noqa: ANN001
        attachment = GlobalAttachment(source=file_name, name=name, type=mime, timestamp=now())
        self._logger.report_globals(Globals(attachments=[attachment]))


def _attachment_file(attachment_type, extension) -> tuple[str, str | None]:  # noqa: ANN001
    """File name and MIME type for an attachment, as ``AllureLifecycle`` derives them."""
    mime = attachment_type
    extension = extension or "attach"
    if isinstance(attachment_type, AttachmentType):
        extension = attachment_type.extension
        mime = attachment_type.mime_type
    return ATTACHMENT_PATTERN.format(prefix=uuid4(), ext=extension), mime
