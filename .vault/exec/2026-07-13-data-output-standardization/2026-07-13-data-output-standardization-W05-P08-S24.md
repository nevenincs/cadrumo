---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:af63a02a8744fd5fd97f7f2925662e69d97d6956edfd38826b693d170f207db5'
step_id: 'S24'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Migrate the weak no-fsync atomic-write variants onto the helper

## Scope

- `bucket pointer`
- `outbound local store`
- `bucket manifest`
- `corpus bundle`

## Description

- Checked for peer WIP in all four target files before editing (`git diff`
  clean; no concurrent edits).
- `core/_bucket_pointer_io.py` `write_pointer`: migrated to
  `atomic_write_text` (standard tier). Deferred the import inside the
  function body rather than at module level -- this module is read during
  `Settings()` construction (`config.py`'s
  `_resolve_database_url_for_active_profile` imports `pointer_path`/
  `read_pointer` from it before `Settings` exists), and `core.atomic_write`
  transitively imports `core.locks`, whose module-level `get_logger(__name__)`
  call configures logging via `load_settings()` -- a module-level import
  here reproduced the exact circular-bootstrap failure the module already
  exists to avoid. Confirmed by reproducing the `ImportError` with an eager
  import first, then fixing it with the deferred form (matching this
  module's existing `core.config`/`core.errors` deferred imports).
- `adapters/outbound/storage/_local.py` `put`: migrated the object-payload
  write to `atomic_write_hardened_bytes` (hardened tier), per the
  2026-05-30 security-paths swarm audit's explicit recommendation to adopt
  the master-key `O_EXCL`/`0o600` pattern at this exact site. Left the
  sidecar write (`sidecar_path.write_text`) untouched -- it was never an
  atomic tmp+replace write at all (a separate, larger gap outside this
  Step's named scope) and the audit's recommendation was specifically about
  the payload file.
- `adapters/persistence/storage/bucket/_manifest_io.py` `write_manifest`:
  migrated to `atomic_write_text` (standard tier; this site already
  fsynced both the tempfile and the parent directory before migration, so
  research finding F2.1's "weak" characterisation had already been
  partially superseded in-tree -- the migration converges it onto the
  canonical helper regardless). Added an explicit `target.parent.is_dir()`
  guard before the write: the helper auto-creates its target's parent
  directory by default, which would have silently changed
  `write_manifest`'s contract from "refuse a missing bucket directory" to
  "provision it" -- caught by the existing
  `test_write_wraps_missing_bucket_directory_as_storage_validation` test,
  which is why the guard exists. Removed the now-dead
  `_unlink_tmp_manifest` helper and its now-unused `get_logger` import.
- `core/corpus_manifest/__init__.py` `build_corpus_bundle`: migrated to
  `atomic_write_bytes` (standard tier) over an in-memory `io.BytesIO`
  buffer, since the helper's public API takes a fully-formed payload, not
  an incremental writer, and `zipfile.ZipFile` needs to write incrementally.
  This is a net durability improvement: the prior direct-to-tmp-path zip
  write had no fsync at all. Deferred the import inside the function body,
  matching this module's existing deferred `from ..locks import
  fsync_parent_dir` in the sibling `save_corpus_manifest` function (same
  bootstrap-cycle concern); `save_corpus_manifest` itself is an untouched,
  separate stem-sibling dialect reserved for S25.
- Updated the three tests that asserted the old deterministic
  `target.with_suffix(target.suffix + ".tmp")` / `output_path.with_name(...
  + ".tmp")` sibling filename to glob-match `*.tmp` in the parent directory
  instead, since the helper's `tempfile.NamedTemporaryFile`-based naming is
  no longer predictable. Left the two "torn write" tests that plant a
  stray `.tmp` file at the OLD deterministic name unchanged -- their
  contract is about the READ path's robustness against a rogue sibling
  file, not about what the WRITE path itself names its tempfile, so they
  remain valid regardless of the migration.
- Added a new real-behaviour test for `_local.py` asserting the migrated
  payload write carries file mode `0o600` (POSIX-conditional, not skipped)
  and leaves no `*.tmp` leftover.
- Ran the repo-wide lazy-import-policy gate; it flagged both new deferred
  imports (`core._bucket_pointer_io -> core.atomic_write`,
  `core.corpus_manifest -> core.atomic_write`) as unclassified. Added both
  edges to the `CORE_INTERNAL_DEFERRAL` allowlist bucket (matching the
  existing edges for the same two modules' other deferred imports) and
  raised both the per-class site ceiling (37 to 39) and the total edge
  ceiling (471 to 473) in the same commit.
- Ran the production file-write inventory gate
  (`test_sensitive_persistence_policy.py`); it flagged three stale entries
  (the migrated call sites no longer directly call `write_text`/
  `write_bytes`/`open`) and three new sites (the AST-tracked
  `tempfile.NamedTemporaryFile`/`os.open`/`os.write` calls now live inside
  `core/atomic_write.py` itself). Removed the three stale entries, added
  three new ones, and kept the untouched `_local.py` sidecar entry.

## Outcome

Four migration sites landed in one commit (`74d7aedc4a`) plus the two gate
reconciliations (allowlist ceilings, inventory entries) in the same commit.
Targeted suites for all four touched production files plus their tests pass
(1080 tests, run sequentially with `-n0` after a `-n auto` run showed one
failure that did not reproduce in isolation or under a second `-n auto` run
-- a shared-tmp-dir xdist race, not a regression; see Notes).
`ruff check` clean on all ten touched files. `pytest --collect-only -q` on
the full tree collects cleanly (12839 collected). The lazy-import-policy
gate and the production file-write inventory gate both pass with their
ceilings/entries updated in the same commit as the code change they
govern.

## Notes

One transient failure during verification:
`test_remote_mirror_inspections_accept_opaque_encrypted_payload_round_trip[oauth-client]`
failed once under the default `-n auto` parallel run with a `content_hash
mismatch`, inside a traceback that (oddly) reported a `src/aeat/...` path
prefix that does not exist in this tree. Re-ran the single test file alone
under `-n auto`: passed. Re-ran the full combined target set sequentially
(`-n0`): all 1080 passed. Per the `aeat-local-execution` rule ("re-run
before blaming the code... more often a loader-cache race than a real
regression"), treated as a parallel-worker/shared-tmp-dir collision under
the large combined run, not a genuine regression from this Step's changes.
No other incidents. No behaviour change beyond the intended added
fsync/hardened-mode durability at each of the four sites.
