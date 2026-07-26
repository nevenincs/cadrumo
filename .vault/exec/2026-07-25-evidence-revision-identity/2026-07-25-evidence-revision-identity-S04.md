---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S04'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# SUPERSEDED BY S08, the idempotence guard was scoped to a supersede verb that is no longer the recommended mechanism

## Scope

- `no source change`

## Description

This record is written after the fact to close a
`plan-closure-requires-exec-records` gap. The step closed without a source change
and this record states why, rather than manufacturing activity that did not
happen.

## Outcome

**Closed without source change. Nothing was built and nothing needed to be.**

The step required the supersede transition to be `idempotent_guarded` on a
clock-free derived id, so a retry resolved to the existing successor rather than
minting a second draft. That obligation was real and correctly stated: a creating
mutation that lands without its guard double-writes on retry, which is why the
plan bound this step into the same commit as the transition itself.

It has no subject. The transition it guarded was withdrawn as unbuildable, and
the mechanism that replaced it creates nothing. The promotion recorded under S10
changes one severity assignment; it mints no record, so there is no creating
mutation for an idempotence guard to protect. A guard authored anyway would have
been dead code guarding a verb that does not exist.

The property the step existed to secure is preserved by the replacement rather
than abandoned, which is the test of whether a superseded step is genuinely
closed or quietly dropped. Under the promotion a blocked verify leaves the
revision in `BORRADOR` and captures no bundle, and the idempotent re-verify guard
keys on a non-`BORRADOR` state, so re-verifying after an attach re-runs rather
than collapsing to the prior outcome. Retry safety on the recovery path is
therefore a property of the existing verify guard rather than of a new one.

The verification report id folds the outcome rather than the clock, so the
blocked report and the later granted report are distinct records — the same
clock-free identity discipline this step asked for, already satisfied by the
surface the recovery actually runs through.

## Notes

The plan row for this step is checked and was not touched by this record.

Semantic search was unusable throughout the campaign: the code index reports
roughly 68 sections against about 4,546 files while self-reporting healthy, and
searches timed out at 120 and 300 seconds against a service whose latest indexing
job had failed. No claim here rests on a search miss.
