---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:0b9820b00018f96b423bd2a70ad7fda1c8750ac1fda9e86d098f7d08033f0b30'
related:
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# `profile-registration-password-policy` audit: `formal campaign review`

## Scope

Independent formal review of the current profile-credential campaign against the
accepted canonical-credential ADR, its research and reference trace, the live plan,
and the original fourteen-scalar TUI crash. The review followed the current code from
the pure core assessment through custody, recovery supervision, application
registration/rotation/proof mapping, TUI and scripted CLI presentation, locale and
error registration, generated API documentation, regression tests, and the S13 gate
record.

Each review phase began with semantic code and ADR discovery and was narrowed with
exact symbol searches against the current HEAD. The reviewer also reran the focused
unit lane (67 passed, 82 deliberately deselected) and the real integration lane (104
passed, 5 deliberately deselected). Those runs independently reproduce the original
fourteen-scalar TUI refusal as a localized expected outcome and exercise real scripted
creation, exact accepted-password unlocks, mutation-free refusals, recovery proofs,
and all four locale catalogues.

## Findings

### live-tui-refusal-matrix | medium | Most invalid boundaries bypass the real Textual submission surface

### secure-input-channel-prose | low | Shared secure-input documentation contradicts the live creation channel order

## Recommendations

- For `live-tui-refusal-matrix`, drive every transportable invalid boundary through the
  real `RegistrationApp` Pilot and assert live feedback plus submitted refusal, no
  worker error, localized pinned status, secret absence, and no persisted capsule.
  Exercise surrogate candidates through the widget's programmatic value boundary if
  Textual accepts them; otherwise retain the direct adapter case and record the widget
  transport limitation explicitly. Keep S14 open until this matrix is green.
- For `secure-input-channel-prose`, make the shared module description precise about
  which helpers it governs and correct the creation resolver's declared precedence.
  Do not change the accepted channel behavior as part of a documentation repair.
- After both findings are resolved, rerun the two focused lanes and the exact obsolete
  symbol and recovery-policy negative searches, then append an immutable resolution
  entry to this audit before closing S14. S15 must also preserve S13's honest statement
  that full-tree gates were not green on the mixed concurrent HEAD; focused success is
  not proof that those repository-wide commands passed.

## Resolution

Commit `e306d10802` closes `live-tui-refusal-matrix`. The parameterized 257-scalar,
1,025-byte, high-surrogate, and low-surrogate cases now set the real Textual password
and confirmation widgets, observe the `Input.Changed` feedback line, click the real
create button, and inspect the pinned refusal channel. Each case proves the exact typed
localized message, no worker error, no raw custody English, traceback, INTERNAL copy,
or candidate echo, and a race-safe empty storage boundary. Independent verification
passes all 15 tests in the TUI module in 23.41 seconds; the four remediated cases would
have failed the previous direct-presenter-only structure by never reaching these widget
assertions.

The same commit closes `secure-input-channel-prose`. The shared module now accurately
describes itself as the owner of three explicit input helpers while leaving each command
resolver responsible for configured sources. The creation resolver documents the live
precedence exactly: explicit bounded stdin, then an interactive no-echo prompt, then the
sanctioned configured fallback. No accepted channel behavior changed.

Post-remediation Ruff lint and format checks pass for the three changed files. The
complete focused unit lane passes 67 tests with 81 expected marker deselections, and the
complete focused integration lane passes 103 tests with 5 expected marker deselections.
Exact searches find obsolete names only inside their intentional negative-space tests,
and find no recovery production dependency on the profile-password assessment. No open
LOW, MEDIUM, HIGH, or CRITICAL finding remains. S14 may close and S15 may begin, subject
to the gate-honesty constraint above.
