---
tags:
  - '#plan'
  - '#open-work-consolidation'
date: '2026-07-30'
modified: '2026-07-31'
tier: L2
related:
  - '[[2026-07-30-open-work-consolidation-adr]]'
  - '[[2026-07-30-open-work-consolidation-audit]]'
---

<!-- RETIRED: S01, S29 -->

# `open-work-consolidation` plan

### Phase `P01` - unblock the publication chain

Releases the largest cascade in the fleet, ten rows that stand behind the release environment approval alone now that the publish opt-in variable is retired, and carries the first canonical publication through to reacquisition evidence.

- [ ] `P01.S02` - Approve the release environment deployment when the publish dispatch requests it, the environment carries a required-reviewer rule naming the account owner, OPERATOR-GATED; `operator action, release environment`.
- [ ] `P01.S03` - Dispatch the publication workflow promoting the stored cohort bytes without rebuilding, then record the run id as the publication of record, the workflow has never run; `.github/workflows/publish-release.yml`.
- [ ] `P01.S04` - Verify the shared tap repository received the bucket manifest and the formula, both directories held only a .gitkeep placeholder before this publish; `operator verification, shared tap repository`.
- [ ] `P01.S05` - Acquire the root and companion distributions from the package index and repeat installed CLI and MCP tax work; `dev/packaging/acquire_pypi.py`.
- [ ] `P01.S06` - Acquire the exact release cohort and verify every retained digest against the promoted manifest; `dev/packaging/acquire_github_release.py`.
- [ ] `P01.S07` - Acquire through the public Scoop bucket and repeat installed behaviour; `dev/packaging/acquire_scoop.ps1`.
- [ ] `P01.S08` - Acquire through the public Homebrew tap and repeat installed behaviour; `dev/packaging/acquire_homebrew.py`.
- [ ] `P01.S09` - Acquire the public marketplace plugin and repeat the MCP tax-work call; `dev/packaging/acquire_claude_plugin.py`.
- [ ] `P01.S10` - Acquire the published MCPB through each claimed client and repeat the MCP tax-work call; `dev/packaging/acquire_mcpb.py`.
- [ ] `P01.S11` - Reacquire every public Claude artifact and verify its harness namespace and bilingual product descriptions against the cohort manifest; `dev/packaging/acquire_claude_plugin.py, dev/packaging/acquire_mcpb.py`.

### Phase `P02` - host and runner topology

Provides the native Windows execution host and sandbox the Scoop evidence rows require, without touching the shared Docker daemon whose mode the governing decision froze.

- [ ] `P02.S12` - Provision a native Windows self-hosted runner labelled windows-scoop under a dedicated non-admin local user with Scoop installed in that user profile, OPERATOR-GATED as a host act, no such label exists on the fleet today; `operator action, Windows workstation runner service`.
- [ ] `P02.S13` - Enable the Containers-DisposableClientVM Windows feature, reading the RestartNeeded result the call itself returns rather than pre-scheduling a reboot, because a restart stops both online runners and every agent session on that box, OPERATOR-GATED; `operator action, Windows host feature`.
- [ ] `P02.S14` - Run the clean Scoop acquisition gate naming run 30387416398 and its exact commit 35a46ff4f25664c2895a56e25196e502511722c2 as a pair, or a fresher successful smoke run whose head commit is an ancestor of main, the workflow hard-matches the run id to that commit; `.github/workflows/packaging-scoop.yml`.
- [ ] `P02.S15` - Install from the intended shared bucket in Windows Sandbox and exercise CLI, MCP, update, and persistence behaviour; `dev/packaging/smoke_scoop.ps1`.

### Phase `P03` - real client captures

Collects the in-application evidence no agent can produce, because a real conversation window and a real tool call in each client are operator acts.

- [ ] `P03.S16` - Perform the in-application Claude Desktop tax-work prompt against the installed bundle and retain the capture, OPERATOR-GATED because no agent can drive a real Desktop conversation; `operator action, Claude Desktop`.
- [ ] `P03.S17` - Install the supported artifact in Cowork and perform the in-application tax-work tool call, OPERATOR-GATED, no capture exists; `operator action, Cowork`.
- [ ] `P03.S18` - Capture each real client harness identifier inventory, MCP server name, and bilingual product descriptions, then compare them against the exact cohort; `var/distribution-install-readiness`.

### Phase `P04` - published claims and support matrix

Publishes only claims that reacquisition evidence supports, so the documentation gate stops passing vacuously and starts passing truthfully.

- [ ] `P04.S19` - Publish only the acquisition commands and support claims that reacquisition evidence proves, the gate currently passes vacuously because no positive claim is made; `README.md`.
- [ ] `P04.S20` - Document clean installation, verification, update, and removal for the package index, Scoop, and Homebrew; `docs/workstation-setup.md`.
- [ ] `P04.S21` - Document Claude Code, Desktop, and Cowork plugin and bundle acquisition with real verification commands; `docs/how-to/connect-an-agent.md`.
- [ ] `P04.S22` - Publish the measured platform, client, and channel support matrix, six of eleven required rows carried real passing evidence on 2026-07-30; `docs/updates.md`.
- [ ] `P04.S23` - Audit every generated artifact claim against retained installed behaviour and public reacquisition evidence; `.vault/audit`.

### Phase `P05` - independent remediation

Carries the work that no publication gates, including live user-facing breakage, the retired PyPI lane residue, and the two rows migrated from campaigns that closed with carry-forwards.

- [ ] `P05.S24` - Correct the broken published plugin forward by publishing the renamed plugin, the published 0.1.1 entry resolves a package that returns 404 on the index so every install fails today with no working alternative, gated on the first publication providing a resolvable target; `operator action, marketplace publication`.
- [ ] `P05.S25` - Retire the three Trusted Publishing registrations on the package index, the workflow and its conformance test were already deleted and the sequencing precondition was voided by decision; `operator action, package index project settings`.
- [ ] `P05.S26` - Delete the three orphaned deployment environments left by the retired second publication lane; `operator action, repository environments`.
- [ ] `P05.S27` - Verify the Clave session salvage with one live authentication run under the live-tests opt-in, inducing a post-auth navigation failure and confirming the salvage line fires while no second approval is requested on retry, OPERATOR-GATED because the second factor is single-use and device-bound; `operator action, live Clave authentication`.
- [x] `P05.S28` - Assess whether the same post-auth failure spends a Clave Permanente credential, a question recorded only inline in one step record and tracked nowhere, escalating to a coding campaign with a discovery gate if it proves a defect; `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py`.
- [x] `P05.S30` - Rerun the twelve semantic duplication probes and record the delta against the baseline they check for recurrence of, closing the residue of a row that was superseded rather than satisfied; `src/cadrumo/, dev/audit/`.
- [ ] `P05.S31` - Submit the winget manifest under the corrected package identifier once an asset-bearing dashboard release exists, blocked on that upstream release process rather than on anything here; `operator action, microsoft/winget-pkgs submission`.

## Description

Every genuinely actionable row left in the fleet, carried as one ordered flow. The governing decision is `2026-07-30-open-work-consolidation-adr`, which rules that six plans close with documented carry-forwards while a single non-coding plan carries the residue; the evidence base is `2026-07-30-open-work-consolidation-audit`, which measured all twenty-one rows those plans held open against the tree, the forge, and the package indexes on 2026-07-30.

One decision governs every Phase here, so no Phase-to-ADR mapping is needed. The plan admits no coding work by construction: a row found to need code leaves this plan for a coding campaign with a semantic-discovery gate in front of it, rather than widening this one. That property is deliberate, because the discovery gate was unavailable when this plan was authored and would have refused coding work while leaving every row below untouched.

Two rows arrive here as migrations rather than fresh work. The semantic-sweep residue comes from a conformance campaign whose row closed as superseded, not satisfied, because its instrument never became trustworthy. The Cl@ve verification comes from an autofill campaign whose fix landed in the tree but cannot be verified without a live single-use second factor.

## Steps

The five Phase blocks carrying this plan's thirty-one Step rows are rendered above, directly beneath the document title. That placement is the plan serializer's canonical anchoring, not an authoring choice: structural blocks are re-anchored ahead of authored prose on every mutating verb, so a Phase block moved beneath this heading by hand would be relocated again by the next progress mark. Read the rows there.

## Parallelization

`P05` is fully parallel with everything else and needs no publication. Two of its rows are actionable the moment this plan lands, retiring the trusted-publishing registrations and deleting the orphaned environments, and neither has any prerequisite at all. `P05` also holds the only row whose cost is borne by users rather than the project, the broken published plugin, so it should be worked first despite sitting last.

`P02` and `P03` are parallel with `P01` and with each other. `P02` is a host-configuration sequence with one hard ordering, the runner before the acquisition gate before the sandbox install. `P03` is three operator captures with no internal ordering beyond the identity comparison needing both client captures first.

`P01` carries the hardest ordering in the plan. The variable and the approval precede the dispatch, the dispatch precedes every acquisition row, and the tap verification precedes the two acquisition rows that read from the shared repository. The acquisition rows themselves are parallel once the publication exists.

`P04` is strictly last. Every row in it publishes a claim, and a claim may only be published once the reacquisition evidence for it exists, which means `P04` cannot start before `P01` completes and cannot finish before `P02` and `P03` do. Its final audit row is the terminal row of the plan.

## Verification

Every row closes against a fact observable outside this worktree, never against a local artefact. Because minted evidence lives in a git-ignored directory, a closure citing a local path is unverifiable by anyone but the machine that produced it, so each execution record names the run identifier and, where a commit matters, the commit whose ancestry was checked.

The publication rows verify against the forge: the publication workflow reporting a successful run where it previously had none, the shared tap repository holding a real bucket manifest and formula where it previously held only placeholders, and each acquisition script completing against a public channel rather than a local staging directory. The host rows verify against the runner inventory exposing a `windows-scoop` label that does not exist today, and against the Scoop acquisition gate passing while naming a run identifier and its exact commit as a pair. The client rows verify against retained captures showing a real tool call in each client, which is why they cannot be satisfied by an agent.

The documentation rows verify against the fail-closed claims gate, which currently passes vacuously because no positive acquisition claim is made. Passing it truthfully, with claims present and evidence behind each, is the criterion; a vacuous pass does not count. The support matrix closes when eleven of eleven required rows carry real passing evidence, against six on 2026-07-30.

Two rows carry criteria that no automated check can express. The Cl@ve verification closes on a live authentication run in which the salvage line fires and no second approval is requested on retry, observed by the operator. The semantic-index repair closes when the indexed section count matches the tracked file count, which is the measurement that three prior attempts failed while the service reported success, so the count is the criterion and the service's own status is not.

The plan is complete when every Step is closed. It is honestly complete only if no row was closed by narrowing what it claimed.
