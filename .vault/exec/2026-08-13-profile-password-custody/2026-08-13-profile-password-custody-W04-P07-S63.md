---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b209861450c287ec593c8f8c4f117903d0b27dd7289fcfcd440e95a764b5f622'
step_id: 'S63'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh sweep the test modules that read workflow state before seeding a profile capsule

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/application/auth/tests/ and src/cadrumo/adapters/outbound/aeat/auth/tests/`

## Description

- Establish the real population before converting anything, reconciling the several
  conflicting counts in circulation.
- Convert each module to publish its capsule before reading workflow state, in
  small batches.
- Verify module by module rather than by aggregate totals.

## Outcome

The population is fully converted: forty-two modules, forty-six call sites, five
batches, and **zero modules still carry the shape**. Guard refusals fell from two
hundred and one to zero and setup errors from a hundred and sixty-eight to zero.

The denominator came first and settled a genuine disagreement. Five different
counts were in circulation, each correct about a different question, and the
author identified their OWN earlier figure as the undercount -- a pattern match
requiring one multi-line formatting had missed eight modules writing the same
call differently. A confident number wrong in the safe-looking direction is the
most dangerous kind, and finding it in one's own work is what made the rest
trustworthy.

Verification was per module rather than by totals, which matters because the
aggregate moves in a confusing direction: the FAILURE count rises while errors
fall to zero. That is the expected shape, not a regression -- tests that
previously errored during fixture setup now actually run, and some then fail on
pre-existing unrelated causes. Not one module regressed; every one improved or
held steady, with the largest movers dropping from twenty-two failures to
thirteen, twenty to thirteen, and thirteen to four. Explaining that shape is what
stops someone reversing the work later on a misread of the totals.

## Notes

The most transferable finding concerns the ORDER of a conformance sweep. After
the fourth batch the converted calendar modules still refused, because a
converted consumer stays broken while its shared fixture seeds the old way.
Converting the eleven shared fixture modules and the package-level configuration
fixed every remaining consumer at once. Fixture-first would have been a
substantially smaller job, and that is a general property of sweeps of this shape
rather than a detail of this one.

The eleven modules previously classified as latent -- carrying the shape but
passing, because their fixtures create the profile through the real command line
first -- were inside the population and are converted too, so the shape is gone
tree-wide rather than merely from the failing set.

Dirty-set intersection was checked immediately before each of the five batches
and was empty every time, so no module was skipped. A peer staged a shared
fixture between batches, and the pathspec commit was verified afterwards to have
taken only this step's files while leaving that staged entry intact -- confirming
that plain pathspec commits behave correctly here, and that it is bare commits
which consume the shared index.

One honest partial: the final aggregate re-run hit a ten-minute ceiling partway
through the population, so the closing numbers cover most of it rather than all.
Every batch was individually verified before its commit.
