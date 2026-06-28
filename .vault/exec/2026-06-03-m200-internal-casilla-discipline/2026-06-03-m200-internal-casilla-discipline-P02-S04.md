---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S04'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Build internal_only identity frozenset in derive_calculation_completeness_casillas

## Scope

- `src/aeat/domain/calculations/registry/_record_design.py`

## Description

At the start of `derive_calculation_completeness_casillas`, after `declared_identities` is built, added a sibling `internal_only_identities` frozenset comprehension scanning every `revision.casillas` and capturing `(casilla.segmento, casilla.number)` whenever `casilla.internal_only` is true. The set is the lookup the multi-segment branch reads to skip the Diseño-presence check.

## Outcome

The function now carries an O(N)-built lookup set of the segment-carrying identities the revision intends as app-internal. For any revision whose casillas declare no `internal_only` flag (every revision other than M200 2024-y-siguientes today), the set is empty and the function's behaviour is unchanged.
