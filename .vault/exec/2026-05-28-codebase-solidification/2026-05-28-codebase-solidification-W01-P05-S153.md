---
step_id: S153
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S153 — canonicalize `_coerce_decimal`

## Outcome

Created `src/aeat/core/decimal/_coerce.py` with the canonical
`coerce_decimal(value, *, default=None) -> Decimal | None` helper.
Exported via `src/aeat/core/decimal/__init__.py`.
Deleted three local copies and migrated all call-sites.

## Variant analysis

| Site | Signature | Return | Usage pattern |
|---|---|---|---|
| `_calc_sheets_pull.py:318` | `(raw: Any) -> Decimal \| None` | nullable, no default | Callers check `if coerced is not None` |
| `_row_set_assembly.py:173` | `(value, *, default: Decimal) -> Decimal` | always Decimal | Required `default=Decimal("0")` on every call |
| `_models.py:93` | `(value: object) -> Decimal` | strict, raises `TypeError` | Pydantic model-validator; pydantic now raises `ValidationError` on `None` |

## Canonical signature reasoning

`coerce_decimal(value, *, default: Decimal | None = None) -> Decimal | None`

One default keyword covers all three: pass nothing for nullable-cell
(returns `None`), pass `Decimal("0")` for aggregation (always returns
`Decimal`), and let pydantic reject `None` for strict-validator callers.
The behavior change in `_models.py` is a net improvement: pydantic's
`ValidationError` is more informative than the raw `TypeError` that
the old implementation raised.

## Files touched

- `src/aeat/core/decimal/_coerce.py` — created (canonical helper)
- `src/aeat/core/decimal/__init__.py` — added `coerce_decimal` export
- `src/aeat/adapters/outbound/google/_calc_sheets_pull.py` — removed local def, added import, updated 2 call-sites
- `src/aeat/application/calculations/_row_set_assembly.py` — removed local def + `InvalidOperation` import, added import, updated 9 call-sites
- `src/aeat/domain/invoices/_models.py` — removed local def, added import, updated 3 call-sites
- `src/aeat/application/calculations/test_row_set_assembly_coercion.py` — updated import to canonical

## Tests

`uv run --no-sync pytest src/aeat/core/decimal/ src/aeat/domain/invoices/ src/aeat/application/calculations/test_row_set_assembly_coercion.py src/aeat/application/calculations/test_row_set_assembly.py` — all passed.
