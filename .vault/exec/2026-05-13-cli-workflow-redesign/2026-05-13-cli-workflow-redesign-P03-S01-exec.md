---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S01`

Added `WorkflowStateRepository.reset_workflow_state()` and supporting
module-level helpers that drop the secure-object row at namespace
`aeat.workflow` / key `state` and return a row-level fingerprint of
the discarded envelope.

- Modified: `src/aeat/application/workflow/_persistence.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/__init__.py`

## Description

The recovery flow needs to read row-level metadata (schema_version,
written_at, byte_length) without decrypting the ciphertext. The
existing `SecureObjectRepository` exposed only decrypt-or-fail paths
on the public surface, so a focused `peek_metadata(namespace,
object_key) -> SecureObjectMetadata | None` was added that issues a
raw `text()` query against the row id and returns row-level columns
plus the wire byte length. The encrypted payload column is read as
raw bytes and never decrypted on this path; an unreadable envelope
still surfaces a usable fingerprint.

A new `SecureObjectMetadata` pydantic model (strict frozen, extra
forbid) carries the fingerprint columns. The model is exported from
`aeat.adapters.persistence.storage.sql`.

`WorkflowStateRepository.fingerprint_state(*, reason_class)` reads
the row-level metadata via `peek_metadata`, attempts a `load()` to
recover the active profile bucket id when the envelope is readable
(catching the four envelope-failure exception classes — `WorkflowError`,
`ClassificationError`, `EnvelopeVersionError`, `ValidationError` — so
the fingerprint path never re-raises an envelope failure), and builds
a `WorkflowStateResetFingerprint`. `reset_workflow_state(*, actor,
source, reason_class)` chains `fingerprint_state`, the existing
`SecureObjectRepository.delete(namespace, object_key)`, and the
`workflow_state.reset` event emitter from `_events.py`.

Module-level `reset_workflow_state()` and `fingerprint_workflow_state()`
helpers wrap the repository methods for CLI-layer use, mirroring the
existing `workflow_state_repository()` accessor.

## Tests

Covered by the P03.S06 CLI tests; the repository helpers are exercised
through the `aeat config repair reset-state --dry-run`, refusal, and
`--yes` invocations.
