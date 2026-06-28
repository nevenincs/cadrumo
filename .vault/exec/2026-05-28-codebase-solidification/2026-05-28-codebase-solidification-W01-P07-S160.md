---
step_id: S160
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P07-S159]]"
---

# codebase-solidification W01.P07.S160 — InputKind real-behaviour tests

## Outcome

`src/aeat/domain/calculations/registry/test_schema.py` created with 10
real-behaviour tests (markers: `unit`, `domain_model`):

- `test_input_kind_members_have_expected_values` — each member equals its TOML string literal.
- `test_input_kind_is_str` — every member is a `str` instance (StrEnum transparency).
- `test_casilla_roundtrip_valid_input_kind[manual/bound/computed/informational]` —
  constructor accepts string literals (TOML-ingest path); `model_dump` returns
  the plain string; field carries the typed `InputKind` member at runtime.
- `test_casilla_rejects_unknown_input_kind` — `ValidationError` on `"garbage"`.
- `test_casilla_rejects_empty_string_input_kind` — `ValidationError` on `""`.
- `test_casilla_rejects_numeric_input_kind` — `ValidationError` on `42`.
- `test_casilla_default_input_kind_is_manual` — omitting `input_kind` defaults to `MANUAL`.

No mocks, no skips, no xfail, no tautological assertions.

## Files touched

- `src/aeat/domain/calculations/registry/test_schema.py` (new)

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_schema.py -xvs` → 10 passed
- `uv run --no-sync pyright src/aeat/domain/calculations/registry/test_schema.py` → 0 errors
- Commit: `1bff7b70f`
