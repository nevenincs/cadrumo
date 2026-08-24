---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e3b6a233a53b5e5d59315b552e7934ada19a0820c73f29c59c772f8ce4d1e734'
step_id: 'S221'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Re-run the complete S206 recovery-enrollment matrix across interactive, TUI, stdin, POSIX descriptor, Windows inherited-handle, mismatch, cancellation, collision, and publication-failure paths and persist the resulting evidence

## Scope

- `src/cadrumo/application/user_profile/tests/test_recovery_enrollment_at_creation.py and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/adapters/inbound/tui/tests/`

## Description

- Re-run the mandatory recovery-at-creation application, scripted CLI, interactive terminal, TUI, and subprocess-platform lanes against current HEAD.
- Exercise exact possession, malformed proof, mismatch, cancellation, descriptor preflight and collision, duplicate-label collision, handoff write failure, and pre-publication rollback through real custody storage and process boundaries.
- Run the Windows inherited-HANDLE creation test locally and provision a lockfile-pinned, isolated WSL test environment outside the worktree to execute the actual POSIX `pass_fds` creation test.
- Repair the nine focused static diagnostics in the lazy profile-projection facade and recovery test surfaces without changing custody behavior or adding an ignore, cast, mock, skip, baseline, or compatibility path.
- Run scoped Ruff and ty gates and submit the resulting source and evidence surface for independent review.

## Outcome

The complete current matrix passed 72 tests with no platform skip claimed as proof.

- Application enrollment, exact proof, delivery failure, publication rollback, and two-process label collision: 11 passed.
- Scripted CLI creation over stdin and inherited descriptors, malformed or mismatched proof, descriptor preflight and collision, write failure, and duplicate-label collision: 35 passed.
- Interactive terminal display/refusal, no-echo prompt, and manager registration: 13 passed.
- Full-screen TUI exact re-entry, cancellation, mismatch, and shutdown: 4 passed.
- Windows fresh-process stdin/descriptor creation, inherited-HANDLE recovery bootstrap, virtual-environment launcher bypass, and cross-scope descriptor collision: 8 passed.
- POSIX fresh-process inherited-descriptor recovery creation under WSL: 1 passed.

Scoped Ruff and ty both passed over the workflow facade and every listed S221 test surface.

## Notes

The Windows host cannot prove the POSIX contract, so the POSIX lane was run inside the isolated WSL environment rather than counted as a host-side skip. One final xdist TUI attempt returned no success outcome after an earlier green run; the mandatory sequential `-n0` rerun passed all four real TUI cases, so no deterministic production regression remained. The reviewer audit records the independent final safety assessment.
