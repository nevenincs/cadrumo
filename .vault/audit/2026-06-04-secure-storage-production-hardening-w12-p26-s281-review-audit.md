---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S281-001 | PASS | Centralized encrypted event persistence

`src/aeat/application/workflow/_events.py` delegates persistence to
`BucketEventHistoryRepository`, whose default route resolves the active-bucket
`SecureObjectRepository` and stores the event catalogue as a `FINANCIAL`
secure object. This slice does not implement a parallel file store or remote
mirror path.

## S281-002 | PASS | Reset fingerprint privacy

The workflow reset event payload is limited to reset metadata: reason class,
actor, source, timestamp, optional schema version, written-at timestamp,
byte length, and recovered bucket id. The discarded encrypted workflow-state
payload is not copied into the event.

## S281-003 | PASS | Adverse-environment guard

The bootstrap-exempt `config repair reset-state --yes` path checks for a missing
active profile before invoking `reset_workflow_state`. On a cold root it returns
a clean no-op instead of trying to instantiate active-bucket event persistence.
The workflow repository also emits the reset event before deleting the state row;
the existing failure test proves an emitter failure leaves the row intact.

## S281-004 | PASS | Localization and exception handling

`_events.py` has no user-facing strings and no exception handlers. User-facing
reset-state messages remain in the CLI layer and use `tr()` locale keys.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_events.py src/aeat/application/workflow/_persistence.py src/aeat/application/workflow/test_persistence.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/domain/buckets/_event_repository.py src/aeat/domain/buckets/test_event_history_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_persistence.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/domain/buckets/test_event_history_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
