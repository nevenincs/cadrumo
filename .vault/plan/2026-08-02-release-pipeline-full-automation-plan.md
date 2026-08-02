---
tags:
  - '#plan'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_hash: 'sha256:e865eb6c601bc67d278fe1fcc238966ceb8e9e1b9c1e96864404dd9903958b48'
tier: L3
related:
  - '[[2026-08-02-release-pipeline-full-automation-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-publication-lane-consolidation-adr]]'
  - '[[2026-07-27-pipeline-config-topology-adr]]'
  - '[[2026-07-04-release-readiness-gate-adr]]'
  - '[[2026-04-12-release-please-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-plan]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
---

# `release-pipeline-full-automation` plan

## Steps

## Wave `W01` - Gate removal and its inverse pin

Strike the human approval gate first, on both legs it sits on, and pin its absence so a later honesty pass reading the three 2026-07-27 records cannot restore it as drift. This Wave changes what the pipeline refuses, not what it does, so it is independently landable and carries no dependency on the orchestration built later. The environment survives everywhere: only the required_reviewers protection rule goes, and its removal on the forge is the operator OP-9 half, tracked here explicitly so the code half and the settings half cannot be confused for each other.

### Phase `W01.P01` - Approval-gate deletion and the inverse conformance pin

Delete the operator-preflight job and its needs edge from the publication authority, keep environment release on the publish job because it is the Trusted Publishing trust anchor, rewrite the header prose that still describes an opt-in variable nothing reads, and invert the conformance test that pinned the gate into one that pins its absence.

- [x] `W01.P01.S01` - Delete the operator-preflight job and the needs operator-preflight edge on the validate job from the publication authority, leaving environment release intact on the publish job because it is the Trusted Publishing trust anchor and the shared-runner product boundary, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with the job absent from the parsed document and the publish job environment still asserted as release; `.github/workflows/publish-release.yml`.
- [x] `W01.P01.S02` - Invert test_preflight_enforces_the_human_approval_gate_it_promises into a gate asserting that no job reads an environment protection rule, that no job conditions on required_reviewers, and that environment release survives on the publish job, so the removal is an asserted property a later honesty pass cannot silently restore, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes and a planted job re-adding a protection-rule read reds the new assertion; `dev/release/tests/test_publish_release_workflow.py`.
- [x] `W01.P01.S03` - Rewrite the publication authority header comments that still promise an operator opt-in variable and an approval click, replacing them with the guard set that actually gates the run, and pin the corrected prose so the described gate and the enforced gate cannot drift apart again, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with an assertion that the header names no approval click and no opt-in variable; `.github/workflows/publish-release.yml, dev/release/tests/test_publish_release_workflow.py`.
- [x] `W01.P01.S04` - Record OP-9 as a named operator settings action removing the required_reviewers protection rule from BOTH the release and docs environments while keeping each environment and its branch_policy, and add a read-only forge inventory probe that reports each environment protection-rule set without mutating anything so the operator half is verifiable rather than assumed, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes over fixture payloads covering a rule-present, a rule-absent, and an unreadable-environment response; `dev/release/environment_inventory.py, dev/release/tests/test_environment_inventory.py, RELEASING.md`.

## Wave `W02` - The mechanisms one dispatch needs

Build every piece of new, testable machinery the orchestrator will consume, before any workflow chains them. Three of these are named by the ADR as the places this design is most likely to be implemented subtly wrong: run-id resolution after a fire-and-forget dispatch has no precedent in this tree, the version bump becomes a pipeline stage for the first time, and the soak wait needs durable state outside any running job. Each lands as an importable module with unit gates that plant the failure it defends against, so the orchestrator in W03 is assembly rather than invention.

### Phase `W02.P02` - Dispatch, run-id resolution, and lane derivation

Build the fire-and-forget dispatch companion this tree has never needed: resolve MY run rather than the newest run, wait on a conclusion cheaply, derive which acquisition lanes a release must dispatch from the same claimed-channel authority the readiness gate reads, and refuse instructively when a claimed host-extension channel has no human-minted evidence.

- [x] `W02.P02.S05` - Build the dispatch-and-resolve module that dispatches one workflow and then resolves the run IT started, keyed on the workflow path, the head commit, and a created-after timestamp captured before the dispatch, refusing on ambiguity rather than guessing, because gh workflow run returns no run id and the smoke workflow queues rather than cancels so the newest run may belong to a neighbour, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes over injected Actions API payloads including a planted competing run started between the dispatch and the poll, and the resolver refuses rather than promoting the neighbour; `dev/release/run_resolution.py, dev/release/tests/test_run_resolution.py`.
- [x] `W02.P02.S06` - Add the conclusion waiter as a bounded backoff poll with a declared budget and an instructive timeout refusal naming the run it was watching, sized as a cheap poll on a short-lived job rather than a busy hold, because a waiting orchestrator occupies one of four self-hosted runner slots shared across products for the whole campaign it watches, gate: uv run --no-sync pytest dev/release/tests/test_run_resolution.py -q passes covering success, failure, cancellation, and budget-exhaustion outcomes against an injected clock with no real sleeping; `dev/release/run_resolution.py, dev/release/tests/test_run_resolution.py`.
- [x] `W02.P02.S07` - Derive the acquisition lanes a release must dispatch from the same claimed-channel authority publication_inputs and the readiness gate already read, so an unclaimed channel is never dispatched and a claimed one can never be skipped, and so flipping a channel availability to available arms its lane with no workflow edit, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes with cases covering the current descriptor claiming python only, a descriptor claiming scoop and homebrew, and a claimed channel absent from the source mapping refusing rather than passing unproven; `dev/packaging/publication_inputs.py, dev/packaging/tests/test_publication_inputs.py`.
- [x] `W02.P02.S08` - Add the fail-closed precondition refusing an orchestration when a claimed host-extension channel has no operator-minted claude evidence release, naming the emit_real_client_evidence capture command in the refusal, and never attempting to produce those four rows because the emit honesty guard refuses SDK-driven runs by design and defeating it would make the evidence a lie about what was installed, gate: uv run --no-sync pytest dev/packaging/tests -q -k precondition passes covering the unclaimed-channel pass, the claimed-and-supplied pass, and the claimed-and-absent refusal carrying the capture command in its message; `dev/packaging/publication_inputs.py, dev/packaging/tests/test_publication_inputs.py`.
- [x] `W02.P02.S40` - Declare the lane-to-workflow mapping that turns a claimed channel into the acquisition workflow the orchestrator dispatches, covering packaging-scoop, packaging-homebrew, and packaging-claude, and keep it separate from the operator-minted claude row source so the dispatchable acquisition lane and the four non-automatable real-client captures are never conflated into one input, gate: uv run --no-sync pytest dev/packaging/tests -q -k publication_inputs passes asserting each mapped channel resolves to an existing workflow path on disk and that the claude channel resolves to BOTH a dispatchable acquisition lane and a human evidence-release precondition; `dev/packaging/publication_inputs.py, dev/packaging/tests/test_publication_inputs.py`.

### Phase `W02.P03` - Version bump as a pipeline stage

Turn the eleven instructions just release-apply prints into an executable, tested bump: compute the version from release-please, apply it to all seven declaration surfaces, regenerate and verify the lock, prepend the changelog block, commit, tag, and push behind the unchanged identity guards. The local apply path is deleted in the same Wave so one authority owns version advancement.

- [x] `W02.P03.S09` - Build the bump executor that runs release-please against the manifest floor, reads the computed version rather than accepting a chosen one, and applies it to all seven declaration surfaces named by the retiring apply target, the release-please manifest, the three pyproject versions, the package dunder version, both base dependency pins, and the changelog block, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes against an injectable temporary repository root asserting each of the seven surfaces individually and asserting the build-stamped mcpb manifest sentinel is NOT touched; `dev/release/version_bump.py, dev/release/tests/test_version_bump.py`.
- [x] `W02.P03.S10` - Add the lock regeneration and verification leg plus the version-surfaces-agree readiness re-check to the bump executor so the transcription error class the readiness check exists to catch cannot survive an automated bump either, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case that plants one stale surface and asserts the executor refuses before committing anything; `dev/release/version_bump.py, dev/release/tests/test_version_bump.py`.
- [x] `W02.P03.S11` - Add the commit, tag, and push leg invoking the all-destination version-identity authority BEFORE any ref leaves the runner, so a bump colliding with an owned, burned, or below-floor version refuses before a tag exists rather than after, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes against an injectable git root covering the clean bump, a burned-version refusal, and a below-floor refusal, with real push execution flagged non-local and CI-only; `dev/release/version_bump.py, dev/release/tests/test_version_bump.py`.
- [x] `W02.P03.S12` - Delete both the unix and windows release-apply recipes in full and update the guidance conformance test to assert their absence and to assert just release survives as the read-only dry-run preview, so one authority owns version advancement and a deleted path cannot be mis-invoked, gate: uv run --no-sync pytest dev/release/tests/test_justfile_release_guidance.py -q passes with release-apply asserted absent from the justfile and rg -n release-apply over the tree matching only vault records and history; `justfile, dev/release/tests/test_justfile_release_guidance.py`.
- [x] `W02.P03.S13` - Add the OP-11 toolchain precondition refusing the bump stage instructively when node is absent from the runner, because release-please shells out through npx and whether the self-hosted Linux fleet carries node is unverified and named by the ADR as a plan precondition, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case asserting the refusal names the provisioning action when the probe reports node missing; `dev/release/version_bump.py, dev/release/tests/test_version_bump.py`.

### Phase `W02.P04` - Soak state and the machine-held wait

Give the 48-72 hour soak durable state outside any running job. The candidate record is sealed alongside the cohort and published through the existing evidence-release draft transport, its deadline is read from the release checklist rather than a new literal, and a scheduled promoter crosses the boundary so no human re-enters the loop and no candidate publishes before its window closes.

- [x] `W02.P04.S14` - Declare the release-candidate record as a strict typed model carrying the cohort id, the version, the source commit, the smoke run id, every acquisition run id, the claimed channel set, the dry_run flag, the soak opened_at, and the computed soak deadline, with the window read from the release checklist soak hours rather than a new literal so one authority still owns the duration, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes with a strict save-load-equality roundtrip populating every defaultable field non-default plus an anti-tautology proof deleting the deadline from the serialized payload and asserting the load refuses; `dev/release/release_candidate.py, dev/release/tests/test_release_candidate.py`.
- [x] `W02.P04.S15` - Publish the sealed candidate record through the existing evidence-release draft transport under a release-candidate tag keyed on the smoke run id, so the durable state lives outside every running job and outside the working tree exactly as the evidence rows already do, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes over the writer and reader against injected release payloads, with live draft creation flagged non-local and CI-only; `dev/release/release_candidate.py, dev/packaging/evidence_release.py, dev/release/tests/test_release_candidate.py`.
- [x] `W02.P04.S16` - Build the promoter selection logic that lists sealed candidates, selects the eldest whose soak deadline has elapsed against a real clock, and refuses every candidate whose window is still open, because publishing early is the one failure this mechanism exists to prevent and a wrong comparison publishes early silently, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes covering an elapsed candidate selected, a not-yet-elapsed candidate refused, a boundary candidate at exactly the minimum window, and an empty candidate set returning no promotion rather than an error; `dev/release/soak_promoter.py, dev/release/tests/test_soak_promoter.py`.
- [x] `W02.P04.S17` - Require the promoter to re-run the readiness gate against the sealed cohort and its bound evidence rows immediately before dispatching, so a candidate whose blocking evidence regressed during its window is invalidated with a named refusal instead of promoted on a stale green, honouring the soak policy that a blocking regression invalidates a cohort and is never repaired in place, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes with a case that reds the readiness report for an elapsed candidate and asserts no dispatch is attempted; `dev/release/soak_promoter.py, dev/release/tests/test_soak_promoter.py`.
- [x] `W02.P04.S18` - Make promotion idempotent by marking a candidate consumed once its publication dispatch succeeds and refusing a second promotion of the same cohort id, backed by the unchanged version-identity authority which refuses an owned version regardless, so a promoter tick overlapping its predecessor cannot double-publish, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes with a case running two promoter passes over one elapsed candidate and asserting exactly one dispatch; `dev/release/soak_promoter.py, dev/release/tests/test_soak_promoter.py`.
- [x] `W02.P04.S19` - Carry the hotfix carve-out onto the candidate record as a shortened window admissible only when the record names an incident reference and a release-owner approval, preserving the readiness gate terms verbatim rather than weakening them while the wait moves from a human to the pipeline, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes covering a shortened window accepted with an incident reference present and refused when it is absent; `dev/release/release_candidate.py, dev/release/soak_promoter.py, dev/release/tests/test_soak_promoter.py`.
- [x] `W02.P04.S20` - Author the scheduled soak promoter workflow on a cron plus workflow_dispatch, running one short-lived job per tick on the self-hosted fleet under a product-scoped no-cancel concurrency group, invoking the selection logic and dispatching the publication authority with the run ids recorded on the candidate, so the soak boundary is crossed by a clock with no human re-entering the loop, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter_workflow.py -q passes pinning the schedule trigger, the runner labels, the concurrency group, the absence of any manual input that could shorten a window, and the dispatch target being publish-release.yml; `.github/workflows/release-soak-promoter.yml, dev/release/tests/test_soak_promoter_workflow.py`.

## Wave `W03` - The orchestrator assembly

Chain the W02 mechanisms into the single operator-facing surface of a release. Hard-depends on W02 in full because every stage invokes a module built there, and on W01 because the publication authority it dispatches must already be gate-free. Nothing here invents behaviour: each job dispatches a workflow an operator could dispatch by hand and waits on a cheap poll, so no new trust path is created and no runner slot is held across a campaign it is merely watching.

### Phase `W03.P05` - The release orchestrator workflow

Author the one workflow an operator dispatches, staging bump, campaign, acquisition lanes, and candidate seal, with dry_run propagating end to end and a resume input that re-enters the chain at an existing campaign rather than re-bumping. Every stage consumes a W02 module, so this Phase adds wiring and conformance pins rather than logic.

- [x] `W03.P05.S21` - Author the release orchestrator workflow shell taking a dry_run boolean and an optional resume input naming an existing packaging-smoke run and nothing else, with no typed confirmation input because the dispatch itself is the intent act, running on the self-hosted fleet under a product-scoped no-cancel concurrency group so two dispatches cannot interleave two versions, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes pinning the exact input set, the runner labels, the concurrency group and its cancel-in-progress false, and asserting no confirmation-phrase input exists; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S22` - Wire the bump stage as the orchestrator first job invoking the bump executor and emitting the bumped commit and version as job outputs the downstream stages key on, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the bump job invokes dev.release.version_bump and that its outputs are consumed by the campaign stage rather than re-derived; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S23` - Wire the packaging campaign stage to dispatch packaging-smoke at the bumped commit and resolve its own run through the run-resolution module rather than the newest run, then wait on the conclusion waiter, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the stage invokes dev.release.run_resolution and never reads a bare latest-run query, with end-to-end chaining flagged non-local and CI-only; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S24` - Wire the acquisition stage to dispatch exactly the lanes the claimed-channel derivation returns, passing its own smoke run id and head commit as each lane source_run_id and source_commit, resolving and waiting on each dispatched run, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the lane set is derived rather than hardcoded and that today's python-only descriptor dispatches no acquisition lane; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S25` - Wire the host-extension evidence precondition into the orchestrator entry so a claimed claude channel with no operator-minted evidence release refuses the whole chain before the bump lands rather than after a version is burned, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the precondition job precedes the bump job in the needs graph; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S26` - Wire the candidate-seal stage as the orchestrator terminal job writing the release-candidate record and ending the run, so no orchestrator job holds a runner slot across the two-to-three day soak and the promoter alone resumes the chain, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the seal job is terminal, that no job sleeps or polls past the seal, and that the orchestrator never dispatches publish-release directly; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S27` - Propagate dry_run through every orchestrator stage and onto the sealed candidate record so the rehearsal that previously proved Gates 1 and 2 now proves bump, campaign, acquisition, seal, and promotion without advancing a version or publishing a byte, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting every stage reads the dry_run input and that the bump job pushes no ref and the promoter refuses to publish a dry_run candidate; `.github/workflows/release-orchestrator.yml, dev/release/soak_promoter.py, dev/release/tests/test_release_orchestrator_workflow.py`.
- [x] `W03.P05.S28` - Implement the resume input so a dispatch naming an existing packaging-smoke run re-enters the chain at the acquisition stage without re-bumping or re-running the campaign, letting a chain that failed after a successful campaign converge instead of burning a second version, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the bump and campaign jobs are skipped when resume is supplied and that the supplied run is identity-verified on the same terms Gate 2 verifies it; `.github/workflows/release-orchestrator.yml, dev/release/tests/test_release_orchestrator_workflow.py`.

## Wave `W04` - Safety net, operator surfaces, and closeouts

Pay the price the click removal creates and finish the two obligations the tree had lost track of. Alerting is a deliverable of this campaign and not a nicety: with no approval prompt, a silently failed orchestration is indistinguishable from a release nobody started, and a plan that lands the chain without it has not landed the decision. The runbook collapses to the single-dispatch procedure, the phantom opt-in variable is swept, and the two partial executions get a trail before the fresh-context honesty review closes the campaign.

### Phase `W04.P06` - Failure alerting across the release chain

Restore the one property the click actually held: that somebody looks. Every workflow on the release path reports a failed or refused run through a channel the operator reads, and a reachability gate makes an unalerted release workflow a test failure rather than a discovery made when a release quietly did not happen.

- [x] `W04.P06.S29` - Build the failure-alert emitter reporting a failed or refused release-path run to a channel the operator actually reads, defaulting to opening a labelled repository issue carrying the workflow, the run URL, the stage, and the refusal text so alerting works before OP-10 nominates a channel, with an optional operator-nominated webhook variable overriding the default once set, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes covering the default issue path, the webhook path once the variable is set, and idempotent re-alerting that updates an open alert rather than opening a duplicate per attempt; `dev/release/alerting.py, dev/release/tests/test_release_alerting.py`.
- [x] `W04.P06.S30` - Attach an always-on failure-alert step to the orchestrator, the soak promoter, the publication authority, and the docs publisher, because the click was the only moment a human was structurally guaranteed to look and a silently failed chain is indistinguishable from a release nobody started, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes asserting each of the four workflows carries an if-failure alert step invoking the emitter; `.github/workflows/release-orchestrator.yml, .github/workflows/release-soak-promoter.yml, .github/workflows/publish-release.yml, .github/workflows/docs-publish.yml`.
- [x] `W04.P06.S31` - Add the alert-reachability gate asserting every workflow on the declared release path carries a failure alert, computing the release-path set from the workflows the orchestrator and promoter dispatch rather than a hand-maintained list, so a future release workflow added without an alert reds a test instead of failing silently in production, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q -k reachability passes and an injectable-root self-test plants a release-path workflow with no alert step and asserts the gate reds; `dev/release/tests/test_release_alerting.py`.

### Phase `W04.P07` - Runbook and operator-surface collapse

Collapse RELEASING.md from a six-stage part-manual runbook to a single-dispatch procedure with a post-publication verification tail, sweep the phantom opt-in variable and the deleted Gate 1 description out of every surface that still describes them, and keep the reacquisition lanes and docs tripwire described as verification rather than authorisation.

- [x] `W04.P07.S32` - Collapse the RELEASING.md release procedure from six part-manual stages to one dispatch followed by a post-publication verification tail, deleting the Stage 0 hand-transcription, the Stage 2 per-lane dispatch instructions, and the Stage 4 Gate 1 description that went with the deleted job, while keeping the reacquisition lanes and the docs tripwire described as verification rather than authorisation, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q and uv run --no-sync pytest dev/docs/tests -m docs -q pass with the runbook conformance assertions updated to the single-dispatch shape; `RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [x] `W04.P07.S33` - Rewrite the RELEASING.md arming section to drop the approval-click prerequisite and the phantom CADRUMO_PUBLISH_ENABLED opt-in variable that no longer exists anywhere in the tree, replacing both with the OP-9 protection-rule removal and the credential prerequisites that genuinely remain, gate: rg -n CADRUMO_PUBLISH_ENABLED over the tree matches only vault records and history, and uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes; `RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [x] `W04.P07.S34` - Rewrite the RELEASING.md release-candidate soak stage to describe the machine-held wait, naming the candidate record, the promoter cadence, and the hotfix carve-out, so the documented soak and the enforced soak describe the same mechanism rather than a human holding a tag, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the release-candidate soak assertions retained and re-pointed at the promoter; `RELEASING.md, docs/_release_checklist.yaml, src/cadrumo/tests/test_release_config.py`.
- [x] `W04.P07.S35` - Sweep every remaining user-facing and developer-facing surface that describes the release flow as part-manual, including the release notes template soak wording and any documented command naming the deleted apply target, gate: uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q and uv run --no-sync pytest dev/docs/tests -m docs -q pass; `docs/, dev/docs/tests/`.

### Phase `W04.P08` - Partial-execution closeouts and campaign honesty review

Finish the two obligations whose tracking artefacts describe a state that stopped being true, splitting each honestly into the half a repository change can close and the half only an operator holding forge or index credentials can. The campaign then takes a fresh-context honesty review before it is declared structurally complete.

- [x] `W04.P08.S36` - Record OP-12 as a named operator settings action deleting the orphaned pypi-data-official environment, which is a live Trusted Publishing trust anchor naming a workflow that no longer exists and therefore standing authority with no owner, and extend the read-only forge inventory probe to report any environment referencing an absent workflow so the orphan class is detectable rather than rediscovered, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes with a case whose fixture environment names a workflow path absent from the tree and is reported as orphaned; `dev/release/environment_inventory.py, dev/release/tests/test_environment_inventory.py, RELEASING.md`.
- [x] `W04.P08.S37` - Comment on tracking issue 618 with the true split naming the repository half landed 2026-07-27, the two environments already deleted, the third pending OP-12, and the index-side Trusted Publisher registrations that no agent can verify, then close it once its forge half is complete, carrying any surviving index-side registration forward as a named operator item rather than silently absorbing it, gate: gh issue view 618 shows the comment and the closed state, flagged forge-side and non-local, and the carried-forward operator item is named in the runbook operator-actions section which the runbook conformance test asserts is present; `RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [x] `W04.P08.S38` - Narrow the delivery record OP-3 on every operator-facing surface to its one remaining half, the deploy-role variable on the already-created docs environment, and state alongside it that the docs environment required_reviewers removal is the second half of OP-9 rather than a separate obligation, so a reader is not told to create an environment that exists, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions section asserting exactly the outstanding halves; `RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [ ] `W04.P08.S39` - Run the fresh-context honesty review against the campaign closure summary before the campaign is declared structurally complete, dispatching an independent reviewer with the ADR, this plan, and the commit range as context, and track every surfaced item as a new Step with a verification gate or formally defer it with a named follow-up, gate: the audit document exists under .vault/audit and uv run --no-sync vaultspec-core vault plan status reports no checked Step without an exec record; `.vault/audit/`.

### Phase `W04.P09` - Honesty-review remediation

Close every item the fresh-context honesty review surfaced against the landed chain. One critical defect makes the soak promoter permanently non-functional after the first rehearsal, and two high findings leave the alerting obligation the decision record calls the price of the click removal undelivered on the live forge. Nothing here reopens a ruling: every Step corrects an implementation divergence from a decision the accepted record already made, or corrects prose asserting a property the code does not hold. The campaign is not structurally complete until these close.

- [x] `W04.P09.S41` - Make the promoter selection skip past a non-promotable candidate rather than returning on the first one, and retire a rehearsal candidate out of the selectable namespace once its window closes, because a rehearsal seals a real GC-exempt draft while the rehearsal input defaults to true, and a refused rehearsal candidate is currently never consumed so it is re-selected on every tick forever and every real candidate sealed afterwards never publishes, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes with a case planting a rehearsal candidate whose deadline precedes a real candidate deadline and asserting the real candidate is still dispatched exactly once, plus a second case asserting the rehearsal candidate leaves the selectable namespace; `dev/release/soak_promoter.py, dev/release/release_candidate.py, dev/release/tests/test_soak_promoter.py`.
- [ ] `W04.P09.S42` - Make the labelled-issue alert path survive a repository carrying no release-alert label, because the live forge carries no such label so every default-path alert is currently refused by the forge and degraded to a run-log warning nobody reads, leaving the alerting deliverable that pays for the removed approval click delivering nothing, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes with a case whose injected executable refuses the label exactly as the live forge does and asserts the alert is still delivered rather than degraded to a warning; `dev/release/alerting.py, dev/release/tests/test_release_alerting.py`.
- [x] `W04.P09.S43` - Record the release-alert label as a named operator provisioning action alongside OP-10 so the forge state the default alerting path depends on is verifiable rather than assumed, and extend the read-only environment inventory probe to report whether that label exists, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions section asserting the label item, and uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes over a fixture payload with the label absent; `dev/release/environment_inventory.py, dev/release/tests/test_environment_inventory.py, RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [x] `W04.P09.S44` - Make the promoter exit status distinguish an ordinary quiet tick from an invalidated candidate so a cohort whose readiness gate reds during its soak reaches the failure-guarded alert instead of reporting to nobody, honouring the decision record obligation that a failed or refused chain alerts, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes asserting a readiness-regressed elapsed candidate yields a non-zero exit while a tick whose every window is still open yields zero; `dev/release/soak_promoter.py, dev/release/tests/test_soak_promoter.py`.
- [ ] `W04.P09.S45` - Carry every acquisition run id from the acquisition stage onto the sealed candidate record, declaring the stage job outputs and giving each dispatched lane its own output name, because the seal module reads three acquisition environment variables the orchestrator never sets and the stage declares no outputs at all, so the ids are dropped and the promoter would dispatch the publication without its acquisition proofs the moment a channel is claimed, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes with a case asserting the seal stage receives every acquisition run id the derived lane set produces under a descriptor claiming scoop and homebrew, and asserting the assertion fails when a lane output is dropped; `.github/workflows/release-orchestrator.yml, dev/release/seal_candidate.py, dev/release/tests/test_release_orchestrator_workflow.py`.
- [ ] `W04.P09.S46` - Fix the promoter report-only shell guard which tests the variable for emptiness rather than truth so a manual dispatch rendering the boolean as the literal string false always passes the flag and can therefore never promote, and pin the input semantics, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter_workflow.py -q passes asserting the promote step passes the report-only flag when the input is true and passes no flag when the input is false or unset; `.github/workflows/release-soak-promoter.yml, dev/release/tests/test_soak_promoter_workflow.py`.
- [ ] `W04.P09.S47` - Pass the captured refusal text to the alert emitter at all four call sites so an alert body carries why the run failed rather than the no-detail placeholder it currently always renders, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes asserting every release-path workflow alert invocation supplies a detail argument and that the rendered payload carries it; `.github/workflows/release-orchestrator.yml, .github/workflows/release-soak-promoter.yml, .github/workflows/publish-release.yml, .github/workflows/docs-publish.yml, dev/release/tests/test_release_alerting.py`.
- [ ] `W04.P09.S48` - Make the rehearsal bump exercise the seven declaration surfaces, the lock regeneration, the parity re-check, and the all-destination identity guard against a discarded temporary tree rather than returning immediately after computing the version, so the rehearsal proves the stage its own prose and the decision record both claim it proves and can surface an owned or burned or below-floor version before a real dispatch, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes asserting a rehearsal run refuses a burned version and leaves no ref and no modified surface in the real repository root; `dev/release/version_bump.py, dev/release/tests/test_version_bump.py`.
- [x] `W04.P09.S49` - Add OP-10 and OP-11 to the runbook operator-actions section as named outstanding items, because the section is gated on naming exactly the outstanding halves and the toolchain precondition in particular is stated as unverified by the decision record itself and blocks the very first real dispatch at its very first stage, gate: uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes with the operator-actions assertions extended to cover the alerting channel and the toolchain precondition; `RELEASING.md, src/cadrumo/tests/test_release_config.py`.
- [ ] `W04.P09.S50` - Reconcile the plan Verification claim that a tree-wide search for the retired apply target matches only vault records and history, either by rewording the bump module docstrings that reference it or by narrowing the claim to the operator-facing surfaces it actually means, gate: rg -n release-apply over the tree matches only vault records, CHANGELOG history, and the conformance test asserting its absence; `dev/release/version_bump.py, .vault/plan/`.
- [ ] `W04.P09.S51` - Extend the alert guards on the multi-job workflows and the promoter to cover cancellation as well as failure, so a run cancelled by a runner eviction or a concurrency interaction is not the same silence the campaign exists to remove, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes asserting each release-path alert guard admits a cancelled outcome and a positive control plants a failure-only guard and reds; `.github/workflows/release-orchestrator.yml, .github/workflows/release-soak-promoter.yml, .github/workflows/publish-release.yml, dev/release/tests/test_release_alerting.py`.

## Description

One plan executes one ADR, the full-automation record, whose nine decisions map
onto the four Waves as follows. W01 executes D1 and the repository-visible half
of D8. W02 executes the mechanism halves of D2 (P02), D3 (P03), and D5 (P04).
W03 executes the assembly half of D2 and the chaining half of D4 (P05). W04
executes D6 (P06), D9 (P07), and D7 (P08). The five records the ADR partially
supersedes or amends are carried in `related:` because every Step inherits their
surviving rulings: only the human-approval-gate premise of R2/R4, the execution
half of P2, and the local-only versioning mandate fall, and every other ruling
in that cluster still binds the Steps below.

D8 is IN SCOPE here and is not deferred to a follow-on. Its repository-side
content is nil - `docs-publish.yml` already exists, already runs on
`release: published`, and already never gates a release - so its only actionable
content is the `required_reviewers` removal on the `docs` environment, which is
the second half of OP-9 and is discharged by `W01.P01.S04` naming both
environments, by `W04.P08.S38` narrowing OP-3 to the deploy-role variable alone,
and by `W04.P06.S30` extending the alerting obligation over the docs publisher.
Splitting it into a separate plan would have separated one operator settings
action from its own other half.

The soak is the campaign's hardest engineering problem and is resolved by
separating the record from the waiter. The orchestrator's terminal job seals a
typed release-candidate record - cohort id, version, source commit, every run
id, claimed channels, `dry_run`, `opened_at`, and a deadline computed from the
release checklist's declared soak hours - and publishes it through the evidence
release draft transport this tree already uses for evidence rows, then ends. No
job holds a runner slot across the window. A scheduled promoter workflow ticks
independently, selects the eldest candidate whose deadline has elapsed, re-runs
the readiness gate against the sealed cohort so a regression during the window
invalidates the candidate rather than promoting on a stale green, and dispatches
the publication authority with the recorded run ids. The mechanism honours both
of D5's invariants: no human re-enters the loop, and no candidate publishes
before its window closes.

The bump joins the pipeline as `W02.P03` plus `W03.P05.S22`. The eleven
instructions `just release-apply` prints become an executable bump module gated
against an injectable temporary repository root, with the all-destination
identity authority invoked before any ref leaves the runner, and `release-apply`
is deleted in the same Wave so one authority owns version advancement while
`just release` survives as the read-only preview.

Nothing in this plan publishes, pushes to a public channel, arms a credential,
removes a protection rule, or deletes an environment. Four operator halves run
beside it and are named rather than performed: OP-9 (the `required_reviewers`
removal on `release` and `docs`), OP-10 (the alerting channel, which
`W04.P06.S29` renders non-blocking by defaulting to a labelled issue), OP-11
(the `node` toolchain on the fleet, refused instructively by `W02.P03.S13`), and
OP-12 (the orphaned `pypi-data-official` environment). The four `claude-*`
real-client evidence captures stay a human precondition outside the loop: no
Step produces them, and `W02.P02.S08` exists only to refuse the chain when a
claimed host-extension channel lacks them.

Agent assignment: `vaultspec-high-executor` for the mechanism Steps in P02, P03,
and P04 and for the orchestrator wiring in P05, because run-id resolution, the
bump, and the soak boundary are the three places the ADR names as most likely to
be implemented subtly wrong. `vaultspec-standard-executor` for P01, P06, and the
inventory probe. `vaultspec-low-executor` for the P07 runbook and documentation
sweep. `vaultspec-code-reviewer` for `W04.P08.S39`.

## Parallelization

Waves are sequenced: W02 hard-depends on nothing in W01 but W03 hard-depends on
both, because the orchestrator dispatches a publication authority that must
already be gate-free and invokes modules that must already exist. W01 may
therefore run concurrently with W02.

Within W01, `P01.S01` precedes `P01.S02` (the inverted test asserts the deleted
job's absence), `P01.S03` follows `S01` on the same file, and `P01.S04` is
independent of all three.

Within W02 the three Phases share no files and run in parallel. P02 is internally
ordered `S05` before `S06` (the waiter consumes the resolver) with `S07` and
`S08` parallel to both, and `S40` (appended after authoring, so it carries a
higher canonical id than its display neighbours) following `S07` because the
lane-to-workflow mapping extends the derivation `S07` lands. P03 is strictly ordered `S09`, `S10`, `S11`, then `S12`
and `S13` in parallel. P04 is ordered `S14`, `S15`, then `S16`, with `S17`,
`S18`, and `S19` parallel after `S16`, and `S20` last because the workflow pins
the selection logic.

W03 is strictly sequential across `S21` through `S28`: every Step touches
`.github/workflows/release-orchestrator.yml`, so they land one at a time in
canonical order regardless of any other parallelism.

Within W04, P06 is ordered `S29`, `S30`, `S31` and must follow W03 because `S30`
attaches the alert to the orchestrator and promoter. P07 must follow W03 so the
runbook describes the landed shape, and its four Steps are internally sequential
on `RELEASING.md`. P08 `S36` may run any time after `P01.S04` (it extends the
same probe), `S37` and `S38` follow `S36`, and `S39` is last by definition.

Hard file serialization exists on three files:
`.github/workflows/publish-release.yml` is touched by `P01.S01`, `P01.S03`, and
`P06.S30`; `.github/workflows/release-orchestrator.yml` by all eight P05 Steps
and `P06.S30`; and `RELEASING.md` by `P01.S04`, `P07.S32`, `P07.S33`, `P07.S34`,
`P08.S36`, `P08.S37`, and `P08.S38`. Steps touching each of those land
sequentially in canonical order.

## Verification

Mission success is measured, not asserted. The plan is complete when every Step
is closed with its named gate green and the following hold together:

- The publication authority carries no `operator-preflight` job and no
  protection-rule read, `environment: release` is still asserted present on the
  publish job, and the inverted conformance gate reds against a planted job that
  re-adds a protection-rule read.
- `rg -n CADRUMO_PUBLISH_ENABLED` over the tree matches only vault records and
  history. `rg -n release-apply` over the tree matches only vault records,
  `CHANGELOG.md` history, and the justfile-guidance conformance test that
  asserts the retired recipe's absence — narrower than "vault records and
  history" alone, because the bump module's docstrings legitimately describe
  the retired manual checklist's numbered steps by paraphrase rather than by
  the literal retired command name.
- The run resolver refuses rather than promoting a neighbour when a competing
  run is planted between the dispatch and the poll, and the conclusion waiter
  covers success, failure, cancellation, and budget exhaustion against an
  injected clock with no real sleeping.
- The bump executor asserts each of the seven declaration surfaces individually
  against an injectable repository root, leaves the build-stamped mcpb sentinel
  untouched, refuses on a planted stale surface, and refuses a burned or
  below-floor version before any ref leaves the runner.
- The candidate record survives a strict save-load-equality roundtrip with every
  defaultable field populated non-default, and an anti-tautology proof deleting
  the deadline from the serialized payload proves the load refuses.
- The promoter selects an elapsed candidate, refuses a candidate whose window is
  still open, refuses an elapsed candidate whose readiness gate reds, dispatches
  exactly once across two overlapping passes, and refuses a shortened window
  with no incident reference.
- The orchestrator conformance suite pins the exact input set with no
  confirmation-phrase input, the no-cancel product-scoped concurrency group, the
  derived rather than hardcoded acquisition lane set, the terminal seal job with
  no post-seal poll, and `dry_run` reaching every stage.
- The alert-reachability gate is green on the tree and reds against a planted
  release-path workflow carrying no failure alert.
- The runbook conformance and docs gates pass with `RELEASING.md` describing a
  single dispatch, a machine-held soak, and exactly the outstanding operator
  halves.
- A fresh-context honesty review audit exists under `.vault/audit` and every
  checked Step carries an exec record, per plan-closure discipline.

Full-tree gates run under the shared-worktree discipline: a red owned by a peer
campaign is recorded and attributed, never absorbed silently into this plan's
completion claim. Live execution of the chain is BLOCKED on OP-9 through OP-12
and every Step whose real behaviour needs a forge dispatch carries a locally
verifiable conformance gate plus an explicit non-local flag.
