---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S10'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# Promote the deductible-IVA evidence finding to BLOCKING at verify while the output-IVA side stays advisory, so a non-granting verify captures no bundle and leaves the draft open, making attach-then-reverify work and the later export and filing refusals unreachable

## Scope

- `src/cadrumo/application/modelo/_verification_actions.py`
- `src/cadrumo/application/modelo/_export.py`
- `src/cadrumo/locales/`
- `src/cadrumo/application/modelo/tests/test_modelo_303_deductible_evidence_gate.py`

## Description

This record is written after the fact from the landed commit and the governing
decision record, to close a `plan-closure-requires-exec-records` gap. It
documents what landed; it does not claim its authorship.

- Promote the deductible input-IVA branch of `_missing_evidence_findings` from
  ADVISORY / WARNING to BLOCKING_RULE / BLOCKING, leaving the output-IVA branch
  advisory.
- Move the export refusal's suggestion off the before-calculate ordering onto the
  attach-then-verify sequence, and move the matching operator-facing locale
  string across all four catalogues through the locales CLI.
- Invert and rename the verify test that asserted the pre-promotion behaviour.
- Add a test driving the recovery ordering an operator actually reaches.

## Outcome

Landed in commit `c04b8f3129`. Three files changed, 157 insertions and 20
deletions.

The defect was one condition classified two ways at two lifecycle points. A
deductible-IVA ledger row with no linked purchase invoice was an advisory warning
at verify, which the outcome classifier does not block on, so verify granted,
froze a gap-carrying evidence bundle onto the revision and locked it. The
identical condition was then a hard refusal at export and at local filing.

That combination was a permanent dead end rather than an inconvenience. The
export gate reads the frozen bundle, and the revision id is content-addressed
over tax facts that an evidence attach does not change, so recalculating returned
the same finalized revision and re-verifying was idempotent. The operator was
told to attach the invoice, did so, and nothing moved.

The fix is at the severity rather than at identity. Promoting the deductible
finding to blocking makes a non-granting verify capture no bundle and leave the
revision in `BORRADOR`, so attach-then-reverify starts working — which is what
the finding's own `next_action` already instructed and which could not work
before. No new concept was required: the blocking severity and the
`BLOCKING_RULE` kind are declared, the outcome classifier already denies the
grant on any blocking finding, and the bundle capture already sat under a
`granted` branch. The `is_deductible_gap` discriminator already existed and both
branches had emitted the same severity.

The promotion is per category and that granularity is load-bearing. The
output-IVA side stays advisory because no CLI path mints issued-invoice evidence,
so blocking it would refuse a taxpayer with no way to comply. The governing
evidence-enforcement decision ruled this finding advisory conditionally and left
room to promote a category once its evidence-free escape hatch closed; on the
deductible side LIVA art. 97 closes it, and that article was already cited on the
finding.

The export and local-filing refusals stay. They become defence in depth over a
state verify no longer lets form, and they still cover a revision finalized
before the gate existed.

Verification, as recorded on the landing commit: 1688 passed across
`application/modelo` and `application/aggregation` with zero failures; 6 passed
on the evidence-gate module, including both unchanged export and local-filing
refusal tests and the unchanged output-IVA advisory, which is what confirms the
promotion is per-category and the later gates survive as defence in depth. Ruff
check and format clean, `ty` clean. Markers were passed explicitly as
`unit or integration` rather than relying on the repository default, which
deselects integration-marked modules and exits green having run nothing.

The test change is worth separating from the count. The existing verify test
asserted the pre-promotion behaviour and was inverted deliberately, renamed, with
the reasoning inline — an inverted test is only honest when the inversion is
visible, and it is. The added test drives the ordering that was the dead end:
verify, hit the refusal, attach, verify again, granted. It also pins that the
revision id does not move across that recovery, which states the decision against
folding evidence into identity as an executable assertion rather than a claim.

## Notes

An honest limit is recorded on both the commit and the decision and is repeated
here rather than smoothed over: a revision ALREADY finalized carrying a gap is
not recovered. The change makes that state unreachable going forward rather than
escapable in retrospect. Under `PRE_RELEASE` that population is local development
state, so the trade was taken deliberately rather than overlooked.

The step row for S06 names the same export and locale surfaces as this one. That
is not duplicated work: the guidance change S06 called for landed inside this
commit, which is why S06 is recorded as resolved here rather than separately.

Semantic search was unusable across this campaign and remains so. The code index
reports roughly 68 sections against about 4,546 files while self-reporting
healthy, and searches issued during this record's preparation timed out at 120
and then 300 seconds against a service whose latest indexing job had failed. A
miss from it is not evidence of absence, so no claim here rests on one; the
commit, its diff and the governing decision record were read directly.

This record is reconstructed from committed evidence rather than written by the
implementer at landing time. Where the commit and the decision record state a
verification count or a gate result, it is reported as their claim and attributed
to them above rather than re-run and asserted here.
