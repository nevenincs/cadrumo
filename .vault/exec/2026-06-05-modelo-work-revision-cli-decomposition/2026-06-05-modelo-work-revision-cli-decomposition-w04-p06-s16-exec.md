---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:6e2764b8e42ba5e2c9b5c562a6dc1aea25a2a83ac5a019c91f4ee181a111fb48'
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
