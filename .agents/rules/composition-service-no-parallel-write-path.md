---
name: composition-service-no-parallel-write-path
trigger: always_on
---

# A composition service never re-implements an existing write path

When a new application-layer service exposes an operator-facing verb
corresponding to an existing single-writer primitive, the service MUST delegate
the write to that primitive — preserving its atomicity and its lifecycle-event
emission — and MUST NOT re-implement the write path.

The service emits its own surface-level event **in addition to** the primitive's
lifecycle event. The two are intentionally distinct: the lifecycle event records
the data change, the surface event records the operator's verb invocation, and a
later query distinguishing "record relabelled" from "operator invoked the verb"
depends on both existing.

A naive re-implementation re-introduces the torn-write risk the single-writer
contracts eliminate, and creates shadow lifecycle-event emission.

## How

- **Good:** a maintenance service's `rename` calls the top-level `rename_profile`
  re-export then appends its own `BUCKET_RENAMED`, while the inner repository
  keeps emitting `PROFILE_RENAMED`, so the two co-emit per action. Its `delete`
  composes the soft-tombstone primitive and the hard-erase primitive, emitting
  `BUCKET_DELETED` between them, with the confirmation and active-bucket refusals
  at the service boundary so a programmatic caller gets the same guarantees the
  CLI flag passes through.
- **Bad:** a `rename` that opens its own bucket session, decrypts, mutates,
  re-encrypts, then separately rewrites the manifest label — re-implementing the
  cross-store atomicity the repository holds, so a crash between writes drifts
  the stores.
- **Bad:** a `delete` looping over secure-object rows directly, bypassing the
  soft-tombstone primitive and losing the tombstone event downstream consumers
  depend on.

Source: ADR `2026-06-03-cli-workflow-redesign-adr`.
