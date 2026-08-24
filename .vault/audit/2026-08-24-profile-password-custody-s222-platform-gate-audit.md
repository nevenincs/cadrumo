---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:56e3deba8499a4de4927593de19d247c171c6dc748b05cce5fe9f0bad581bfbb'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S222 platform gate review`

## Scope

Independently review the S222 rerun of the complete S209 native-Windows and WSL/Linux KDF and machine-secret platform gate. Verify exact descriptor attestation, ready-before-secret ordering, platform skips, real subprocess coverage, and the narrow timeout-budget change required by mandatory recovery creation.

## Findings

### current-head-platform-evidence | MEDIUM | Recorded counts predate a later same-module platform-test refactor

The S222 evidence truthfully records the four commands and results obtained for the intended change: native Windows KDF 18 passed with one POSIX-only skip, native subprocess matrix 71 passed with one POSIX-only skip, WSL KDF 19 passed, and WSL subprocess matrix 70 passed with two Windows-only skips. The only S222 behavioral delta in that measured tree raises the real profile-create helper's `subprocess.run` timeout from 45 to 120 seconds in both Windows and POSIX arms. It does not change commands, inherited HANDLE or `pass_fds` allowlists, ready-before-secret behavior, descriptor-closure canaries, recovery proof, success assertions, KDF configuration, skip markers, or production code. An independent native rerun of both stdin and fd profile-create cases passed through real subprocesses in 75.90 seconds, confirming the old 45-second budget is no longer sound and the 120-second budget is not a bypass.

However, later commit `4c0bcae136` modifies the same subprocess module after those four gate runs: it combines the mutually exclusive Windows and POSIX recovery tests into one runtime-dispatched platform test and removes the separate bootstrap-interpreter invariant test. Consequently the recorded pass/skip counts no longer describe current HEAD, and the exact complete native/WSL commands have not been rerun against that changed collection. The functional Windows recovery test still launches `bootstrap_interpreter()` through a real process and would expose a launcher that cannot consume its allowlisted inherited HANDLEs, so no direct custody weakening is established; the blocker is closeout evidence freshness and exact-count truthfulness.

No CRITICAL or HIGH finding was identified. The reviewed timeout change itself preserves the S209 exact descriptor attestation, worker isolation, real KDF execution, fail-closed supervision, and secret-channel assertions.

## Recommendations

Rerun the complete native Windows and WSL KDF/subprocess commands at current HEAD after `4c0bcae136`, then replace the S222 matrix counts and platform-skip notes with those observed results. If `4c0bcae136` is unrelated concurrent work and excluded from S222, pin the execution evidence explicitly to the reviewed pre-refactor commit instead of presenting its counts as a current-HEAD gate. Do not reopen the 45-to-120-second timeout decision unless the refreshed real profile-create cases reveal a non-timing failure.
