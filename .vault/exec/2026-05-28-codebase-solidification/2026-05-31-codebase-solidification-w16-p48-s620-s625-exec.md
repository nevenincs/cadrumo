---
step_id: "S620,S621,S622,S623,S624,S625"
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W16.P48 S620-S625 — boundary type-narrowing + canonical extraction

## Steps closed

S620, S621, S622, S623, S624, S625

## Commit

`6ad580faa` — `solidification(W16.P48.S620-S625): boundary type-narrowing + canonical extraction`

## Collision signal

Clean — zero non-authored WIP on all 7 target files at start of session.

## Files touched

- `src/aeat/core/identity/_documents.py` — S620: `IdentityError` now inherits `ValueError` so pydantic `AfterValidator` wraps it directly.
- `src/aeat/core/identity/__init__.py` — S620: Removed re-raise shim; `_subject_tax_id_validator` now delegates directly to `validate_spanish_tax_id`.
- `src/aeat/domain/calculations/registry/_validate_cross_revision.py` — S621: `raise ValueError(` replaced with `raise RegistryValidationError(` (already imported).
- `src/aeat/domain/calculations/registry/_validate_revision_context.py` — S622: All 17 `dict[str, Any]` fields narrowed to concrete schema types; `construct_member_objects` return type replaced with typed union.
- `src/aeat/core/external_constants.py` — S623: `ANY-RETURN-RATIONALE-PRE303-RAW-STAGING` marker added inline on `pre303_raw`.
- `src/aeat/application/invoices/_importing.py` — S624: `ANY-RETURN-RATIONALE-INVOICE-PARSE-STAGING` marker added (>3 test callers block typed-model refactor).
- `src/aeat/domain/transactions/_models.py` — S625: Import and use `CLASSIFIED_BY_MANUAL` constant; removes bare `"manual"` literal.

## S624 design choice

Marker path chosen. `_synthesise_single_line_if_needed` has 7 call sites in the test module (`test_importing_helpers.py`) plus 1 production call. Introducing a typed intermediate would require updating >3 callers. The `InvoiceRowPayload` `TypedDict` already governs field names at the decode boundary; the `dict` mutation for line-synthesis back-fill is a parse-stage slot. Marker documents this rationale inline.

## Grep post-conditions

- S620: zero `raise ValueError(` in `src/aeat/core/identity/` — PASS
- S621: zero `raise ValueError(` in `_validate_cross_revision.py` — PASS
- S622: zero `dict[str, Any]` in `_validate_revision_context.py` — PASS
- S625: zero bare `"manual"` in `transactions/_models.py` — PASS

## Pytest outcomes

| Scope | Result |
|---|---|
| `src/aeat/core/identity/` | 54 passed |
| `src/aeat/domain/calculations/registry/` (cross-revision + context) | 29 passed |
| `src/aeat/application/invoices/` | 54 passed |
| `src/aeat/domain/transactions/` | 81 passed |
