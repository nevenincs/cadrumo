---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4371228be2619c6b3fb4d9755068620127b4aa73cc6873dc414ed2327045cee5'
step_id: 'S12'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Resolve the Clave credentials in the operator readiness probes and status surfaces through the same profile-first resolver the session entry uses, so a profile-borne credential reports as configured

## Scope

- `src/cadrumo/application/auth/_operator_probes.py`

## Description

- Split the resolver so the profile facts can arrive either from the lifecycle service, which needs an unlocked bucket, or from a projection a surface already holds.
- Keep the profile-beats-settings precedence in one function, so the session entry and the readiness surfaces cannot drift apart.
- Add a probe wrapper that resolves without refusing, because an absent credential is the state a readiness surface reports rather than a fault it raises.
- Degrade an unreadable profile to an empty projection, so a probe reports the credential absent instead of failing.
- Re-point the identity-state probe, the identity classifier, the standalone identity probe, the configure result and the login precondition at the resolved credential.
- Feed the configure result its own values directly, since it already holds the profile projection and need not open the record again.
- Promote the resolver, the facts model and the facts reader to the package facade so no consumer reaches into the private module.
- Resolve the preflight report's two contraste booleans through the same resolver after a review pass found them still reading the settings fields alone.

## Outcome

Thirteen tests in `src/cadrumo/application/auth/tests/test_operator_probe_credential_resolution.py`, each leaving the environment empty so a pass cannot be explained by the fallback.

`uv run --no-sync pytest` over the auth package reported `201 passed in 116.88s`, against `188` before this Step. An earlier run of the package plus the two consumer surfaces reported `235 passed in 195.99s`.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!` across the package.

The lazy-import ceiling gate names no site in the touched modules, so the split introduced no new function-local edge.

## Notes

The login precondition was the sharpest case and is worth naming separately from the status surfaces: it refused login outright for an operator whose credential sat on the profile, so the check meant to spare them a failed AEAT round-trip was itself the thing stopping them. Three tests hold the line in the other direction, proving the change did not blunt what the surfaces must still report: a credential disagreeing with the profile tax identity is still a mismatch, a credential absent from both sources is still absent, and an environment-configured operator still reports as configured.

The two readers were tempting to fix by giving the probes their own profile-first branch. That would have been a second copy of the precedence, which is the drift this Step exists to remove, so the resolution stayed in one function and only the way its facts are obtained differs.

An independent review pass caught a site this Step's first pass missed: the preflight report's contraste booleans still read the settings fields directly, so a taxpayer whose numero de soporte or validity date lived on the profile read false for a credential live authentication resolved fine. The identity reads were re-pointed but the contraste pair was not; enumerating the reads by the value they report, rather than by the identity concept, would have caught it. The report also gained a profile read as a result, so the redaction posture is now pinned by a test proving neither the identity nor either contraste value reaches the serialised report, instead of resting on the docstring that asserts it.
