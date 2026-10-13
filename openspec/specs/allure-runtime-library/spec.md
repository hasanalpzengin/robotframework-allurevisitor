# allure-runtime-library Specification

## Purpose

Offer Robot Framework keywords for adding attachments and global attachments or errors to Allure results during a run, compatible with the keywords of upstream `AllureLibrary`.

## Requirements

### Requirement: Attachment keywords

The package SHALL provide a keyword library importable as `Library    robotframework_allurevisitor.AllureLibrary` with keywords `Attach    data    name=None    attachment_type=None    extension=None` and `Attach File    source    name=None    attachment_type=None    extension=None`. `attachment_type` SHALL accept an `allure_commons.types.AttachmentType` member name (for example `PNG`, `JSON`, `TEXT`) or a literal MIME type. With the listener active, the attachment SHALL be added to the step of the calling keyword.

#### Scenario: Attach text from Robot
- **WHEN** a test runs `Attach    hello    name=greeting    attachment_type=TEXT` with the listener active
- **THEN** the `Attach` step has a `text/plain` attachment named `greeting` containing `hello`

#### Scenario: Attach a file with a literal MIME type
- **WHEN** a test runs `Attach File    trace.zip    attachment_type=application/vnd.allure.playwright-trace`
- **THEN** the attachment type is `application/vnd.allure.playwright-trace`

#### Scenario: Listener not active
- **WHEN** the keywords run without the listener
- **THEN** they pass without error and produce no files

### Requirement: Global keywords

The library SHALL provide `Global Attach`, `Global Attach File`, and `Global Error    message    trace=None`, which produce Allure globals entries when the listener is active.

#### Scenario: Global attachment
- **WHEN** a suite setup runs `Global Attach    build-info    name=build`
- **THEN** a `*-globals.json` file references an attachment named `build`
