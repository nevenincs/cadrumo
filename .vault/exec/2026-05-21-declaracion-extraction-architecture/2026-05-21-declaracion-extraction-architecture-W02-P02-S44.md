---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P02.S44'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W02.P02.S44`

Schema extension: introduces `ExtractionTargetDefinition` and migrates
`ExtractionProfileDefinition.target_casillas` from flat `tuple[CasillaId, ...]`
to `tuple[ExtractionTargetDefinition, ...]`. Covers steps S06, S07, S08, S09,
S10, S42, S43, S44.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`

## Description

Added `ExtractionTargetDefinition` — a strict, frozen, `extra="forbid"`
`RegistryModel` — carrying `casilla_id: CasillaId`,
`match_strategy: Literal["numeric_casilla", "named_label"]`,
`value_kind: Literal["amount", "text", "enum"]`, and
`label_pattern: str | None = None`.

A `model_validator` (`_label_pattern_matches_strategy`) enforces:
- `named_label` targets require `label_pattern` (non-empty string)
- `numeric_casilla` targets must not define `label_pattern`

`ExtractionProfileDefinition.target_casillas` was restructured from
`tuple[CasillaId, ...]` to `tuple[ExtractionTargetDefinition, ...]`.
The `_tuple_values_unique` validator was split into
`_accepted_artefact_kinds_unique` and `_target_casillas_unique`, the
latter keying on `.casilla_id`.

`ExtractionTargetDefinition` was added to `__init__.py` `__all__`.

Tests added: `test_extraction_target_definition_roundtrip`,
`test_extraction_target_definition_anti_tautology`,
`test_extraction_target_named_label_requires_label_pattern`,
`test_extraction_target_numeric_casilla_rejects_label_pattern`,
`test_extraction_profile_target_casillas_uniqueness_rejects_duplicate_casilla_id`.

## Tests

`uv run pytest -q src/aeat/domain/calculations/registry/test_registry_schema.py` passed with 120 tests in 58.6s.

Collision check on `_schema.py` via `git diff` showed no non-authored WIP.
