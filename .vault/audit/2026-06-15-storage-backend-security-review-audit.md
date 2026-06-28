---
tags:
  - '#audit'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
related: []
---



# `storage-backend-security-review` audit: `campaign close honesty review`

## Scope

Mandated `aeat-campaign-close-honesty-review` gate run BEFORE declaring the
33/33 campaign structurally complete. An independent fresh-context
`vaultspec-code-reviewer` was dispatched (read-only) against the seven
code-bearing commits of this session — S31 per-transaction-row catalogue and its
`apply_batch` primitive, S33 WAL, S30 streaming enumeration, S32 salt-artefact
removal, S08 read-time revision self-consistency, S23 fincas hexagonal inversion,
S25 sealed-archive surface — with priorities on the security/correctness-critical
data paths (S31 atomicity & cross-bucket isolation, S08 gate false-positives, S32
unrecoverable key-store risk, S33 at-rest test tautology under WAL, S30 ordering
regressions).

## Findings

**Clean (adversarially confirmed):**

- **S31 atomicity & isolation — CLEAN.** `apply_batch` is one `session_scope`
  (upserts + digest-addressed deletions all-or-nothing; proven by a real
  mid-batch `SecureObjectRevisionConflictError` rollback test). `_reconcile`
  bounds deletions to this bucket via the per-bucket membership index; cannot
  delete or leak another bucket's rows. `payload_hash` stability holds
  (`written_at = transaction.modified_at`, no `now()`/non-deterministic field in
  the envelope). No orphaned rows (dropped id emitted as a deletion in the same
  batch).
- **S08 gate — CLEAN.** `_canonical_instant` makes write-time and read-time
  `written_at` agree, so no false-positive on legitimate rows; correct for
  non-UTC inputs; composes with per-row writes.
- **S32 salt removal — CLEAN.** KEK derivation reads salt only from
  `master.kdf` (`salt_b64`); the standalone `salt` file is never read on any
  path. Unrecoverable-loss risk cleared.
- **S30 streaming — CLEAN.** No consumer relies on the dropped lexicographic
  order without re-sorting; the four documented-sorted consumers were given
  explicit sorts.
- **Exec-record completeness — SATISFIED.** All 33 closed steps have matching
  exec records.

**HIGH — at-rest plaintext scans tautological under WAL (FIXED).** Eight at-rest
plaintext-absence tests read the raw `aeat.db` in-context (engine open,
pre-checkpoint) without a positive table-marker assertion; under the WAL pragma
S33 enabled, the just-written rows sit in the `<db>-wal` sidecar, so the scans
passed regardless of whether encryption/redaction worked. They were outside
S33's migrated-reader set (which covered the marker-bearing post-dispose
readers). Affected: `llm` `test_redaction` / `test_cache`, `domain/modelos`
`test_secure_storage_roundtrip`, `outbound/aeat/sede` `test_observation_store`,
`profile` `test_inventory` / `test_assets`, `application/user_profile`
`test_lifecycle`, and the `storage/sql` `test_secure_objects_part1` at-rest
canary.

**MEDIUM — S31 atomicity proof did not land with its implementation (documented).**
`test_apply_batch.py` (the transactional-rollback proof) was swept into a peer's
broad-`git add` quality-churn commit before the S31 implementation commit, so the
primitive shipped without its proof in the same atomic commit (against the
relocation-atomicity discipline). The test is correct and green at HEAD; history
cannot be rewritten on the shared branch.

**LOW — S33 commit's "post-dispose" coverage claim was overbroad (corrected here).**
The S33 message asserted the un-migrated readers were all post-dispose /
marker-verified; the HIGH finding shows several were pre-dispose and marker-less.

## Recommendations

- **HIGH — DONE.** Routed all eight at-rest scans through `read_db_at_rest_bytes`
  (main file + `-wal` sidecar), whose `-wal`-scanning contract is locked by
  `test_read_db_at_rest_bytes_includes_the_wal_sidecar`; the assertions are now
  non-tautological (a broken-encryption regression surfaces the plaintext in the
  `-wal` bytes the scan covers). All eight pass under WAL.
- **MEDIUM — accepted.** No code action; recorded for honesty that the
  `apply_batch` proof landed one commit early via peer churn. Confirmed green at
  HEAD.
- **LOW — corrected.** This audit narrows the S33 coverage claim.

## Codification candidates

- **Source:** HIGH finding (at-rest scans tautological under WAL).
  **Rule slug:** `at-rest-scans-read-the-wal-sidecar`.
  **Rule:** A test that asserts plaintext is absent from the on-disk SQLite
  store MUST scan through `read_db_at_rest_bytes` (main file + `-wal` sidecar),
  never a raw `db_path.read_bytes()`; under WAL the just-written rows live in the
  sidecar, so a main-only scan passes tautologically and silently stops
  defending the at-rest-encryption guarantee.
  **Status:** candidate only — first encounter (WAL was just enabled by S33).
  Per the `vaultspec-codify` discipline, promote after the lesson holds across at
  least one more cycle (e.g. the next new at-rest test that correctly uses the
  helper, or a peer reintroducing a raw read that the lesson would have caught).


