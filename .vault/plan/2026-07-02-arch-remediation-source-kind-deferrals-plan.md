---
tags:
  - '#plan'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:501efe7b2c0e47a5c84070091bfa6072a881aef82ccb9f685fc064cca5ae19f5'
tier: L1
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-source-kind-deferrals-adr]]'
  - '[[2026-07-06-arch-remediation-source-kind-deferrals-research]]'
---
# `arch-remediation-source-kind-deferrals` plan

- [x] `S01` - Add the structured owner-and-trigger annotation type on the deferred source-kind declaration carrying the owning ADR stem and the promotion trigger condition, annotations only per the Wave 1 freeze; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S02` - Migrate the prorrata_regularizacion deferral from its free-prose comment to a structured annotation citing its accepted 2026-07-01 IVA ADR and the provisional-carry plus Q4 regularisation trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S03` - Migrate the bienes_inversion_regularizacion deferral to a structured annotation citing its accepted 2026-07-01 ADR and the prorrata-definitiva-source-lands dependency trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S04` - Migrate the atribucion_member deferral to a structured annotation citing this deferrals ADR with no promotion date and the M184 next-hardening-campaign review trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S05` - Migrate the related_party_operation deferral to a structured annotation citing this deferrals ADR with no promotion date and the M232 next-hardening-campaign review trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S06` - Migrate the foreign_asset deferral to a structured annotation citing this deferrals ADR with no promotion date and the M720 next-hardening-campaign review trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S07` - Migrate the refund_operation deferral to a structured annotation citing this deferrals ADR with no promotion date and the M360 next-hardening-campaign review trigger; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `S08` - Extend the enrollment-status gate to assert every DEFERRED member carries both an owning ADR and a trigger annotation; `src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py`.
- [x] `S09` - Add a fired-trigger check surfaced at the swarm-audit cadence that flags a deferred kind whose trigger has fired but which remains deferred; `src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py`.
## Description

This L1 plan implements the source-kind-deferrals ADR, discharging register items
D4 and D5 by making the deferred source-kind set governed rather than merely
enumerated. Register item D4 requires each `DEFERRED_SOURCE_KINDS` member to gain
a live resolver or be re-ratified with a target condition; the ADR chose
re-ratification with typed promotion targets. The six deferred kinds fall into
two groups: two IVA kinds (prorrata regularizacion, bienes-inversion
regularizacion) whose promotion mechanics are already designed in accepted
2026-07-01 ADRs, and four informativa detail-row kinds (M184 atribucion members,
M232 related-party operations, M720 foreign assets, M360 refund operations)
re-ratified with no promotion date and a per-modelo review trigger.

The plan lands one structured owner-and-trigger annotation type on the deferral
declaration, then migrates each of the six members' free-prose comments to that
annotation citing its owning ADR and trigger (one step per member per the
no-compression rule), extends the enrollment-status gate to assert every DEFERRED
member carries both an owning ADR and a trigger, and adds a fired-trigger check
surfaced at the swarm-audit cadence so a kind whose trigger has fired but which
remains deferred becomes a mechanically-detectable finding.

This is annotations only. The ADR is explicit that the aggregation-taxonomy
safety floor is invariant: every deferred kind keeps its standing calculate-path
operator advisory, none may enter the manual-input allowlist, and there is zero
calculate-path behaviour change. It also respects the Wave 1 freeze: no new source
kinds and no resolver-convention changes, only the target annotations on the
existing set.

## Steps

## Parallelization

The steps are ordered by construction. S01 (the annotation type) must land before
the six per-member migrations (S02 through S07), which all edit the same
declaration in `_source_mesh.py` and therefore run under one owner in sequence
rather than in parallel. S08 (the gate assertion) depends on all six annotations
being present; S09 (the fired-trigger check) follows S08.

There is a cross-plan contention constraint the executor must honour: this plan
edits `application/aggregation/_source_mesh.py`, the same file the modelo-surface
campaign's W3 lands the precedence-ladder declaration in. Sequence this plan
after modelo-surface W3 closes, or coordinate the edit explicitly with that
owner. Combined with the Wave 1 freeze (annotations only, no new kinds, no
convention changes), this plan is a small single-owner change with no
calculate-path behaviour impact.

## Verification

- The annotation type carries an owning ADR stem and a trigger condition on each
  deferred member (S01 through S07); the two IVA kinds cite their 2026-07-01 ADRs
  and the four informativa kinds cite the deferrals ADR.
- The enrollment-status gate asserts every DEFERRED member carries both an owning
  ADR and a trigger (S08), failing if either is absent.
- The fired-trigger check flags a deferred kind whose trigger has fired but which
  remains deferred, surfaced at the swarm-audit cadence (S09).
- No calculate-path behaviour changes: every deferred kind keeps its standing
  operator advisory and none enters the manual-input allowlist.
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
