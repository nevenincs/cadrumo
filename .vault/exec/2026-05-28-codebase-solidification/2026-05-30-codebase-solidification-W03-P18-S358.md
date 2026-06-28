---
step_id: S358
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
---

# codebase-solidification W03.P18 — decimal canonical enrollment (S358–S368)

## Steps closed

S358, S359, S360, S361, S362, S363, S364, S365, S366, S367, S368

## Summary

Enrolled all in-scope inline quantize and bare Decimal(str()) sites into
the canonical helpers from aeat.domain.fincas._rounding and aeat.core.decimal.

### quantize migrations (_round_to_cents) — S358–S363

- `entrypoints/cli/_modelo.py` (S358): 4 sites (lines 2527, 2598, 2600–2601, 2604).
  Note: changes were already present in HEAD from a prior agent commit.
- `application/invoices/_projection.py` (S359): 1 site (line 124).
- `domain/calculations/registry/_formula_runtime.py` (S360): 1 site in `_apply_rounding` money-2 branch.
- `domain/iva/_prorrata.py` (S361): 1 site (line 430); rounding now explicit ROUND_HALF_UP.
- `adapters/outbound/aeat/export/_formats/_deserialise.py` (S362): 2 sites (lines 100, 110).
- `adapters/outbound/aeat/export/_formats/_record_spec.py` (S363): 1 site (line 316).

### coerce_decimal migrations — S364–S367

- `application/review/_edit.py` (S364): removed `Decimal(clause.raw_value)` reimpl; regex guard preserved; local `_coerce_decimal` wrapper now calls canonical `coerce_decimal`.
- `domain/calculations/registry/_schema.py` (S365): removed `Decimal(value)` reimpl; `bool|float` rejection preserved; `_coerce_decimal` BeforeValidator now delegates to `coerce_decimal`.
- `adapters/inbound/financial/providers/_base.py` (S366): float branch now calls `coerce_decimal(value)` with explicit None guard.
- `application/overview/__init__.py` (S367): `_to_decimal` closure now calls module-level `_coerce_decimal` alias.

### Inventory test — S368

Added `src/aeat/test_decimal_enrollment_inventory.py` with two tests:
- `test_no_inline_quantize_round_half_up`: asserts zero quantize(Decimal("0.01"), ROUND_HALF_UP) in production (excluding canonical module).
- `test_no_bare_decimal_str_coercion`: asserts no new Decimal(str()) coercions beyond declared DECIMAL_STR_PENDING (11 pre-existing follow-up sites).

## Collision check

`git diff` on all target files before first edit: no WIP from other agents.
`_modelo.py` S358 changes were already present in HEAD from a peer commit.

## Pytest outcome

- Inventory test: 2 passed.
- application/review/, application/invoices/, domain/iva/, adapters/outbound/aeat/export/: 601 passed, 2 skipped (excluding pre-existing `test_modelo_303_golden_sha_fichero_boe` failure).
- application/overview/: 132 passed.
- domain/calculations/registry/ formula/runtime tests: 139 passed (3 pre-existing catalogue coverage failures excluded).

## Commit SHAs

- `8ed77b08a` — W03.P18.S359-S368: decimal canonical enrollment
- `098da3776` — vault(plan): close W03.P18.S358-S368 decimal canonical enrollment

## Code review

Self-review passed all six standing gates (G1–G6). No naked env reads,
no shims, no tautological tests, no locale yml edits, no missing tr() calls.
