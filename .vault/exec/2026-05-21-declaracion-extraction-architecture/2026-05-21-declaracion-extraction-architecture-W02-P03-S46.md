---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P03.S46'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W02.P03.S46`

Parser match-strategy branch: `_find_casilla_hits` branches on
`match_strategy`; numeric path left byte-for-byte unchanged; named-label
path anchors on the printed label via `TEXT_VALUE_GROUP`. Covers steps
S11, S12, S13, S14, S45, S46.

- Modified: `src/aeat/adapters/inbound/declaracion/_parser.py`
- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- Modified: `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`

## Description

`_find_casilla_hits` now receives a full `ExtractionTargetDefinition` record
rather than a bare `CasillaId`. Branching on `match_strategy`:

- `numeric_casilla`: uses the existing `SPANISH_AMOUNT_GROUP` pattern
  anchored to the numeric casilla label — behaviour identical to before.
- `named_label`: uses `TEXT_VALUE_GROUP` anchored to `target.label_pattern`
  (or falls back to `re.escape(target.casilla_id)` when no pattern).

`_extract_profile_values` iterates `ExtractionTargetDefinition` records,
branches on `value_kind` for the `ExtractedCasilla` construction.

`modelo_100_summary_v2025.py` updated: `target_casillas` set comprehension
replaced with `{t.casilla_id for t in extraction_profile.target_casillas}`.

Collision check on `_parser.py` via `git diff` showed no non-authored WIP.

## Tests

`uv run pytest -q src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py` passed with 18 tests.
