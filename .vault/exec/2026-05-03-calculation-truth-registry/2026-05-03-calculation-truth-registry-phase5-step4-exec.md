---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step4`

Disabled public application draft construction through legacy Python filing
builders.

- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_modelo_303_390.py`
- Modified: `src/aeat/application/filing/test_import.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `src/aeat/application/filing/_test_repository.py`
- Modified: `src/aeat/application/filing/_test_complementaria_repository.py`
- Modified: `tests/import_contract/test_registry_deletion_gates.py`

## Description

`aeat.application.filing.build_draft` now fails closed with a registry snapshot
requirement instead of resolving `get_builder` and dispatching the Modelo 130,
303, or 390 Python builders. The application package no longer exports those
legacy builder classes or `get_builder`.

The application filing tests were rewritten to assert the hard boundary while
retaining real validator checks over synthetic draft records. Justificante
import now proves parsed PDFs stop before draft reconstruction when no
validated registry snapshot exists.

Complementaria and repository tests were moved off `build_draft` and onto the
application test synthesis helper so persistence behaviour remains exercised
without restoring the legacy builder dispatch path.

## Tests

Verified with targeted `ruff check`, `ty check`, and the application filing
slice. The slice passed 205 tests with 4 pre-existing skipped reconciliation
tests, covering import-contract gates, build refusal, validator behavior,
review-status behavior, complementaria refusal, repository persistence,
Modelo 303/390 boundary tests, justificante import refusal, runtime
schema-provider refusal, and filing CLI fail-closed behavior.

Review evidence is recorded in
`2026-05-03-calculation-truth-registry-phase5-step4-review`.
