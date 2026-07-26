---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S05'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# SUPERSEDED BY S08, the supersession event was scoped to a new verb, and PRESENTADO_SUPERSEDIDO already models supersession for the filed case across roughly a dozen surfaces

## Scope

- `no source change`

## Description

This record is written after the fact to close a
`plan-closure-requires-exec-records` gap. The step closed without a source change
and this record states why, rather than manufacturing activity that did not
happen.

## Outcome

**Closed without source change. Nothing was built, and building it would have
been actively harmful.**

The step required a supersession bucket event naming the superseded revision id,
keeping the original finalized record readable rather than rewriting it. The
event was scoped to the supersede transition, which was withdrawn as unbuildable,
so its subject is gone.

Two independent reasons make this a genuine close rather than a deferral.

The first is that the concept already ships.
`CalculationRevisionState.PRESENTADO_SUPERSEDIDO` is set when a later verified
revision is filed and is read by roughly a dozen surfaces including export, the
ledger lifecycle guards, the participation index and the IVA wallet seed.
Supersession is therefore already modelled for the filed case. A new event and a
new verb would have introduced a second supersession notion over the same word —
a parallel authority of exactly the kind the discovery mandate exists to prevent,
and one the degraded semantic index would not have surfaced.

The second is that the replacement produces no supersession to record. The
promotion recorded under S10 prevents the bad state from forming instead of
superseding a record after the fact. Nothing is superseded, so there is no
supersession event to emit.

The immutability guarantee this step was protecting is strengthened rather than
weakened by that substitution. The step's concern was that a recovery path must
not rewrite a finalized filing record. Under the promotion no finalized record is
touched at all: a verify that does not grant captures no bundle and leaves the
revision in `BORRADOR`, so the gap-carrying finalized record simply never forms.
The audit trail the event would have carried is unnecessary because the history
it would have explained does not occur.

## Notes

The plan row for this step is checked and was not touched by this record.

Semantic search was unusable throughout the campaign: the code index reports
roughly 68 sections against about 4,546 files while self-reporting healthy, and
searches timed out at 120 and 300 seconds against a service whose latest indexing
job had failed. The already-shipped supersession state cited above was found by
direct read and targeted grep, not by search — it is precisely the kind of
pre-existing authority a search miss would have hidden.
