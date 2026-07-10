---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S20'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# author the A5-210 engine-wiring ADR for the IRNR calculation surface grounded in TRLIRNR RDLeg 5/2004 (vaultspec-high-executor)

## Scope

- `.vault/adr/2026-05-27-m210-irnr-full-engine-adr.md`

## Description

- Reconcile the stale-open P04 ADR row against the current accepted ADR corpus.
- Ground the reconciliation with `uvx vaultspec-rag search "modelo multiyear renta P04 mechanism ADR 353 720 income 714 151 210 721 accepted ADR canonical" --doc-type adr --limit 20`.
- Update the plan related set and S20 row to point at the canonical M210 IRNR engine ADR.

## Outcome

- `2026-05-27-m210-irnr-full-engine-adr.md` exists and is accepted.
- The ADR predates this plan and owns the Modelo 210 IRNR full calculation engine path after the Path-B stub.
- No product code changed in this step; the downstream declared-but-unwired link and enrollment work remain owned by the later implementation wave.

## Notes

- This closes the ADR-authoring row only. The canonical ADR uses the `m210` naming and date already present in the corpus instead of the stale plan filename.
