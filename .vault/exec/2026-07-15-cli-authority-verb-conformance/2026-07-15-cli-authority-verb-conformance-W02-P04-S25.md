---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:dbc7a7943f58559217b8f790aa14afd42d8a21d28c60e9412d0fb450ec01cbea'
step_id: 'S25'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove exact pointer bytes and atomic write and clear behavior through real child-process interruption

## Scope

- `src/cadrumo/core/tests/test_bucket_pointer.py`

## Description

- Ground the accepted pointer contract with fresh explicit-port code and ADR searches, then corroborate the public facade, implementation, and nearest process-test analogues with exact symbol searches.
- Exercise capture and replacement with a payload containing a UTF-8 byte-order mark, invalid UTF-8, a null byte, line feed, carriage-return line feed, and a trailing carriage return.
- Prove direct clear of an existing pointer, repeated clear of an absent pointer, and `restore_pointer(None)` against the real filesystem.
- Spawn a real pointer writer with a distinct 16 MiB payload, observe its process-qualified randomized staging file while the child is alive, interrupt it, and require the visible pointer to remain one complete old or new payload.
- Bound and clean every spawned-process path with join, terminate, kill, close, and test-owned staging-file removal.
- Run repeated focused interruption tests, the complete pointer and atomic-write lane, Ruff, the uncached five-contract import graph, and post-change semantic and exact duplication searches.

## Outcome

PASS. The public pointer boundary now has mutation-sensitive real-behavior coverage for exact bytes, observable clear idempotence, restrictive POSIX mode, and interrupted atomic replacement.

- The exact-byte node replaces distinct prior content without decoding, parsing, or normalizing the arbitrary payload and leaves no staging file after success.
- Direct clear removes an existing pointer, a repeated clear remains successful, and `restore_pointer(None)` clears a recreated target.
- The spawned-child node observes the live child process's actual hardened staging path before interruption, requires a non-success exit, and accepts only an exact complete old or new target.
- The interruption node passed ten consecutive isolated runs; the strengthened two-node check also passed.
- The pointer, pointer-IO, atomic-write, and sensitive-persistence-policy lane passed all 34 tests, and focused Ruff passed.
- The fresh uncached import graph analyzed 3,418 files and 16,136 dependencies; all five contracts were kept and zero were broken.
- Post-change RAG and exact searches found one S25 interruption helper and one canonical core restore-to-atomic-writer delegation; the later caller-routing duplicates remain assigned to S26-S28.

## Notes

Repeated clear proves observable idempotence; it does not directly observe the best-effort parent-directory sync. The test makes no Windows parent-directory durability claim.

A force-killed child can leave its randomized staging file because process termination does not run the writer's `finally` block. The parent test removes only that child process's staging files in its own `finally`; it does not claim the writer cleans up after an operating-system kill.

This Step changes no production source; its implementation scope is test coverage only. Closing S25 leaves S26 as the next caller-routing Step. It does not route later callers, define rollback concurrency or compare-and-swap semantics, or change lifecycle ordering assigned to S26 and later Steps.
