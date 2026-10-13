## Purpose

Let Allure test plans (for example from Allure TestOps reruns) choose which Robot Framework tests run, compatible with the upstream `allure_robotframework.testplan` pre-run modifier.

## ADDED Requirements

### Requirement: Test plan selection

The package SHALL provide a pre-run modifier usable as `--prerunmodifier robotframework_allurevisitor.testplan` that reads the Allure test plan JSON from the path in `ALLURE_TESTPLAN_PATH` and keeps only tests whose `allure.id` tag value matches an entry `id` or whose full name matches an entry `selector`, removing suites left without tests. When the variable is unset or the plan is empty, the modifier SHALL leave the suite unchanged.

#### Scenario: Select by allure.id
- **WHEN** the plan contains `{"id": "42"}` and only test `A` has tag `allure.id:42`
- **THEN** only test `A` runs

#### Scenario: Select by full name
- **WHEN** the plan contains `{"selector": "Root.Suite.Test B"}`
- **THEN** only `Root.Suite.Test B` runs

#### Scenario: No plan
- **WHEN** `ALLURE_TESTPLAN_PATH` is not set
- **THEN** all tests run
