---
tags:
  - '#exec'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8b065d47e4832f1d38ebaba12f61fdbcbf96711caf51f830c6bd891e9c570ff6'
step_id: 'S03'
related:
  - "[[2026-08-13-facturae-invoice-class-plan]]"
---




# Ground the draft's invoice class on the declared code where one is present - OO and CO are ordinaria, OR and CR are rectificativa - keeping the corrective-presence inference as the fallback for a record declaring nothing. Do NOT map OC or CC onto ordinaria: they declare recapitulativa, which the domain taxonomy cannot express, so they keep the operator-stated class

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Carry the parsed Facturae class privately through structured draft assembly.
- Resolve original and copy-original codes to the domain ordinary class.
- Resolve original and copy-corrective codes to the domain corrective class.
- Preserve operator input for recapitulativa and the corrective-reference fallback for absent declarations.

## Outcome

- Confirmation now takes its class from the document's recognised declaration where the domain can represent it.
- Focused lint and seven relevant parser, draft-projection, and corpus tests passed.

## Notes

- The first projection test exposed that a public draft field would widen an out-of-scope payload contract; the wire-only value was kept as private assembly state instead.
- No repository-wide readiness claim is made from the focused gates.
