---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e0d288b8745bfd07ea6b72a71787845c4f3a564349197284682d5ae05ac3919a'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
  - '[[2026-08-06-ci-lane-deconflation-integration-lane-external-dependency-audit]]'
  - '[[2026-07-21-ci-discipline-adr]]'
---

# `ci-lane-deconflation` adr: `the integration parallel lane's non-blocking flag and its live external-service dependency` | (**status:** `proposed`)

## Problem Statement

The integration parallel step in the full-conformance workflow carries
`continue-on-error: true`. It was landed non-blocking against a measured backlog of
thirteen real failures, with the workflow comment instructing that the flag be removed
once that backlog closed and warning against letting it become permanent.

The backlog closed on 2026-08-06. Closing it surfaced a stronger obstacle in its place,
and both are established in
`2026-08-06-ci-lane-deconflation-integration-lane-external-dependency-audit` and in
`2026-08-05-ci-lane-deconflation-P02-S09`; neither is re-argued here. An operator ruled in
passing, while that step was being closed, that the flag stays on permanently.

**A decision is needed now because that ruling has no home and no authority proportional to
its effect.** It exists in one execution record, whose own Notes state that it settles that
step only and that the question "deserves a proper decision record with research, not a
ruling taken in passing". The grounding audit exists and is thorough, but an audit reports;
it does not decide. Meanwhile the workflow comment asserted the opposite of the ruling for
five days, and a reader following it would have flipped a lane whose verdict depends on a
third party nobody here operates. That comment has since been corrected to describe the
flag as an open decision; this record is the decision it points at.

The narrow question is whether one CI step blocks. The real question is whether a campaign
gate may be made permanently non-blocking, and on whose authority.

**The commitment this record would override is an accepted ADR, not only a workflow comment, and until 2026-08-11 no document said so.** `2026-07-21-ci-discipline-adr` D6.6 — *"Newly-enrolled lanes are non-blocking, and this is explicitly open, not resolved"* — is the record that enrolled this step non-blocking, and it closed with a commitment in terms: *"`continue-on-error` on the two steps above MUST flip to blocking once triage completes — that is a commitment this amendment makes, not a decision it defers indefinitely."* "The two steps above" are the `src/cadrumo` integration suite and the `just test-dev-tooling` gates, so the commitment binds precisely the step this record is about. This is not an inference from adjacency: it is the same pair the corrected workflow comment scopes itself to.

**What changed is a fact, not an opinion, and that is why D6.6 is being overridden rather than corrected.** D6.6 conditioned its interim posture on exactly one obstacle — an untriaged backlog of 19 measured failures plus 58 never-measured serial tests — and on nothing else. That obstacle is discharged. The obstacle that replaced it, a transitive live external-service dependency reached through a multi-currency fixture, was not a known fact on 2026-07-21 and appears nowhere in D6.6; it was established on 2026-08-06 by the grounding audit. D6.6 ruled correctly on the evidence it had. Its condition ("once triage completes") has been met without its conclusion ("flip to blocking") becoming safe, which is a state its author had no way to anticipate and no reason to write for.

**Consequence for whoever accepts this record.** D6.6 is accepted and its commitment stands until amended. Accepting this record without amending D6.6 leaves two accepted ADRs ruling opposite ways on the same flag, reachable from each other only by a reader who opens both. The amendment is therefore a condition of acceptance rather than a follow-up; it is stated as the fourth constraint below.

**A narrowing this record does not close, named here so it is not lost.** D6.6's commitment covers two steps; this record examines one. The `just test-dev-tooling` step carries the same flag under the same D6.6 commitment, and this record makes no ruling on it. What the standing D6.6 goal still asks for that this record excludes: whether the dev-tooling gate's flag may also stay on, and on what evidence — a question with no live-service dependency behind it, so its answer will not be this one.

## Considerations

- The backlog premise is discharged and corroborated in the tree, not only in the records:
  the one genuine defect is fixed in `963dd72f08`, and the audit landed in `2e944c6dcf`.
  The thirteen are closed and are not an argument for anything now.
- The live-dependency finding, the one-real-defect finding, and the twenty-seven
  extraction-unmeasurable failures are all established in the grounding audit at severity
  high, high and medium respectively. This record takes them as given.
- **Two consequences of that audit bear on the decision rather than on the evidence, and
  are stated here because they are decision-shaped:** no local evidence can certify this
  lane by anyone at any revision, and the runner that could is currently unobtainable.
- A permanently red or permanently non-blocking lane decays the same way: this repository
  has already documented that a lane which is always red is one everyone learns to ignore.
  A lane that can never fail is the same decay with the sign flipped, and worse for being
  invisible on a dashboard that shows it running.
- **The workflow this step lives in is dispatch-only.** Flipping the flag would not gate
  any push at any revision; it changes only the verdict of a manually launched lane. This
  materially shrinks the benefit of flipping, and it is recorded in no other document.
- Foreign-exchange rates are regulated inputs. A stale committed rate fixture would ground
  calculations in silently wrong numbers, the failure class this project guards hardest
  against.
- The repository's established posture for external access in tests is an explicit opt-in
  gate that is never set on CI, with the non-live path as the default.

## Considered options

- **Remove the flag now.** Rejected. It wires the release verdict to an endpoint nobody
  here operates, and the outage mode is observed rather than hypothetical.
- **Declare the flag permanent.** Rejected as the recorded outcome, though it is the status
  quo. It converts a remark made while closing a step into standing policy that a campaign
  gate never blocks, discoverable only by whoever next opens the workflow file. The effect
  is large, the authority behind it is not, and nothing would ever revisit it.
- **Pin exchange rates to a committed fixture, then flip.** Rejected on the operator's
  grounds, which are correct: a stale fixture grounds regulated calculations in wrong rates
  silently. Trading a loud external flake for a quiet wrong number is the wrong direction
  for this project.
- **Remove the live dependency from the lane rather than accepting it, then flip.**
  **The recommended option, and the one no record has evaluated.** If the multi-currency
  fixture's live call were held behind the same explicit opt-in every other external
  surface here uses, the lane would become deterministic and the trade would dissolve
  rather than be accepted. It neither pins a stale rate nor depends on a third party: the
  live lookup keeps working where it is opted into, and the lane stops depending on it.
- **Keep the flag, marked as an open decision, pending the measurement below.** The interim
  state, and what the corrected workflow comment now describes.

## Constraints

**This record deliberately does not decide, and the reason is a missing measurement rather
than a missing opinion.** The grounding audit establishes that the endpoint is reached
*transitively* through a multi-currency fixture and is invisible from the test identifier,
appearing only in assertion text. It does **not** establish whether that fixture or its
module declares a live-test marker, and that is the hinge:

- If no marker is declared, the call is escaping this repository's own external-access
  posture, and the defect is larger than this flag.
- If a marker is declared and the parallel selector simply does not exclude it, this is a
  lane-selection change and not a defect at all.

These lead to materially different work and the difference is one measurement: which
fixture reaches the endpoint, whether it or its module carries a live-test marker, and
whether the parallel selector excludes that marker today. A fourth question decides whether
the option is acceptable at all — whether the lane still exercises the multi-currency
behaviour with the live call held out. **Losing real coverage to make a lane green would be
a worse outcome than the flag.** That measurement is local, cheap, and blocked by nothing
except being unowned. It must not be taken against a working tree carrying the registry
migration, which would swamp it.

**The remaining twenty-seven cannot be measured at all right now, and this is a hard
constraint rather than a scheduling one.** The grounding audit records that the workflow
requires a self-hosted Linux runner, that the sole runner carrying those labels is offline,
and that the one online runner is a Windows host which can never satisfy a Linux label. A
dispatched run is not queued behind capacity; it is unsatisfiable until that runner
returns. **Restoring it is a physical host act and therefore operator-held**, and no amount
of agent work substitutes for it.

**A third constraint binds whoever accepts this record: the permanence question requires an
operator.** An agent may rule on lane selection and marker hygiene. An agent may not rule
that a campaign gate never blocks.

**A fourth constraint, binding on the ACT of accepting rather than on the decision: accepting this record amends `2026-07-21-ci-discipline-adr` D6.6, and the two land in one action.** D6.6 is accepted and commits in terms that this step's flag MUST flip to blocking once triage completes. Triage completed on 2026-08-06. Whoever accepts this record therefore also writes the D6.6 amendment recording that the condition was met and the conclusion superseded by a fact D6.6 did not have — in the same action, not as a follow-up.

The reason it is a constraint and not a courtesy is that an amendment ruling on a standing commitment is not self-executing. "This record supersedes D6.6" is a claim about the corpus, not a change to it: until D6.6's own text says so, a reader who arrives via the accepted 2026-07-21 record gets the flip commitment with nothing beside it. As of 2026-08-11 both records carry a `related:` edge to the other and D6.6 carries a pending-amendment paragraph naming this one — so the two are now mutually reachable, and what acceptance still has to do is convert that paragraph from *pending* to *amended*. An acceptance that leaves it saying "nothing here is amended yet" produces two accepted ADRs ruling opposite ways on one flag, which is the exact failure this record was written against, reproduced one layer up.

**And the amendment is narrower than the commitment, which must be said in it rather than discovered later.** D6.6 binds two steps; this record examines one. The `just test-dev-tooling` half stays bound by D6.6 as written, and an amendment that silently retires the whole commitment would grant this record authority over a step it never looked at.

## Implementation

No code change is carried by this record. The workflow comment has already been corrected
to state what is corroborated — the backlog closed, the live dependency is the live
obstacle — and to mark the flag an open decision rather than a permanent state, scoped
explicitly to the two of the four `continue-on-error` steps the reasoning actually governs.
The serial pass and the vault-drift step carry their own, different release conditions.

If the recommended option survives its measurement, the change is to hold the live call
behind the existing opt-in gate and then remove the flag from this step alone, leaving the
serial pass unchanged. If it does not survive, this record is amended to accept the flag
with a stated review trigger rather than as an unqualified permanence.

## Rationale

The knockout criterion is not which state the flag should be in. It is that **the current
state is held by an authority that does not match its effect**, and that the only artefact
a future reader reaches — the workflow file — asserted the opposite for five days without
anyone noticing. The grounding audit is good and it is not the gap; the gap is that a
report and a passing remark were together doing a decision's work, and neither is reachable
from the file that carries the behaviour.

Recording the question as open is therefore worth more than resolving it quickly in either
direction. Both quick resolutions are unsafe: flipping wires a release verdict to a third
party, and declaring permanence launders a passing remark into policy. The option that
dissolves the trade has never been evaluated, and the reason is that the question was
closed inside a step record before anyone asked whether the dependency had to exist.

## Consequences

**Gains.** The permanence question acquires a home a workflow reader can reach and an
operator can rule on. The measurement the recommended option needs is named, narrowed to
the one thing the grounding audit left open, and ownable. The constraint that this lane
cannot be certified from local evidence — and that the runner which could is currently
unobtainable — is carried into the decision layer, where it will be found before the next
request to prove the lane clean rather than after.

**Difficulties, stated plainly.** This record leaves a gate non-blocking while proposed,
which is the status quo but now an acknowledged one rather than an unexamined one. That is
deliberate: an acknowledged open gap is recoverable, a laundered decision is not, because
nothing ever prompts a reader to revisit it.

**A pitfall this record cannot close.** If the measurement is never taken, this ADR becomes
exactly what it was written against — a permanent state with a proposed label instead of a
permanent state with a stale comment. The interim state is only honest for as long as
someone owns the measurement.

**A pathway it opens.** The blindness generalises past this flag. All four
`continue-on-error` steps live in a dispatch-only workflow, so none gates a push at any
revision, and several recipes in this repository are invoked by no automatically triggered
workflow at all. Whether a lane's verdict reaches anyone is a separate question from
whether the lane is correct, and this repository has an instrument for the second and none
for the first.
