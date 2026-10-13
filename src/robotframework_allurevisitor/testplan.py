"""Pre-run modifier selecting tests from an Allure test plan.

Use ``--prerunmodifier robotframework_allurevisitor.testplan`` with
``ALLURE_TESTPLAN_PATH`` pointing at the plan JSON. Tests are kept when their
``allure.id`` tag matches an entry ``id`` or their full name matches an entry
``selector``; suites left without tests are removed. Without a plan, nothing
changes.
"""

from __future__ import annotations

from allure_commons.types import LabelType
from allure_commons.utils import get_testplan
from robot.api import SuiteVisitor

from robotframework_allurevisitor._labels import tag_labels_and_links


class testplan(SuiteVisitor):  # noqa: N801 - Robot uses the class named like its module
    def __init__(self) -> None:
        plan = get_testplan()
        self.active = bool(plan)
        self.ids = {str(item["id"]) for item in plan if "id" in item}
        self.selectors = {item["selector"] for item in plan if "selector" in item}

    def start_suite(self, suite) -> None:  # noqa: ANN001
        if self.active:
            suite.tests = [test for test in suite.tests if self._selected(test)]

    def end_suite(self, suite) -> None:  # noqa: ANN001
        if self.active:
            suite.suites = [child for child in suite.suites if child.test_count > 0]

    def visit_test(self, test) -> None:  # noqa: ANN001
        """Tests need no visiting; selection happens per suite."""

    def _selected(self, test) -> bool:  # noqa: ANN001
        labels, _ = tag_labels_and_links(test.tags)
        allure_ids = {str(label.value) for label in labels if label.name == LabelType.ID}
        full_name = getattr(test, "full_name", None) or test.longname
        return bool(allure_ids & self.ids) or full_name in self.selectors
