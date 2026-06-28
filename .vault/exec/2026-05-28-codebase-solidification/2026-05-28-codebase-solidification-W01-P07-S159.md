---
step_id: S159
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P07.S159 — promote InputKind to StrEnum

## Outcome

`InputKind` promoted from a module-local `Literal` alias in `_modelo.py` to a
`StrEnum` in the registry's canonical schema authority (`_schema.py`).

Members: `MANUAL = "manual"`, `BOUND = "bound"`, `COMPUTED = "computed"`,
`INFORMATIONAL = "informational"`. Each carries its TOML-authoritative string
value for transparent serialisation.

`InputKindValue = Annotated[InputKind, BeforeValidator(_coerce_input_kind)]`
introduced so `CasillaDefinition.input_kind` accepts plain strings from TOML
ingestion (loader uses `model_validate` with string payloads) while the field
type is always the typed enum at runtime. The coercion raises
`RegistryValidationError` for non-members.

`CasillaDefinition.input_kind` field changed from
`Literal["manual", "bound", "computed", "informational"] = "manual"` to
`InputKindValue = InputKind.MANUAL`.

Both `InputKind` and `InputKindValue` exported from `registry/__init__.py`.

The `InputKind = Literal[...]` alias in `_modelo.py` is left for S161.

## Files touched

- `src/aeat/domain/calculations/registry/_schema.py` — added `InputKind`,
  `_coerce_input_kind`, `InputKindValue`; updated `CasillaDefinition.input_kind`.
- `src/aeat/domain/calculations/registry/__init__.py` — exported `InputKind`,
  `InputKindValue`.

## Verification

- `uv run --no-sync pyright src/aeat/domain/calculations/registry/_schema.py` → 0 errors
- 59/60 registry tests pass (1 pre-existing coverage gap unrelated to this change)
- Commit: `1bff7b70f`
