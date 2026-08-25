---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:42017c3671b5ec32dde23da7874066f7903135373cc7501b6c5b70d4c21edfa5'
step_id: 'S253'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Replace stale ledger-evidence and invoice output assumptions with stable authority-backed dynamic witnesses on ledger-evidence and manage-invoices

## Scope

- `docs/_sequences/contracts/ledger-evidence/ and docs/_sequences/contracts/manage-invoices/`

## Description

- Trace evidence mutation, invoice catalogue projection, link, and Modelo 349 source authority with Vaultspec RAG and exact symbols.
- Replace generated-identity assumptions with captured evidence, invoice, transaction, and work-unit witnesses.
- Preserve independent assertions for invoice kind, totals, operation type, evidence linkage, and calculation lifecycle state.
- Regenerate only the ledger-evidence and manage-invoices page outputs through the sequence owner CLI.

## Outcome

Both pages now address the objects created in their own examples and verify that the returned projections retain those identities. The assertions remain semantically independent: they also check monetary totals, invoice direction, intra-community classification, evidence linkage, removal refusal, and the Modelo 349 calculation state without duplicating ledger or invoice projection logic.

## Notes

- Earlier concurrent commit `98f34aa7b01` had already converted the evidence attachment and removal examples to captured identity and target-specific refusal assertions; S253 retained and extended that work.
- Verification passed: both page golden and cumulative coherence checks; 16 focused ledger/invoice application tests; 61 parser/comparator tests; 349 documented-command conformance tests; scoped Ruff and ty.
- The broader catalogue CLI integration run passed 14 tests and exposed one unrelated localisation assertion that expects an English field token while the command emits the Spanish refusal envelope; no product behavior in S253 caused that mismatch.
- Formal review approved the Step with no findings and independently reran both pages in isolated and cumulative modes.
