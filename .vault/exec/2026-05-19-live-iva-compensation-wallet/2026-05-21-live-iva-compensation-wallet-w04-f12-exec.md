---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F12'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F12`

Mitigated the unreadable secure-object repair hazard by routing operators to read-only inventory before quarantine and classifying secure-object namespaces for IVA reconciliation risk.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/application/test_diagnostics.py`

## Description

WALLET-059 identified unreadable secure-object rows in wallet-relevant and calculation-relevant namespaces. Direct quarantine is unsafe in this context because rows can be filing history, wallet observations, ledger evidence, invoices, Modelo state, submission receipts, or auth context needed for multiyear IVA reconciliation.

This step keeps the repair path non-destructive. `secure_objects.integrity` now points to `aeat config repair list <namespace> --unreadable` instead of direct quarantine, and the generic secure-object unreadable error suggestion now points to the integrity inventory surface. The repair list report now emits namespace-level classification: role, IVA reconciliation relevance, compensation-history participation, destructive-repair risk, and a conservative operator note. Unknown namespaces are labelled `unknown_do_not_quarantine_blindly`.

No live AEAT operation was performed in this step. No secure-object payloads are decrypted for display or printed.

## Residual Risk

This is a mitigation, not full closure. Row-level bucket/profile attribution is still missing when the object key is unreadable or only an opaque HMAC digest is available. Destructive quarantine remains out of scope until that classification is complete.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py -q --disable-warnings` completed with 37 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/core/errors/registry/_adapters.py` passed.
