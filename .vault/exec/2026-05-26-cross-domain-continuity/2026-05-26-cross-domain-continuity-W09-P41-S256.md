---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S256'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# FU-W07-D surface legal_refs and source_refs on projected M100 casilla values in modelo project verb output payload

## Scope

- `calculation-grounding rule requires every casilla observation to carry its provenance`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

Audited `modelo project` verb's output payload at
`src/aeat/entrypoints/cli/_modelo.py:5322-5331` for legal_refs and
source_refs surfacing per the calculation-grounding rule.

## Outcome

Already implemented. `casilla_observations` is built as a list of
`CasillaObservationPayload` from `engine_result.entries`, each
carrying `casilla_id`, `value`, `formula_id`, `legal_refs`, and
`source_refs`. The inline comment at lines 5296-5301 references
the grounding rule and explains that input/bound casillas are
operator-supplied and surface in the `m130_accumulated` block.

## Notes

Provenance surfacing is production-active; no additional code
authored by this record.

