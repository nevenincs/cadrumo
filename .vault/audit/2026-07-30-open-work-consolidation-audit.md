---
tags:
  - '#audit'
  - '#open-work-consolidation'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# `open-work-consolidation` audit: `fleet-wide reconciliation of vault plans against code`

## Scope

Every open row across the six plans that were in flight on 2026-07-30 — twenty-one rows spanning post-release distribution, CLI authority verb conformance, censal profile autofill, account distribution standard, scoop runner topology, and the delivery pipeline audit — reconciled against the state of the tree, the forge, and the package indexes as measured that day rather than as narrated by the rows themselves.

The audit exists because the percentages had stopped describing reality. Four plans read as one row from completion and one read as half finished, while the actual distribution of remaining work was the inverse. Measurements are live reads: the Actions API for runner, run, variable, secret and environment state, `git merge-base` for commit ancestry, the package indexes for project existence, and the working tree at `HEAD` for whether described defects still exist.

The prompting question was whether the open set was actionable. It was not: rows had been reading as blocked on conditions that cleared days earlier, and one row's stated remedy would have caused an outage.

## Findings

### dangerous-stale-instruction | critical | acting on one row's stated blocker would take down the runner fleet

One distribution row records its blocker as the Windows host needing to run Docker in Windows-container mode, and a triage pass faithfully relayed that text as an operator instruction. The accepted scoop runner topology decision explicitly rejected that mode switch on the grounds that Docker Desktop serves one container mode at a time, so a switch tears down every running Linux container, and ruled instead that the daemon stays permanently in Linux-container mode with a dedicated native runner. Two of the fleet's four runners are the standing Linux and Windows workers on that daemon, both online and busy at audit time. Had the instruction been executed, the remedy for one evidence row would have stopped the infrastructure every other row depends on. The row's text is not merely out of date; it is an active hazard, and it survived because a reader trusted the plan over the decision that governs it.

### stale-blocker-drift | high | fourteen rows cited a repository that had existed for five days

The most-repeated blocker in the distribution plan is operator creation of the public shared repository serving both the Scoop bucket and the Homebrew tap, recorded as returning 404 on a structured query at 2026-07-25. That repository exists, is public, and was created at 21:42 UTC on 2026-07-25 — hours after the probe that the rows still cite. It carries the expected `bucket/` and `Formula/` directories, each holding only a `.gitkeep`, and nothing has been pushed since creation. The precise truth is therefore that the repository precondition is satisfied and only the content a publish writes is absent, which is a materially different and much smaller blocker. The drift had a visible cause: the account distribution plan recorded the creation as done in its own rows, while the distribution plan was never swept, so one plan knew what the other still denied.

### deleted-release-still-narrated | high | seven rows reason about a release that no longer exists

Three rows narrate the asset list of a hand-published v0.2.1 release, and four more inherit conclusions from it. That release is gone: there are zero non-draft releases in the repository, `git ls-remote --tags origin` returns zero tags, and a direct query for the tag reports it as not found. Only evidence drafts remain. Every conclusion drawn from its incomplete asset set — that a digest gate needs the missing cohort manifests, that an attached bundle is the wrong one, that a close audit must reconcile an artefact that bypassed the publication authority — is reasoning about an object that is absent. The operator ruling of 2026-07-30 makes 0.1.0 the canonical release target, and the practical consequence is the opposite of what was assumed: rather than a version-ordering conflict requiring a yank or retag, 0.1.0 publishes into an entirely empty release namespace.

### no-coding-work-outstanding | high | the fleet holds zero implementation rows

The single row that appeared to require implementation — salvaging an authenticated Cl@ve session that a post-auth navigation failure was closing before its cookies were read — was already fixed at `HEAD`. Two commits landed it, the first adding the salvage call ahead of context teardown and the second narrowing the recorded landing so an unusable URL is not persisted; both are ancestors of `HEAD`, and both functions are present in `_clave_movil.py`. Its execution record is populated rather than a scaffold. Across all six plans, therefore, not one open row needs code written. This matters beyond bookkeeping: the mandatory semantic-discovery gate was unavailable throughout this session, which would have refused any coding work, and that constraint turned out to cost nothing.

### rag-instrument-never-recovered | high | a discovery row's instrument degraded to zero while reporting success

The conformance plan's penultimate row is a rerun of ten semantic sweeps. Its record shows the original attempt on 2026-07-25 missing all ten concepts against an index holding 466 sections for 3,982 tracked files, with two unrelated probes returning the same file and offset — the signature of a tiny candidate pool. Re-measurement on 2026-07-28 found 20 sections against 3,742 files, and the final measurement found zero code sections and zero vault documents, the service self-reporting success at every stage. A rebuild added chunks without moving coverage. The row is therefore not waiting for someone to run probes against a working instrument; it is waiting on an instrument that has never worked and whose dependency the operator subsequently dropped for that campaign. Closing it as satisfied would be false, and leaving it open blocks a 287-row campaign on a tool rather than on work.

### persona-relay-defect-degraded-a-prior-review | high | a shipped harness defect silently corrupted a campaign-close review

All ten agent personas shipped by the development harness declare a fixed tool list, and not one includes a team-coordination tool. Dispatched as background workers they therefore have no channel to return findings: four such agents were launched during this audit, all four performed their investigations, all four reported idle, and none delivered a word, including after direct requests. The failure is silent, because an idle signal is indistinguishable from a clean completion. This is not a new fault. The formal close review of 2026-07-28 records itself as the weakest of the three sanctioned honesty-review forms precisely because a dispatched independent reviewer "produced nothing across three idle signals and two direct requests" — the same defect, two days earlier, degrading a governance gate rather than a triage pass. Filed upstream against the harness on 2026-07-30.

### publish-gate-collapsed | medium | the publish row's four preconditions are now two

The publication row lists four operator preconditions: repository creation, the opt-in variable, the environment approval, and two channel secrets. Two have cleared. The repository exists, and both channel secrets exist as of 2026-07-28, their presence readable through the Actions API even though their values are not. What remains is the opt-in repository variable, confirmed absent because variable values are readable and only two unrelated variables are set, and the required-reviewer approval on the dispatch itself. The workflow has never run. So the largest cascade in the fleet, roughly thirteen rows, stands behind one variable and one approval click.

### pypi-lane-already-retired | medium | a row described as event-gated is unconditional and two thirds done

The delivery pipeline row describes deleting a second PyPI upload workflow, its conformance test, and three trusted-publishing registrations, upon the first successful publication through the canonical lane. Two of the three targets are already gone: the workflow and its conformance test were deleted on 2026-07-27 in a commit that is an ancestor of `HEAD`, authorised by a publication-lane consolidation decision that struck the sequencing precondition outright. The publication that the row waits for has still never happened, so the deletion did not wait for it and did not need to. Only the three registrations and their three now-orphaned deployment environments remain. The row is unconditionally actionable today, and was the only such row in the fleet.

### arm64-row-resolved | medium | the Homebrew evidence row's blocker no longer exists

The Homebrew acquisition row is annotated as partially green and blocked on an operator toolchain fix for a source build dying with an illegal-instruction fault on the Linux ARM64 host. A later run is green across all five of its jobs, including that ARM64 leg and the terminal seal, at a commit confirmed to be an ancestor of `HEAD`. The defect that a dedicated campaign diagnosed no longer reproduces. Consequently the published support matrix count is also stale: six of eleven required rows now have real passing evidence, not five.

### evidence-lives-in-an-ignored-directory | medium | minted evidence is invisible to a clean checkout

The artefacts that evidence rows are minted from live under `var/`, which is git-ignored. Every such file is therefore untracked and absent from any fresh clone, from CI, and from a peer's tree. The durable record of a green acquisition is the run itself, not the local directory. Any row closure that cites a local path rather than a run identifier is unverifiable by anyone but the machine that produced it, which is the same class of defect as evidence captured from a dirty worktree.

### published-plugin-broken-for-users | high | a live install path is broken independently of any plan

The published plugin at version 0.1.1 wires its server to resolve a package that returns 404 on the index, having been deleted during the product rename, while the replacement package is not yet published. Anyone installing that plugin today gets a broken install and there is no working alternative to point them at. This is live user-facing breakage rather than plan bookkeeping, it sits outside every open row's dependency chain, and it is the only finding in this audit whose cost is borne by users rather than by the project.

### submission-row-not-ripe | low | a package-name correction has nothing to submit

The winget package-name correction is to be made forward, by submitting subsequent versions under the correct identifier and leaving the wrongly-named published version orphaned, since a published identifier cannot be renamed in place. The wrong identifier is confirmed published and the correct one confirmed absent, as the row states. But the latest release of the product being submitted carries zero assets, so no installable artefact exists to submit. The blocker is a defect in that repository's own release process, outside the scope of any plan in this fleet, and the row cannot be actioned even by the operator until an asset-bearing release is cut.

### permanente-salvage-unexamined | low | a sibling authentication path was left unassessed and untracked

The record for the Cl@ve salvage fix notes that the Permanente authentication path carries no salvage at all, and that whether the same post-auth failure spends a Permanente credential was never examined. That observation exists only inline in one execution record; no row, plan, or decision tracks it. The supporting module for that path exists, so the surface is real. Severity may well differ, because Permanente does not consume a fresh single-use factor the way the mobile path does, but the question is explicitly unexamined rather than answered.

### permanente-salvage-gap-confirmed | low | the unexamined sibling path shares the defect, at a far lower cost

Answered on the same day it was raised, by the assessment row this audit recommended. Cl@ve Permanente does carry the same structural window: its fresh-login capture reads session state only on the success path, and its failure branch closes the context and re-raises without reading it, so a post-authentication redirect timeout discards a session whose credentials the identity provider has already accepted. Nothing analogous to the Movil salvage exists for it, and the two providers do not share the flow-driving code, so the recent fix did not carry over and a deliberate port is required.

The severity is nonetheless low rather than a second instance of the original problem, because the cost of a discarded session is what made the Movil case urgent and Permanente does not share it. Movil spends a single-use, device-bound approval the operator must physically grant; Permanente resubmits a reusable identifier and password headlessly, and the SMS-OTP elevation path is refused outright rather than driven, so no second factor is ever consumed. Two questions remain open and bear only on priority: whether repeated late logins can trip a lockout or anti-automation challenge, in which case the salvage becomes a mitigation rather than a convenience, and whether the timeout has ever fired outside a test. The remediation is deliberately not carried by the consolidation plan, since that plan admits no coding work.

## Recommendations

Consolidate the residue. Twenty of the twenty-one open rows are blocked on an operator act, an upstream defect, or a decision, and none needs code; they are scattered across six plans whose percentages misdescribe them. A follow-on decision record must rule on whether the originating plans close with documented carry-forwards while a single non-coding plan carries every genuinely actionable row as one ordered flow, and on the disposition of the two rows that cannot close on their own terms — the semantic-sweep row whose instrument never worked, and the Cl@ve verification row that requires a live single-use second factor.

Correct before closing. Nine rows carry text that is false at `HEAD`, and one of those, the container-mode blocker, is a hazard rather than an inaccuracy. Correction precedes any closure decision, because a reader who trusts the current text will either act dangerously or conclude that cleared blockers still stand.

Cite runs, never paths. Because minted evidence lives in an ignored directory, every closure must name the run identifier and the commit whose ancestry was checked. Applied immediately to the Homebrew evidence row, whose blocker is resolved and whose closure cites a run.

Treat the broken published plugin as unscheduled work. It is the only finding here that harms users, it is independent of the publication cascade, and it should not wait behind a plan.

Track the Permanente gap or rule it out deliberately. An unexamined question recorded only in a step record is indistinguishable, six months on, from a question that was answered.
