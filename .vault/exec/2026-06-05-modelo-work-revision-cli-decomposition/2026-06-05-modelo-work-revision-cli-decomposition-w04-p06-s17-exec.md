---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:30405add2cadf588f13029cc37beebc994a53725eb4e078c081830124d8373c8'
step_id: 'S17'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P06.S17 Execution

Extracted the ledger `evidence` subgroup into `src/aeat/entrypoints/cli/_ledger_evidence_cli.py`.

Implementation:
- Added `evidence_app` and `register_evidence_commands`.
- Replaced the root evidence command bodies in `_ledger.py` with a registrar mount.
- Kept evidence persistence and mutation behavior delegated to `PurchaseInvoiceEvidenceService`.

Outcome:
- `_ledger.py` line count moved from 4341 to 4084.
