---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:022056396202ae5f7adec4c63e83657c5ba2f3b11125367750051e38a8461935'
step_id: 'S74'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Record and verify that the profile inspect surface already refuses on the ambiguity error

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`

## Outcome

The surface refuses correctly, and it did so before this campaign began. It raises a boundary refusal keyed `cli.config.profile.preflight_revision_ambiguous`, carrying the modelo, the period token and both candidate revision ids taken from the typed `candidate_ids` tuple rather than parsed out of a message. No code change was needed.

**Verified by exercising it, not by reading it**, which is the whole reason this row was opened. Two tests now cover it where none did:

- The ambiguity path raises the boundary refusal and its context names **both** candidate revisions. Asserting the candidates arrive is what proves the typed channel is consumed rather than merely caught: a surface can catch the error and drop them, and that reads identically at the catch site.
- A **positive control** proves the first assertion is about ambiguity rather than about "some refusal happened". A filing year resolving no revision at all must produce the `preflight_revision_unresolved` key instead. Without it, a surface raising the ambiguity key unconditionally would pass the first test while telling an operator the wrong remedy for the opposite condition.

The reason a read was not accepted as evidence: this campaign found three surfaces that looked handled and were not - a notice that read as wired had no caller, a box-number marker that read as matching covered under one percent of a modelo, and a record declared required was never written by the writer. Read-then-conclude is how all three survived.

## Verification

    uv run --no-sync pytest <the new module> -p no:randomly -n0 -q
    2 passed in 9.68s

    uv run --no-sync ruff check / ruff format --check / ty check   All checks passed!

The positive control is the anti-vacuity device here rather than an out-of-repo mutation: the refusal is caught inline in the resolver with no seam to suppress, so the discriminating evidence is that the two conditions produce two different keys.

## Notes

Two defects in the first draft, both caught by running it: the relative import depth was one level short, resolving to `cadrumo.entrypoints.application`, and `Period` was constructed through a `parse` classmethod that does not exist - the real constructor is `from_year_and_code`. Both would have been invisible to a reading of the test.

Nothing about this row's subject changed. Its value is that the claim is now measured, and the row that originally named this surface as needing work was re-pointed to the caller that actually lacked handling.
