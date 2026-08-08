---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8521dea117fc335f63877d5188535abf83c35a7d89a674a620d7e7a33c8ad014'
step_id: 'S220'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Give the honesty gate's helper-following branch a guard that fails when the branch is deleted, and correct the docstring and record that claim it. Measured: removing the branch entirely leaves all five tests passing including the anchor written to pin it, and following adds nothing on any of the 19 live rows, because every predicate spells the attribute out in the call arguments as _identified_in_another_member_state(criteria.issuer_identification_state), which a plain attribute walk already finds. The branch would only matter for a helper handed the WHOLE criteria object, and no row does that today. So the anchor's failure message advertising that either the branch stopped working or the rows stopped reading identification is blind to the first cause while its name convinces a reader it is covered. Add a synthetic predicate in the test module that hands the whole criteria to a module-local helper and assert it yields the attribute the helper reads, which exercises the branch without requiring the production table to adopt that shape. Deleting the branch is the defensible alternative

## Scope

- `src/cadrumo/domain/iva`

## Description

- Add a lookup seam to the extractor and to the fact resolver, so a helper
  declared in the test module is followable without the production table
  adopting a shape it has no reason to.
- Add two synthetic predicates and a module-local helper: one delegating
  everything to the helper, one reading an attribute inline and delegating the
  identification.
- Add the branch's real guard, asserting both shapes yield the delegated read.
- Add the measurement that decides keep-versus-delete, pinning that the mixed
  shape loses the identification silently when nothing is followed.
- Narrow the anchor's docstring and failure message to the one cause it can
  observe, and correct the module docstring's account of what following is for.
- Correct the originating record, which recorded the anchor as pinning the
  branch.

## Outcome

**The row's measurement reproduced exactly.** Following changes the extracted
set on 0 of the 19 live rows. Every predicate spells the attribute out in the
call it makes, and the argument is an attribute OF the subject, so the plain
walk records it before any helper is considered. Removing the branch left all
five tests green including the anchor named for it.

That anchor was the defect rather than the branch. Its failure message named two
possible causes and could observe only one, while its name persuaded a reader
the other was covered -- an assertion advertising a detection it does not have,
which is worse than no assertion because it stops anyone looking.

**Kept rather than deleted, on a measured asymmetry rather than a preference.**
Deleting was the defensible alternative and the row said so, so the decision was
made by measuring both shapes the branch could ever matter for:

- A predicate delegating EVERYTHING extracts nothing without the branch. The
  unreadable-row refusal already catches that, out loud. Fail-closed, visible,
  and the branch is not needed for it.
- A predicate reading one attribute inline and delegating the identification
  extracts that one attribute. Non-empty, so no refusal fires; the fact set
  comes back carrying no party fact at all; and the row passes the honesty
  comparison while its predicate turns on an identification it never declared.

The second is the silent direction this module exists to catch, and it is the
whole case for the branch. Recorded as a claim about a FUTURE row, which is why
it is pinned as a test rather than left as a comment.

**Threading the seam through the fact resolver was load-bearing, not tidiness**,
and the first run proved it: with the resolver still defaulting to the
production module, the mixed predicate returned an EMPTY fact set and raised
nothing, because the attribute list was non-empty so the refusal never fired.
That failure is the defect in miniature and is what the second assertion now
pins.

The synthetic shapes are deliberate. Covering the branch by making the
production table hand a helper the whole criteria would be the gate dictating
the code it audits, and the table has no reason to adopt that shape.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    690 passed in 25.07s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_consumes_declaration_honesty.py -n0 -q -m unit
    7 passed in 0.91s

The gate went from five tests to seven, and the deletion proof is what the row
asked for. Run from OUTSIDE the repository, a plugin rebinds the extractor to a
copy that never follows a helper, which is exactly what deleting the branch
would do:

    PYTHONPATH=<scratch> uv run --no-sync pytest <the module> -n0 -q -m unit -s -p delete_follow_branch_plugin
    [MUTATION] delete-follow-branch plugin LOADED
    [MUTATION] rebinding installed on a real holder
    [MUTATION] APPLIED: calls=60 follows_suppressed=44
    1 failed, 6 passed in 1.14s

    FAILED test_the_helper_following_branch_finds_a_read_the_plain_walk_misses

The suppression counter is the rung that matters for a subtraction mutation:
counting invocations proves the patch ran, but only counting removals proves
there was something to remove. Forty-four follows were suppressed across sixty
calls, so the branch was demonstrably active before it was taken away.

**The old anchor stays GREEN under the deletion**, and that is now its
documented behaviour rather than a false claim. It is the direct demonstration
of the row's premise: the anchor never observed the branch. The other survivor
is the asymmetry test, which simulates the unfollowed walk itself and is
therefore correct to be unaffected by a mutation that does the same thing.

## Notes

The originating record was corrected in the same action rather than left to
describe a guard that does not exist. Its description line now states the
narrower claim the anchor really carries and records the measurement that
retired the wider one, so a later reader meets the correction where they would
meet the claim.

A latent fragility was noticed and is recorded rather than changed, since it is
outside this row and currently harmless. The extractor recurses into a helper
handed a criteria ATTRIBUTE as well as one handed the whole object, and inside
that helper it attributes reads to the helper's own first parameter -- which is
the attribute value rather than the criteria. A helper that read a field off the
value it was handed would therefore contribute that field name as if it were a
criteria attribute, and the unknown-attribute refusal would fire on a correct
predicate. No shipped helper does this today, which is why nothing is changed.
