---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S16'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P06.S16 Execution

Inventoried the residual `_ledger.py` monolith guard offender.

Findings:
- `_ledger.py` was 4341 lines against a 4255-line frozen budget.
- The coherent extraction selected was the `evidence` subgroup.
- The subgroup delegates persistence and mutation policy to `PurchaseInvoiceEvidenceService`; extraction keeps accounting/evidence policy in the application layer.

Discovery:
- Exact `rg` found `evidence_app`, evidence payload/text helpers, and `evidence add/view/list/update/remove`.
- `vaultspec-rag` semantic search for ledger evidence commands identified the same command group.
