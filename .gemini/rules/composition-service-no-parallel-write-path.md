---
name: composition-service-no-parallel-write-path
trigger: always_on
---

# Composition service never re-implements an existing write path

## Rule

When a new application-layer service exposes an operator-facing verb that
corresponds to an existing single-writer primitive, the service MUST delegate
the write to the existing primitive (preserving its atomicity and lifecycle-
event emission) and MUST NOT re-implement the write path. The service emits
its own surface-level event in addition to the primitive's lifecycle event;
the two events are intentionally distinct (lifecycle records the data change,
surface records the operator's verb invocation).

## Why

The BucketMaintenanceService design pass on 2026-06-03 found a real
hexagonal-design risk: every method except ``search`` already had a partial
or full authoritative primitive in the application or adapter layer (the
cross-store profile rename in ``ProfileRepository.rename``, the soft/hard
delete split in ``delete_profile_with_lifecycle_span`` +
``remove_profile_bucket_directory``, the bundle assembly in
``serialize_profile_bundle`` / ``deserialize_profile_bundle``). A naive
service that re-implemented any of these would re-introduce the torn-write
risk the single-writer contracts eliminate and create shadow lifecycle-event
emission.

The two-event co-emission pattern (``PROFILE_RENAMED`` plus
``BUCKET_RENAMED`` per rename invocation) is a deliberate audit feature, not
a bug. A future audit query distinguishing "the record was relabelled" from
"the operator invoked the maintenance verb" relies on the two events being
distinct.

## How

- **Good:** ``BucketMaintenanceService.rename`` calls the top-level re-export
  ``rename_profile`` for the cross-store relabel, then appends
  ``BUCKET_RENAMED`` to the bucket-event history. The inner
  ``ProfileRepository.rename`` keeps emitting ``PROFILE_RENAMED``; the two
  events co-emit per operator action.
- **Good:** ``BucketMaintenanceService.delete`` composes
  ``delete_profile_with_lifecycle_span`` (soft tombstone) and
  ``remove_profile_bucket_directory`` (hard erase) in sequence; emits
  ``BUCKET_DELETED`` between them. The destructive-action ``confirmed=True``
  + active-bucket refusals live at the service boundary so a programmatic
  caller observes the same guarantees the CLI ``--yes`` flag passes through.
- **Bad:** a service ``rename`` method that opens its own bucket session,
  decrypts the encrypted profile record, mutates ``display_name``,
  re-encrypts, writes back, then separately rewrites the plaintext manifest
  label. This re-implements the cross-store atomicity that
  ``ProfileRepository.rename`` already holds; a crash between the two writes
  leaves the stores drifted.
- **Bad:** a service ``delete`` that loops directly over the bucket
  directory's secure-object rows to clear them. The soft-tombstone primitive
  exists for a reason; bypassing it loses the ``PROFILE_TOMBSTONED``
  lifecycle event downstream consumers depend on.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr`` (composition pattern); research
``2026-06-03-cli-workflow-redesign-research``; exec record
``2026-06-03-cli-workflow-redesign-exec``. Codified per the
``vaultspec-codify`` discipline because the constraint binds future agents
across sessions whenever a new composition service is introduced over an
existing single-writer primitive.
