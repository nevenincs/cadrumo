---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:e36cfce4a8f1ac67733bd1397ee4d445766592e633c449cedd7056d5c062e162'
step_id: 'S14'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# author the A3 ADR for the 720 prior-year asset-baseline previous_filing binding and re-declaration trigger grounded in RD 1065/2007 (vaultspec-high-executor)

## Scope

- `.vault/adr/2026-06-02-modelo-720-prior-year-baseline-adr.md`

## Description

- Reconcile the stale-open P04 ADR row against the current accepted ADR corpus.
- Ground the reconciliation with `uvx vaultspec-rag search "modelo multiyear renta P04 mechanism ADR 353 720 income 714 151 210 721 accepted ADR canonical" --doc-type adr --limit 20`.
- Update the plan related set and S14 row to point at the canonical 720 prior-year baseline ADR.

## Outcome

- `2026-06-02-modelo-720-prior-year-baseline-adr.md` exists and is accepted.
- The ADR owns the prior-year asset-baseline and re-declaration trigger for modelo 720, grounded in RD 1065/2007 and the 720 order/legal chain.
- No product code changed in this step; the downstream 720 registry binding and enrollment work remain owned by the later implementation wave.

## Notes

- This closes the ADR-authoring row only. It does not claim the M720 previous_filing binding or E2E enrollment test is complete.
