---
tags:
  - '#reference'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:03f3ca3d004f63393e72432ffb9e1ae32bd227cb0e5210974a72d8e555161e37'
related:
  - "[[2026-08-13-secure-storage-hardening-successor-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `secure-storage-performance-hardening` reference: `current profile listing and secure storage execution paths`

This blueprint traces the empty and populated `config profile list` paths at
HEAD `b965eaf9f3`, records measured cost centers, and identifies the security and
durability seams an implementation must preserve.

## Summary

The handler in `src/cadrumo/entrypoints/cli/_config/__init__.py:194` resolves the
active pointer and calls `list_profile_buckets`. The projection in
`src/cadrumo/application/workflow/_profile_bucket_scan.py:67` constructs
`CommittedProfileRepository`; its `list()` at
`src/cadrumo/application/user_profile/_profile_repository.py:144` delegates UUID
inventory to `list_current_profile_custody_capsule_ids` at
`src/cadrumo/adapters/persistence/storage/custody/_capsule.py:721`.

An empty inventory checks retired locations and returns when `buckets/` is
absent. Direct execution costs below one millisecond and invokes no crypto,
KDF, keyring, or master key. End-to-end samples took 5.2--8.5 seconds, almost
entirely command resolution and imports. `application.workflow` eagerly imports
`_adapters` and `_engine` before `_profile_bucket_scan` at
`src/cadrumo/application/workflow/__init__.py:94`; config payloads create another
broad graph at `src/cadrumo/entrypoints/cli/_config_payloads.py:22`. The nearest
facade-preserving lazy pattern is `src/cadrumo/application/user_profile/__init__.py`.

On a populated store, `_aggregate_for` at
`src/cadrumo/application/user_profile/_profile_repository.py:176` is not a
summary read. `_load_current_custody_state` at line 88 locks and loads password
material, label, creation journal, and label head. Password material at
`src/cadrumo/adapters/persistence/storage/custody/_capsule.py:971` opens commit,
password envelope, and sentinel without decrypting. Independent helpers repeat
commit recognition. `verify_or_recover_initial` at
`src/cadrumo/adapters/persistence/storage/custody/_label_head_repository.py:54`
can mutate state during listing.

The implementation seam should expose a pure public summary inventory through
the owning facade. Its contract is deterministic UUID plus authenticated label.
It must not read envelope, sentinel, recovery, session, KDF, keyring, or
decrypted facts; must not repair; and must retain canonical commit/label
provenance. Full aggregate inspection and explicit repair remain separate.

Preserve the anchored discovery rules at
`src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py:191` and
retired-path refusal ordering at `_capsule.py:735`. Reuse the active label from
listing so rendering at `src/cadrumo/entrypoints/cli/_common.py:703` does not
resolve the profile again.

Verification needs a quiet-CI subprocess median, direct repository
microbenchmark, import/model-construction budgets, O(n) populated timing and
read counts, negative crypto/KDF/keyring/session spies, read-only filesystem
side-effect assertions, malformed-marker and retired-layout refusals,
concurrent rename/delete/label-update cases, and slow/denied/interrupted
filesystem behavior. Calibrate absolute budgets on a quiet runner; structural
and ratio gates are the portable authority.
