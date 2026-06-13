---
step_id: S170
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S170 — CasillaFieldKind tests

## Outcome

Extended `src/aeat/domain/calculations/registry/test_schema.py` with 8 new tests:

- `test_casilla_field_kind_members_have_expected_values` — asserts each of 8 members
  carries the TOML-authoritative string value.
- `test_casilla_field_kind_is_str` — asserts all members are `str` instances.
- `test_export_field_roundtrip_valid_casilla_field_kind` (parametrized, 4 cases) —
  `ExportFieldDefinition` accepts each member as raw string and round-trips via
  `model_dump()`. ID fixtures use lowercase pattern `f001` to satisfy `ExportFieldId`
  regex.
- `test_export_field_rejects_unknown_kind` — unknown token raises `ValidationError`.
- `test_export_field_rejects_empty_string_kind` — empty string raises `ValidationError`.
- `test_export_field_rejects_numeric_kind` — numeric value raises `ValidationError`.

19 tests in `test_schema.py` pass (11 pre-existing + 8 new). Full suite 282 passing.

## Commit

`8381a5f9a`
