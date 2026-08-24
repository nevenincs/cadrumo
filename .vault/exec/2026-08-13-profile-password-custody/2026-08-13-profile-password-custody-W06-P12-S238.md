---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0421a178567b92a642d7f00ac827e6fd0dd2014802137b33ecc7dab2348e2e5b'
step_id: 'S238'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Remove inactive profile deletion from the root login gate while preserving active-profile refusal, explicit confirmation, custody preflight, and exact target binding in real subprocess execution

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py and src/cadrumo/entrypoints/cli/_config/_profile_delete.py and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/application/config_reset.py and src/cadrumo/application/user_profile/_custody_repository.py and src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/user_profile/_custody_transactions.py and src/cadrumo/application/user_profile/_lifecycle.py and src/cadrumo/application/user_profile/tests/test_custody_transactions.py`

## Description

- Reclassify exact profile deletion from the root login-gated registry to a
  dedicated sessionless target-destruction leaf exemption.
- Preserve exact label resolution, active-pointer refusal, confirmation,
  retention assessment, and journal-bound custody destruction at the leaf.
- Remove the in-capsule bucket lock from the Windows rename span while retaining
  custody transaction locking and immutable inventory revalidation.
- Persist inactive-only authority in the custody journal and revalidate it under
  the canonical reentrant pointer transaction before destructive owner effects.
- Add real subprocess proofs for logged-out inactive deletion success and active
  deletion refusal, including post-state listing assertions.

## Outcome

Logged-out operators can delete only an exact inactive named profile through the
real root entrypoint. Active deletion still returns the typed boundary refusal
and leaves the profile active and listed. The admission record cites both
subprocess proofs so later drift makes the exemption gate fail.

## Notes

- RAG discovery grounded the change in the accepted per-profile custody ADR and
  located the stale negative admission beside the sessionless deletion owner.
- Exact subprocess tests passed 2 tests; admission, login-gated, profile-delete,
  and destructive-confirmation suites passed 89 tests; command graph and
  authentication posture passed 38 tests; Ruff and ty passed.
- The durable crash/resume guard passed natively and under WSL/POSIX; final
  formal review passed with no remaining findings.
- The complete subprocess lifecycle module passed 17 tests and failed 3
  unrelated host/stale-expectation cases: two require unavailable OS-keychain
  persistence and one expects retired wording.
