---
tags:
  - '#reference'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:3e8f53062bea9a0cbeab3e5482dcd264d3b25e9b2a1e6648cf0d7f9a71cc2178'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
---

# `arch-remediation-crash-window` reference: `multi-store crash-window matrix`

Grounding artifact for register item D11 (audit finding
persistence-multi-store-crash-windows). A profile bucket's durable state
spans four sibling stores plus a lock: the plaintext `manifest.toml`
(labels/pointers, atomic write-then-rename), the encrypted SQLite database
`db/` (plus its `-wal` sidecar; WAL with `synchronous=NORMAL`), the
content-addressed blob store `blobs/` (per-blob DEK, atomic byte writes),
the keystore (`bucket.dek.json`, Argon2id-KEK-wrapped DEK), and the bucket
`.lock` file. Every SINGLE write is atomic (fsync plus `os.replace`, or a
`session_scope` transaction); this matrix enumerates the COMPOSED verbs'
inter-store orderings so each crash window becomes a crash-injection test
around the existing repair/diagnostic verbs. Sources: the persistence
sections of the architecture-review audit (verified reads of the envelope,
blob-store, manifest-io, rotation, and secure-objects modules). Rows marked
VERIFY need their ordering confirmed against HEAD by the executing team
before a test is authored - this matrix is a worklist, not gospel.

## Summary

Matrix convention: stores M (`manifest.toml`), S (SQLite db+WAL), B (blob
store), K (keystore/DEK), L (lockfile). Each row: composed verb, write
order, crash windows, recovery expectation.

| Verb | Order | Crash windows | Recovery expectation |
| --- | --- | --- | --- |
| create profile | dirs, then K (DEK mint+wrap), then S (schema CREATE), then M (pointer/label), then registration | orphan dirs; K without S; S without M | creation is idempotent-guarded and the atomic-create rollback removes partial buckets; VERIFY rollback covers every window including K-without-S |
| rename profile | S (encrypted record label) then M (plaintext label) via the single-writer primitive | S updated, M stale | `ProfileRepository.rename` owns cross-store ordering; diagnostics detect label drift; VERIFY repair re-syncs M from S (S is authority) |
| soft delete | S tombstone plus lifecycle event, one transaction | none (single store) | no window by construction |
| hard delete | soft-tombstone S, then remove bucket directory (M/S/B/K all go) | tombstone without removal; partial directory removal | re-run is idempotent; readiness refuses a half-removed bucket; VERIFY partial-dir detection in repair-integrity |
| bundle export | read-only snapshot, then sealed archive write (tmp plus rename) | truncated tmp archive | atomic rename means no torn artifact; VERIFY the archive checkpoints or includes the `-wal` sidecar so no committed rows are silently absent |
| bundle import | staging dir, then K, then S, then B, then M last | any prefix without M | M-last means an aborted import is invisible to the pointer; VERIFY staging cleanup |
| attachment/evidence put | B (bytes), then S (manifest row in transaction) | B written, S row absent | orphan blob is unreferenced and content-addressed - harmless; VERIFY a GC sweep exists or is a declared non-goal |
| master-key rotation (envelope files) | per-file: new-key decrypt probe, re-encrypt, atomic replace; miss/error counters | any file boundary | idempotent re-run (probe skips already-rotated); errors counted, never silent |
| master-key rotation (blob manifests) | per-manifest wrapped-DEK re-wrap, atomic envelope save | any manifest boundary | same probe-skip idempotency; VERIFY the mixed-key window ACROSS envelope files, blob manifests, and the keystore (three stores, partial states validated only implicitly today) |
| participation-index writes | co-emitted in the same `apply_batch` as revision persistence | none intra-batch | derived and rebuildable by design; a stale index is a rebuild input, never a correctness input |

Cross-cutting expectations the D11 plan must pin: (1) every VERIFY cell
resolves to either a confirmed guarantee with a crash-injection test or a
documented non-goal; (2) every at-rest plaintext-scan surface and the
sealed archive account for the `-wal` sidecar; (3) repair-integrity
coverage is asserted per window using the anti-tautology pattern
(interrupt/corrupt, then prove detection or recovery - a repair that passes
with the window un-simulated proves nothing); (4) the mixed-key rotation
window is the highest-value row - it spans three stores and is the one
place a crash currently leaves states no gate has ever enumerated.

## VERIFY cell resolution (HEAD-confirmed)

Each row's actual inter-store write ordering was read at HEAD and its
crash-window guarantee resolved to either a confirmed guarantee (with a
crash-injection test) or a documented non-goal. Where the worklist matrix
above (authored from the audit reads) diverged from the code at HEAD, the
resolution below is authoritative; the matrix is preserved as the original
worklist. Coordinates cite the file and symbol read during resolution.

### create profile - CONFIRMED (rollback covers every window incl. K-without-S)

Actual ordering at HEAD (the matrix's "dirs, then K, then S, then M" is
wrong on order): the wrapped DEK (K) is minted by the create SPAN
(`profile_create_storage_span` -> `activate_master_key_provider(
allow_bucket_dek_enrollment=True)` -> `load_or_mint_bucket_dek` bootstrap
mint) BEFORE `ProfileRepository.create` runs. `create` then guards
(manifest-already-registered, duplicate-label, duplicate-tax-id, and a
fail-closed "DEK present" precondition), stages the bucket directory
(`_ensure_bucket_directory`), writes the plaintext manifest (M,
`write_manifest`), writes the active-profile pointer, and last commits the
encrypted record (S, the lifecycle `register`). So the true order is
K (span), dirs, M, pointer, S. Rollback is two-layered and covers every
window including K-without-S: on any exception inside `create`,
`dispose_engines_for_bucket` then `_remove_bucket_directory` (removes
dirs+M) then `_restore_pointer_text` (restores the pre-create pointer); on
any span-level failure, `_remove_create_span_artifacts` additionally deletes
the minted DEK and keystore dir and restores the pointer. A directory with
no manifest is reclaimable staging, not a registered profile, so a crash
before the manifest write leaves only reclaimable garbage. Test:
`test_bucket_crash_windows.py` (create rollback removes partial buckets and
restores the pointer at the K-without-S window).

### rename profile - detection CONFIRMED; automated re-sync NON-GOAL

Actual ordering at HEAD: `ProfileRepository.rename` loads+integrity-checks,
then `lifecycle_service.rename` writes the encrypted record `display_name`
and emits `PROFILE_RENAMED` (S), then `write_manifest` rewrites the manifest
`label` projection (M). S-then-M. A crash between leaves a stale manifest
label over a renamed record. DETECTION is confirmed: `verify_profile_integrity`
(run on every `ProfileRepository.load`) raises `ProfileIntegrityError`
naming `manifest_label` / `secure_record_display_name` on label drift, so a
drifted profile is refused (fail-closed), never served with the stale label.
Automated "repair re-syncs M from S" is a DOCUMENTED NON-GOAL at HEAD: no
repair verb rewrites the manifest label from the authoritative record, and
`rename` itself loads first (so it raises on the drifted profile rather than
repairing it). The guarantee is fail-closed detection, not silent service or
auto-repair. Test: `test_bucket_crash_windows.py` (crash between S and M ->
next load raises `ProfileIntegrityError` on the label-drift mismatch).

### hard delete - CONFIRMED (idempotent re-run + non-ready refusal + torn-manifest detection)

Actual ordering at HEAD: soft tombstone first (pointer cleared, manifest
`status` mirrored to `tombstoned`, then record tombstoned - a chosen order
where every torn intermediate fails closed off the live surface), then
`remove_profile_bucket_directory` trash-renames the whole bucket directory
to a `.trash-<id>-<hex>` sibling and `rmtree`s it (M/S/B/K all go at once).
The trash-rename is atomic, so a crash during it loses nothing; the Windows
in-place `rmtree` fallback (used when an open SQLite handle refuses the
rename) is the only path that can leave a partial directory. Recovery: the
removal is idempotent (`remove_profile_bucket_directory` early-returns when
the target is absent and completes a partial removal on re-run);
`assess_active_profile_health` refuses a half-removed active bucket with a
non-`ready` status (`dangling_pointer` / `manifest_unreadable` /
`profile_record_unreadable`); and `list_profile_bucket_scan_issues` detects
a partial directory whose manifest is present-but-torn. A partial directory
whose manifest is absent is excluded from the live inventory as reclaimable
garbage (same principle as the create-rollback staging directory), not a
served profile. Test: `test_bucket_crash_windows.py`.

### bundle export - CONFIRMED (with a tracked residual); tmp+rename is a NON-GOAL

Actual behaviour at HEAD (the matrix's "tmp plus rename" is wrong):
`write_sealed_archive` writes DIRECTLY to the operator's `output_path` via
`tarfile.open(output_path, "w:gz")` and refuses to overwrite an existing
target. There is no tmp-file + `os.replace`; a crash mid-write leaves a
truncated archive at `output_path`. The torn-artifact guarantee is met by
READ-TIME DETECTION plus an AEAD backstop, not atomic rename:
`read_sealed_archive` fast-fails a layout-drifted archive
(`SealedArchiveLayoutError` via `tarfile.TarError`) and a torn write that
damages the gzip stream (`SealedArchivePayloadError` via `EOFError` /
`gzip.BadGzipFile`); a near-complete truncation that still decompresses is
caught downstream by the AEAD tag on the encrypted payload, which the importer
verifies before it provisions any bucket store. Refuse-overwrite means a torn
export never clobbers a prior good archive. tmp+rename is a documented NON-GOAL:
the writer relies on read-side detection plus refuse-overwrite instead.

Reader hardening landed under this campaign: the reader previously caught only
`tarfile.TarError` / `OSError`, so a torn-write truncation leaked a raw
`EOFError`; the D11 fix widened the caught set to `gzip.BadGzipFile` / `EOFError`
and re-raises them as the documented `SealedArchivePayloadError`, and the reader
docstring now states the truncation-detection reality honestly. TRACKED
FOLLOW-UP (a real deferral, not closed here): read-time detection of a
near-complete truncation that decompresses cleanly would require a trailing
integrity marker in the archive format (a writer + reader change, out of scope
for this test campaign); today that case is caught by the AEAD backstop before
provisioning, never as a partial restore. Test:
`test_bundle_crash_windows.py` (30-80% truncation -> typed payload error at
read; member corruption -> typed layout error at read; near-complete truncation
-> AEAD refusal at import before provisioning; writer refuses to overwrite).

### bundle import - CONFIRMED (aborted archive invisible; staging cleanup NON-GOAL)

Actual behaviour at HEAD: `BucketMaintenanceService.import_` reads the whole
sealed archive into MEMORY (`read_sealed_archive`), validates the layout and
header, decrypts + strict-validates the bundle, and only THEN provisions the
bucket (`_provision_imported_bucket`, a create span writing K/dirs/M) and
`deserialize_profile_bundle` (S/B) inside a session. There is no on-disk
staging directory to extract or clean, so "staging cleanup" is a documented
NON-GOAL (moot - the archive never lands on disk during import). The
"aborted prefix is invisible to the manifest pointer" guarantee is confirmed
and stronger than the matrix framed it: a truncated / torn / wrong-schema
archive is rejected BEFORE any bucket store is written, so no partial bucket
is provisioned. A same-id re-import is guarded (collision refusal without
`force_replace`). Test: `test_bundle_crash_windows.py` (a truncated archive
fed to `import_` raises `BucketImportError` and provisions no manifest).

### attachment / evidence put - CONFIRMED (orphan blob harmless); GC sweep NON-GOAL

Actual storage model at HEAD (the matrix's "B (bytes) then S" implies a
filesystem blob store separate from SQL - wrong for this store): the modern
`AttachmentStore` writes BOTH the content-addressed blob and its manifest as
rows in the SAME encrypted SQLite secure-object store (two separate
`SecureObjectRepository.save` calls: `put_bytes`/`put_file` then
`write_manifest`). A crash between leaves an orphan blob row with no manifest
row. Recovery: the orphan blob is keyed by `sha256(content)` (content-
addressed), unreferenced (`load_manifest` raises `AttachmentNotFoundError`),
and harmless; `put_bytes` is idempotent (`if objects.exists(...): return
digest`), so a retry reuses the orphan rather than duplicating it. An
orphan-blob GC sweep is a DOCUMENTED NON-GOAL: an unreferenced content-
addressed blob is inert and dedup-reused on retry. (The filesystem
`EncryptedBlobStore` roots the rotation walks - `aeat_blob_store_dir`,
`aeat_attachments_dir` - are the secret-store / blob-manifest surfaces
covered by the rotation row below, a different substrate from this SQL-backed
attachment store.) Test: `test_attachment_crash_windows.py`.

### master-key rotation - CONFIRMED per-store probe-skip idempotency; keystore leg is custody-owned

Actual surface at HEAD: two production rotation primitives, each per-item
atomic and probe-skip idempotent - `rotate_master_key` over the
`*.envelope.json` file consumers (per-file tempfile + `os.replace`;
already-rotated files decrypt under the new key first and are skipped) and
`rotate_blob_stores` over the blob-manifest wrapped DEKs (per-blob re-wrap;
same probe-skip). There is NO single orchestrator wiring the two together
(no application-layer caller of either primitive), so the "rotation across
all stores" is convention: run both, and on a crash re-run both. The
mixed-key window across the two ciphertext stores is recovered by the
probe-skip re-run (already-rotated items skipped, un-rotated items rotated).
The THIRD store, the keystore bucket DEK (`bucket.dek.json`), is re-wrapped
value-preservingly by the custody / rekey path under the sanctioned
`wrap_dek` / `unwrap_dek` helpers - its DEK VALUE never changes on a master-
key change, which is precisely why the SQL `secure_objects` store is
intentionally NOT in the rotation plan (its ciphertext stays valid under the
unchanged DEK). Test: `test_rotation_crash_windows.py` interrupts a rotation
across envelope files, blob manifests, and the bucket-DEK keystore, proving
the mixed state fails a new-key-only read for the un-rotated store and that a
probe-skip re-run of all three recovers every partial state under real
crypto (no patched primitives).
