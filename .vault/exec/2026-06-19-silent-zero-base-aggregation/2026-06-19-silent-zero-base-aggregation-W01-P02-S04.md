---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S04'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# SUPERSEDED/deferred with S03: volumen-con-derecho per-period binding is not the regulated provisional+regularised prorrata

## Scope

- `deferred to the cross-period prorrata model`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/bindings/`

## Description

- Re-read the silent-zero ADR, research inventory, and July 2 audit before acting on the open `volumen-con-derecho` step.
- Confirmed `iva.prorrata-volumen-con-derecho` cannot be safely bound to a current-period `base_amount_sum` selector without the same cross-period prorrata model required by S03.
- Confirmed HEAD already carries the deliberate deferred source-kind/advisory path for annual prorrata regularisation instead of a fabricated live binding.

## Outcome

- `W01.P02.S04` is formally deferred with S03.
- Blocker: the legal numerator for annual prorrata is not the current-quarter taxable base. It depends on the regulated annual deductibility classification and provisional/definitive prorrata lifecycle, so a per-period binding would silently misstate mixed traders.
- Follow-up: the same cross-period prorrata regularisation mechanism named by S03, including the provisional carry and fourth-quarter regularisation model.
- Verification evidence: RAG and grep against HEAD found the ADR/research deferral and current `PRORRATA_REGULARIZACION` deferred-source/advisory implementation, with no promotion of the automatic feed to a live binding.

## Notes

- No code was edited for this step. S04 must remain coupled to S03 until the cross-period prorrata model lands.
