---
step_id: S53
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W03.P12.S53 — delete CLI registry private-regex import

## Scope

Delete the `from ...domain.calculations.registry._ids import
_CASILLA_RE, _REF_RE` import in `src/aeat/entrypoints/cli/_modelo.py`
per ADR Rule 8 and switch the CLI input-validators
`_validate_binding_key` and `_validate_casilla_key` to consume the
registry public aliases `BindingId` and `CasillaId` via pydantic
`TypeAdapter`. The registry's public alias contract (not the
private regex constants) is the contract the CLI now relies on.

## Outcome

`src/aeat/entrypoints/cli/_modelo.py`:
- Import line replaced with
  `from ...domain.calculations.registry._ids import BindingId, CasillaId`.
- Module-level `_BINDING_ID_ADAPTER` and `_CASILLA_ID_ADAPTER`
  TypeAdapters declared once.
- `_validate_binding_key` and `_validate_casilla_key` invoke
  `TypeAdapter.validate_python(key)` inside a `try/except
  ValidationError -> typer.BadParameter` shell, preserving the
  user-facing error envelope and the i18n translation key.

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py
  -k "casilla_override or binding_override"` returns `14 passed`.

## Plan steps closed

`W03.P12.S53`.
