"""Suite labels and tag/link mapping follow allure-robotframework."""

from __future__ import annotations

import pytest

from robotframework_allurevisitor._labels import suite_labels, tag_labels_and_links


def _pairs(labels):
    return [(label.name, label.value) for label in labels]


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("S1.T", [("suite", "S1")]),
        ("S1.S2.T", [("suite", "S1"), ("subSuite", "S2")]),
        ("Root.Mid.Leaf.T", [("parentSuite", "Root"), ("suite", "Mid"), ("subSuite", "Leaf")]),
        ("A.B.C.D.T", [("parentSuite", "A"), ("suite", "B"), ("subSuite", "C.D")]),
    ],
)
def test_suite_labels_match_listener(full_name, expected):
    assert _pairs(suite_labels(full_name)) == expected


def test_legacy_link_tags():
    _, links = tag_labels_and_links(
        ["issue:[Bug 7]https://tracker/7", "tms:T-1", "link:[Docs]https://docs", "other"]
    )
    assert [(link.type, link.name, link.url) for link in links] == [
        ("issue", "Bug 7", "https://tracker/7"),
        ("tms", "T-1", "T-1"),
        ("link", "Docs", "https://docs"),
    ]


def test_allure_tags_and_dedup():
    labels, links = tag_labels_and_links(
        [
            "allure.severity:minor",
            "allure.severity:critical",
            "allure.feature:F",
            "allure.feature:F",
            "allure.issue:ABC-1",
            "smoke",
        ]
    )
    pairs = _pairs(labels)
    # Unique labels keep the last value; duplicate (name, value) pairs collapse.
    assert pairs.count(("feature", "F")) == 1
    assert [p for p in pairs if p[0] == "severity"] == [("severity", "critical")]
    assert ("tag", "smoke") in pairs
    assert [(link.type, link.url) for link in links] == [("issue", "ABC-1")]
