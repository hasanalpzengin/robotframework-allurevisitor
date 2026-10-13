"""Attachment sinks: immediate copies for the converter, deferred copies for a live run."""

from __future__ import annotations

from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import TestStepResult as StepResult

from robotframework_allurevisitor._mapping import AttachmentSink, DeferredAttachmentSink


def test_immediate_sink_copies_now(tmp_path):
    source = tmp_path / "shot.png"
    source.write_bytes(b"png")
    results = tmp_path / "results"
    owner = StepResult(name="step")

    AttachmentSink(AllureFileLogger(str(results))).attach_file(
        owner, source, name="shot.png", mime="image/png"
    )

    (attachment,) = owner.attachments
    assert (results / attachment.source).read_bytes() == b"png"


def test_deferred_sink_copies_files_created_later(tmp_path):
    results = tmp_path / "results"
    warnings = []
    sink = DeferredAttachmentSink(AllureFileLogger(str(results)), warn=warnings.append)
    owner = StepResult(name="New Context")
    late = tmp_path / "trace_context=late.zip"
    gone = tmp_path / "trace_context=gone.zip"

    sink.attach_file(owner, late, name=late.name, mime="application/zip")
    sink.attach_file(owner, gone, name=gone.name, mime="application/zip")
    assert len(owner.attachments) == 2
    assert not list(results.glob("*-attachment.zip"))  # nothing copied yet

    late.write_bytes(b"trace")  # e.g. written by Close Context in Suite Teardown
    sink.flush()

    (attachment,) = owner.attachments  # the missing file's attachment was dropped
    assert attachment.name == late.name
    assert (results / attachment.source).read_bytes() == b"trace"
    assert warnings == [f"Allure attachment skipped, file not found: {gone}"]
