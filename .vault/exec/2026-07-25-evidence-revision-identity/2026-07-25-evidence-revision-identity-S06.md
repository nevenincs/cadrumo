---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:054aaaae9d4235cb1e8a336417875647ce5a3a833cdfb3ba59fb5e7de21940c8'
step_id: 'S06'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# RESOLVED BY S10, the refusals needed no recovery verb named, the export guidance moved off before-calculate onto attach-then-verify which now works

## Scope

- `src/cadrumo/application/modelo/_export.py`
- `src/cadrumo/locales/`

## Description

This record is written after the fact from the landed commit, to close a
`plan-closure-requires-exec-records` gap. It documents what landed; it does not
claim its authorship.

- Move the export refusal's suggestion off the before-calculate ordering onto the
  attach-then-verify sequence.
- Move the matching operator-facing locale string across all four catalogues
  through the locales CLI.

## Outcome

**Resolved inside commit `c04b8f3129` rather than as separate work.** The surfaces
this step names are the surfaces that commit changed, which is why there is no
distinct commit for it.

The step as written required the refusals to name the supersede transition,
replacing a silence that was correct only while no recovery verb existed. That
requirement dissolved rather than being met. No recovery verb was built, because
the mechanism that landed prevents the bad state instead of recovering from it —
so there was never a verb for the refusals to name.

What the refusals needed instead was a correction, and they got one. The export
refusal's suggestion said to link the invoice BEFORE running calculate. That was
true only while verify granted over the gap and froze a gap-carrying bundle; once
a deductible gap blocks the grant, linking before VERIFY suffices, and the
earlier instruction is wrong rather than merely unhelpful. The suggestion now
names the attach-then-verify sequence and the operator-facing locale string moved
with it across all four catalogues through the locales CLI, never by hand-editing
a catalogue.

The verify-time `next_action` needed no edit. It already told the operator to
attach the invoice and rerun verification, which was false while verify granted
and which the promotion makes true. That is the same defect class — prose
asserting a guarantee that does not hold — corrected at its remaining site.

The refusals themselves stay in place. They are now defence in depth over a state
verify no longer lets form, and they still cover a revision finalized before the
gate existed. Their unchanged tests passing is part of what confirms the
promotion was per-category rather than a blanket change.

## Notes

The record for S10 carries the verification evidence for this commit, since the
two steps landed together. This record does not restate those counts as if they
were separately obtained.

Because this step's scope overlaps S10's, a reader auditing file coverage will
see the same two surfaces named twice. That is a consequence of the plan being
re-cut after the original mechanism was withdrawn, not duplicated work.

Semantic search was unusable throughout the campaign: the code index reports
roughly 68 sections against about 4,546 files while self-reporting healthy, and
searches timed out at 120 and 300 seconds against a service whose latest indexing
job had failed. No claim here rests on a search miss.
