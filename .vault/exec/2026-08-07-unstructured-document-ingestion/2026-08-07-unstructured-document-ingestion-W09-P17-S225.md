---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:df509bea4cfde43c59f34db2378b946bccf736656ba97dd7985ac2918efb692b'
step_id: 'S225'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Sweep the counterparty-country consumers for a resolved-versus-stated read

## Scope

- `src/cadrumo`

## Description

- Census every production site naming a counterparty country field, printed in full rather than sampled, and classify each by the row's distinguishing question.
- Read the behaviour rather than the parameter name where the two disagree, because one call passes the resolved field into a parameter named for the stated one.
- Establish which lane can populate the code fields at all, since a consumer on a lane that never sees a value cannot be silent about it.

## Outcome

No consumer was found reading the resolved field where it wants the stated one. Every surface the producer's own comment names as having once read that emptiness is correct at the tree measured: the country advisory, the relief guard, the review row and the structured provenance envelope. The row's premise that only two were verified is right, and the other two are now checked.

One site looked like the defect and is not. The party-attribution advisory passes the resolved field into a parameter called stated_country_code, which reads as the swap this row hunts. The behaviour settles it the other way: that parameter's value is returned as a country code and consumed as an alpha-2, so it wants what the vocabulary could place, and the site is correct. The parameter's own docstring calls it a code the document states, which is the looser of the two prose claims about it.

One measured observation, not a defect. The attribution field set carries both resolved code fields and no stated token, yet the reading model cannot emit a country code at all, and the lane that can populate those fields does not run colocation. So those two entries are unreachable capacity rather than a live silence. If a hybrid document ever routed a structured draft through colocation, they would match a resolved code against printed region text, which is the wrong comparison; that is worth a decision before such a path is built rather than after.

## Verification

**Superseding reading, and the one this row closes on.** Run by the single test-run authority at `4664fa299e`:

    unit lane          1267 passed / 1 failed / 29 deselected
    integration lane   ran, no failures

The single failure is `test_attach_evidence_under_finalized_revision.py::test_stale_revision_advisory_names_no_harmful_recovery_verb`, which reads a `suggestion` field off a `Notice` that no longer carries one — the typed-notice-action migration's orphaned consumer, already rowed separately and owned elsewhere. Zero failures attributable to this sweep.

**The reading it supersedes is recorded rather than deleted, because why it was void is the more useful half.** The original entry cited `3 failed, 1221 passed` from a run the sweeping worker executed itself, in breach of the single-authority rule. Those figures are not merely unverified but UNFALSIFIABLE: they were contaminated by a peer's uncommitted rewrite of the relief guard, live in the working tree and being edited between two runs of the identical subset, which is why the same command produced three failures and then six with different names. That peer work has since vanished without landing, so no tree exists — at HEAD, in any working copy, or in any reflog — against which three-or-six could ever be reproduced.

So this row had never had an admissible reading until now. Its conclusion did not change; its evidence did.

The attribution in the original entry was nonetheless correct, and reaching the right cause after two contaminated readings is not the same as the process working. A serialised queue would not have produced either reading.

## Notes

The attribution is worth recording because the first measurement pointed the other way. Swapping the legend module for an earlier revision made the same subset pass, which read as this campaign's diacritic folding having caused the failures. Re-running the identical subset minutes later, with the folding restored, produced six failures rather than three and a different set of names. Two runs of one comparison disagreeing meant the variable under test was not the one being changed, and the tree confirmed it: the relief guard and the classification assembly were both dirty and being edited between the runs. The legend module was identical to the committed tree throughout.

A swap-and-rerun comparison assumes everything else holds still, which is not true of this tree. The cheap defence is to run each arm twice before believing either.
