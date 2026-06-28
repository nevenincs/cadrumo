---
tags:
  - "#research"
  - "#secure-persistence-foundation"
date: 2026-04-29
modified: '2026-04-29'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave15-16-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave17-audit]]"
---

# `secure-persistence-foundation` wave-18 research: rotation correctness gaps

## Trigger

The wave-17 PR (#441) absorbed external review feedback on the
operator-facing surfaces (recover atomicity, key-export TOCTOU). Two
**pre-existing** P1 findings from `@chatgpt-codex-connector`, however,
were deferred as "out of scope for the wave-17 absorption pass" and
flagged for a follow-up.

This document confirms both findings against the current code, scopes
the security blast-radius, and feeds the wave-18 ADR.

## Finding R1: `default_blob_store_roots` targets the wrong directory

### Evidence

- `src/aeat/adapters/persistence/storage/_rotation.py:451-453` — `default_blob_store_roots(settings)`
  appends `Path(settings.aeat_secret_store_dir)` (default `var/secrets`).
- `src/aeat/adapters/persistence/storage/_materialisation.py:72-75` — the live `SecretStore`
  is wired with `EncryptedBlobStore(root_dir=Path(resolved.aeat_blob_store_dir))`
  (default `var/blobs`).
- `src/aeat/config.py:260-267` — the two settings have **distinct
  defaults**: `aeat_secret_store_dir = var/secrets`,
  `aeat_blob_store_dir = var/blobs`.

### Blast radius

`aeat security rotate-master-key` walks `default_blob_store_roots`
to find blob-store DEKs that need re-wrapping. Because the helper
points at `var/secrets` instead of `var/blobs`, every secret-store
record's wrapped DEK keeps its old-key wrapping. The CLI reports
`rotated/skipped/errors` summary — there are **no errors** because
the wrong directory simply has no manifests to walk, so the operator
sees a clean rotation summary.

When the operator decommissions the old master key per the runbook
("move ``old.hex`` to a sealed offline backup, then overwrite the
operating master-key source with the new key bytes"), every persisted
secret in the secret-store becomes **permanently unreadable**: the
DEK wraps cannot be unwrapped under the new master key, and the old
master key is gone. There is no silent fallback path; on the next
`SecretStore.get()` call the substrate raises a hard error.

This is **catastrophic and irreversible**: the secret-store holds
opaque-bearer credentials, OAuth refresh tokens, and the operator's
NIF-bearing identity records.

### Why earlier waves missed it

Wave-10 introduced `default_blob_store_roots` against the
attachments store (`aeat_attachments_dir`) only. Wave-15+16 extended
it to add the secret-store DEKs but pointed at the wrong setting —
the audit gate accepted the change without reconciling against
`get_secret_store`'s wiring. Existing rotation tests cover the
attachments path and the new secret-store DEK code path
**in isolation** (using a fixture that points the secret-store
directly at `var/secrets/blobs`), so the production-defaults wiring
is untested.

## Finding R2: rotation lock-target ≠ writer lock-target

### Evidence

- `src/aeat/adapters/persistence/storage/_lock.py:47-49` — `_lock_path_for(target)`
  appends `.lock` to whatever path the caller passes. Every
  `exclusive_file_lock(X)` call therefore protects the byte-range on
  `X.lock` (and writes the lock-file as `X.lock`).
- `src/aeat/application/filing/_repository.py:102-105` — wave-4 writers compute
  `lock_target_for(draft_id)` as `<store>/<draft_id>.lock`, then call
  `exclusive_file_lock(self.lock_target_for(...))`. The actual lock
  file is `<store>/<draft_id>.lock.lock`.
- `src/aeat/adapters/persistence/storage/_rotation.py:226-227` — rotation computes
  `lock_target = path.with_suffix(path.suffix + ".lock")` for the
  envelope file `<store>/<draft_id>.envelope.json`, yielding
  `<store>/<draft_id>.envelope.json.lock`. Then `exclusive_file_lock`
  appends `.lock` again — the actual lock file is
  `<store>/<draft_id>.envelope.json.lock.lock`.

The two acquirers are operating on **different sidecar files**
(`<draft_id>.lock.lock` vs `<draft_id>.envelope.json.lock.lock`),
so the OS-level file locks **do not serialise** them.

### Blast radius

A concurrent repository writer that calls `save()` while
`rotate-master-key` is mid-run can:

- Overwrite the envelope file the rotation just decrypted but has
  not yet re-encrypted — the writer's plaintext gets lost.
- Read a half-rotated envelope (partial atomic-replace window) — but
  this is mitigated by the per-file atomic-replace contract in
  `_atomic_write` (line 158-179), so the stale read is the previous
  consistent state, not a corrupt file.

The lost-update path is the real risk. The substrate's runbook is
explicit about quiescing the substrate before rotation, so production
hits this only if an operator ignores the runbook — but the lock was
*meant* to be the defensive belt-and-braces, and right now it is not.

### Why earlier waves missed it

Wave-10 introduced rotation without per-file locks. Wave-15+16 added
the locks specifically to address the codex P1 finding "rotate_master_key
performs in-place re-encryption without acquiring exclusive_file_lock"
— but the implementation chose a lock-target convention
(`envelope_path + ".lock"`) that does not match the wave-4 writer
convention (`stem + ".lock"`). Wave-16's tests cover that the
rotation-side lock is acquired and released, but not that it locks
the **same file** as the writer-side lock.

## Adjacent risks reviewed and dismissed

- **codex P1 #1 (envelope_suffix coverage of single-file envelopes)**:
  closed — `default_rotation_plan` lines 320-388 set `target_filename`
  for the usage-ratios profile and the operator profile, and
  `_iter_envelope_files` lines 107-115 honour the override.
- **codex P1 #4 (migrate_master_key_kdf write order)**:
  closed — `_master_key.py:1069-1080` writes `master.key` first and
  `master.kdf` last; the partial-migration recovery branch at lines
  1041-1054 detects the half-state and completes it.
- **codex P2 #1 (master-key mint race)**:
  closed — `_master_key.py:471-478` acquires `exclusive_file_lock` on
  `master.lock` before the existence check, so concurrent first-time
  callers route through `_unwrap_existing` instead of double-minting.
- **codex P2 #2 (`_try_decrypt_bytes` malformed AAD)**:
  closed — `_rotation.py:142-147` catches every exception in the AAD
  build path and returns `None`, increments errors counter at the
  outer caller.
- **codex P2 #3 (corpus manifest symlink containment)**:
  closed — `_corpus_manifest.py:179-180` checks `is_symlink` BEFORE
  `is_file` so the link itself is rejected even when it would
  otherwise resolve to a containment-violating target.
- **codex P2 #4 (corpus manifest backslash separator)**:
  closed — `_corpus_manifest.py:77-80` rejects `\` in `relative_path`.
- **codex P2 #5 (master.kdf non-object preview)**:
  closed — `_master_key.py:992-995` checks `isinstance(preview, dict)`
  before the `.get("version")` lookup.
- **gemini medium findings on `_envelope.py` / `_blob_store.py` atomic
  save patterns**: pre-existing wave-1 / wave-7 patterns; the rotation
  fix uses a tempfile-and-replace. The gemini suggestions
  ("assign tmp_path immediately after creation") are stylistic
  hardening; the `_atomic_write` helper at `_rotation.py:164-172`
  already does this. No regression.

## Decision space

Two findings, two scoped fixes:

- **D1 — blob-store rotation roots**: change
  `default_blob_store_roots` to add `aeat_blob_store_dir` (where
  `SecretStore` actually writes blobs) instead of
  `aeat_secret_store_dir`. Add a regression test that loads default
  settings and asserts the blob-store walks the right directory.
- **D2 — rotation lock-target alignment**: extend
  `RotationPlanEntry` with a `lock_path_resolver: Callable[[Path], Path]`
  that maps an envelope file path to the writer-canonical lock path,
  with a default that matches the wave-4 convention (strip the
  `envelope_suffix`, append `.lock`). Update each plan entry that
  uses a non-default suffix (single-file envelopes for usage-ratios
  and operator profile) with a resolver that locks the same target
  the writer locks. Add a regression test that proves the rotation's
  lock acquisition and the writer's lock acquisition contend on the
  same OS-level lock-file.

Both fixes are surgical, test-able, and do not touch any operator-
facing surface (CLI commands, doctor rows, error registry).

## Verification plan

- Unit test: `default_blob_store_roots(Settings())` returns
  `(Path('var/blobs'), Path('var/attachments'))` against the
  production defaults; on a settings instance with both dirs
  pointing at the same place, no duplicate is yielded.
- Integration test: provision a SecretStore at `var/blobs` (default
  wiring), persist a record, run `rotate-master-key`, decommission
  the old key, verify the record still decrypts under the new key.
  Assert the rotation summary's `rotated` count is non-zero (proof
  that the helper saw the right directory).
- Unit test: under a synthetic `tmp_path` repository setup, hold the
  writer's `exclusive_file_lock(repository.lock_target_for(id))`
  open, then attempt the rotation's lock acquisition with `timeout=0`
  — expect `LockAcquisitionError` (proof both acquirers contend on
  the same lock file). Repeat with the locks taken in the other
  order.

## Out of scope for wave-18

- Wave-7 envelope atomic-write hardening (gemini stylistic findings)
  — the existing `_atomic_write` is correct; the suggestions are
  pattern-consistency tweaks across the repo, not security fixes.
- Concurrent-writer-during-rotation lost-update tests — the runbook's
  quiesce-then-act expectation makes this an operator-discipline
  concern, not a substrate-correctness concern. Wave-18 closes the
  belt-and-braces lock; wave-19 (if needed) can add the lost-update
  test fixture.
