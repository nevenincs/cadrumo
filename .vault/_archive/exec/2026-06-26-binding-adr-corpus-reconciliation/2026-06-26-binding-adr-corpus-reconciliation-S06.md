---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-10'
body_hash: 'sha256:4e6c1ff3bdc14d88a14850f2aa00b1c1268254f4c5c86befe44caecc0e5e6c15'
step_id: 'S06'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# REWORK: align the m390-annual-autoconsumo fold-in to the one carry mechanism (phase 2.3)

## Scope

- `re-point from the apex`
- `.vault/adr/2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md`

## Description

- Reconstruct the execution record for the already-checked S06 row.
- Confirm commit `e511d8fed3` aligned `2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md`.
- Verify the status block assigns unified carry direction to phase 2.3 and the wallet anchor.

## Outcome

- S06 is backed by landed evidence. The M390 annual fold-in arithmetic stands, and
  the ADR now states that future phase 2.3 unifies it with the one compensacion
  carry mechanism anchored by the live IVA wallet ADR.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline e511d8fed3`.
