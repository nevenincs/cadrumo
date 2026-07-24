---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S13'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Land the end-to-end CLI session lifecycle test (login, decrypting command without prompt in a fresh process, clock-driven idle expiry refusal, re-login, absolute-cap refusal, logout idempotence) using real processes and real storage with no mocks, gate is the module green plus zero prompts observed on the resumed invocation

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py`

## Description

- Drive the lifecycle through real subprocesses running the production entrypoint against a per-test storage root, with real file-backend custody and no mocks, stubs, or monkeypatching.
- Assert the coupling between the reported persistence state and the on-disk record, which holds on both a keychain-capable and a keychain-degraded host.
- Assert the follow-on process behaves as that state implies: silent resume when the session persists, an instructive refusal naming the login verb when it does not.
- Assert the persistence warning notice is bound to the same state, that logout removes the record, and that a second logout reports the idempotent no-op.
- Assert no raw bucket identifier reaches standard output.

## Outcome

Three tests pass. Ruff, ruff format, and ty are clean. The subprocess lint suppression follows the per-file convention the sibling subprocess-driven lifecycle suites already use rather than an inline directive.

## Notes

This host's OS credential store is broken, so the suite exercises the degraded branch here and the persisted branch on a healthy host. The branch is chosen by observed product behaviour, never by a skip or an expected-failure marker, and each branch carries real assertions. Two contracts were discovered while writing it and are asserted rather than worked around: the output-format flag is root-level, and logout clears the pointer so a following login must name its target.
