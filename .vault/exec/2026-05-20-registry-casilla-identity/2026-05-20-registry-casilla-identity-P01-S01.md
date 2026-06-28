---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S01'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---



# `registry-casilla-identity` `P01.S01`

Added the optional strict-pydantic `segmento` field to `CasillaDefinition`
in the registry schema, carrying the AEAT record-segment code for
multi-segment modelos.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`

## Description

`CasillaDefinition` gained an optional field
`segmento: str | None = Field(default=None, min_length=1, max_length=32)`,
placed directly after `number`. It carries the AEAT record-segment
identifier (e.g. `DP200014`) for multi-segment modelos and is left unset
for single-segment modelos.

The field uses the Spanish stem `segmento` rather than the bare English
noun `segment`, per the Spanish-stem terminology authority decision. The
`min_length` / `max_length` bounds keep an unset value distinct from an
empty string under the model's strict discipline; the AEAT `DPxxxxxx`
segment codes are short fixed-shape tokens well within the 32-character
bound.

The change is purely additive. `CasillaDefinition` inherits the
`RegistryModel` config (`strict=True`, `frozen=True`, `extra="forbid"`),
and the new field defaults to `None`, so every existing
`CasillaDefinition` whose `segmento` is unset validates unchanged. The
`_validate_input_kind` model-validator is untouched.

## Description (collision)

The shared-worktree collision check (`git diff` against
`_schema.py`) returned clean before the edit; no non-authored
uncommitted WIP was present.

## Tests

`uv run --no-sync ruff check` on `_schema.py` passed. The full registry
schema test module (`test_registry_schema.py`, 66 tests) passed against
the bundled registry corpus, confirming that the additive field does not
disturb any existing single-segment `CasillaDefinition` load or any
snapshot-build validator path.
