---
tags: ['#audit', '#secure-storage-production-hardening']
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S46-001 | HIGH | Stale runtime-bound repositories could write after session drift

Initial review found that `SecureObjectRepository` instances created through the storage runtime could continue writing after the active session changed bucket or downgraded to the unsecured backend. The gap affected normal `save` calls and `save_with_raw_key`, with risk of cross-bucket or wrong-key writes after a stale repository handle survived a session transition.

Resolved in `src/aeat/adapters/persistence/storage/runtime.py`, `src/aeat/adapters/persistence/storage/sql/secure_objects.py`, and `src/aeat/adapters/persistence/storage/test_runtime.py`. Runtime-created repositories now carry the active session bucket id and require a secure active session; normal-key writes, raw-key writes, unsecured downgrades, and no-mutation outcomes are covered by real repository tests.

## S46-002 | HIGH | Stale runtime-bound repositories could quarantine rows after session drift

Second review found that `quarantine_unreadable_rows` could still mutate storage after the active session changed because it did not enter the runtime-bound session guard before creating quarantine state, copying rows, and deleting from `secure_objects`.

Resolved in `src/aeat/adapters/persistence/storage/sql/secure_objects.py` and `src/aeat/adapters/persistence/storage/test_runtime.py`. The quarantine path now calls `_check_session_freshness` before destructive work, and the regression test writes under one bucket, switches to another bucket with different key material, verifies refusal, and verifies the original row remains readable.

## S46-003 | MEDIUM | Runtime-bound diagnostic surfaces allowed stale-session reads

Final review found that raw and diagnostic surfaces still allowed access after the active session changed, including raw row iteration, namespace listing, decryptability probes, failure iteration, and metadata peeking. This was no longer a destructive write path, but it conflicted with the runtime-created repository contract that a secure active session remains required.

Resolved in `src/aeat/adapters/persistence/storage/sql/secure_objects.py` and `src/aeat/adapters/persistence/storage/test_runtime.py`. Runtime-bound public repository surfaces now call `_check_session_freshness` directly or route through a guarded method. A regression test covers the previously unguarded diagnostic surfaces under a drifted bucket session and verifies the original row remains readable after returning to the correct session.

## S46-004 | PASS | Final review found no remaining findings

The final `vaultspec-code-reviewer` pass confirmed S46-001, S46-002, and S46-003 resolved. No HIGH or CRITICAL findings remain, and no additional findings were reported.
