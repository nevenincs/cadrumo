---
tags:
  - "#adr"
  - "#secure-persistence-foundation"
date: 2026-04-29
modified: '2026-04-29'
related:
  - "[[2026-04-29-secure-persistence-foundation-wave18-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave15-16-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave17-audit]]"
---

# `secure-persistence-foundation` wave-18 ADR: rotation-correctness fixes

## Status

Accepted (in-PR follow-up to wave-17 audit gate).

## Context

The wave-17 audit gate PASSED but the consolidated review flagged
two pre-existing P1 findings in the rotation substrate. Both are
confirmed-real against current code (see the related wave-18
research artefact in the frontmatter):

- **R1**: `default_blob_store_roots` adds `aeat_secret_store_dir`
  but `SecretStore` writes blobs to `aeat_blob_store_dir`. A default-
  settings rotation silently skips every secret-store DEK; old-key
  cutover bricks the secret-store irreversibly.
- **R2**: The wave-15+16 lock-acquisition added in rotation uses a
  `<envelope>.json.lock` target, but wave-4 writers lock `<id>.lock`
  — different sidecar files, no actual serialisation against the
  writer.

Both are scoped, surgical, and have zero operator-facing surface.

## Decision

### D1 — blob-store rotation roots

Change `default_blob_store_roots(settings)` in
`src/aeat/adapters/persistence/storage/_rotation.py` to point at `aeat_blob_store_dir`
instead of `aeat_secret_store_dir`. The contract is "where the
EncryptedBlobStore wraps DEKs"; `aeat_blob_store_dir` is the only
location wired up by `get_secret_store()`. The
`aeat_attachments_dir` entry stays as-is (the attachments store
also has its own `EncryptedBlobStore` rooted there).

When `aeat_blob_store_dir` and `aeat_attachments_dir` happen to
resolve to the same absolute path (operator override / shared
deployment), the helper deduplicates so the rotation does not visit
the same blob twice.

### D2 — rotation lock-target alignment

Extend `RotationPlanEntry` with an optional
`lock_path_resolver: Callable[[Path], Path] | None = None`. When
`None`, default to `_default_lock_resolver`, which maps an envelope
file path to the writer-canonical lock target by stripping the
plan's `envelope_suffix` and appending `.lock`:

```python
def _default_lock_resolver(envelope_path: Path, *, envelope_suffix: str) -> Path:
    name = envelope_path.name
    if name.endswith(envelope_suffix):
        stem = name[: -len(envelope_suffix)]
    else:
        stem = envelope_path.stem
    return envelope_path.with_name(stem + ".lock")
```

This matches the wave-4 writer convention (`<store>/<id>.lock`).
Combined with `exclusive_file_lock`'s automatic `.lock` suffix
append, the **actual** lock file becomes
`<store>/<id>.lock.lock` — identical to what the writer locks.

Single-file envelope entries (`usage_ratios`, `default_profile`)
that already use `target_filename` and have non-`.envelope.json`
suffixes pass an explicit resolver so the rotation locks the
writer-canonical path for those repositories too.

The lock acquisition in `rotate_master_key` switches to call
`entry.lock_path_resolver(path)` instead of computing
`path.with_suffix(path.suffix + ".lock")` inline.

## Alternatives considered

### D1 alternatives

- **Add both `secret_store_dir` and `blob_store_dir`**: rejected —
  the secret-store dir contains `master.key`, `master.kdf`, `salt`,
  the secret-store index, and `master.recovery.key`; none of those
  are blob-store roots. Walking it as a blob root yields zero
  manifests at best and noisy log warnings at worst.
- **Pass blob-store roots explicitly per-call**: rejected — the
  CLI already calls `default_blob_store_roots(settings)` and
  operators expect the canonical helper to cover every wired-up
  store. Forcing the operator to enumerate roots violates
  the wave-15+16 ergonomic contract.

### D2 alternatives

- **Make the writer convention conform to the rotation convention
  (`<envelope>.json.lock`)**: rejected — wave-4 ships in production
  and the on-disk lock-file naming is observable through normal
  filesystem operations (sweep scripts, backup tools). Renaming
  every existing lock file is a substrate-level migration we do
  not need to take on for what is fundamentally a rotation bug.
- **Drop the rotation-side lock entirely**: rejected — wave-15+16
  added it explicitly to close the codex finding. The lock is
  defensive-in-depth on top of the runbook's "quiesce then act"
  expectation; we are not removing it.
- **Lock the parent directory store-wide**: rejected — that would
  serialise the rotation against unrelated writers in the same
  directory, defeating the per-record concurrency the wave-4
  contract was designed for.

## Consequences

### Positive

- Default-settings rotation correctly visits the secret-store DEKs;
  the secret-store survives master-key rotation cleanly under the
  out-of-the-box configuration.
- Rotation and writers contend on the same OS-level lock file. A
  concurrent writer during rotation now blocks on the lock, and the
  rotation blocks on a concurrent writer — no lost updates.
- The lock-resolver hook is reusable: future plan entries with
  exotic naming conventions can pass a custom resolver without
  touching the rotation core.

### Negative

- `RotationPlanEntry` grows one field. Since the field has a default,
  existing call sites do not break.

### Neutral

- The `default_blob_store_roots` change is a bug fix; production
  installations that ran rotation before this fix may have left
  their secret-store DEKs under the old master key. The runbook's
  rotation section is updated to call out this hardening so
  operators with concerns can rotate again under the corrected
  helper.

## Implementation surfaces touched

- `src/aeat/adapters/persistence/storage/_rotation.py`:
  - `default_blob_store_roots` — point at `aeat_blob_store_dir`.
  - `RotationPlanEntry` — add `lock_path_resolver` field.
  - `_default_lock_resolver` — new helper.
  - `default_rotation_plan` — pass explicit resolvers for
    single-file entries.
  - `rotate_master_key` — use the resolver.
- `src/aeat/adapters/persistence/storage/_test_rotation.py`:
  - New test: `default_blob_store_roots` against production defaults
    visits `var/blobs` and `var/attachments`, deduplicates on
    overlap.
  - New test: rotation lock and writer lock contend on the same
    file (parametrised across each wave-4 repository's
    convention).
- `docs/security-runbook.md`:
  - Operator note in the rotation section pointing at the wave-18
    hardening so installations that ran rotation pre-fix can
    re-run safely.

No CLI surface, no new error registry entries, no setup wizard
changes, no doctor rows.

## Tests added

- Unit: `test_default_blob_store_roots_uses_blob_store_dir`.
- Unit: `test_default_blob_store_roots_dedupes_overlap`.
- Unit: `test_default_lock_resolver_strips_envelope_suffix`.
- Unit: `test_default_lock_resolver_falls_back_to_stem`.
- Integration: `test_rotation_and_writer_serialise_on_same_lock`
  — holds the writer's lock with `timeout=0`, attempts rotation
  acquisition, expects `LockAcquisitionError`. Reverses the order
  too.
- Integration: `test_default_rotation_e2e_secret_store_survives`
  — provisions a `SecretStore` against the default
  `aeat_blob_store_dir`, persists a record, rotates, decommissions
  the old key, asserts the record still decrypts.

## Out of scope

- Wave-7 envelope atomic-save pattern-consistency tweaks (gemini
  stylistic).
- Lost-update integration tests under live concurrent writers
  (operator-discipline concern).
