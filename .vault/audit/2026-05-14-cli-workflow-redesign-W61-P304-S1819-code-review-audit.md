---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]'
---

# `cli-workflow-redesign` Code Review

W61-P304-S1819-001 | LOW | Legacy underscore rejection test covers only two former transaction values
`test_ledger_event_catalogue_rejects_legacy_underscore_transaction_events` asserts rejection for `ledger_transaction.created` and `ledger_transaction.updated`, but the new catalogue establishes a wider `ledger.transaction.*` lifecycle for imported, classified, allocated, removed, archived, stashed, and exported events. The implementation itself does not expose aliases or compatibility shims: `BucketEventType` defines only dot-separated ledger transaction values, and strict event deserialization goes through Pydantic enum validation when the bucket-event repository loads persisted catalogues. This is therefore a test-coverage gap, not an observed runtime defect. Expanding the rejection test with a parameterized legacy-value list would better lock the no-legacy-alias contract for future S1820 emitters.

No HIGH or CRITICAL issues found.

Review notes:

- Collision/shadow risk: no duplicate event or object string values were found in `BucketEventType` or `BucketEventObjectType`; the reviewed enum additions are a closed catalogue and do not add legacy aliases.
- ADR vocabulary: ledger transaction events use the accepted `ledger.transaction.*` namespace. `LEDGER_TRANSACTION_ALLOCATED` follows the later ledger transaction management ADR's `split` to `allocate` rename, while evidence and attachment values match the accepted source-kind terminology.
- Object types: added object types cover the S1820 mutation targets without broadening to bare `invoice`; `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`, and `attachment` remain distinct.
- Tests: the value assertions are contract tests against literal ADR-approved strings rather than tautological derivations from implementation logic, and the catalogue filtering test exercises real `BucketEvent` construction plus type filtering.

Verification observed from the implementation handoff:

- `uv run --no-sync ruff check src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py`
- `uv run --no-sync ty check src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py`
- `uv run --no-sync pytest src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py -q`

Resolution re-review, 2026-05-14:

W61-P304-S1819-001 | RESOLVED | Legacy underscore rejection now covers the full ledger transaction lifecycle
The remediated `test_ledger_event_catalogue_rejects_legacy_underscore_transaction_events` parameterizes the rejection assertion over all nine legacy underscore transaction values: created, imported, updated, classified, allocated, removed, archived, stashed, and exported. This closes the original test-coverage gap against the `ledger.transaction.*` catalogue contract. The changed test continues to exercise real `BucketEventType` enum construction and does not introduce a tautological assertion, fake, mock, skip, or xfail shortcut. No new issue was found in the test change.

No HIGH or CRITICAL issues remain.
