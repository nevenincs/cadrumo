---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S07'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate

## Scope

- `src/cadrumo/application/filing/_export.py`

## Description

- Imported `CasillaCollection` from `...domain.filing` in `_export.py`.
- Added `required_applicable_casilla_ids(manifest, *, collection, representable) -> frozenset[CasillaId]` as a public function in `_export.py`, documenting it as the single required-set authority.
- Modified `assert_export_mirrors_manifest` to call `required_applicable_casilla_ids` instead of inlining the set comprehension.
- Added `required_applicable_casilla_ids` to `_export.py`'s `__all__`.
- Added `required_applicable_casilla_ids` to the application `filing` facade import and `__all__`.

## Outcome

`required_applicable_casilla_ids` is the single derivation authority for the required-applicable casilla set. `assert_export_mirrors_manifest` delegates to it. The function is exported through the `application.filing` public facade. Commit: `9c64ec0d99`.

Gates: `ruff check` clean; `pyright` 0 errors; 12 tests in the two filing test modules pass.

## Notes

S07 and S08 land in the same commit (`9c64ec0d99`) because the test re-pointing (S08) depends on the extraction (S07) — they share one atomic pathspec commit per the plan's coupling guidance.
