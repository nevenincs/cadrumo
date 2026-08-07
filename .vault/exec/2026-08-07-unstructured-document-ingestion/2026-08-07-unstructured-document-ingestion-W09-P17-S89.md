---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5fe95473691e393bd004f38b9c3944a1168fd23f4c45c177379634576a482631'
step_id: 'S89'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the category-contradiction finding class to the blocking set the confirm gate refuses past, covering a reverse-charge legend printed beside a repercutido line and a legend the rate pattern belies, gated by a refusal test per contradiction shape with a positive control proving a coherent document still confirms

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `DraftDiscrepancyKind.REGIME_CONTRADICTED` and
  `ConfirmationBlockReason.CONTRADICTED_REGIME` to their closed core enums.
- Add the single mapping row enrolling the new kind as a blocking reason. No
  change to the blocker loop, which already iterates every discrepancy a draft
  carries.
- Add `_regime_contradiction.py`: the producer that reads the legend axis's
  contradicted outcome and raises the finding, plus the repercutido-line
  predicate it needs.
- Call it in the grounded-reading assembly beside the arithmetic findings rather
  than inside them.
- Promote both new symbols onto the package facade in the same change.

## Outcome

A document whose printed regime and charged tax cannot both be true now stops at
the confirm gate. Either the mention was printed in error or the tax was charged
in error, and which is not decidable from the page, so the finding names the
conflict and stops rather than picking a side. The operator holds the document
and is the only party who can settle it.

The producer decides nothing of its own. The statutory expectation lives on the
legend declaration as `expects_repercutido_line`, precisely so one place answers
what a mention implies, and re-testing it here would create a second authority
that drifts the moment the regulation's encoding changes. The axis also withholds
the declared category on a contradiction, so this module could not use that value
even by mistake. Nothing bridges into the counterparty-dependent rule table.

Placed beside the arithmetic findings rather than among them: a document whose
figures close perfectly can still contradict itself in words, so folding this
into a function named for arithmetic closure would have made that name lie.

One judgement is deliberate and covered in both mutation directions. A printed
zero rate or zero cuota is NOT read as a repercutido line. A reverse-charge or
exempt invoice may legitimately print zeroes to show that no tax was charged, and
treating that as tax charged would fire on exactly the documents this check
exists to respect -- a check that looks strict and is simply wrong.

The two contradiction shapes the Step names collapse into one reachable check,
and the collapse is measured rather than assumed. Printing all seven rows shows
the sole mention that declares a category is also the sole row declaring that it
expects no repercutido line. So "a reverse-charge mention beside a charged line"
and "a mention the rate pattern belies" are the same row, checked in the only
direction it can fail. The other six mentions declare nothing to contradict, and
the exempt case fixes no phrase to match at all.

The second direction becomes reachable only when a row declares a category while
expecting a repercutido line -- a mention whose regime DOES expect Spanish IVA,
contradicted by a document printing none. No such row exists, so a refusal case
for it would exercise a branch no legend can reach. The condition is named in the
test module and asserted directly, which is worth more than a test that cannot
fail, and it means the suite reports that its scope claim has expired rather than
continuing to read as complete.

## Verification

The enrolment guard proved itself by observation rather than by assertion. The
enum member was added before its mapping row, and the module refused to import:

    RuntimeError: every DraftDiscrepancyKind must declare a ConfirmationBlockReason; unmapped: regime_contradicted

The suite:

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_regime_contradiction.py -n0 -p no:cacheprovider -q -m unit
    20 passed in 0.83s

The same suite against the committed tree, extracted with `git archive` rather
than read from the working copy:

    20 passed in 2.09s

The surrounding surface, in the lane whose marker is stated because the default
selection is `unit` and part of the confirm surface is `integration`:

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/ src/cadrumo/core/tests/ -n0 -p no:cacheprovider -q -m unit
    2 failed, 1711 passed, 19 deselected in 325.08s (0:05:25)

Both failures belong to the tabular lane and neither names a symbol from this
Step, confirmed by grep rather than inferred: a closed role enum gained two
members without its member-set fixture, and that lane's own fixture filename
trips the combined-period-string gate.

The gate was mutation-proven in BOTH directions, because a refusal case and a
positive control fail in opposite ways and one mutation cannot prove both. Each
run carried a collection hook asserting the substitution actually reached the
module under test:

    PROBE: mutation reached the module under test = True
    producer made to NEVER fire   ->  3 failed, 17 passed
    producer made to ALWAYS fire  ->  9 failed, 11 passed

A third mutation proves the scope claim itself, since a newly-added assertion is
exactly the kind that can hold vacuously. A synthetic row declaring a category
while expecting a repercutido line was added to the statutory table:

    PROBE: declaring rows the suite sees = 2 (unmutated is 1)
    1 failed, 19 passed

Only the premise test reds. The nineteen behavioural cases stay green, which is
the intended reading: the covered behaviour did not break, the suite's claim
about what it covers did.

The never-fire direction reds the refusal cases; the always-fire direction reds
the coherent reverse-charge document, the zero-rate presentation, all six silent
mentions and the ordinary invoice. Without the second direction every refusal
case would pass against a gate that refuses everything. Both mutations ran from
outside the repository at plugin module scope, and no tracked file was modified.

## Notes

The change reached the committed tree through another lane's sweeping commit
before this lane could commit it. All seven files travelled together and the
result is coherent, which was luck rather than design: the same mechanism split
an earlier Step in this lane across two commits and left a member-set gate red in
between. Because of this there is no commit authored by this lane to cite for the
code; the landing is the sweeping commit named in the plan discussion, and the
verification above was therefore run against the committed tree rather than
against a commit of this lane's own making.
