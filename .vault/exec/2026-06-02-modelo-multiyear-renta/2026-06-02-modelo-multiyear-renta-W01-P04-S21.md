---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:7ae2acfe59fb678c57a5956c64c6902a73b563746bf3edd2c1e42afe4b2adea4'
step_id: 'S21'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# author the A5-721 data-fidelity and obligation-trigger ADR grounded in Ley 58/2003 DA18 and Orden HFP/886/2023 (vaultspec-high-executor)

## Scope

- `.vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`

## Description

- Reconcile the stale-open P04 ADR row against the current accepted ADR corpus.
- Ground the reconciliation with `uvx vaultspec-rag search "modelo multiyear renta P04 mechanism ADR 353 720 income 714 151 210 721 accepted ADR canonical" --doc-type adr --limit 20`.
- Update the plan related set and S21 row to point at the canonical 721 crypto data-fidelity ADR.

## Outcome

- `2026-06-02-modelo-721-cripto-data-fidelity-adr.md` exists and is accepted.
- The ADR owns the 721 data-fidelity and obligation-trigger direction, including the correction from Orden HFP/887/2023 to Orden HFP/886/2023 and the Ley 58/2003 DA18 anchor.
- No product code changed in this step; downstream legal-registry correction, 721 registry work, and enrollment remain owned by later implementation work.

## Notes

- This closes the ADR-authoring row only. The current accepted ADR treats 721 primarily as data-fidelity and legal-source correction work, not as a completed calculation engine.
