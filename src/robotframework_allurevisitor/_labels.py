"""Suite-label and tag/link mapping, mirroring the allure-robotframework listener."""

from __future__ import annotations

import re

from allure_commons.mapping import labels_set, parse_tag
from allure_commons.model2 import Label, Link
from allure_commons.types import LabelType, LinkType

# Legacy Robot link tags understood by allure-robotframework: ``issue:[name]url``,
# ``tms:[name]url``, and ``link:[name]url`` (the ``[name]`` part is optional).
_LEGACY_LINK_TYPES = (LinkType.ISSUE, LinkType.TEST_CASE, LinkType.LINK)
_LEGACY_LINK_NAME = re.compile(r"^\[(.+)\]")


def suite_labels(full_name: str) -> list[Label]:
    """Split a test full name into parentSuite/suite/subSuite labels.

    Same rules as allure-robotframework: ``S1.T`` -> suite; ``S1.S2.T`` ->
    suite + subSuite; deeper names -> parentSuite (first level), suite (second
    level), and subSuite (all remaining suite levels joined by ``.``).
    """
    parts = full_name.split(".")[:-1]
    if not parts:
        return []
    labels = []
    if len(parts) >= 3:
        labels.append(Label(name=LabelType.PARENT_SUITE, value=parts.pop(0)))
    labels.append(Label(name=LabelType.SUITE, value=parts.pop(0)))
    if parts:
        labels.append(Label(name=LabelType.SUB_SUITE, value=".".join(parts)))
    return labels


def tag_labels_and_links(
    tags,  # noqa: ANN001 - RF tags collection
    issue_pattern: str | None = None,
    link_pattern: str | None = None,
) -> tuple[list[Label], list[Link]]:
    """Map Robot tags to de-duplicated Allure labels and links via ``parse_tag``."""
    labels: list[Label] = []
    links: list[Link] = []
    for tag in map(str, tags):
        parsed = parse_tag(tag, issue_pattern=issue_pattern, link_pattern=link_pattern)
        if isinstance(parsed, Link):
            links.append(parsed)
        else:
            labels.append(parsed)
        legacy = _legacy_link(tag)
        if legacy is not None:
            links.append(legacy)
    return labels_set(labels), links


def _legacy_link(tag: str) -> Link | None:
    prefix, separator, value = tag.partition(":")
    if not separator or prefix not in _LEGACY_LINK_TYPES:
        return None
    value = value or "unknown"
    name = value
    match = _LEGACY_LINK_NAME.search(value)
    if match:
        name = match.group(1)
        value = value[match.end() :]
    return Link(type=prefix, url=value, name=name)
