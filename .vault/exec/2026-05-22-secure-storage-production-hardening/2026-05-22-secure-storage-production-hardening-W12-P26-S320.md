---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S320'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S320 bucket event catalogue

## Scope

- `src/aeat/domain/buckets/_event.py`

## Description

- Audited `domain.buckets._event` against the target `remote-mirror` (owner `W12.P24.S98`).
- Confirmed `BucketEventType` carries the censo-mirror event-kind values (`profile.censo.refreshed`, `profile.censo.applied`, `modelo.censo.dependent_stamped_stale`, plus the `modelo.036.declaration.{alta,modificacion,baja}` declarative-recording events landed by the M036 commit 3 verb mount).
- Confirmed the `manifest-bucket` signal is appropriate: every emitted event carries a `bucket_id` field bound to the active manifest bucket, and the deterministic `derive_bucket_event_id` SHA-256 incorporates `bucket_id` into the content-address so cross-bucket replay cannot silently coalesce events.
- Confirmed the `remote-provider` signal is appropriate: the censo refresh/apply events explicitly mirror state read from the AEAT sede remote provider into the bucket-scoped event log, with no remote-write surface. The `MODELO_RECONCILED` and `MODELO_FILING_IMPORTED` events similarly mirror sede-side or operator-imported state into the local catalogue.
- The mirror events are content-addressed and frozen at strict-pydantic boundaries; no parallel write path bypasses the catalogue per the `composition-service-no-parallel-write-path` rule.

## Outcome

- AFR-218 closed: the remote-provider mirror events are appropriately scoped to the bucket-local catalogue; no source change required.
- No new tests authored — the existing bucket-event roundtrip + content-address tests cover the contract.

## Notes

- Audit-only Step; the source file is unchanged.
