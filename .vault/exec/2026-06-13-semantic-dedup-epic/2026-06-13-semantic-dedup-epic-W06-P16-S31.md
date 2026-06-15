---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S31'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# A2 Replace the two zero-collapse canonical-decimal-string copies with domain canonical_decimal_string

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Re-verified at HEAD: two byte-identical zero-collapse canonical-decimal-string
  copies (`_calculation_actions._canonical_decimal_str`,
  `_calculation_revision._canonical_decimal`) vs canonical
  `domain._identifiers.canonical_decimal_string`.
- Replaced both defs with aliased imports from `domain._identifiers` (matching
  the four existing consumers' import convention), preserving the local call
  names.

## Outcome

Committed as `b0319cc5f`, tagged `relocation:canonical_decimal_string`. Ruff
clean; 136 modelo/calculation tests green. Hash inputs unchanged.

## Notes

Kept the established `from ...domain._identifiers import ...` convention rather
than promoting to a top-level re-export, for consistency with the four existing
consumers (a top-level promotion would be a separate 5-site change).
