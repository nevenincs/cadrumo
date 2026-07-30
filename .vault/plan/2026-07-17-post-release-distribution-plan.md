---
tags:
  - '#plan'
  - '#post-release-distribution'
date: '2026-07-17'
modified: '2026-07-30'
tier: L2
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-16-distribution-harness-identity-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
  - '[[2026-07-17-distribution-installation-readiness-audit]]'
  - '[[2026-07-16-distribution-harness-identity-research]]'
  - '[[2026-07-19-post-release-distribution-reference]]'
  - '[[2026-07-17-post-release-distribution-audit]]'
---

<!-- RETIRED: S01, S02, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25 -->

# `post-release-distribution` plan

### Phase `P01` - Prove local channel artifacts in real acquisition environments

Exercise the generated Scoop, Homebrew, and MCPB artifacts in the real clean-acquisition environments they target. Every step here needs multi-OS runner or real-publisher access unavailable from this development worktree.

- [x] `P01.S03` - RESOLVED 2026-07-28, run 30391339584 at commit 0b4fba14f9 is green across all five jobs including homebrew-linux-arm64, the SIGILL toolchain defect no longer reproduces, evidence lives as a per-run GitHub draft per the aggregation gap named in the plan Description, no further blocker on this row; `.github/workflows/packaging-homebrew.yml`.
- [x] `P01.S04` - RESOLVED by accepted ADR 2026-07-18-mcpb-signing-publisher-adr, the MCPB ships unsigned by operator decision (no purchased certificate), integrity channel is the published SHA-256 plus in-bundle cohort digest pins already enforced by the bootstrap, no signing identity to bind; `packaging/mcpb/build.py`.

### Phase `P02` - Execute the platform and client support matrix

Run cohort-bound installed-behavior oracles on every claimed operating-system row and inside every real Claude client. Every step needs multi-OS CI runners and real Claude-client installs unavailable from this worktree.

- [x] `P02.S05` - DONE, Linux Python row green in push-to-main Cadrumo Packaging Smoke run 29657832151 at commit 1abbc48c72 (cohort build, installed grounded tax oracle DP200014:00562 = 23000.00, installed-oracles attestation suite), first fully green three-OS matrix; `.github/workflows/packaging-smoke.yml`.
- [x] `P02.S06` - DONE, Windows Python row green in the same run 29657832151 (fourth consecutive green Windows leg); `.github/workflows/packaging-smoke.yml`.
- [x] `P02.S07` - DONE, macOS Python row green in run 29657832151 after root-causing the deterministic per-binary Keychain hang via the worker-stack capture (custody file-backend pin b5e6780fb1, product follow-up issue 615); `.github/workflows/packaging-smoke.yml`.
- [x] `P02.S08` - DONE, Homebrew Linux x86-64 row green in Cadrumo Homebrew Acquisition run 29895959334 at commit 1af8f4fb13, sanctioned homebrew-linux-x86-64 distribution-evidence row minted against release cohort bfe3df0bae (version 0.2.1, source commit 1c9c523d7c) with the installed CLI oracle and the installed MCP oracle both computing DP200014:00562 = 23000.00 via modelo-200-cuota-integra from the brew Cellar keg, the second Linux row homebrew-linux-arm64 stays red and is tracked under P01.S03; `.github/workflows/packaging-homebrew.yml`.
- [x] `P02.S09` - DONE via local subscription-authed Claude Code 2.1.214 per operator ruling (no CI API key), evidence var/distribution-install-readiness/s27-plugin-68a8433c/run-20260718T164855Z/plugin-evidence.json against cohort 68a8433c at commit 02b3656095, marketplace install with byte-verified three-wheel cohort, real client session connected and called cadrumo_harness_load (status passed), protocol oracle on the same install returned DP200014:00562 = 23000.00 via modelo-200-cuota-integra with the sole permitted plazo-vencido notice; `.github/workflows/packaging-claude.yml`.

### Phase `P03` - Promote and reacquire the public channels

Publish the tested cohort through the protected workflow and reacquire the exact bytes from every advertised public endpoint. Blocked by held operator publish approval and by public-registry reacquisition access.

### Phase `P04` - Publish availability documentation and audit against public evidence

Write availability language and the support matrix only for channels with passing post-public evidence, and audit every artifact claim against retained installed-behavior and public-reacquisition evidence. Blocked until the reacquisition evidence exists.

### Phase `P05` - Harness-identity brand migration (operator-gated)

The distribution identity verifier honestly fails: generated harness identifiers (7 personas, 34 skills, 7 rules) carry no cadrumo- prefix and the MCP plugin, marketplace, and MCPB product descriptions are English-only rather than bilingual EN and ES. Distribution steps W02.P06.S67 and S68 are intentionally left open because bringing them green requires a brand-identifier rename plus a bilingual product-description migration that the accepted distribution-harness-identity ADR does not authorize. This phase tracks that migration; it is BLOCKED pending explicit operator authorization, parallel to the held publish approval, per the cadrumo-product-authority-names brand-identifier discipline.

- [x] `P05.S26` - UNBLOCKED by operator GO 2026-07-18 and DONE, harness-identity migration landed as the distribution-harness-identity campaign (12/12 steps, exec records under .vault/exec/2026-07-18-distribution-harness-identity), verify_distribution_identity exits 0 with report.ok true (evidence var/distribution-install-readiness/s11-migration-identity-bilingual), distribution S67 and S68 closed; `src/cadrumo/_data/agent, src/cadrumo/agent, packaging/mcpb/manifest.json, dev/packaging/verify_distribution_identity.py`.

### Phase `P06` - Close the close-honesty-review findings

Track every finding the close honesty review raised as a step with a verification gate, rather than prose left in the audit document

- [x] `P06.S27` - Supersede the topology ADR through the pipeline rather than the in-place rewrite already landed, the superseding record must answer the two deleted objections, sibling-serving answered by the shared repo and no-precedent answered by verda-cloud/homebrew-tap carrying Formula and bucket together, and must reconcile the scoop-runner-topology ADR explicitly as unaffected because it rules on which runner executes the lane not where manifests live. Ownership is with account-distribution-lead if its account-wide ruling subsumes the cadrumo scope, asked 2026-07-25 and awaiting reply. GATE, vault check all passes and the superseded record carries superseded_by; `.vault/adr`.
- [x] `P06.S28` - CORRECTED 2026-07-25. The closure reports declared the TOPOLOGY work complete, which it is and which was reviewed, but did not scope that claim, so they read as a claim over the whole post-release-distribution plan, which is not complete. The plan stands at 12 of 35 with 23 open. Of those 23, seven are operator-gated, three need a host or runner the worktree does not have, nine chain to the operator-held publish at P03.S13, and four are agent work, the honesty-review rows in this phase. The remainder is therefore overwhelmingly operator-blocked rather than incomplete engineering, and no closure claim may be made over the plan until those close or are formally deferred. GATE, this correction is recorded and vault plan status is the ratio any future claim must cite; `.vault/plan/2026-07-17-post-release-distribution-plan.md`.
- [x] `P06.S29` - Re-audit the six step annotations the review flagged, three claim partial unblocking where only a redundant clause was struck and three moved their blocker from private to nonexistent, restate each as the blocker it actually carries today. GATE, every P01 and P03 row names a blocker that is true at the time of reading; `.vault/plan/2026-07-17-post-release-distribution-plan.md`.
- [x] `P06.S30` - DONE 2026-07-25. Swept the plan rows naming retired distribution variables against the live variable set, which is exactly HOMEBREW_TAP_REPO and CLAUDE_MARKETPLACE_REPO. P04.S23 named the retired CADRUMO_MARKETPLACE_REPO and now names the live one. P03.S13 additionally asserted that the scoop, homebrew and marketplace variables and tokens are all set, which is false, Scoop needs neither and the two renamed secrets do not exist yet because secrets cannot be renamed, so that row now names the two missing secrets as a remaining operator precondition. GATE, no plan row outside this one names a variable absent from the live repository variable set; `.vault/plan/2026-07-17-post-release-distribution-plan.md`.
- [x] `P06.S31` - DONE 7d20b2d984, the docs-claims gate now measures, a positive control asserts every pattern against a must-match and a must-not-match string and a guard requires a new pattern to arrive with its own cases, the retired tap pattern fails 2 of 4 control cases so the control discriminates. GATE, uv run --no-sync pytest dev/docs/tests/test_distribution_claims.py collects 12 and passes; `dev/docs/tests/test_distribution_claims.py`.
- [x] `P06.S32` - DONE 7d20b2d984, the three tap-pattern over-broadenings are closed, scanning moved per line so a cross-newline match cannot form and the regression document genuinely reproduces the whole-file match, the pattern re-anchored on the account so a third-party tap is not a claim, and a negation preceding the command marks a disclaimer. GATE, the positive control carries all three strings as must-not-match cases; `dev/docs/tests/test_distribution_claims.py`.
- [x] `P06.S33` - DONE 7d20b2d984, marketplace publish is atomic, the whole cohort validates before any mutation so a refusal leaves the tree byte-identical, and the multi-plugin case that was entirely uncovered now has both a refusal test and a success test. GATE, the pre-fix loop leaves a torn tree so the atomicity test discriminates; `dev/packaging/marketplace_publish.py`.
- [x] `P06.S34` - DONE 7d20b2d984, plugin-name collision refuses instead of silently overwriting, index entries carry published_by and a cohort declaring a name another product published is refused, while an unattributed entry stays claimable so the first release adopting it is not deadlocked. GATE, the sibling tree and its attribution both survive a refused takeover; `dev/packaging/marketplace_publish.py`.
- [x] `P06.S35` - DONE 7d20b2d984, concurrent publication is closed rather than only recorded, the marketplace push re-clones and re-applies on a rejected push because concurrency groups are per-repository and cannot serialise across product repos, and refuses after three lost races. GATE, a workflow conformance test pins the retry, the re-clone inside the loop, and the fail-closed exhaustion; `.github/workflows/publish-release.yml`.

## Description

This plan holds the tail of the distribution-installation-readiness campaign that cannot be completed from this development worktree. The parent campaign built and locally proved every generated artifact: the cohort manifest, the Python wheel and sdist lanes, the Scoop and Homebrew generators, the plugin, marketplace, and MCPB artifacts, and the release-readiness evidence schema. What remains is the work that requires real external access, and it is gated on two conditions that this worktree cannot satisfy.

The first gate is operator publish-workflow approval. Publication is currently HELD by the operator until the worktree is declared settled, so promoting the cohort through the protected manual OIDC workflow (P03.S13) cannot proceed. No agent may flip that gate; only the operator can.

The second gate is real public-registry and multi-operating-system access. Reacquiring the exact published bytes from PyPI, the GitHub release, the public Scoop bucket, the public Homebrew tap, the Claude marketplace, and the MCPB clients (all of P03) needs those registries to have received the promoted cohort first and needs credentialled reacquisition. Executing the platform and client support matrix (all of P02) needs multi-OS CI runners and real Claude Code, Claude Desktop, and Cowork client installs. Proving the local channel artifacts in their target environments (all of P01) needs Windows Sandbox, multi-OS acquisition-gate runners, and a real publisher signing identity for MCPB. Writing availability documentation and auditing the artifact claims (all of P04) can only assert channels that already have passing post-public evidence, which does not yet exist.

Every step in this plan was lifted verbatim from the distribution-installation-readiness plan and its originating step identifier is recorded in each row. The completable local remainder stays in the parent plan for the distribution peer to finish; this plan is the honest home for the deferred work so the parent can close its local scope without falsely completing what only the post-release environment can prove.

State verification on 2026-07-24 confirmed both gates still hold and recorded each open row's exact precondition in the row itself. It also surfaced three live blockers that sit UPSTREAM of every remaining step, because none of them can start until a fresh cohort can be built. First, the packaging campaign is red at its first step: the campaign runner executes the packaging preflight test pass before any wheel, cohort, or oracle work, and the frozen model-facing MCP description digest in the distribution identity verifier has drifted on committed main, so every operating-system leg aborts immediately. The remedy is the established one-line mechanical re-pin, performed on a clean tree once the in-flight CLI and locale changes land. Second, the self-hosted Windows runner workspace is wedged, failing three consecutive smoke runs at repository checkout, which reds both Windows rows. Third, the self-hosted Linux ARM64 runner is offline, and it is the host the red Homebrew arm64 row needs.

Two further findings bear on the promotion phase. A public v0.2.1 GitHub release was hand-published on 2026-07-21 outside the publication authority, carrying only seven cohort members and no cohort manifest, so it is not a promotion the digest gate can verify and it should be reconciled or replaced. The five distribution-evidence rows that do pass live on per-run GitHub evidence drafts rather than in the local evidence directory, so the readiness gate cannot reach a complete row set until they are aggregated back down.

On 2026-07-30, 18 open rows (P01.S01, P01.S02, P02.S10 through P02.S12, P03.S13 through P03.S20, and P04.S21 through P04.S25) were removed from this plan and migrated to 2026-07-30-open-work-consolidation-plan, which now carries them as one ordered flow authorised by 2026-07-30-open-work-consolidation-adr. These rows were migrated, not delivered: the reduced row count reflects a change of carrier, not a narrowing of scope, and none of the underlying blockers or preconditions described above changed as part of this migration.

## Steps

## Parallelization

The phases are ordered by the release lifecycle and cannot be freely parallelized. P01 proves the local channel artifacts in their target acquisition environments; P02 executes the platform and client support matrix against those artifacts; P03 promotes the tested cohort and reacquires it from public endpoints; P04 documents and audits only channels with passing post-public evidence. P03 cannot begin until the operator lifts the publish hold, and P04 cannot begin until P03 has produced reacquisition evidence. Within each phase, the individual operating-system and client rows are mutually independent and may run concurrently on separate runners once that phase's gate is open.

## Verification

- Every Scoop, Homebrew, and MCPB artifact installs and runs its real-behavior oracle in its target clean-acquisition environment (Windows Sandbox and the multi-OS acquisition-gate runners), and the MCPB signing identity binds to the immutable cohort.
- The installed tax oracle reports the grounded Modelo 200 result on every claimed Linux, Windows, and macOS Python row, and the Claude Code, Claude Desktop, and Cowork clients each start the cohort-pinned server and complete the tax-work tool call; a missing client or a skip cannot pass.
- Publication consumes the stored cohort without any build or regeneration, and every advertised public endpoint reacquires the recorded SHA-256 digests and repeats installed behavior.
- README and user documentation name only acquisition paths, platforms, and clients with passing post-public evidence, and the close audit maps every artifact claim to retained installed-behavior and public-reacquisition evidence.
- The plan is complete only when every step above is closed against real external evidence; a fresh-context honesty review runs against the closure summary before completion is declared.
