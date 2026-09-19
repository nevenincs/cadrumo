---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:db64951fd4317c75202f2b2ced7017c34705bc5c8701694b4b972e5e0da9801c'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S221 recovery-enrollment matrix review`

## Scope

Independent review of the S221 recovery-enrollment implementation and real-test evidence across application creation, scripted CLI, TUI, controlling-terminal, interactive refusal, subprocess machine-secret, Windows inherited-handle, and POSIX descriptor lanes. The review covered exact handoff and verification, secret non-disclosure, cancellation, mismatch, collision, publication-failure atomicity, and platform authority.

## Findings

### recovery-enrollment matrix | pass | No finding

The reviewed implementation requires recovery enrollment and exact proof before capsule publication; refusal, mismatch, cancellation, collision, and failed handoff paths remain fail-closed without durable profile state. Recovery material is confined to the handoff channels and transient custody buffers; the reviewed tests found no mnemonic or passphrase leakage in output, logs, arguments, environment, or results.

The final evidence is green: application creation and rollback/collision coverage is 11/11; scripted CLI is 35/35; interactive prompt and manager coverage is 10/10; controlling-terminal coverage is 3/3; TUI is 4/4 on the required sequential -n0 rerun; Windows inherited-handle coverage is 8/8; and the WSL POSIX descriptor lane is 1/1. One preceding xdist TUI run had a single transient app.outcome is None failure; the mandated sequential rerun passed all four tests, so it is dispositioned as an execution race rather than a custody defect. Scoped Ruff and ty checks are clean.

No CRITICAL, HIGH, MEDIUM, or LOW finding remains. No production or test code, plan, or exec record was changed during this independent review.

## Recommendations

Accept S221. Retain the sequential TUI disposition and the Windows/WSL platform lanes as the authoritative evidence for this matrix.
