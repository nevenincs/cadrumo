---
step_id: S02
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W01.P01.S02 — fix _parse_decimal argument order in _export_parse.py

## Scope

FIX-002: `_parse_decimal` in `domain/calculations/registry/_export_parse.py` declared
`(field: ExportFieldDefinition, raw: str)` while every other `_parse_decimal` in the
codebase uses `(raw, ...)` first. Any positional caller silently passed the
`ExportFieldDefinition` object as the decimal string and the raw value as the field
context, causing silent data corruption on decimal BOE export fields.

Swap the signature to canonical `(raw: str, field: ExportFieldDefinition)` and update
the one positional call site in `_parse_field_value` at line 372. No wrapper or shim
introduced.

## Outcome

- `_export_parse.py` line 402: signature is now `_parse_decimal(raw: str, field: ExportFieldDefinition) -> Decimal`.
- `_export_parse.py` line 372: caller updated to `_parse_decimal(raw, field)`.
- `test_export_parse.py`: two regression tests added:
  - `test_parse_decimal_raw_first_yields_correct_value`: `_parse_decimal("3005,06", field)` → `Decimal("3005.06")`.
  - `test_parse_decimal_invalid_raw_includes_field_id_in_error`: invalid raw raises `RegistryValidationError` with `"casilla.0501"` in message.
- Positional caller count changed: 1 site (line 372 in `_parse_field_value`). No external callers of this module-private function exist.

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_export_parse.py -x -q`

40 passed in 0.17s.

## Commit

`cebf206ad` — fix(registry): swap _parse_decimal argument order to (raw, field) (W01.P01.S02)
