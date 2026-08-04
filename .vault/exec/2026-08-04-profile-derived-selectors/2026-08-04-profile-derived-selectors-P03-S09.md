---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:85b9fee3e231a4579bdeaea3386ced0687bcfcfa10d7f1b90a2df49fc20b2b1a'
step_id: 'S09'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Delete the twenty derived field declarations, then run the locales scaffold verb in the same commit to prune all eighty catalogue leaves in one pass because the per-key remove verb accepts a live key silently and would need eighty invocations, and delete the one registry-contract test that asserts the year-suffixed selectors are declared field paths while keeping the shared year constant its surviving siblings consume

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/locales/`
- `src/cadrumo/domain/user_profile/tests/test_registry_contract.py`

## Description

## Outcome

The twenty derived field declarations are deleted, their eighty locale leaves pruned across
all four catalogues, and the one registry-contract test that asserted those selectors were
declared field paths is gone. Eight files, three hundred and eighty-nine deletions.

The locale instrument was the scaffold verb rather than the per-key remove, and the reason is
measured rather than stylistic: remove has no cross-check and accepts a live key silently,
and would have needed eighty invocations. Scaffold recomputes the required key set from the
schema and prunes what is no longer required in one pass. Sequencing mattered too -- it ran
AFTER the field deletion, since before it the keys are still required and it would have done
nothing. The executor ran the drift check first, saw the twenty extra leaves per catalogue,
then scaffolded and confirmed all four clean.

The count was measured, not taken from the brief, and the brief was imprecise. There are
three six-year families rather than two, and the third is findable only through the pattern
header block rather than from the field keys. Both kept operator fields and their locale keys
were confirmed untouched.

One test in the Step's scope did NOT break, as a grounding pass had predicted: it reads the
compiled binding rather than the schema and resolves through the pattern namespace, so only
its docstring went stale. Fixed as prose. Without that prediction an executor would have
spent a cycle debugging a passing test.

A regression the executor caused was caught and absorbed rather than left. An anti-vacuity
guard in the overview localisation gate asserted that at least one declared field also matched
a derived pattern -- true only while declarations and patterns coexisted, and permanently
vacuous once the declarations went. That guard was the coordinator's own, written during the
transitional window without noticing it could not survive the deletion it was meant to
survive.

The Step's stated headline was WRONG and the executor said so rather than massaging the
number. It was briefed as the commit that would drop the visible row count, and instructed to
measure that delta because it is the campaign's original purpose. It measured both schema
states through the real loader and reported: declared field paths fell from one hundred and
seventy-seven to one hundred and fifty-seven, and the rendered row count did not move at all.
The rows had already gone when the overview filter landed in the refusal commit, because that
filter matches by pattern independent of whether a per-year declaration exists. The
coordinator verified this independently against the current head. This Step removes the
declarations permanently and shrinks the locale and registry surface, which is necessary; it
is not what moved the rows.

Gates: five hundred and forty-two profile tests, three thousand four hundred and eighty-eight
registry tests, clean collection tree-wide, lint clean.

## Notes
