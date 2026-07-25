---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S16'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Bind the schema declared provenance set to UserProfileFact, widening it first for the shipped censal token, and gate every shipped fact path and provenance token against the schema

## Scope

- `src/cadrumo/domain/user_profile/_values.py`

## Description

- Sweep every provenance token shipped code can stamp before touching anything, confirming exactly one was undeclared.
- Widen the declared provenance set to carry the censal-artefact token, first and on its own, so enforcement could not red a shipped path.
- Validate the carrier's provenance against the declared set, read through the schema loader rather than a second copy of the enum.
- Gate every shipped provenance token against the declared set, enumerating each from its own definition site.
- Gate every literal fact path in shipped source against the declared field set, with an anti-tautology proof, because the gate asserts an empty list.
- Correct the roundtrip fixture, which carried invented paths and provenance tokens from before the schema bound either.
- Restore the readiness probe's session-free contract by declining the profile read when no bucket session is bound.

## Outcome

Ten tests across two new files in `src/cadrumo/domain/user_profile/tests/`.

`uv run --no-sync pytest` over the domain, application and adapter trees reported `1 failed, 12322 passed in 849.01s`. The single failure was another campaign's new censal-acquisition test, mid-flight during the run; re-run in isolation it reported `1 passed in 4.12s`.

The same sweep before the corrections reported `14 failed, 12270 passed`; every one of those fourteen is green.

`uv run --no-sync pytest` over the previously failing set reported `71 passed in 20.42s`, and the reported doctor regression's own command reported `3 passed in 24.39s`.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!` across the touched trees.

## Notes

Validating the fact path on the carrier was built, tried, and withdrawn. The value object holds no schema, so it has to reach for the bundled one, and four of the six tests it broke were injecting a synthetic schema, wizard flow or binding to isolate what they prove. Those fixtures are correct against the definition they inject and wrong only against the bundled schema, so enforcing there would have forced them to depend on a file that churns, which is exactly what they were written to avoid. The path contract moved to a source-tree gate, which covers the case that actually escaped, a literal path in shipped code, and leaves injection intact.

Enforcement broke the readiness probe's session-free contract, reported independently while the work was uncommitted. The probe reads the profile, the encrypted store refuses without a bucket session, and SQLAlchemy wraps that refusal in a driver error no domain except clause catches. The fix declines the read when no session is bound rather than widening the catch, so a genuine fault still surfaces as a red row. Stopping the wrapper at the persistence boundary would be the better fix and belongs to whoever owns that layer.

Two roundtrip fixtures had drifted from anything a profile could hold, carrying invented paths and invented provenance tokens. They were corrected to declared paths and declared tokens, which keeps the non-default discipline the roundtrip contract requires while making the record a shape the profile can really store.

The command DTOs that feed a fact still type their provenance as a bare length-constrained string. A bad value now fails at fact construction rather than at the DTO, so the refusal is a little later than it could be; tightening them was not in scope here.
