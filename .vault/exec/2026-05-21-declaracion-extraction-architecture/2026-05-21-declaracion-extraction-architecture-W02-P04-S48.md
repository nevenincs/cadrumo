---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P04.S48'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W02.P04.S48`

Validator text-casilla gate: the snapshot-build validator rejects a
`declaracion_pdf` profile targeting a `data_type="text"` casilla without
`named_label` strategy. Covers steps S15, S16, S17, S47, S48.

- Modified: `src/aeat/domain/calculations/registry/_validate_references.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

`_IdReferenceChecker` gains `casilla_data_types: dict[str, str]` populated
from `{c.id: c.data_type for c in revision.casillas}` in `__init__`.

`_check_extraction_profile_refs` updated to extract `.casilla_id` from each
`ExtractionTargetDefinition`: `target_ids = tuple(t.casilla_id for t in profile.target_casillas)`.

`_check_text_casilla_strategy` added after `_check_extraction_profile_refs`:
iterates `profile.target_casillas`, looks up `data_type` from
`checker.casilla_data_types`, and appends a failure when a `text`-typed
casilla uses any strategy other than `named_label`.

`_validate_extraction_profile_section` in `_validate.py` updated to
extract `target_casilla_ids` via `tuple(t.casilla_id for t in profile.target_casillas)`.

Collision check on `_validate_references.py` via `git diff` showed no non-authored WIP.

Tests added to `test_referential_integrity.py`:
- `test_text_casilla_without_named_label_strategy_fails_gate` — proves the
  gate fails loud on a `declaracion_pdf` profile with a `text`-typed casilla
  using `numeric_casilla` strategy.
- `test_text_casilla_with_named_label_strategy_passes_gate` — proves a
  correctly-formed `named_label` target passes the gate.

## Tests

`uv run pytest -q src/aeat/domain/calculations/registry/test_referential_integrity.py` passed with 49 tests in 48.3s.
