---
tags:
  - '#exec'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0c76de580428f7db535863b9041142271654ef4f22e2c4aff9facee80474c488'
step_id: 'S04'
related:
  - "[[2026-08-13-facturae-invoice-class-plan]]"
---

# Surface the two cases the mapping refuses to resolve: a record declaring a recapitulativa code, and a record whose declared code disagrees with its own corrective reference in either direction. Both are findings about the document rather than states to be picked between

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Add exact closed discrepancy kinds for unmodelled and contradicted invoice classes.
- Add exact confirmation reasons and operator-action mappings for both conditions.
- Detect recapitulativa declarations without flattening them into the domain taxonomy.
- Detect class-versus-corrective-reference disagreement in both directions.

## Outcome

- Structured draft assembly now surfaces both document conditions as blocking, individually resolvable findings.
- Focused lint and twelve relevant finding/gate/corpus tests passed.

## Notes

- Semantic discovery was temporarily unavailable; exact source discovery and targeted search supplied the grounding fallback.
- The parent authorized the minimal closed-vocabulary expansion after the original Step scope proved insufficient for an honest finding.
- Focused verification does not establish repository-wide readiness.
