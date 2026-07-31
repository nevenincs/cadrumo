---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:f9dc3ab003cb08658a52321f4e5a1f5f809db53648a892fa611bca5b15dfc63a'
step_id: 'S18'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace invoice test-export repository imports with the real persistence adapter source

## Scope

- `src/aeat/application/invoices/tests/test_bulk_import.py`
- `src/aeat/application/filing/tests/test_source_mesh_review.py`

## Description

- Grounded the cleanup with `uvx vaultspec-rag search "InvoiceCatalogueRepository TransactionCatalogueRepository SecureObjectRepository application_adapter_exports real adapter source tests" --type code`.
- Confirmed `InvoiceCatalogueRepository` is defined in `src/aeat/adapters/persistence/profile/invoices.py` and is the concrete encrypted invoice-catalogue repository behind the application tests.
- Replaced imports from `src/aeat/tests/application_adapter_exports.py` with direct imports from the real adapter source.
- Updated the bulk-import test docstring reference so it names the real adapter class rather than the test-export bundle.

## Outcome

The invoice bulk-import and filing approval-staleness tests now provision `InvoiceCatalogueRepository` from the concrete persistence adapter. This removes another campaign-owned test-export provisioning site while preserving the real encrypted repository behavior.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/invoices/tests/test_bulk_import.py src/aeat/application/filing/tests/test_source_mesh_review.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/invoices/tests/test_bulk_import.py src/aeat/application/filing/tests/test_source_mesh_review.py -n 0 -m "integration or not integration"` - `10 passed`.

## Notes

The first pytest run without the explicit marker expression deselected the integration-marked tests (`10 deselected`), so verification used the repository's integration-inclusive marker expression.
