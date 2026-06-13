---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1821'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1821-code-review-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1821`

Closed plan rows:

- `W61.P304.S1821`

## Description

Implemented backend ledger transaction lifecycle state for archive and stash behavior. Archive and stash are durable `ledger_transaction` lifecycle states, not review overlays and not CLI-local state.

`TransactionLifecycleState` is closed to `ACTIVE`, `ARCHIVED`, and `STASHED`. `Transaction` now carries `lifecycle_state` and `lifecycle_lineage`, with JSON string coercion for persisted lifecycle fields. `TransactionLifecycleLineageEntry` records previous/current state, actor, source command, timestamp, reason, and bucket event id, and rejects noop transitions.

`archive_manual_transaction` and `stash_manual_transaction` transition bucket-scoped ledger transactions through backend ledger services. These transitions emit `ledger.transaction.archived` and `ledger.transaction.stashed`, update the catalogue row, append lifecycle lineage, and persist the transaction catalogue plus bucket event history through the combined secure-object write path.

`update_manual_transaction` refuses non-`ACTIVE` rows before constructing replacements, so archived or stashed rows cannot be silently reactivated by edit, classify, allocate, or attach paths. Active-row replacements preserve lifecycle state and lineage.

IVA, Renta, and preflight workflow projections skip non-active rows before producing observations, casilla values, prorrata references, or readiness blockers. `list_manual_transactions` remains an all-rows bucket listing surface; active-only filtering is limited to the active workflow consumers covered by this row.

The internal `aeat.application.archive` package only re-exports backend ledger lifecycle services and is not an operator CLI root. S1821 does not introduce or imply `aeat archive` or `aeat app archive`. Removal, reset, and export behavior remain separate plan rows.

The S1821 audit initially found two HIGH issues: edit reactivation/lifecycle loss and archived/stashed rows feeding active aggregation/preflight. The re-review records both findings as remediated, with no remaining HIGH or CRITICAL issues.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1821-code-review-audit.md`
- `src/aeat/domain/transactions/_enums.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/__init__.py`
- `src/aeat/domain/transactions/test_models.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/archive/__init__.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/aggregation/test_iva_ledger.py`
- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/aggregation/test_renta_ledger.py`
- `src/aeat/application/ledger/_preflight.py`
- `src/aeat/application/ledger/test_preflight.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/test_preflight.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/test_preflight.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/domain/transactions/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/application/ledger/test_preflight.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
  - 95 passed

Coverage includes lifecycle JSON round-trip, noop transition rejection, archive/stash event and lineage persistence, invalid lifecycle transition refusal, archived edit refusal without catalogue or event mutation, active-only IVA projection, active-only Renta expense aggregation, active-only ledger preflight, and existing bucket-event and secure-object persistence behavior.
