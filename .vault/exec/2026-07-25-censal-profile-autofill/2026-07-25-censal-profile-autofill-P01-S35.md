---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S35'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Make a schema-required field bind per row on repeatable sections, closing both the declaration that enforced nothing and the completeness count an operator read as permanently wrong, through one helper both surfaces share

## Scope

- `src/cadrumo/application/user_profile/_completeness.py`

## Description

- Establish by execution that the enforcing validator reaches only two of the
  fifteen fields the schema declares required, the remaining thirteen being
  row-fields of repeatable sections it skips wholesale.
- Establish that the displayed surface does not skip them but tests the
  unindexed path, so it reports twelve fields missing on a profile the
  lifecycle validator has just accepted.
- Establish that a third surface, the compiled key registry behind profile
  health, covers one of the thirteen, so all three disagree.
- Prove that removing the skip alone is wrong in both directions at once,
  rather than carrying that claim forward as read.
- Confirm the blast radius by counting every indexed row in the tree before
  proposing anything.
- Add one row-aware helper deciding which required paths a value mapping
  leaves unsatisfied, and route both surfaces through it so they cannot drift.
- Treat an unindexed fact in a repeatable section as a single implicit row
  rather than dropping it from validation, without settling why a producer
  writes one that way.
- Gate the rule per row, including the second-row case the index-dropping
  presence set would wave through, and pin the deliberate whitespace looseness.

## Outcome

A schema-required field on a repeatable row now binds per row, and a valid
profile no longer reads as incomplete. A section with no rows raises nothing,
so a taxpayer is not incomplete for lacking a section they have no business
having.

The two surfaces read one helper. They previously disagreed about the same
question against the same record, and the agreement is now asserted rather
than assumed, so giving either its own copy of the rule fails a test.

Verification: the four affected suites pass at 772, and the new gate at 4.
Lint, format and type check clean on the changed modules.

Three mutations were run against the finished work. Restoring the skip reds
exactly the per-row enforcement case and leaves the rest green. Reverting only
the displayed surface's grouping returns it to twelve unsatisfiable paths
against the shipped schema - five partner columns, five attribution columns,
two ratio columns - which is the defect verbatim. Every case exercises the
shipped schema rather than a synthetic one, deliberately: the reason this
survived is that the pre-existing completeness tests inject a two-section
fixture with no repeatable sections, so they are green against a schema that
structurally cannot exhibit the defect.

The third mutation is the reason the assess-first path was correct, and it is
recorded here as that rather than as a curiosity. Switching to the per-section
reading was expected to report an ordinary profile incomplete - a wrong number
on a screen. It does something else: profile registration REFUSES, and all
four cases fail at fixture setup rather than at their assertions. So the
obvious one-line repair would not have shipped a bad count, it would have
shipped a product that cannot create an ordinary taxpayer profile. That is a
different severity class, and nothing in the diff distinguishes the two - the
line removed is the same line either way. It is discoverable only by running
the wrong version and watching WHERE it fails, which is why "propose, do not
implement" was worth the delay it cost.

## Notes

Two findings, one change. They were filed separately and correctly so - one is
a declaration that binds nothing, the other is a number an operator reads - but
there is a single rule underneath, and writing it twice in two modules is how
the two surfaces came to disagree in the first place.

The claim that the one-line repair fails in both directions was carried for a
while as reasoned-from-source rather than executed, because confirming it meant
editing a file another campaign was holding. It was run once that cleared, and
it held: an ordinary taxpayer draws thirteen errors, while a partner row
missing four of its five required fields draws none. Worth stating that the
gap between reading and running was real and was closed rather than assumed
away - a claim flagged as unexecuted either retires by being run or quietly
becomes an assumption, and which of the two happens depends on whoever picks
the work up.

The two findings landing together is better argued from what the change does
to a screen than from the code sharing a helper. Fixing only the displayed
half would quiet an indicator that currently always fires, so its failure
direction becomes a real missing field going unnoticed - and the enforcement
half is what covers that. A display fix shipped alone would have made the
surface calmer and less trustworthy at the same time.

The whitespace treatment is deliberately unchanged. These surfaces count a
whitespace-only value as present while the censal read strips before comparing
and would refuse it. That divergence fails safe, since the strict surface is
the one guarding a live external read, and tightening it here would silently
break the agreement this change establishes. It is pinned by a test so that
changing it has to be a decision.

The unindexed-fact treatment is a deliberate non-decision. A producer writes a
repeatable section's field without an index, so the helper counts it as one
implicit row; dropping it would have removed a field from validation while
fixing twelve others. Why the producer does that is a separate question and is
not answered here.
