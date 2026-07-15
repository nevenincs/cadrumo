---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S25'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Migrate the remaining stem-sibling atomic-write sites onto the helper

## Scope

- `envelope`
- `blob store`
- `secret store`
- `rotation`
- `env_io`
- `corpus manifest`
- `locales`

## Description

- Checked for peer WIP in all seven target files before editing (`git diff`
  clean; no concurrent edits). Confirmed wave-1 review PASS before starting,
  per the coordinator's green-light.
- `envelope/_envelope.py` `save_envelope` and `save_encrypted_envelope`:
  migrated both to `atomic_write_text` (standard tier). Removed the now-dead
  `_cleanup_tmp_file` helper and its `tempfile`/`os`/`fsync_parent_dir`
  imports (all had zero remaining call sites after both functions were
  migrated). Eager top-level import of `core.atomic_write` -- confirmed by
  standalone import that this module carries no bootstrap-adjacency
  concern.
- `blob_store/_blob_store.py` `_atomic_write_bytes`: migrated to
  `atomic_write_bytes` (standard tier), eager import (same confirmation).
- `secret_store/_secret_store.py` `_write_index`: migrated to
  `atomic_write_text` (standard tier), deferred import matching this
  method's pre-existing deferred `core.locks` import (same
  bootstrap-adjacency reasoning the method already carried); the old
  `fsync_parent_dir` deferral retires since `atomic_write_text` now owns
  that step internally. Removed the redundant `self._store_dir.mkdir(...)`
  call (the helper's own parent-mkdir covers it; `target.parent ==
  self._store_dir` via `_index_path()`).
- `_rotation.py` `_atomic_write`: migrated to `atomic_write_text` (standard
  tier). This dialect never fsynced its tempfile before `os.replace` (only
  fsynced the parent directory after) -- migrating closes a real durability
  gap, not merely a naming convergence.
- `core/env_io.py` `_atomic_write_text`: migrated to
  `atomic_write_text`, deferred import. Investigated the module's
  documented "minimal install context, storage substrate may be
  unimportable" property before migrating: confirmed by a standalone
  `python -c "import cadrumo.core.env_io"` probe that this module ALREADY
  unconditionally imports `core.config` today, via its own module-level
  `_log = get_logger(__name__)` call (`get_logger` triggers
  `configure_logging()` -> `load_settings()` on first use) -- so the
  "avoid a hard dependency on Settings" property the deferred `core.locks`
  import's comment described no longer holds in practice; the deferred
  import is retained anyway to keep this module's OWN eager import
  footprint unchanged for callers that merely import it without writing,
  matching the S24 precedent's discipline rather than relying on the
  now-moot Settings-avoidance claim.
- `core/corpus_manifest/__init__.py` `save_corpus_manifest`: migrated to
  `atomic_write_text` (standard tier), deferred import matching the
  sibling `build_corpus_bundle` migrated in S24 (same bootstrap-cycle
  concern, same module).
- `locales/manager.py` `_rewrite_locale_mapping`: migrated to
  `atomic_write_text` (standard tier) over an in-memory `yaml.dump()`
  string (the helper's public API takes a fully-formed payload; `yaml.dump`
  needs a stream, so the payload is rendered to a string first). Eager
  top-level import (module already carries a heavy transitive Settings
  dependency via its calculations-registry / workbook-parity import chain,
  confirmed by the same standalone-import probe technique).
- **Hidden-file quirk decision** (locales/manager.py): converged the
  `.{name}.` leading-dot tempfile prefix onto the canonical non-hidden
  naming. Investigated every directory-scan call site in the module
  (`self.locales_dir.glob("*.yml")`, four call sites) -- all filter by the
  `.yml` suffix, which a `.tmp`-suffixed tempfile never matches whether or
  not it also carries a leading dot. Checked git history for the naming
  convention's origin: it was introduced in the SAME commit
  (`4a3511c9d6f`, "fix(locales): atomically rewrite catalogue mappings",
  authored the day before this Step) that first added atomicity to this
  write path -- no older precedent, no documented functional reason found.
  Concluded there is no reason to preserve the divergent dialect; converged
  it.
- **Master-key reference-implementation decision**
  (`master_key/_master_key_io.py` `atomic_write_secure_bytes`): left
  UNTOUCHED, not migrated to delegate. This function is the literal
  hardened-tier template `atomic_write_hardened_bytes` was modelled on in
  S23 (byte-identical logic today). Reasoning for keeping it standalone
  rather than inverting the dependency: (1) it is the single
  highest-security-sensitivity write path in the codebase -- it persists
  the master encryption key material itself; (2) keeping it self-contained
  means a security review of this exact file needs to trust nothing beyond
  `core.locks`/`core.logging`, not also audit a shared, broader-scoped
  helper that many unrelated, lower-sensitivity call sites also import and
  could indirectly influence through a future change; (3) there is zero
  correctness benefit to delegating since the logic is already
  byte-identical -- only a coupling cost this site does not need to take
  on. Either choice was acceptable per the coordinator's framing; this is
  the reasoned choice, recorded here.
- Ran the lazy-import-policy gate; it flagged two new deferred-import
  edges as unclassified (`secret_store._secret_store -> core.atomic_write`,
  `core.env_io -> core.atomic_write`). While reconciling, found three now-
  STALE allowlisted edges the migrations retired (`secret_store._secret_store
  -> core.locks`, `core.env_io -> core.locks`, `core.corpus_manifest ->
  core.locks` -- all three modules' deferred `core.locks` imports were
  replaced by deferred `core.atomic_write` imports that internally own the
  `fsync_parent_dir` call). Added the two new edges, removed the three
  stale ones, and adjusted the `CORE_INTERNAL_DEFERRAL` site ceiling and
  the total edge ceiling to the net change (+1 overall: 2 added, 1 net
  retired after S24's +2 and this Step's +2/-3).
- Ran the production file-write inventory gate; it flagged 8 stale tracked-
  call entries for the migrated sites (their direct `write_text`/
  `write_bytes`/`tempfile.NamedTemporaryFile` calls no longer exist at
  those file/function pairs). Removed all 8; no new entries were needed
  because the three `core/atomic_write.py` entries S24 already added cover
  every AST-tracked call (`tempfile.NamedTemporaryFile`, `os.open`,
  `os.write`) now living inside that module, regardless of which caller
  reaches it.

## Outcome

Seven migration sites landed in one commit (`9302f3e918`) plus both gate
reconciliations (allowlist edges/ceilings, inventory entries) in the same
commit. Targeted suites for all seven touched production files plus their
existing tests pass unchanged in shape (759 tests, run sequentially with
`-n0`). `ruff check` clean on all nine touched files. `pytest
--collect-only -q` on the full tree collects cleanly (12856 collected).
The lazy-import-policy gate (5/5) and the production file-write inventory
gate (2/2) both pass with their edges/entries reconciled in the same
commit as the code change they govern. The untouched `master_key` test
suite (185 tests) still passes, confirming the reference implementation
was not disturbed.

## Notes

No incidents. Two deliberate non-migrations, both reasoned above: the
master-key hardened-tier reference implementation (kept standalone by
design) and the locales hidden-file naming quirk (converged, not kept, per
the investigation finding no functional dependency on it).

**Deferred finding for the W06 honesty review** (per the coordinator's
explicit instruction to carry this forward from S24): the
`adapters/outbound/storage/_local.py` `put()` sidecar write
(`sidecar_path.write_text(...)`) is STILL not an atomic tmp-then-replace
write at all -- it is a direct in-place write with no tempfile staging, no
fsync, and no crash-safety guarantee, unlike the object-payload write
alongside it (migrated to the hardened tier in S24). A crash between the
payload write and the sidecar write, or mid-sidecar-write, can leave a
committed object file with a missing, truncated, or stale sidecar --
which `_load_sidecar`/`get()` would then either refuse to read or read
with corrupted metadata. This gap was identified but deliberately left out
of scope in both S24 and S25 (the team lead's S24 brief named only the
payload write; S25's scope was the seven stem-sibling sites named above),
so it remains open. Recommend a follow-up Step migrating the sidecar write
onto `atomic_write_text` (standard tier is sufficient; the sidecar
carries only hash/length/label metadata, not the payload itself) before
this campaign is declared closed.
