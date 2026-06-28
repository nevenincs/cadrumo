---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S16'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P06.S16`

Split the largest remaining snapshot reference section walkers out of the
orchestration module without changing registry schema semantics or diagnostics.

- Modified: `src/aeat/domain/calculations/registry/_validate_references.py`
- Created: `src/aeat/domain/calculations/registry/_validate_reference_sections.py`
- Modified: `.vault/plan/2026-05-22-schema-hardening-plan.md`

## Description

The reference validator now keeps `_check_all_id_references` as the snapshot
entrypoint and delegates construct, dependency-classification, algorithm,
export-layout, and binding-selector reference walks to
`_validate_reference_sections.py`.

The module-size baseline improved from `_validate_references.py` at 312 lines
to `_validate_references.py` at 228 lines plus
`_validate_reference_sections.py` at 94 lines. The extracted helpers are
mechanical moves of the previous logic and preserve the same accumulated
failure messages.

## Tests

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_references.py src/aeat/domain/calculations/registry/_validate_reference_sections.py`
passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_referential_integrity.py`
passed with 71 tests.
