---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S281'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S281 - Close AFR-179 for workflow reset events

Scope: close `AFR-179` for `src/aeat/application/workflow/_events.py` with
signals `manifest-bucket, remote-provider`, target `remote-mirror`, and owner
`W12.P24.S98`.

## Description

- Audited workflow-state reset event emission and bucket-event persistence.
- Confirmed reset events persist through the centralized encrypted
  `BucketEventHistoryRepository` and `SecureObjectRepository` route.
- Verified the reset fingerprint records row metadata only: schema version,
  write timestamp, byte length, reason class, and recovered bucket id when
  available; it does not record decrypted workflow-state payloads.
- Checked the cold-root CLI guard that prevents bootstrap-exempt reset-state
  from reaching active-bucket event persistence without an active profile.
- Closed `W12.P26.S281` through `vaultspec-core vault plan step check` and
  updated the `AFR-179` register status to `closed`.

## Outcome

`AFR-179` is closed as a centralized encrypted bucket-event audit path. No
production code change was required for `src/aeat/application/workflow/_events.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_events.py src/aeat/application/workflow/_persistence.py src/aeat/application/workflow/test_persistence.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/domain/buckets/_event_repository.py src/aeat/domain/buckets/test_event_history_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_persistence.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/domain/buckets/test_event_history_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The row remains classified as a storage-affecting path because reset-state emits
an encrypted bucket event before deleting the workflow-state envelope. The current
implementation is fail-closed for the tested adverse path: an event-emission
failure leaves the workflow-state row intact.
