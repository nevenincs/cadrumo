---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:12f991ccd44f0b83d80e06b106bdf6d8b1e14e99224f1ef2e9d1e78dc61f8097'
step_id: 'S36'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Record the per-activity modulos precondition at the divergence predicate in every revision carrying it, and the mixed-scope warning at the profile schema, so the reasoning sits where the promoting change would be made rather than in a record

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/131`

## Description

- Find every revision carrying the divergence advisory rather than the one the
  assessment happened to read, since the precondition binds wherever the engine
  could be promoted.
- Record at each of those sites what must exist before the advisory is raised to
  blocking or the summed casilla is bound to the engine, quoting the órden's own
  summation sentence and naming the one-activity limitation.
- Record the companion warning at the profile schema, where the twelve fields
  live, that the section mixes two scopes while presenting as one.
- Confirm the registry still compiles and that each revision still carries its
  predicate, rather than assuming a comment is inert in a validated tree.

## Outcome

The reasoning now sits at the three predicate sites and at the schema, which is
where a change would be made, instead of only in an assessment record. All three
revisions compile and still carry their divergence predicate; the profile schema
loads and the wizard catalogue imports.

Verification: profile-schema and profile-application suites pass at 361, the
M131 and verification registry selection at 308. The change is comment-only,
confirmed by filtering the diff for non-comment lines and finding none.

Deliberately a note and not a gate. A gate refusing the binding would also
refuse it after the inputs become per-activity, which is the state worth
reaching - the same reasoning that kept two earlier findings in this campaign as
comments rather than rules.

## Notes

Three carry-forwards are recorded here because they must not inherit as done.

Nobody has run a two-activity módulos calculation end to end to watch the
advisory fire. The second-order effect - a correct filing drawing a false
advisory - is inference from reading the predicate chain, not measurement.

Two questions remain unverified. Whether the other renta modelo's
estimación-objetiva section carries the same shape was not checked; only the
pago-fraccionado one was. And whether any of the seven unit slots is genuinely
shared across activities rather than per-activity is a módulos-semantics
question left open - it would change how a per-activity model should be shaped,
not whether one is needed.

The registry legal-grounding gate is red at HEAD on a Python source-ref literal
in another campaign's committed module. It is unrelated: this change adds only
comments, which was confirmed by filtering the diff rather than assumed from the
nature of the edit.

One finding worth keeping visible: the section's twelve fields do not share a
scope. Four carry exclusion limits the law computes across all activities
together and are correctly flat; eight are per-activity and are not. The section
reads as uniform, so a reshaping that moved all twelve would look right and
would silently make four of them wrong.
