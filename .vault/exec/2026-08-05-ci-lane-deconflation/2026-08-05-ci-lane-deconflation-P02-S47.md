---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:288d0573cacb34b2fd08205d4dfb653fe2d09d3bacc06232cc2ca58635630361'
step_id: 'S47'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Route the same self-cancelling concurrency defect in the quick packaging lane to its owner rather than sweeping it, carrying the measurement that lane's gate author never had. MEASURED WITH AUTHENTICATED gh ON 2026-08-11 AND IT IS WORSE THAN THE PER-PUSH LANE. Of the last 300 retained runs of that workflow, 299 are CANCELLED and 1 is in flight. There are ZERO completed runs in that window and the last successful run of any age was 2026-07-28, fourteen days ago. The per-push lane by comparison had 99 cancelled of its last 100 and a green as recently as 2026-07-24, so the quick lane is the more starved of the two. That workflow carries the identical concurrency group and the identical push trigger on main, so every push cancels the run the previous push started, and the mechanism is the one already fixed in the per-push lane. WHAT MAKES THIS A SEPARATE ROW RATHER THAN A SWEEP is that the setting there is deliberate and gate-pinned. A conformance gate asserts the value is true and states its reason, that quick is the per-push signal and superseded runs are cancelled rather than queued, which is a real intent an agent may not overrule by sweep. But an intent stated against an assumed commit rate is not an intent stated against this fleet's rate, and the number now says the stated reason has produced no completed run in 299 attempts. Carry to the owner the mechanism, the run history above, and the finding that cancellation buys no machine occupancy over the default queue, because only one run may be pending in a group and a newly queued run cancels the previously pending one, so both settings cap the lane at one in flight and one waiting and differ only in whether the in-flight run finishes. The runners are self-hosted and consume no Actions minutes, so there is no billing saving either. The decision is the owner's and the row does not presume it

## Scope

- `.github/workflows/packaging-quick.yml and dev/packaging/tests/test_packaging_quick_workflow.py`

## Description

- Re-measure the lane with authenticated `gh` rather than carrying the row's
  2026-08-11 figure forward unverified.
- Confirm the mechanism is the one already fixed in the per-push lane, by
  reading both concurrency blocks rather than assuming they matched.
- Confirm the gate that pins the value, and read the reason it states.
- Route the mechanism, the run history and the queue-semantics finding to the
  lane owner as an issue, without touching the workflow or its gate.

## Outcome

Routed as issue 635, labelled `domain:infra`. No workflow or gate was
changed, which is the row's own instruction: the setting is deliberate and
gate-pinned, so the decision belongs to the lane owner and this row carries
evidence to them rather than a fix.

Re-measured on 2026-08-12 and the row's reading holds. The last 100 runs of
the quick lane are 99 cancelled and 1 queued, with ZERO completed runs in the
retained window and the last success of any age on 2026-07-28. The row
recorded 299 cancelled of 300 on 2026-08-11; a day later the picture is
unchanged, so this is a steady state rather than a bad week.

The two workflows were read side by side rather than assumed identical, and
they are not identical any more. The per-push lane now carries
`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so pushes
queue while pull requests still supersede. The quick lane still carries a bare
`true`. The fix is therefore not hypothetical -- it is landed, in production,
one file away, on the same trigger shape.

The pin is real and was not overruled. The packaging-quick workflow gate
asserts the value is `True` and states its reason: quick is the per-push signal
and superseded runs are cancelled rather than queued. That is an intent an
agent may not sweep away. What the routing adds is that the intent was stated
against an assumed commit rate rather than this fleet's, and at this fleet's
rate it has produced no completed run in 299 consecutive attempts. A per-push
signal that never completes is not a signal, but concluding that is the
owner's call.

Two findings were carried because the pin's author could not have had them.
Cancellation buys no machine occupancy over the default queue, since only one
run may be pending in a group and a newly queued run cancels the previously
pending one -- both settings cap the lane at one in flight and one waiting, and
differ only in whether the in-flight run is allowed to finish. And there is no
billing saving, because the runners are self-hosted and consume no Actions
minutes. Both were the plausible reasons to keep the setting, and neither
survives measurement.

## Notes

The issue states explicitly that the workflow edit and the gate assertion must
move together if the decision is to change it, because separating them reds the
gate on the fix. That is the same collateral class as S48 in this plan, where a
gate pinned a mechanism its own campaign had correctly removed, and naming it
in the handover is cheaper than the owner rediscovering it.

This row closes on a routing artefact rather than on a repaired lane, and that
is the honest close for it. A row that ends in someone else's decision is
complete when the decision has everything it needs and is with the person
entitled to make it. What would NOT close it is flipping the flag, which the
row forbids in its own text, or filing the observation only in this campaign's
vault, which the lane owner has no reason to read.
