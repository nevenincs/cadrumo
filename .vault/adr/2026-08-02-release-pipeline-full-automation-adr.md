---
tags:
  - '#adr'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:448527659bf00cdcca9aee9920c3a34c62c3386eda72d85ea93cb197f5780de4'
related:
  - "[[2026-07-27-canonical-release-pipeline-adr]]"
  - "[[2026-07-27-publication-lane-consolidation-adr]]"
  - "[[2026-07-27-pipeline-config-topology-adr]]"
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
  - "[[2026-07-27-canonical-release-pipeline-research]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-20-release-asset-transport-adr]]"
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-04-12-release-please-adr]]"
---

# `release-pipeline-full-automation` adr: `the release pipeline runs itself: the human approval gate is deleted, one dispatch drives bump through publish, and the mechanical guards are the whole safety net` | (**status:** `accepted`)

## Problem Statement

The release pipeline is complete and unrunnable without a human at five separate
keyboards. `.github/workflows/publish-release.yml` opens with an
`operator-preflight` job (`:66-111`) whose sole function is to refuse the
publication unless the `release` forge environment carries a
`required_reviewers` protection rule, and the `publish` job then runs inside
that environment (`:317`) so a human must click approve before any byte moves.
Three accepted records chose that click deliberately: the workflow's own comment
states that "the approval click is the gate. There is deliberately no separate
opt-in variable" (`:63-65`), the delivery record
`2026-07-27-canonical-release-pipeline-adr` builds its R2/R4 docs-consequence
reasoning on a human-approved publication authority, the publication record
`2026-07-27-publication-lane-consolidation-adr` keeps it through P4/P5, and the
conformance gate `test_preflight_enforces_the_human_approval_gate_it_promises`
in `dev/release/tests/test_publish_release_workflow.py` (`:258-278`) pins it so
it cannot be removed by accident.

The operator has reversed that choice. The ruling, verbatim: "I want cadrumo
publish gate deleted. not required, not wanted... I want a cohesive full
orchestration pipeline implemented." This record formalises a ratified ruling;
it does not weigh whether to adopt one.

Deleting the click alone would not produce a pipeline. Measured against the tree
on 2026-08-02, five human acts stand between a merged feature and a published
release, and only one of them is the click:

- **The version bump.** `just release` runs release-please in `--dry-run` and
  writes a log; `just release-apply` verifies the tree state and then *prints
  eleven instructions* for a human to execute by hand -- seven version surfaces,
  `uv lock`, a changelog block, a commit, a tag, and two pushes. Neither target
  applies anything. The publication record's P2 mandates exactly this shape and
  rejected a CI release-please workflow "for no mechanical gain".
- **Three acquisition dispatches.** `packaging-scoop.yml`,
  `packaging-homebrew.yml`, and `packaging-claude.yml` are `workflow_dispatch`
  only and each takes `source_run_id` and `source_commit`, transcribed by hand
  from the smoke run. Nothing chains them to the campaign that produced the
  cohort they test.
- **Four real-client `claude-*` evidence captures**, minted locally through
  `dev.packaging.emit_real_client_evidence`; the honesty guard in
  `dev/packaging/distribution_evidence_emit.py` refuses SDK-driven runs by
  design.
- **The publication dispatch**, hand-assembled from up to four run-id and tag
  inputs and preceded by a hand-created evidence release carrying the claude
  rows.
- **The approval click**, and afterwards six reacquisition lanes plus -- until
  the docs deploy role exists -- a local `just docs-deploy`.

Exactly one leg is already automatic. `packaging-campaign-trigger.yml` fires on
a main push touching `pyproject.toml`, `uv.lock`, `packaging/**`,
`dev/packaging/**`, or the smoke workflow, and dispatches `packaging-smoke.yml`;
`docs-publish.yml` already runs on `release: published` and is inert only
pending the deploy-role variable of the delivery record's OP-3.

One further gap sits between "one dispatch" and "one run", and the ruling did
not anticipate it: `2026-07-04-release-readiness-gate-adr` mandates a 48-72 hour
immutable-candidate soak for every non-hotfix release. No single workflow run
spans that window, so the orchestration must decide whether the soak boundary is
crossed by a human or by a machine.

A second, unrelated gap surfaced while measuring the first, and it is the same
shape twice. Two accepted operator obligations have been PARTIALLY executed on
the forge with no commit trail and no vault record, so the tree's description of
the pipeline and the pipeline's actual state have quietly diverged. The forge
reported exactly three environments on 2026-08-02: `release`, `docs`, and
`pypi-data-official`. First, the retiring lane's cleanup (tracking issue #618,
the publication record's OP-6) is half done: its repository half landed in full
on 2026-07-27, deleting `pypi-upload.yml` and its conformance test, while its
forge half deleted only two of the three orphaned publisher environments --
`pypi` and `pypi-data-manuals` are gone, `pypi-data-official` survives as an
orphan pointing at a workflow that no longer exists. The issue is still open,
carries no comment, and was last touched 2026-07-24, so nothing records that it
is partly done. Second, the delivery record's OP-3 is half done the same way:
the `docs` environment now exists, but it carries no variable at all, so the
deploy-role variable `docs-publish.yml` refuses on is still absent and the
documentation consequence remains inert. Neither half-execution is the
2026-07-27 burned-version disposition, which is separately ruled and closed;
these are undocumented drift.

Measuring those environments also settles a question this record would otherwise
have had to assume, and surfaces a third gate. All three environments carry
`required_reviewers` -- including `docs`, which means the automated documentation
consequence the delivery record's R2 designed would itself stop at a human
approval click the moment its role variable is set. The gate the ruling strikes
is therefore not confined to the publication leg.

This record rules what is removed, what replaces the click as the safety
mechanism, what the single trigger is, how the soak boundary is crossed, which
manual legs join the loop and which stay deliberately outside it, and how the
two untracked partial executions are closed out. It names its partial
supersessions by ruling rather than contradicting them silently.

## Considerations

- The removal is a reversal, not an oversight: three accepted records and one
  conformance test assert the gate. A reversal recorded nowhere reads to the
  next agent as drift, and the next honesty review restores it.
- What the click actually held is narrower than what it claimed. It carried
  three candidate properties -- intent ("yes, now, this cohort"), input
  correctness (a human eyeballing four run ids), and a last-look veto. Only the
  first is a property a click can hold: an approver of a dispatched run sees a
  run summary, never the cohort, never the evidence rows, never the diff.
- The environment is load-bearing beyond the click. Per
  `2026-07-27-pipeline-config-topology-adr`, Trusted Publishing anchors trust in
  workflow-run identity plus the environment NAME, and the OIDC trust policy
  pins repository and environment; the environment is also the shared-runner
  product boundary.
- The guard set already behaves as though it were the real defence. The
  all-destination authority `dev/release/version_identity.py` checks the three
  index projects, the tag and release namespaces including drafts, the monotonic
  release-please manifest floor, and the append-only burned-version ledger
  `dev/release/burned_versions.json`; it runs at cohort seal and again at Gate
  2. Nothing in it consults a human.
- The guard set is silent on exactly one question the click nominally answered:
  whether this release should happen at all, now. A fresh, correct, unburned
  version passes every guard there is.
- Chaining a dispatch from a workflow is blessed precedent here, not novelty:
  `packaging-campaign-trigger.yml` dispatches `packaging-smoke.yml` and carries
  the recorded honesty note that the dispatched run is an ordinary dispatch run,
  promotable under Gate 2's own rule, and "only presses the same button an
  operator would" -- it adds no trust path.
- Gate 2 verifies every supplied run independently (conclusion, workflow-path
  pin, repository pin, `main`-ancestry for a dispatch event) and hash-verifies
  every downloaded asset against its sealed manifest, so a machine-supplied run
  id is checked exactly as a hand-typed one is -- and cannot be mistyped.
- The four `claude-*` rows cannot be automated without voiding their meaning;
  the emit guard refuses SDK-driven runs deliberately.
- Those rows are not currently in the loop. `docs/_data/download_channels.toml`
  marks `scoop`, `homebrew`, `claude-plugin`, and `mcpb` as `public_launch`, so
  only the registry-tier `python` channel is claimed and
  `dev/packaging/publication_inputs.py` demands `packaging_run_id` alone for the
  first release.
- `CADRUMO_PUBLISH_ENABLED` no longer exists anywhere in the tree, yet the
  workflow header (`:4-7`) and the runbook's arming section still describe an
  opt-in variable nothing reads. The gate surfaces are already drifting from the
  code they describe.
- Removing the click removes the only moment at which a human was structurally
  guaranteed to look at the pipeline. Nothing currently alerts on a failed
  publication run.
- The soak policy of `2026-07-04-release-readiness-gate-adr` is a wall-clock
  constraint on the sealed cohort, not a human-review constraint; nothing in it
  requires a person to be the thing that waits.
- Measured on the forge 2026-08-02: three environments exist -- `release`,
  `docs`, `pypi-data-official` -- all three carrying `required_reviewers` and
  `branch_policy`, and none carrying a variable. The `branch_policy` rule pins
  which refs may deploy and is not a human gate; only `required_reviewers` is.
- Issue #618 is open, comment-free, and last updated 2026-07-24, while its
  repository half landed 2026-07-27 and two of its three environments have since
  been deleted. A tracking issue that does not know it is two-thirds done is how
  the remaining third gets forgotten.
- An orphaned publisher environment is not inert. It is a live Trusted
  Publishing trust anchor naming a workflow that no longer exists, so it is
  standing authority with no owner -- exactly the class of configuration the
  publication record removed by deletion rather than confinement.
- The self-hosted fleet is four runners shared across products; the smoke
  campaign carries a 90-minute timeout and the Homebrew matrix spans three
  hosts.

## Considered options

**The trigger shape** (the ruling did not specify; this is the record's call).

- **One dispatch of one orchestrator workflow, every stage after it automatic.
  Chosen.** One deliberate act carries the release decision; nothing downstream
  asks a human anything.
- Fully hands-off: the chain runs on every main-branch version-bump commit, with
  no trigger action at all. Rejected -- it does not remove a human act, it
  disguises one, since the bump commit is still authored by someone, while
  making the project's one irreversible act a side effect of a push. A
  mis-scoped or replayed push then publishes permanently and no guard objects:
  the identity guard refuses an *owned* version, and a fresh correct version
  passes. It also contradicts the standing posture that a merge to main
  publishes nothing outward, which the delivery record's R2 chose on this
  ground.
- One dispatch plus a typed confirmation input. Rejected -- a second click
  wearing a costume. Navigating to a workflow and pressing Run already is the
  deliberate act; a confirmation phrase re-adds the human ceremony the ruling
  struck, under a new name, and protects against nothing the guard set does not.
- Delete only the approval click and keep the per-stage dispatches. Rejected --
  satisfies the letter of the ruling and none of "cohesive full orchestration":
  five human dispatches and a hand transcription of four run ids survive.

**The approval gate's disposition.**

- Delete the `operator-preflight` job and the `required_reviewers` protection
  rule; keep `environment: release` on the publish job. **Chosen.**
- Delete the environment too. Rejected -- it is the Trusted Publishing trust
  anchor and the shared-runner product boundary; removing it breaks OIDC
  publication outright.
- Neutralize the job so it warns instead of refusing. Rejected -- it leaves a
  live job asserting a gate that no longer exists, which is precisely the
  documented-but-unenforced shape that job was built to close.

**The version bump.**

- The orchestrator executes release-please and lands the bump commit and tag;
  `just release-apply` is deleted and `just release` survives as the read-only
  preview. **Chosen.**
- Keep the bump a local human act per P2. Rejected under the new driver -- a
  single trigger preceded by an eleven-step hand transcription is two acts, not
  one, and that transcription is the exact error class the
  `version-surfaces-agree` readiness check exists to catch.
- Automate the bump but keep the local apply path as an equal alternative.
  Rejected -- two authorities over one version manifest is the dual-authority
  configuration `2026-07-15-distribution-installation-readiness-adr` rejected on
  principle and `2026-07-27-publication-lane-consolidation-adr` P4 removed by
  deletion rather than confinement.

**Crossing the soak boundary.**

- A machine-held wait: the orchestration seals the candidate, then resumes
  itself and publishes once the window has elapsed and the readiness gate is
  green. **Chosen.**
- A second human dispatch after the soak. Rejected -- it reinstates a per-step
  human action in the loop, which is the thing the ruling removes; the soak is a
  clock, and a clock does not need a person.
- Shorten or drop the soak so one run spans the release. Rejected outright --
  the soak is an accepted policy grounded in installed-behaviour proof, and this
  record has no mandate to weaken a safety property while removing another.

**The real-client evidence captures.**

- They stay human and stay outside the loop, as a precondition the orchestrator
  refuses on when a host-extension channel is claimed. **Chosen.**
- Absorb them into the orchestrator. Rejected -- the emit honesty guard refuses
  SDK-driven runs, and defeating it would make the evidence a lie about what was
  installed.

## Constraints

- Depends on the three 2026-07-27 records remaining in force everywhere this
  record does not name. It reverses exactly two rulings and amends two more;
  every other ruling in that cluster stands unchanged.
- Removing a protection rule and deleting an environment are operator acts on
  forge settings, not repository changes, and are surfaced as decision points
  below. Their present state is measured, not assumed: on 2026-08-02 the forge
  reports exactly three environments -- `release`, `docs`, and
  `pypi-data-official` -- each carrying `required_reviewers` and `branch_policy`,
  and none carrying any variable.
- Deleting a Trusted Publisher REGISTRATION is an index-account act, outside both
  this repository and the forge, and cannot be performed or verified by any agent
  from this session. Only the forge-side half of that cleanup is actionable here;
  the index-side half is reportable at most.
- `gh workflow run` returns no run id, so the orchestrator must resolve each
  dispatched run by polling for the newest run of that workflow at its own head
  commit. This tree has no precedent for that resolution --
  `packaging-campaign-trigger.yml` fires and forgets -- so it is new, testable
  code the implementing plan must gate rather than assume.
- `packaging-smoke.yml` queues rather than cancels on a newer dispatch, so a
  running campaign always completes; the orchestrator must therefore identify
  ITS OWN run, not merely the most recent one, or it will promote a neighbour's
  cohort.
- A waiting orchestrator occupies a runner slot for the whole campaign it waits
  on. The fleet is four self-hosted runners shared across products and the smoke
  campaign alone carries a 90-minute timeout, so the waiter must be a cheap poll
  on a short-lived job, not a busy hold. The soak wait is far longer again and
  cannot be held by a running job at all.
- release-please execution needs `node` and a forge token on the runner; the
  local targets shell out to `npx --yes release-please@16`. Whether the
  self-hosted Linux runners carry `node` is not verified here and is a plan
  precondition.
- The docs consequence stays blocked on the deploy-role variable (delivery
  record OP-3). Nothing here unblocks it, and nothing here makes docs a gate.
- Nothing in this record arms a credential, creates an environment, deletes a
  protection rule, or publishes anything. It is a design obligation on an
  un-armed pipeline.

## Implementation

**D1 -- The approval gate is deleted; the environment survives.** The
`operator-preflight` job is removed from `publish-release.yml` in full, the
`needs: operator-preflight` edge on the validate job goes with it, and the
operator removes the `required_reviewers` protection rule from the `release`
environment -- measured present on 2026-08-02, so this is a live removal and not
a precaution. Only that rule goes: the environment's `branch_policy` stays,
because it pins which refs may deploy and is not a human gate.
`environment: release` STAYS on the publish job, because it is the
Trusted Publishing trust anchor and the shared-runner product boundary, not
merely the click's host -- a naive removal that deletes the environment breaks
publication outright. The stale header comments claiming an opt-in variable and
an approval gate are rewritten to describe what actually gates the run. The
conformance test that pins the gate is not simply deleted: it is INVERTED into a
gate asserting that no job conditions on a human protection rule, that no
protection-rule read survives, and that `environment: release` is still present
on the publish job. A removal that is pinned cannot be silently restored by a
later honesty pass reading the three 2026-07-27 records and concluding the gate
went missing.

**D2 -- One orchestrator, one dispatch, nothing downstream asks a human.** A new
release orchestrator workflow becomes the single operator-facing surface of a
release. It takes a `dry_run` boolean and an optional resume input naming an
existing packaging-smoke run, and nothing else; there is no typed confirmation
input, because the dispatch itself is the intent act. It runs on the self-hosted
fleet under a product-scoped `cancel-in-progress: false` concurrency group, so
two dispatches cannot interleave two versions. Its stages are: bump, dispatch
the packaging campaign and wait for its conclusion, dispatch the acquisition
lanes the claimed channels require and wait for theirs, hold the soak, then
dispatch the publication authority with run ids derived from its own chain
rather than from a human's clipboard. `docs-publish.yml` continues to fire on
`release: published`, so the delivery leg needs no wiring here. Every dispatched
run is an ordinary dispatch run that Gate 2 verifies exactly as it verifies a
hand-dispatched one -- the orchestrator presses the same buttons an operator
would and inherits no trust it did not already have. `dry_run` propagates end to
end, so the validate-everything-publish-nothing rehearsal covers the whole chain
rather than the last leg alone.

**D3 -- The version bump joins the pipeline; the local apply path is deleted.**
The orchestrator's first job executes release-please against the release-please
manifest floor, applies the computed version to all seven declaration surfaces,
regenerates and verifies the lock, prepends the changelog block, commits, tags,
and pushes -- the eleven steps `just release-apply` presently prints. The
version stays computed, never chosen, from conventional-commit history, and the
seal-time and Gate 2 identity guards are unchanged, so a bump colliding with an
owned, burned, or below-floor version still refuses before anything is built.
`just release-apply` is DELETED rather than kept as an alternative, so one
authority owns version advancement; `just release` survives as the read-only
dry-run preview, which advances nothing and is therefore not a second authority.
This reverses the execution half of P2 in
`2026-07-27-publication-lane-consolidation-adr` and the local-only versioning
mandate that survives in `2026-04-12-release-please-adr`. The reversal is narrow
and its ground is stated: P2 rejected a CI release-please workflow "for no
mechanical gain", and under the full-orchestration ruling the gain is precisely
the difference between a one-act and a two-act release. What P2 was actually
protecting -- that a bump never happens by omission -- is protected better here,
because the bump now happens inside a deliberately dispatched orchestration
rather than nowhere at all, with both identity guards still behind it.

**D4 -- The acquisition lanes chain; the real-client captures stay human and out
of the loop.** The orchestrator dispatches `packaging-scoop.yml`,
`packaging-homebrew.yml`, and `packaging-claude.yml` with its own smoke run id
and head commit, waits for their conclusions, and feeds the resulting run ids to
the publication dispatch. Which lanes it dispatches is DERIVED, not fixed: it
reads the same claimed-channel authority that
`dev/packaging/publication_inputs.py` and the readiness gate already read, so an
unclaimed channel is not dispatched and a claimed one cannot be skipped. The
four `claude-*` real-client rows remain a human act, because the honesty guard
in `dev/packaging/distribution_evidence_emit.py` refuses SDK-driven runs and
that refusal is the evidence's whole value. They are therefore a PRECONDITION
the orchestrator refuses on -- instructively, naming the capture command -- when
a host-extension channel is claimed, never a step it performs. Under today's
descriptor no host-extension channel is claimed, so the loop is already closed
for the first release; the refusal exists so that flipping a channel to
available cannot silently publish it unevidenced.

**D5 -- The soak is a machine-held wait, and the policy is not weakened.** The
48-72 hour immutable-candidate soak of `2026-07-04-release-readiness-gate-adr`
stands untouched in duration, in what it forbids, and in its hotfix carve-out.
What changes is who waits. A single workflow run cannot span the window, so the
orchestration seals the candidate, records its soak deadline alongside the
sealed cohort, and resumes itself -- by scheduled continuation or by a scheduled
promoter that publishes the first sealed candidate whose window has elapsed and
whose readiness gate is green. The mechanism choice belongs to the implementing
plan; the invariant is this record's: no human action re-enters the loop to
cross the soak boundary, and no candidate publishes before its window closes.
The soak therefore stops being the reason a release needs a second human act and
becomes what it always was, a clock the pipeline honours.

**D6 -- The safety net after the click, named in full.** What remains is not a
residue; it is what was doing the work. Retained unchanged: the all-destination
version-identity authority over the three index projects, the tag and release
namespaces including drafts, the monotonic manifest floor, and the append-only
burned-version ledger, run at cohort seal and again at Gate 2; the readiness
gate's complete blocking evidence set, derived from the claimed channels and
re-run in CI rather than trusted from a local aggregation; per-run identity
verification and per-asset digest verification of every evidence draft; the
fail-closed leak sweep over every byte about to be attached; the marketplace
supersession preflight; the immutable-candidate soak; reversible destination
writes first with the sole irreversible index upload last; per-destination
idempotent convergence on re-dispatch; and the `dry_run` rehearsal mode. Three
additions the click's removal obliges, and they are additions rather than
restatements. First, FAILURE MUST ALERT: the click was the only moment a human
was guaranteed to look, so the orchestrator must report a failed or refused
chain through a channel the operator actually reads -- a silently failed
orchestration is indistinguishable from a release nobody started, and that is
the one new failure mode this record creates. Second, the `dry_run` leg must
cover the whole chain, so the rehearsal that previously proved Gates 1 and 2 now
proves the orchestration too. Third, the inverse conformance gate of D1, so the
gate's absence is an asserted property rather than an accident. Stated honestly
and not papered over: no mechanism replaces the last-look veto, because the
click never performed one -- it authorised, it did not inspect -- and the intent
it did carry now lives in the dispatch.

**D7 -- The two untracked partial executions are finished and recorded.** A
half-executed obligation with no trail is worse than an unstarted one, because
its tracking artefact reports a state that is no longer true. Both are closed
here rather than left for a reader to rediscover. For the retiring lane (issue
#618, publication record OP-6): the surviving orphan environment
`pypi-data-official` is deleted, completing the forge half whose other two
thirds were already done; the index-side Trusted Publisher registrations for all
three retired projects are then VERIFIED and REPORTED, never assumed -- an
index-account action is outside this repository and outside the forge, so no
agent can execute or confirm it and the honest output is a stated finding, not a
claim of completion; and issue #618 is commented with the true split and closed
once its forge half is complete, with any surviving index-side registration
carried forward as a named operator item rather than silently absorbed. Because
publication has never run, the issue's original sequencing premise -- deletion
after the first successful publication -- is already void by the publication
record's P4, so nothing waits on anything. For the documentation consequence
(delivery record OP-3): the `docs` environment exists but carries no variable,
so the record's remaining half is the deploy-role variable alone, and this
record narrows OP-3 to that rather than leaving it stated as wholly outstanding.
Deleting an environment is an operator act and is NOT performed as part of
authoring this decision; it is an implementation step for the follow-on pass and
is worth an explicit operator confirmation, because the matching index-side
registration cleanup cannot be checked from inside the repository.

**D8 -- The approval gate falls on the delivery leg too.** The `docs`
environment carries `required_reviewers`, so the documentation consequence that
the delivery record's R2 designed as automatic would stop at a human approval
click the moment its role variable lands. That is the same gate class the ruling
strikes, sitting one leg over, and it is removed on the same terms: the
`required_reviewers` rule comes off `docs`, the environment and its
`branch_policy` stay, because the environment is the OIDC trust boundary that
makes the deploy role assumable only from this repository and this job. The
consequence direction is unchanged -- documentation still never gates a release
-- and D6's alerting obligation covers it, since a docs publish that fails
unwatched is the same silent failure as an orchestration that does.

**D9 -- The record and runbook surfaces.** This record supersedes no 2026-07-27
record wholesale, and deliberately so: each rules five to seven independent
couplings and only one sub-ruling in each is reversed, so whole-record
supersession would retire rulings that stand. The supersessions are therefore
partial and named. It SUPERSEDES the human-approval-gate premise of R2/R4 in
`2026-07-27-canonical-release-pipeline-adr`; those rulings' docs consequence,
ordering, credential, and handshake content are untouched, and only their
assumption of a human-approved publication authority falls. It SUPERSEDES the
execution half of P2 in `2026-07-27-publication-lane-consolidation-adr` and the
local-only versioning mandate surviving in `2026-04-12-release-please-adr`; P1,
P3, P4, and P5 of the former stand entirely, and the release-please manifest
remains the single version source. It AMENDS
`2026-07-27-pipeline-config-topology-adr` by narrowing the `release`
environment's role from protection-plus-identity to identity alone, leaving its
four homes, its detector, and its inventory unchanged. It AMENDS
`2026-07-04-release-readiness-gate-adr` by moving the soak wait from a human to
the pipeline without altering its duration or its terms. It COMPLETES, rather
than reverses, the publication record's OP-6 and narrows the delivery record's
OP-3 to its one outstanding half; both are executions the tree had lost track
of, not decisions being changed. On the operator-facing
side, `RELEASING.md` collapses from a six-stage part-manual runbook to a
single-dispatch procedure with a post-publication verification tail, its arming
section loses both the approval prerequisite and the phantom opt-in variable,
and the Stage 4 description of Gate 1 goes with the job. The reacquisition lanes
and the docs tripwire stay described as post-publication verification, because
they prove what a release did rather than authorise it.

## Rationale

The knockout for the trigger shape is that the fully hands-off option removes no
human act at all. Someone still authors and pushes the commit that would start
it; push-triggering only relocates the intent signal from a place where it is
explicit to a place where it is inferred, and inference is exactly what fails
badly around an irreversible act. The identity guard is the proof: it refuses a
version some destination already owns, which makes it a guard against REPEATING
a release, not against starting the wrong one. Under push-triggering, the first
release nobody meant to make passes every check in the repository. Under one
dispatch, the same guard set is unchanged and the one question it cannot answer
is answered by the act of dispatching. That is the whole design -- keep every
mechanical guarantee, and relocate the single human judgement to the one place
where a human is unambiguously making it.

The same reasoning disposes of the typed confirmation. Its only function is to
distinguish an accidental press from a deliberate one, and the dispatch form
already carries that distinction; adding a phrase to type reproduces the removed
ceremony while adding no property, which is the shape of a gate that exists to
feel safe rather than to be safe. The operator's ruling is precisely against
that class of gate.

On the bump, the honest reading of P2 is that it rejected CI execution "for no
mechanical gain" -- a conditional rejection whose condition the new driver
removes. It is worth naming what P2 got right and this record keeps: the failure
it was fixing was that NOTHING executed the bump, so two builds shared one
version. Moving execution into the orchestrator fixes that more completely than
a runbook step does, because a runbook step can be skipped and a pipeline stage
cannot. Deleting the local apply path rather than keeping it follows the
publication record's own precedent at P4: a second authority is removed more
thoroughly by deletion than by confinement, and a deleted path cannot be
mis-dispatched.

On the soak, the decisive observation is that the policy never asked for a
person -- it asked for elapsed time against an immutable candidate. Reading it
as a human checkpoint is what made it look incompatible with a single trigger.
Once the wait is machine-held, the strongest safety property in the release
cycle and the operator's ruling stop competing, and neither is compromised to
accommodate the other.

The captures are the one place where full automation is refused, and refused on
the project's own terms. The evidence rows assert that a real client installed
real bytes; an SDK-driven emit would assert the same sentence about a different
event. Automating them would not speed the pipeline, it would make it lie --
which is the failure mode every gate in this pipeline exists to prevent.

## Consequences

- A release becomes one act. The operator dispatches once and reads a result;
  bump, campaign, acquisition proofs, soak, publication to every channel, and
  the docs consequence all follow with no further human input. The four run-id
  transcriptions disappear as an error class, not merely as a chore.
- The only human judgement left in the loop is the release decision itself,
  expressed as the dispatch. Every other property the click was credited with is
  either held by a mechanical guard that already existed or was never held at
  all, and this record says which is which rather than implying completeness.
- One new failure mode is created and must be paid for: with no approval prompt,
  nobody is structurally guaranteed to look at a release run, and a silently
  failed orchestration looks exactly like a release nobody started. The alerting
  obligation is not a nicety; it is the price of the click's removal, and a plan
  that lands the orchestration without it has not landed this decision.
- The blast radius of a mis-dispatch grows. Previously a wrong dispatch stopped
  at an approval prompt; now it proceeds. The mitigations are the unchanged
  guard set, the whole-chain rehearsal, the soak window, and the
  reversible-first ordering that leaves everything except the final index upload
  undoable -- but the honest statement is that the pipeline is now trusted to be
  right rather than watched to be right.
- Two accepted rulings and one governing mandate are reversed in the open, with
  their surviving siblings named, and two further records are amended rather
  than contradicted, so a future honesty review reads a decision rather than a
  regression. The inverse conformance gate makes that durable in code as well as
  in prose.
- The soak boundary becomes the orchestration's hardest engineering problem
  rather than its hardest policy problem: a machine-held wait across two or
  three days needs durable state outside a running job, and getting that wrong
  either publishes early or never publishes at all. It is the second place, with
  run-id resolution, where this design is most likely to be implemented subtly
  wrong.
- Run-id resolution after a fire-and-forget dispatch is new code with no
  precedent in this tree, and the identify-MY-run hazard is real given the smoke
  workflow's queueing concurrency; the implementing plan should gate it with a
  test that plants a competing run.
- The orchestrator holds a runner slot for the length of the campaigns it waits
  on, on a four-runner fleet shared with sibling products. Sizing that wait
  cheaply is an implementation obligation, and a badly sized one starves the
  fleet for hours per release.
- New operator decision points: **OP-9** remove the `required_reviewers`
  protection rule from the `release` AND `docs` environments while KEEPING both
  environments and their `branch_policy`, since each is an OIDC trust anchor
  registered against its name; **OP-10** nominate the alerting channel the
  orchestrator reports failures to, since the approval prompt was previously the
  notification surface; **OP-11** confirm the self-hosted Linux runners carry the
  `node` toolchain release-please needs, or provision it; **OP-12** confirm
  deletion of the orphaned `pypi-data-official` environment and report whether
  the index-side Trusted Publisher registrations for the three retired projects
  were also removed, which no agent can check. The delivery record's OP-3
  narrows to its one remaining half, the deploy-role variable on the
  already-created `docs` environment.
- The two untracked partial executions get an owner and a trail. Their real cost
  was never the unfinished work -- it was that issue #618 and the OP-3 line both
  described a state that had silently stopped being true, so the next reader
  would have planned against fiction. The generalisable lesson, recorded because
  it will recur: a forge-side or index-side act leaves no commit, so an
  obligation split across the repository and an account is half-invisible by
  construction and needs its tracking artefact updated by hand or it rots.
- Not verified from this session, stated plainly: whether the index-side Trusted
  Publisher registrations for `pypi`, `pypi-data-manuals`, and
  `pypi-data-official` still exist, which needs index-account access no agent
  has; whether `node` is present on the fleet; and the wall-clock duration of a
  full chained release. Measured first-hand on 2026-08-02 and therefore
  load-bearing rather than assumed: the three live environments, their
  protection rules, their empty variable sets, the open comment-free state of
  issue #618, and the commit that landed its repository half. The workflow
  contents, justfile targets, channel descriptor, conformance pins, evidence
  tooling, and runbook text cited above were also read first-hand the same day.
