---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:791a77264b0c68613fe7a81b7319d494d98da03c67fccf131f524bdc7b6c0664'
step_id: 'S19'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Hold every auth provider to the identity guard, since each binds a comparable NIF at session bind and an absent expectation silently disarms the downstream session check

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Establish what identity each provider actually binds at session bind, rather than inferring it from the type annotations.
- Confirm the certificate provider parses a normalised tax identifier from the certificate subject and refuses a session that has none, so its identity is comparable.
- Confirm the permanente provider carries the same identity on its own session metadata.
- Return the profile identity as the expectation for every provider, since an absent expectation makes the downstream session comparison pass rather than skip.
- Keep the pre-flight credential comparison for both Clave modes, which the permanente mode never received.
- Leave the certificate to the session-bind comparison, because it has no operator-configured credential to check before a browser opens.
- Pin the expectation across the whole provider enum, so a provider added later cannot inherit the same silence.
- Correct two earlier tests that asserted the old behaviour, one of which documented the gap in its own comment.

## Outcome

Two new cases plus two corrected ones in `src/cadrumo/application/auth/tests/test_clave_credential_resolution.py`, fourteen in the file.

`uv run --no-sync pytest` over the auth, live and config-CLI trees reported `455 passed in 107.40s`. The file alone reported `14 passed in 9.53s` at the committed HEAD.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!`.

## Notes

The question posed was whether a certificate session even has an identity worth comparing, and the answer decided the shape of the fix. It does: the provider parses a normalised tax identifier out of the certificate subject and marks the session invalid when it cannot, so no provider needed the exemption the guard was effectively granting two of them. Widening was therefore the right move rather than declaring a limit, which would have been the alternative had any provider genuinely lacked one.

The second-order effect is the part that made this more than a one-line change. The guard's return value is what the session comparison downstream consults, and that comparison treats an absent expectation as nothing to check. So the early return did not merely skip the pre-flight comparison, it disarmed the session comparison as well, and the second failure is invisible from the call site because it looks like an ordinary optional value.

Two tests had to change because they asserted the old behaviour, and one carried a comment stating that only one provider bound a session to the profile identity. Tests that encode a gap read as documentation of intent, which is how a hole survives review.

The whole worktree's git index was locked twice during this Step, once for roughly six minutes with zero commits landing and the lock frozen at zero bytes. It was reported rather than cleared, on the same reasoning as before, and resolved without intervention.
