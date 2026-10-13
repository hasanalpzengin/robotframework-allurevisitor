"""Robot Framework keywords adding attachments and global entries to Allure results.

Import with ``Library    robotframework_allurevisitor.AllureLibrary``. Keywords
match upstream ``AllureLibrary``. They take effect while
``robotframework_allurevisitor.Listener`` is active and do nothing otherwise.
"""

from __future__ import annotations

import allure
from allure_commons.types import AttachmentType

__all__ = ["attach", "attach_file", "global_attach", "global_attach_file", "global_error"]


def _attachment_type(name):  # noqa: ANN001, ANN202
    """``AttachmentType`` member by name (``PNG``, ``TEXT``, ...), else the literal value."""
    if name is None:
        return None
    try:
        return AttachmentType[name]
    except KeyError:
        return name


def attach(data, name=None, attachment_type=None, extension=None):  # noqa: ANN001, ANN201
    """Attach ``data`` to the current step."""
    allure.attach(
        data, name=name, attachment_type=_attachment_type(attachment_type), extension=extension
    )


def attach_file(source, name=None, attachment_type=None, extension=None):  # noqa: ANN001, ANN201
    """Attach the file at ``source`` to the current step."""
    allure.attach.file(
        source, name=name, attachment_type=_attachment_type(attachment_type), extension=extension
    )


def global_attach(data, name=None, attachment_type=None, extension=None):  # noqa: ANN001, ANN201
    """Attach ``data`` to the whole report (Allure globals)."""
    allure.global_attach(
        data, name=name, attachment_type=_attachment_type(attachment_type), extension=extension
    )


def global_attach_file(source, name=None, attachment_type=None, extension=None):  # noqa: ANN001, ANN201
    """Attach the file at ``source`` to the whole report (Allure globals)."""
    allure.global_attach.file(
        source, name=name, attachment_type=_attachment_type(attachment_type), extension=extension
    )


def global_error(message, trace=None):  # noqa: ANN001, ANN201
    """Record an error for the whole report (Allure globals)."""
    allure.global_error(message, trace=trace)
