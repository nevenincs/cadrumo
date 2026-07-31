---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:455f082d4e8d8f39b12734417ad0449a0066ea7868dd51596bee2998aeff731b'
step_id: 'S35'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Compose strong profile logout by closing and evicting the current BucketSession before clearing the active pointer under the existing pointer transaction, then let provider bookkeeping unwind through its owning context and release the pointer sidecar lock without inventing a provider cache or bucket-lock authority

## Scope

- `src/cadrumo/application/user_profile/_orchestration.py`

## Description

- Rebuild the resident Vaultspec-RAG code index and ground logout, pointer ownership, provider lifetime, lockfiles, and resolver precedence before editing.
- Reconcile the stale provider-cache and bucket-lock premises against the shipped lifecycle authorities.
- Acquire the existing pointer transaction before teardown, close and evict the current bucket session, then clear the pointer only after successful close.
- Leave provider bookkeeping with the provider context that owns it so normal CLI resource teardown remains identity-safe and idempotent.

## Outcome

- Landed the implementation in `2d8154d64c` after plan reconciliation in `576fdd6000`.
- Ruff passed for the touched production file.
- Twelve orchestration and pointer-transaction tests passed in an isolated frozen environment.
- The uncached import graph analyzed 3,424 files and 16,172 dependencies with five contracts kept and none broken.
- Fresh-RAG formal review passed with no findings and confirmed lock order, close-before-clear failure semantics, idempotency, provider-context teardown, facade imports, and explicit-override limitations.

## Notes

- The plan and ADR assumed a long-lived OS-keystore session cache and logout-owned bucket lockfile. S32 proved the cache is retired, and exact scans found no production bucket-lock acquisition for logout to release.
- The real lock released by S35 is the active-pointer sidecar lock owned by `active_profile_pointer_transaction`.
- Explicit `CADRUMO_ACTIVE_PROFILE` or root `--profile` inputs remain higher-priority external selectors. Logout closes the current process session and clears the durable local pointer but cannot mutate the caller's parent environment.
- No new cache, provider registry, bucket-lock authority, compatibility path, data loss, skipped test, persistent failure, or runtime scaffold was introduced.
- The shared damaged `.venv` remained untouched; every Python-backed command used an isolated frozen environment.
