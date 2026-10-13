## MODIFIED Requirements

### Requirement: Release documentation

The documentation SHALL present the package for public consumption: `README.md` SHALL include install-from-PyPI instructions, document both entry points (the `rf-allure` converter and the `robotframework_allurevisitor.Listener` listener), link to the migration guide from `allure-robotframework`, and render correctly as the PyPI long description; a `CHANGELOG.md` SHALL record each release, including the `0.1.0` release.

#### Scenario: README is PyPI-ready
- **WHEN** `README.md` is inspected
- **THEN** it documents `pip install robotframework-allurevisitor` and is referenced as the package `readme`

#### Scenario: Changelog records the release
- **WHEN** `CHANGELOG.md` is inspected
- **THEN** it contains a `0.1.0` entry describing the initial release

#### Scenario: README documents the listener and migration
- **WHEN** `README.md` is inspected
- **THEN** it shows `--listener robotframework_allurevisitor.Listener` usage and links to the migration guide from `allure-robotframework`
