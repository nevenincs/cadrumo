---
name: composition-service-no-parallel-write-path
trigger: always_on
---

# Composition service never re-implements an existing write path

## Rule

When a new application-layer service exposes an operator-facing verb that
corresponds to an existing single-writer primitive, the service MUST delegate the
write to that primitive (preserving its atomicity and lifecycle-event emission) and
MUST NOT re-implement the write path. The service emits its own surface-level event
in addition to the primitive's lifecycle event; the two events are intentionally
distinct (lifecycle records the data change, surface records the operator's verb
invocation).

## Why

The BucketMaintenanceService design pass (`2026-06-03-cli-workflow-redesign-adr`)
found every method except ``search`` already had an authoritative primitive (the
cross-store rename, the soft/hard delete split, the ``serialize_profile_bundle`` /
``deserialize_profile_bundle`` assembly), so a naive re-implementation would
re-introduce the torn-write risk the single-writer contracts eliminate and create
shadow lifecycle-event emission. The two-event co-emission (``PROFILE_RENAMED`` plus
``BUCKET_RENAMED`` per rename) is a deliberate audit feature: a later query
distinguishing "record relabelled" from "operator invoked the verb" relies on the two
events being distinct.

## How

- **Good:** ``BucketMaintenanceService.rename`` calls the top-level re-export
  ``rename_profile`` then appends ``BUCKET_RENAMED``; the inner
  ``ProfileRepository.rename`` keeps emitting ``PROFILE_RENAMED``, so the two events
  co-emit per action. ``delete`` composes ``delete_profile_with_lifecycle_span``
  (soft tombstone) and ``remove_profile_bucket_directory`` (hard erase), emitting
  ``BUCKET_DELETED`` between them, with the ``confirmed=True`` + active-bucket
  refusals at the service boundary so a programmatic caller gets the same guarantees
  the CLI ``--yes`` flag passes through.
- **Bad:** a ``rename`` that opens its own bucket session, decrypts/mutates
  ``display_name``/re-encrypts, then separately rewrites the manifest label —
  re-implementing the cross-store atomicity ``ProfileRepository.rename`` holds (a
  crash between writes drifts the stores); or a ``delete`` that loops over
  secure-object rows directly, bypassing the soft-tombstone primitive and losing the
  ``PROFILE_TOMBSTONED`` event downstream consumers depend on.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr`` (composition pattern); research and
exec record of the same feature.
