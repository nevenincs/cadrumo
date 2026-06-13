---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S402'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W14.P29.S402`

Populated 6 optional `ModeloDraft` fields with non-default values in both roundtrip test fixtures and added 6 parametrized anti-tautology field-drop proof cases.

- Modified: `src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- Modified: `src/aeat/domain/filing/test_roundtrip_anti_tautology.py`

## Description

Per the roundtrip-discipline rule, every defaultable field must carry a non-default value in fixtures so a save-drops-field / load-re-defaults-field regression cannot pass vacuously.

The `_populated_draft()` helper in both test files previously omitted 6 optional fields, leaving them at pydantic defaults: `casilla_provenance=()`, `notes=""`, `approved_at=None`, `approved_by=None`, `review_checksum=None`, `approval_basis=None`.

Both helpers were updated to carry:

- `casilla_provenance`: one `ModeloCasillaProvenance` entry (`casilla_id="iva.devengado"`, `legal_refs=("LIVA.art-92",)`, `source_refs=("AEAT.IVA.2025.casilla-01",)`)
- `notes`: `"Draft pending operator review"`
- `approved_at`: `datetime(2026, 5, 25, 14, 30, tzinfo=UTC)`
- `approved_by`: `"operator-reviewer-1"`
- `review_checksum`: `"a" * 64` (64-char deterministic hex literal)
- `approval_basis`: a `ModeloApprovalBasis` with all five fingerprint fields set to distinct repeated-char 64-char strings

Per-field witness assertions were also added to `test_filing_draft_survives_encrypted_storage_roundtrip` to enable immediate diagnosis on regression.

The anti-tautology file received a new `@pytest.mark.parametrize` test (`test_boundary_catches_optional_field_drop`) with one case per field. Each case deletes the field key from the on-disk JSON envelope and asserts either `ValidationError` or strict inequality — proving the boundary surfaces data loss for every field rather than re-defaulting silently.

## Outcome

- 9 tests pass (`src/aeat/domain/filing/` suite: 11 total including 2 pre-existing amendment roundtrip tests)
- Ruff: all checks passed
- Plan step `W14.P29.S402` closed
