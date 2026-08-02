---
tags:
  - '#audit'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:f45a6a4040824e600ab09c6dc2cdfe54ad64a1c2e6121c066ba44bf02040c0e3'
related:
  - "[[2026-08-02-release-pipeline-full-automation-adr]]"
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# `release-pipeline-full-automation` audit: `fresh-context honesty review of the full-automation campaign`

## Scope

The mandatory fresh-context honesty review required before this campaign may be
declared structurally complete. The reviewer saw none of the implementation work
and treated every self-reported claim as unverified. Audited: the accepted
full-automation decision record and its nine rulings, the L3 plan with its forty
Steps and its Verification section, all thirty-nine execution records, and the
landed tree at HEAD across the campaign commit range.

Verification was first-hand rather than transcribed. Every named gate command was
re-run in this session; the three highest-risk mechanisms named by the decision
record as most likely to be implemented subtly wrong (run-id resolution, the
version bump, the soak boundary) were read in full rather than summarised; the
orchestrator and promoter job graphs were parsed from the landed workflow
documents rather than from their prose; the live forge state was probed
read-only; and one suspected defect was proven by executing the shipped library
functions rather than by reasoning about them.

What is materially sound, stated before the findings so the findings are read in
proportion. All 249 tests across the ten campaign gate modules pass, as do the
packaging and release-config gates. The inverted approval-gate conformance pin is
real and mutation-sensitive: it carries positive controls that plant a restored
gate claim, a protection-rule reader, and a protection-rule-conditioned job, and
it separately proves the honest negation does not trip the matcher. The
alert-reachability gate computes its release-path set rather than hand-listing
it, and reds against a planted unalerted workflow under an injectable root. The
orchestrator alert job genuinely needs every other job, which is the subtle
coverage failure the campaign explicitly set out to avoid. The candidate record
reserved tag namespace is genuinely disjoint from the evidence garbage collector
namespace, and that disjointness is pinned. The version bump runs the
all-destination identity guard before any ref leaves the runner, including before
the local commit, and reads the manifest floor from the committed HEAD rather
than from the working tree it has already rewritten. The four real-client
evidence captures were never automated or SDK-substituted anywhere in the landed
code, and the emit honesty guard is intact. The campaign live-mutated no
environment, no protection rule, and no credential: a read-only probe of the live
forge confirms all three environments still carry their protection rules and the
orphaned publisher environment still exists, exactly as the runbook describes
them as outstanding operator items. Thirty-nine execution records exist for
thirty-nine checked Steps. The scope deviations the implementing agents declared
were sound rather than overreach: adding module entry points was forced by the
plan gates demanding a module invocation of modules the plan was authored before,
and each was reasoned in its record.

## Findings

### dry-run-candidate-starves-the-promoter | critical | A rehearsal dispatch permanently deadlocks the soak promoter, and no release ever publishes again.

The rehearsal input defaults to true, the seal stage carries no rehearsal guard,
and `dev/release/seal_candidate.py` calls its publish routine unconditionally, so
a rehearsal mints a real sealed candidate draft on the forge. That draft lives in
the deliberately garbage-collector-exempt namespace, which is correct for a real
candidate and permanent for a rehearsal one. `select_promotable` then returns the
eldest elapsed candidate on every tick, and `promote_once` refuses a rehearsal
candidate by returning immediately without consuming it and without considering
any other candidate. The rehearsal candidate is therefore selected, refused, and
left selectable forever, and every real candidate sealed afterwards sits behind
it permanently. This was proven, not reasoned: executing the shipped
`promote_once` over a rehearsal candidate and a real candidate across three ticks
dispatches nothing and consumes nothing on every tick, with the real candidate
never reached. Because the promoter entry point returns zero for every decided
tick, the workflow failure-guarded alert step never fires, so the deadlock is
silent. The decision record names publishing-never as one of the two ways this
design is most likely to be implemented subtly wrong; this is that failure,
reachable by the default value of the first input an operator will ever supply.
The single-element fixture in the promoter rehearsal test is what let it ship
green.

### default-alert-channel-is-inert | high | The labelled-issue alert path cannot deliver on the live forge, because the label does not exist.

The alerting module states that the labelled repository issue needs no
configuration, no secret, and no nominated channel, so that alerting works from
the moment it lands rather than from the moment someone provisions a webhook. A
read-only probe of the live forge shows the repository carries no `release-alert`
label. The issue-creation call passes that label explicitly, so the forge refuses
the creation, the emitter raises, the entry point catches it, and the alert
degrades to a warning annotation on a run log. That is precisely the delivery
surface the campaign docs-publisher test rejects by name as reaching only someone
already looking. The decision record states that a plan landing the orchestration
without alerting has not landed the decision; on the live forge the default path
currently delivers nothing. The unit tests cannot catch this because they inject
a fake executable that accepts any label. This is prose asserting a property the
code does not have, in the one component whose whole purpose is to pay for the
removed approval click.

### invalidated-candidate-alerts-nobody | high | A candidate whose readiness gate reds during its soak is refused silently, and the release simply never happens.

`promote_once` correctly re-runs the readiness gate against the sealed bytes
immediately before dispatching, and refuses a regressed candidate rather than
promoting it on an expired green, which is right. But the entry point returns
zero for every decided tick, including that refusal, on the reasoning that most
ticks legitimately promote nothing and a non-zero ordinary case would train the
operator to ignore the channel. The reasoning is sound for the ordinary case and
wrong for this one: a readiness regression during a soak window is a refused
chain, not an ordinary quiet tick. Because the exit status is zero, the promoter
failure-guarded alert step never runs, so a release that has been built, sealed,
soaked, and then invalidated reports to nobody. The decision record alerting
obligation covers a failed or refused chain explicitly, and names a silently
failed orchestration as indistinguishable from a release nobody started. The two
cases must be distinguishable at the exit boundary: a tick that promotes nothing
because every window is still open is ordinary, and a tick that invalidates a
soaked candidate is not.

### acquisition-run-ids-are-dropped | high | The acquisition run ids never reach the sealed candidate, so the publication would be dispatched without its acquisition proofs.

`dev/release/seal_candidate.py` reads the scoop run id, the homebrew run id, and
the claude evidence release from three environment variables. The orchestrator
seal step sets none of them: its environment carries only the token, the
packaging run id, and the rehearsal flag. The acquisition stage that produced
those ids declares no job outputs at all, and each dispatched lane writes its run
id under the same default output key, so the ids are overwritten and then
discarded. Two docstrings assert the opposite, one claiming the seal records the
acquisition run ids the chain produced, and the other claiming every field the
publication dispatch needs is recorded on the candidate. The defect is currently
vacuous because the live descriptor claims only the registry-tier channel, so the
lane set is legitimately empty and every gate is green. It arms silently the
moment a channel is flipped to available, which is exactly the transition the
host-extension evidence precondition was built to make safe on the other axis:
the promoter would dispatch the publication with those inputs absent, and the
publication would either refuse or proceed without the acquisition proofs. A
condition that is green only because a descriptor happens to be empty needs a
gate that fails when the descriptor is not.

### promoter-dispatch-can-never-promote | medium | A manually dispatched promoter tick always runs report-only, because the shell guard tests for emptiness rather than truth.

The promoter workflow passes the report-only flag through a shell expansion that
emits the flag whenever the variable is non-empty. A scheduled run leaves the
input unset, so the variable is empty and the flag is correctly omitted. A manual
dispatch renders the boolean as the literal string false, which is non-empty, so
the flag is always emitted. Verified by direct shell expansion: the empty value
yields no flag while both false and true yield the flag. The consequence is that
a manual promoter dispatch can never promote, only report, and the two dispatch
options are indistinguishable in effect. This direction is fail-safe rather than
fail-open, which is why it is medium rather than high, but it removes the manual
recovery path an operator would reach for precisely when the scheduled path has
not fired. No test covers the input at all.

### alert-carries-no-refusal-text | medium | Every alert body renders no detail captured, because no call site passes one.

The alerting emitter accepts a detail argument, and the plan Step that landed it
requires the alert to carry the workflow, the run URL, the stage, and the refusal
text. All four call sites pass only the stage, and the detail argument defaults
to empty, so the rendered body always falls back to its no-detail placeholder. An
operator opening the alert learns which workflow failed and at which stage, but
not why, and must open the run to find the refusal the alert exists to surface.
The emitter is correct; the wiring never uses the field.

### rehearsal-skips-the-stage-it-claims-to-prove | medium | The rehearsal bump stops after computing a version, so it exercises neither the seven surfaces nor the identity guard.

`dev/release/version_bump.py` returns immediately after parsing the computed
version when the rehearsal flag is set, writing no surface and creating no ref.
The orchestrator comment claims the rehearsal proves this stage rather than
skipping it, and the decision record claims the rehearsal covers the whole chain
rather than the last leg alone. Neither holds for this stage: the seven-surface
mutation, the lock regeneration, the parity re-check, and the all-destination
identity guard are all downstream of the early return. The practical consequence
is that a rehearsal cannot discover that the next computed version is already
owned, burned, or below the manifest floor, which is the class of refusal an
operator would most want surfaced before committing to a real dispatch. A
rehearsal that applied the surfaces and ran the guard against a temporary tree,
then discarded it, would prove what the prose claims.

### two-operator-items-are-unrecorded | medium | The runbook operator-actions section names neither the alerting channel nor the toolchain precondition.

The decision record creates four new operator decision points. The runbook
operator-actions section names two of them plus the carried-forward index-side
item and the narrowed documentation half, and the plan Step for that section is
gated on it naming exactly the outstanding halves. The alerting-channel
nomination and the toolchain precondition appear nowhere in it. The plan reasons
that both are rendered non-blocking, the first by defaulting to a labelled issue
and the second by an instructive refusal. The first of those reasons is currently
false on the live forge, for the reason recorded above. The second is true but
incomplete: whether the self-hosted Linux fleet carries the toolchain the version
computation shells out to is stated as unverified by the decision record itself,
and it blocks the very first real dispatch at the very first stage. An operator
reading the runbook is not told to check it.

### deleted-target-survives-in-live-source | low | The plan tree-wide sweep claim does not hold for the retired apply target.

The plan Verification section states that a tree-wide search for the retired
apply target matches only vault records and history. It does not:
`dev/release/version_bump.py` carries roughly a dozen references to it across its
module and function docstrings, mapping each new function onto the numbered step
of the retiring checklist it replaces. The references are descriptive rather than
instructional and the mapping has genuine explanatory value, so the substance is
defensible; the Verification bullet as written is simply not satisfied, and
should either be narrowed to the operator-facing surfaces it actually means, or
the docstrings reworded. The conformance gate that Step landed asserts absence
from the recipe file only, so nothing enforces the broader claim either way.

### rehearsal-test-cannot-see-the-deadlock | low | The promoter rehearsal test uses a single-candidate fixture, so the interaction that matters is unobservable.

The test asserting that a rehearsal candidate completes its soak and never
publishes constructs exactly one candidate. With a one-element set the assertion
holds identically whether the refusal returns early or continues to the next
candidate, so the test cannot distinguish the correct behaviour from the critical
defect recorded above. It is not tautological in the usual sense, and the
property it does assert is real and worth asserting; the gap is that the
selection function it exercises is defined over a set, and the fixture never
gives it one. This is recorded separately from the defect because the coverage
shape is what let the defect ship green, and the same shape would let a fix
regress.

### cancellation-is-not-alerted | low | A cancelled release-path run alerts nobody, because the alert jobs guard on failure alone.

Both multi-job alert jobs and the promoter alert step guard on the failure status
function, which is false when a run is cancelled. A cancelled orchestration
therefore reports through no channel. Cancellation is usually operator-initiated
and so usually already known, which is why this is low rather than medium, but a
run cancelled by a runner eviction or a concurrency interaction is not, and it
presents as the same silence the campaign exists to remove.

### claude-evidence-release-conflated-with-its-lane | high | The S45 remediation feeds the acquisition lane run id into the operator-minted evidence-release input, collapsing two things the module forbids collapsing.

Confirmation pass, second round. The scoop and homebrew halves of the dropped
run ids are now correctly carried: the acquisition stage declares outputs, each
lane receives its own output name from the derivation, and an unmapped lane
refuses loudly rather than dropping its id. The claude half is wired to the wrong
source. The seal stage sets `CLAUDE_EVIDENCE_RELEASE` from the acquisition
stage `claude_plugin_run_id` output, which is the run id of the dispatchable
`packaging-claude.yml` lane. That input is consumed by the publication authority
as a release tag, through `gh release download` with a `claude-*.json` pattern,
and the claimed-channel authority maps both host-extension channels to it as the
operator-minted evidence release. The two are different artifacts, and
`LANE_WORKFLOW_BY_CHANNEL` says so in its own docstring in the imperative: the
lane proves the acquisition mechanism works, the human capture proves a real
client actually used it, and the two must never collapse into one input. This
collapses them. Three consequences follow, worsening in order. The dispatch would
fail at the last leg after a full soak, because no release carries a run id as
its tag. The operator-minted evidence release the precondition job verified is
discarded and replaced by a machine-produced value, which is the substitution the
governing ruling refuses on the ground that it would make the evidence a lie
about what was installed. And nothing in the chain ever captures the real
evidence-release tag, so correcting the wiring also needs a source for the value.
The condition is latent under the current python-only descriptor and arms the
moment a host-extension channel is claimed, which is the same arming shape the
original finding had. It is recorded separately from that finding because it is a
new regression introduced by the remediation rather than a survival of the
original defect, and because a new test now asserts the collapsed mapping as
correct, which is what keeps the suite green over it.

## Recommendations

The campaign is not honestly ready to be declared structurally complete. One
critical defect makes the pipeline terminal stage permanently non-functional
after the first rehearsal, and two high findings leave the alerting obligation
that the decision record calls the price of the click removal undelivered on the
live forge. Every finding above is recorded as a new Step on the plan with a
verification gate; none is deferred, because none requires a decision the
accepted record has not already made.

The rehearsal-starvation defect needs both halves fixed together, and the gate
must be the interaction rather than either half: the selection must continue past
a non-promotable candidate rather than returning on the first one, and a
rehearsal candidate must be retired out of the selectable namespace once its
window closes so it cannot accumulate. The gate must plant a rehearsal candidate
with an earlier deadline than a real one and assert the real one still
dispatches, because that is the assertion the current fixture shape cannot make.

The alerting findings need a delivery proof rather than a wiring proof. The label
existence is forge state that leaves no commit, so it belongs in the runbook
operator-actions section alongside the channel nomination, and the emitter should
be made to survive a missing label rather than depend on one being provisioned.
Separately, the promoter exit status must distinguish an ordinary quiet tick from
an invalidated candidate, and the refusal text must reach the alert body that
already has a field for it.

The acquisition-run-id gap needs a gate that fails against a descriptor claiming
a host-extension channel, not against the live one. A condition that is green
only because a channel set happens to be empty is not verified, and the campaign
already established the correct shape for this on the evidence axis.

No follow-on decision record is required. Every finding is an implementation
divergence from a ruling the accepted record already made, or prose asserting a
property the code does not hold; none of them reopens a decision. The remaining
operator items are correctly described as outstanding and were not silently
claimed as done.

Second confirmation pass, appended. Nine of the ten original findings are
confirmed closed against their own reproductions, replayed rather than read: the
rehearsal candidate is skipped and retired so the real candidate dispatches
exactly once, the alert survives a label-refusing forge on both the lookup and
the creation call, an invalidated candidate now exits non-zero while three
distinct quiet-tick shapes stay zero, the report-only guard tests for truth
across unset, false, and true, every workflow parses with no mangled expression
and the refusal detail renders, the rehearsal bump exercises the surfaces, the
lock, and the identity guard against a discarded copy, the label probe reports
the live absence with its fix command, the runbook names both remaining operator
decision points, and the cancellation guards carry a positive control. The one
guard assertion that was loosened to containment was a step SELECTOR, and the
meaning it stopped pinning is now pinned more strongly by a dedicated assertion,
so that loosening swallowed nothing.

The tenth is not closed. The acquisition-run-id remediation fixed two of its
three legs and mis-wired the third, and the campaign is still not structurally
complete on that account alone. The correction is tracked as its own Step. Its
gate must assert the negative - that the seal stage does not source the
evidence-release input from any lane run-id output - because the test written
alongside the remediation asserts the collapsed mapping as correct, and a gate
that only checks the ids arrive would pass over it exactly as the current one
does.
