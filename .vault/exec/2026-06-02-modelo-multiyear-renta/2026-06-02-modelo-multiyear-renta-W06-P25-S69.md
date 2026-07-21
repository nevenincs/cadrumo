---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S69'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile Modelo 721 against the accepted no-calculation threshold-continuity ADR and retire the stale crypto engine requirement

## Scope

- `.vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`

## Description

- Reconcile the stale engine-build row against the accepted Modelo 721 ADR.
- Ground the reconciliation with vault RAG over the Modelo 721 ADR, plan, and current registry/test surfaces.
- Update the plan row so it no longer asks for a crypto calculation engine that the accepted ADR forbids.
- Keep the unresolved row-set prior-year binding as separate open hardening work under `S89`.

## Outcome

- The current Modelo 721 direction is no-calculation threshold continuity.
- The stale engine-build requirement is retired from this row rather than implemented.
- The accepted ADR remains the governing record for the residual per-custodian baseline binding question.

## Notes

- No calculation engine was built in this step.
- Current code rejects `source_output` in `previous_filing` selectors, so the ADR's prospective row-set baseline binding is not claimed here.
