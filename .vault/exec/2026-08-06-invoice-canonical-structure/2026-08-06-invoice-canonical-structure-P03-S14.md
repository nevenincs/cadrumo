---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f92660a98393c01e186d7612f9ba9774d95099e6db7fa13ba853637ae640e4d8'
step_id: 'S14'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Delete the slim model, both services, the repository, the storage namespace and the BusinessOperationInvoiceDirection enum in one atomic explicit-path commit carrying every consumer, fixture and __all__ update, with no alias, bridge or re-export left behind

## Scope

- `src/cadrumo/application/ledger/_business_operation_invoice.py`

## Description

- Delete the slim module, its test-support helper and its eight dedicated test files.
- Delete the generated api stub and re-run the scaffolder so the parent toctree follows.
- Strip the eleven slim exports from the ledger package facade and rewrite the package docstring, which described the slim-versus-rich split as the design.
- Delete the storage namespace definition, its registry entry, its facade re-exports and the custody-carry resolver in one change.
- Delete the two slim error-registry entries.
- Repoint the namespace tests onto the canonical invoice namespace and re-pin the inventory count.

## Outcome

A search for the slim type across source, dev and docs returns nothing. No alias, bridge or re-export survives.

The custody-carry registration and the namespace definition moved together, as the Step required: a namespace whose custody resolver outlives it is a store nothing can carry and nothing can find.

The structured-custody assertion in the namespace tests named the deleted namespace. Rather than delete the assertion, it was repointed onto the canonical invoice catalogue namespace, which is the structured-custody invoice store the assertion was always really about.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/ src/cadrumo/application/invoices/ src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py -m "unit or integration"
    638 passed in 50.75s

    uv run --no-sync python -m dev.docs.apidocs scaffold --check
    Stub tree is conformant. No drift detected.

## Notes

Two tests reaching into the slim module were reconciled rather than deleted wholesale. The content-addressed-id file tests several record types; only its slim class was removed, and its evidence-id coverage kept. The attach-refusal test asserts that an invoice id is not a valid evidence reference -- a live capability -- and was repointed onto a canonical invoice id, which keeps the two id spaces provably distinct even though both are content-addressed digests.

The custody matrix already carried a case for the canonical namespace, so the slim case was pure duplication and went.

The namespace inventory count moved twice: down one for this deletion, then back up one when a peer landed an extracted-document-cache namespace. It is pinned to the live figure.
