---
generated: true
tags:
  - '#index'
  - '#post-release-distribution'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:4fe9c0d184b236bae4bed9d056b1dac68e4603f5419fbef7c06daf7b45519c1d'
related:
  - '[[2026-07-17-post-release-distribution-P01-S03]]'
  - '[[2026-07-17-post-release-distribution-P01-S04]]'
  - '[[2026-07-17-post-release-distribution-P02-S05]]'
  - '[[2026-07-17-post-release-distribution-P02-S06]]'
  - '[[2026-07-17-post-release-distribution-P02-S07]]'
  - '[[2026-07-17-post-release-distribution-P02-S08]]'
  - '[[2026-07-17-post-release-distribution-P02-S09]]'
  - '[[2026-07-17-post-release-distribution-P05-S26]]'
  - '[[2026-07-17-post-release-distribution-P06-S27]]'
  - '[[2026-07-17-post-release-distribution-P06-S28]]'
  - '[[2026-07-17-post-release-distribution-P06-S29]]'
  - '[[2026-07-17-post-release-distribution-P06-S30]]'
  - '[[2026-07-17-post-release-distribution-P06-S31]]'
  - '[[2026-07-17-post-release-distribution-P06-S32]]'
  - '[[2026-07-17-post-release-distribution-P06-S33]]'
  - '[[2026-07-17-post-release-distribution-P06-S34]]'
  - '[[2026-07-17-post-release-distribution-P06-S35]]'
  - '[[2026-07-17-post-release-distribution-audit]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
  - '[[2026-07-19-post-release-distribution-adr]]'
  - '[[2026-07-19-post-release-distribution-reference]]'
  - '[[2026-07-21-post-release-distribution-v0-2-1-publication-audit]]'
  - '[[2026-07-24-post-release-distribution-operator-action-list-reference]]'
  - '[[2026-07-25-post-release-distribution-close-honesty-review-audit]]'
---

# `post-release-distribution` feature index

Auto-generated index of all documents tagged with `#post-release-distribution`.

## Documents

### adr

- `2026-07-19-post-release-distribution-adr` - `post-release-distribution` adr: `post-release distribution defers the external-access tail of the parent distribution ADRs` | (**status:** `accepted`)

### audit

- `2026-07-17-post-release-distribution-audit` - `post-release-distribution` audit: `distribution post-release deferral split`
- `2026-07-21-post-release-distribution-v0-2-1-publication-audit` - `post-release-distribution` audit: `v0.2.1 publication record and outstanding fast-follow`
- `2026-07-25-post-release-distribution-close-honesty-review-audit` - `post-release-distribution` audit: `close honesty review`

### exec

- `2026-07-17-post-release-distribution-P01-S04` - RESOLVED by accepted ADR 2026-07-18-mcpb-signing-publisher-adr, the MCPB ships unsigned by operator decision (no purchased certificate), integrity channel is the published SHA-256 plus in-bundle cohort digest pins already enforced by the bootstrap, no signing identity to bind
- `2026-07-17-post-release-distribution-P02-S05` - DONE, Linux Python row green in push-to-main Cadrumo Packaging Smoke run 29657832151 at commit 1abbc48c72 (cohort build, installed grounded tax oracle DP200014:00562 = 23000.00, installed-oracles attestation suite), first fully green three-OS matrix
- `2026-07-17-post-release-distribution-P02-S06` - DONE, Windows Python row green in the same run 29657832151 (fourth consecutive green Windows leg)
- `2026-07-17-post-release-distribution-P02-S07` - DONE, macOS Python row green in run 29657832151 after root-causing the deterministic per-binary Keychain hang via the worker-stack capture (custody file-backend pin b5e6780fb1, product follow-up issue 615)
- `2026-07-17-post-release-distribution-P02-S09` - DONE via local subscription-authed Claude Code 2.1.214 per operator ruling (no CI API key), evidence var/distribution-install-readiness/s27-plugin-68a8433c/run-20260718T164855Z/plugin-evidence.json against cohort 68a8433c at commit 02b3656095, marketplace install with byte-verified three-wheel cohort, real client session connected and called cadrumo_harness_load (status passed), protocol oracle on the same install returned DP200014:00562 = 23000.00 via modelo-200-cuota-integra with the sole permitted plazo-vencido notice
- `2026-07-17-post-release-distribution-P05-S26` - UNBLOCKED by operator GO 2026-07-18 and DONE, harness-identity migration landed as the distribution-harness-identity campaign (12/12 steps, exec records under .vault/exec/2026-07-18-distribution-harness-identity), verify_distribution_identity exits 0 with report.ok true (evidence var/distribution-install-readiness/s11-migration-identity-bilingual), distribution S67 and S68 closed
- `2026-07-17-post-release-distribution-P02-S08` - DONE, Homebrew Linux x86-64 row green in Cadrumo Homebrew Acquisition run 29895959334 at commit 1af8f4fb13, sanctioned homebrew-linux-x86-64 distribution-evidence row minted against release cohort bfe3df0bae (version 0.2.1, source commit 1c9c523d7c) with the installed CLI oracle and the installed MCP oracle both computing DP200014:00562 = 23000.00 via modelo-200-cuota-integra from the brew Cellar keg, the second Linux row homebrew-linux-arm64 stays red and is tracked under P01.S03
- `2026-07-17-post-release-distribution-P06-S27` - Supersede the topology ADR through the pipeline rather than the in-place rewrite already landed, the superseding record must answer the two deleted objections, sibling-serving answered by the shared repo and no-precedent answered by verda-cloud/homebrew-tap carrying Formula and bucket together, and must reconcile the scoop-runner-topology ADR explicitly as unaffected because it rules on which runner executes the lane not where manifests live. Ownership is with account-distribution-lead if its account-wide ruling subsumes the cadrumo scope, asked 2026-07-25 and awaiting reply. GATE, vault check all passes and the superseded record carries superseded_by
- `2026-07-17-post-release-distribution-P06-S28` - CORRECTED 2026-07-25. The closure reports declared the TOPOLOGY work complete, which it is and which was reviewed, but did not scope that claim, so they read as a claim over the whole post-release-distribution plan, which is not complete. The plan stands at 12 of 35 with 23 open. Of those 23, seven are operator-gated, three need a host or runner the worktree does not have, nine chain to the operator-held publish at P03.S13, and four are agent work, the honesty-review rows in this phase. The remainder is therefore overwhelmingly operator-blocked rather than incomplete engineering, and no closure claim may be made over the plan until those close or are formally deferred. GATE, this correction is recorded and vault plan status is the ratio any future claim must cite
- `2026-07-17-post-release-distribution-P06-S29` - Re-audit the six step annotations the review flagged, three claim partial unblocking where only a redundant clause was struck and three moved their blocker from private to nonexistent, restate each as the blocker it actually carries today. GATE, every P01 and P03 row names a blocker that is true at the time of reading
- `2026-07-17-post-release-distribution-P06-S30` - DONE 2026-07-25. Swept the plan rows naming retired distribution variables against the live variable set, which is exactly HOMEBREW_TAP_REPO and CLAUDE_MARKETPLACE_REPO. P04.S23 named the retired CADRUMO_MARKETPLACE_REPO and now names the live one. P03.S13 additionally asserted that the scoop, homebrew and marketplace variables and tokens are all set, which is false, Scoop needs neither and the two renamed secrets do not exist yet because secrets cannot be renamed, so that row now names the two missing secrets as a remaining operator precondition. GATE, no plan row outside this one names a variable absent from the live repository variable set
- `2026-07-17-post-release-distribution-P06-S31` - DONE 7d20b2d984, the docs-claims gate now measures, a positive control asserts every pattern against a must-match and a must-not-match string and a guard requires a new pattern to arrive with its own cases, the retired tap pattern fails 2 of 4 control cases so the control discriminates. GATE, uv run --no-sync pytest dev/docs/tests/test_distribution_claims.py collects 12 and passes
- `2026-07-17-post-release-distribution-P06-S32` - DONE 7d20b2d984, the three tap-pattern over-broadenings are closed, scanning moved per line so a cross-newline match cannot form and the regression document genuinely reproduces the whole-file match, the pattern re-anchored on the account so a third-party tap is not a claim, and a negation preceding the command marks a disclaimer. GATE, the positive control carries all three strings as must-not-match cases
- `2026-07-17-post-release-distribution-P06-S33` - DONE 7d20b2d984, marketplace publish is atomic, the whole cohort validates before any mutation so a refusal leaves the tree byte-identical, and the multi-plugin case that was entirely uncovered now has both a refusal test and a success test. GATE, the pre-fix loop leaves a torn tree so the atomicity test discriminates
- `2026-07-17-post-release-distribution-P06-S34` - DONE 7d20b2d984, plugin-name collision refuses instead of silently overwriting, index entries carry published_by and a cohort declaring a name another product published is refused, while an unattributed entry stays claimable so the first release adopting it is not deadlocked. GATE, the sibling tree and its attribution both survive a refused takeover
- `2026-07-17-post-release-distribution-P06-S35` - DONE 7d20b2d984, concurrent publication is closed rather than only recorded, the marketplace push re-clones and re-applies on a rejected push because concurrency groups are per-repository and cannot serialise across product repos, and refuses after three lost races. GATE, a workflow conformance test pins the retry, the re-clone inside the loop, and the fail-closed exhaustion
- `2026-07-17-post-release-distribution-P01-S03` - RESOLVED 2026-07-28, run 30391339584 at commit 0b4fba14f9 is green across all five jobs including homebrew-linux-arm64, the SIGILL toolchain defect no longer reproduces, evidence lives as a per-run GitHub draft per the aggregation gap named in the plan Description, no further blocker on this row

### plan

- `2026-07-17-post-release-distribution-plan` - `post-release-distribution` plan

### reference

- `2026-07-19-post-release-distribution-reference` - Cadrumo release & orchestration pipeline — holistic review
- `2026-07-24-post-release-distribution-operator-action-list-reference` - `post-release-distribution` reference: `Operator action list for the 19 externally-blocked steps`
