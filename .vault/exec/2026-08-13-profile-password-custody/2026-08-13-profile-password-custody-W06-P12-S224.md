---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cc02981484538d3b64b62fe30a1ef73cb8585a981e32d6e86e12e9baf6a94105'
step_id: 'S224'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Extend every machine-secret refusal and dispatch-state snapshot to include session and receipt artifacts while preserving unread-channel and cross-platform harness evidence

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Centralize the embedded durable-snapshot predicate shared by the portable/POSIX and Windows inherited-HANDLE harnesses.
- Include session and receipt payloads in every refusal and dispatch-state snapshot while excluding diagnostic logs and ephemeral lock files only.
- Preserve unread-stdin, unread-descriptor, descriptor-closure, Windows HANDLE bootstrap, and POSIX inherited-descriptor witnesses.
- Bite-prove the tightened predicate against real session-lock churn, then retain only the precise `.lock` exclusion required by the observed filesystem behavior.

## Outcome

The complete native Windows matrix passed 70 tests in 510.95 seconds against the final predicate. The complete WSL/POSIX matrix passed 68 of 70 cases; two late cases encountered a transient `SyntaxError` in a concurrently edited peer-owned acceleration-receipt module rather than an S224 assertion failure. After that peer file stabilized and compiled, all eight descriptor-refusal cases containing both interrupted cases passed natively in 43.49 seconds and under WSL in 128.46 seconds. Ruff and ty passed on the Step-owned module.

The initial stronger snapshot deliberately failed fifteen refusal cases because authentication probing leaves empty `.session.v2.json.lock` synchronization files. Narrowing the exclusion to the `.lock` suffix kept durable session and receipt JSON inside the equality witness. A subsequent current-HEAD targeted run reproduced the failure when a concurrent commit dropped that exclusion, confirming the gate bites; restoring it returned both platform subsets to green.

## Notes

Two concurrent commits touched the same test module during execution. The final source and evidence were re-read and rerun after each overwrite. The embedded snapshot predicate is now one shared source fragment consumed by both subprocess harnesses, reducing their prior duplication; the host-side helper remains a separate implementation because it executes in the parent test process rather than in generated child-interpreter source. No production mechanism, compatibility path, mock, skip, or xfail was added.
