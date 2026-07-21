---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace ledger evidence test-export storage imports with real adapter sources

## Scope

- `src/aeat/application/ledger/tests/test_evidence_draft.py`

## Description

- Grounded the cleanup with `uvx vaultspec-rag search "ledger evidence draft AttachmentStore InvoiceCatalogueRepository SecureObjectRepository application_adapter_exports real adapter source" --type code`.
- Confirmed `AttachmentStore` is the concrete encrypted attachment-byte store named by the attachment/evidence domain, `InvoiceCatalogueRepository` is defined in `src/aeat/adapters/persistence/profile/invoices.py`, and `SecureObjectRepository` is provided by the storage SQL adapter surface.
- Replaced the `src/aeat/tests/application_adapter_exports.py` import with direct imports from those real adapter modules.

## Outcome

The ledger invoice-evidence draft tests now provision attachment, invoice, and secure-object storage dependencies from their real adapter sources. The tests continue to exercise real in-memory PDF extraction, secure-storage evidence resolution, and invoice confirmation wiring without mocks.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/tests/test_evidence_draft.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/ledger/tests/test_evidence_draft.py -n 0` - `25 passed`.

## Notes

No production code changed. This is a direct-source test cleanup for the ledger evidence surface.
