---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:17a698de8ebc187ebd0a75611565ce4888e140db121baf8ee4b8b1d4169c8c6a'
step_id: 'S43'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Correct Modelo 038 source-era scope: retain the 2024 dr038 design only from the June 2024 declaration, acquire and hash-pin an earlier official design before asserting the 2002-to-May-2024 window, and split the revision or source binding through the validated temporal authority without guessed coverage, legacy fallback, a filing-grade promotion, or an export layout.

## Scope

- `src/cadrumo/_data/registry/aeat/legal/modelo-038.toml`
- `src/cadrumo/_data/registry/aeat/modelos/038/revisions/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/`
- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py`

## Description

- Retain the canonical, hash-pinned AEAT `dr038_2005.pdf` inspection receipt outside the modelo and revision source graphs because its official evidence does not state a complete filing-period applicability window.
- Declare its unique `record_design_epoch` as `2012`, grounded by the official bundled manifest title ("actualizado a 18/01/2012") and the byte-pinned PDF metadata, without inferring an `applies_from` or `applies_to` value.
- Prove the exact binary still verifies by byte count and SHA-256, while `resolve_record_design_binary` refuses selection for filing year 2012 because the source deliberately lacks `applies_from`.
- Preserve M038's June 2024 source cutover, inspection-only grade, and absence of export layout.

## Outcome

- The historical PDF remains 79,486 bytes with SHA-256 `e9008d9c0c407c76143d6997f3a5fb52a2a482c40571f395da7dcf8a8fee3d9d`; its 2012 epoch identifies the official document era only, not a claim of temporal applicability.
- M038 continues to refuse all periods before June 2024, selects the 2024 design only from June 2024 onward, and remains inspection-only/non-fileable.

## Verification

- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py` - 30 passed.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_record_design.py src/cadrumo/domain/calculations/registry/tests/test_cited_design_field_bounds_are_self_consistent.py -k '038 or record_design'` - 81 passed, 3 deselected.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_record_design_source_selection.py` - 22 passed.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_record_design_epoch_convention.py` - 9 passed.
- `uv run --no-sync ruff format --check ...` and `uv run --no-sync ruff check ...` - passed.

## Notes

- The official index title and PDF metadata establish document-era identity only; neither supports a complete filing-period window, so no revision citation, applicability expansion, grade promotion, or export layout was authored.
