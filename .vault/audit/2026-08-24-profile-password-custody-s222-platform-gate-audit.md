---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6dd9ba72b35250d60e9b82585a15f93cf23253299d6ebbadae6e97adcc9e569b'
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

### current-head-platform-evidence-resolved | MEDIUM | Fresh Windows and WSL matrices close the stale-count finding

At current HEAD `8ba379538256adc9146acc2623edd03e19e21e66`, the exact sequential integration command `pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py` passed natively on Windows with 70 tests in 524.11 seconds and in the isolated Ubuntu CPython 3.13 WSL environment with 70 tests in 1192.31 seconds. Neither run reported a skip. These are the current collection after `4c0bcae136`, so they resolve the prior MEDIUM evidence-freshness finding without changing the reviewed descriptor attestation, worker isolation, ready-before-secret sequencing, or fail-closed supervision conclusions.

No CRITICAL or HIGH finding was identified. The reviewed timeout change itself preserves the S209 exact descriptor attestation, worker isolation, real KDF execution, fail-closed supervision, and secret-channel assertions.

### refusal-snapshot-excludes-session-receipts | LOW | Refusal mutation proof omits session and receipt artifacts

`_storage_snapshot` excludes every file whose name contains `session` or `receipt`, while `_assert_refused` treats equality of that filtered snapshot as its no-mutation proof. The exact conflict, descriptor-refusal, and root/leaf-inapplicability cases therefore could not fail if a refusal created an acceleration session or receipt. This weakens the evidence for the accepted requirement that channel refusal precedes session activation. Source review found no production mutation, so this is a LOW test-coverage gap rather than a demonstrated custody defect.

## Recommendations

Treat the refreshed Windows and isolated-WSL results as resolving the MEDIUM S222 evidence-freshness finding; no further S222 platform rerun or source change is required by this review. Carry the LOW refusal-state witness gap into S223, where the fresh-context honesty review must ensure pre-read refusal assertions include session and receipt persistence artifacts.

Extend the refusal-state witness to cover session and receipt artifacts, or separately assert their absence, in the exact conflict and inapplicability tests. This must prove that selection refusal occurs before any session activation or persistence rather than excluding those artifacts from comparison.
