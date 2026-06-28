---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S151
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S151 — consolidate `_format_decimal` into `aeat.core.decimal._format`

## Outcome

Created `src/aeat/core/decimal/__init__.py` and `src/aeat/core/decimal/_format.py`
with `format_decimal(value, *, normalize, none_value)` as the canonical implementation.
Deleted all four local copies. Migrated three existing helper-tests to import from
the canonical path.

## Behavioural variants found

| Source | None handling | Normalize | Extra logic |
|---|---|---|---|
| `_censo_live.py` | not accepted | yes | caller adds `.00` if no dot |
| `_reconcile.py` | not accepted | no | plain `format(value, "f")` |
| `_projection.py` | None → `"0"` | yes | none |
| `_translator.py` | not accepted | no | empty-string guard (dead) |

Resolution: canonical function accepts `none_value: str | None = None`
(None = reject None input) and `normalize: bool = False`. The `_censo_live`
caller's `.00` suffix logic remains inline at call-site as it is display-specific.

## Files changed

- **Created**: `src/aeat/core/decimal/__init__.py`
- **Created**: `src/aeat/core/decimal/_format.py`
- **Deleted local copy + migrated**: `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`
- **Deleted local copy + migrated**: `src/aeat/application/filing/reconciliation/_reconcile.py`
- **Deleted local copy + migrated**: `src/aeat/application/invoices/_projection.py`
- **Deleted local copy + migrated**: `src/aeat/application/storage/calc_sheets/_translator.py`
- **Migrated imports**: `src/aeat/application/filing/reconciliation/test_reconcile_helpers.py`
- **Migrated imports**: `src/aeat/application/invoices/test_projection_format.py`

## Collision check

`git diff` on all four target files before edit returned empty — no non-authored WIP.

## Review gates (G1–G6)

All pass. No naked env reads, no pydantic boundary changes, no user-facing strings,
no locale edits, no shims introduced (all four copies deleted), no tautological tests.
