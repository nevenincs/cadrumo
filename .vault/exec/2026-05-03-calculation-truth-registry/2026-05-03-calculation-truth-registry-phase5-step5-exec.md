---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step5`

Removed public domain filing exports for legacy Python filing builders and the
application-level quarterly 303 builder input key.

- Modified: `src/aeat/domain/filing/__init__.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/_complementaria.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `tests/import_contract/test_registry_deletion_gates.py`

## Description

`aeat.domain.filing` no longer imports `aeat.domain.filing._builders` as part
of package import and no longer exposes `get_builder`, concrete model builder
classes, or `QUARTERLY_303_INPUT_KEY` through `__all__`.

`aeat.application.filing` no longer imports or exports the quarterly 303
builder input key, and complementaria construction now delegates directly to
the registry-gated `build_draft` path instead of enforcing a legacy
Modelo 390-specific builder input shape before the validated snapshot boundary.

The remaining direct importability of `aeat.domain.filing._builders` is
recorded as the next Phase 5 residual and is outside this public facade slice.

## Tests

Verified with targeted `ruff check`, `ty check`, focused filing tests, and the
application filing slice. The application filing slice passed 206 tests with
4 pre-existing skipped reconciliation tests.

Review evidence is recorded in
`2026-05-03-calculation-truth-registry-phase5-step5-review`.
