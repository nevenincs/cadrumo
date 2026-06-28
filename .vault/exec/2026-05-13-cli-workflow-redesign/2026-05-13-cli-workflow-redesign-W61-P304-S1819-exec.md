---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1819'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1819-code-review-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1819`

Closed plan rows:

- `W61.P304.S1819`

## Description

Extended the closed bucket event and object catalogues for ledger transaction mutation history. Catalogue query behavior is unchanged, and ledger event emission remains owned by `W61.P304.S1820`.

`BucketEventType` now uses the ADR-approved `ledger.transaction.*` event namespace for ledger transaction mutations: created, imported, updated, classified, allocated, removed, archived, stashed, and exported.

Supporting event values were added for `ledger.catalogue.reset`, `ledger.sanitization.completed`, `purchase_invoice_evidence.attached`, `purchase_invoice_evidence.replaced`, `purchase_invoice_evidence.detached`, `attachment.linked`, and `attachment.removed`.

`BucketEventObjectType` now covers the mutation targets required by the ledger lifecycle: `ledger_transaction`, `ledger_import_batch`, `ledger_catalogue`, `ledger_export`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`, and `attachment`.

The implementation keeps `ledger.transaction.*` as the event namespace and `ledger_transaction` as an object/source kind. It does not introduce bare `invoice` terminology. Tests reject legacy `ledger_transaction.*` event values so the old underscore event namespace cannot remain as a compatibility alias.

The S1819 review recorded one LOW test-coverage finding. The re-review records that finding as resolved, with no HIGH or CRITICAL issues remaining.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1819-code-review-audit.md`
- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/test_event_catalogue.py`

## Tests

- `uv run --no-sync ruff check src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/domain/buckets/test_event_catalogue.py src/aeat/application/ledger/test_actions.py -q`
  - 35 passed

Coverage includes approved literal event values, rejection of legacy underscore transaction event names, object-type coverage for ledger lifecycle targets, catalogue filtering for ledger event types, and existing manual-ledger event emission behavior.
