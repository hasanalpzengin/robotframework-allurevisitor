"""Generate Allure input files from Robot Framework results.

Two entry points share one Robot -> Allure mapping:

- ``generate()`` / the ``rf-allure`` CLI post-process existing ``output.xml``
  files with the Robot Framework ``ResultVisitor`` API;
- ``Listener`` (``robot --listener robotframework_allurevisitor.Listener``)
  writes results during a run and adds runtime-only data (``allure.attach``,
  ``allure.dynamic``, ``allure.step``), replacing ``allure-robotframework``.
"""

from robotframework_allurevisitor.listener import Listener
from robotframework_allurevisitor.visitor import AllureResultVisitor, generate

__all__ = ["AllureResultVisitor", "Listener", "generate"]
