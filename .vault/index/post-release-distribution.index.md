---
generated: true
tags:
  - '#index'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - '[[2026-07-17-post-release-distribution-P01-S04]]'
  - '[[2026-07-17-post-release-distribution-P02-S05]]'
  - '[[2026-07-17-post-release-distribution-P02-S06]]'
  - '[[2026-07-17-post-release-distribution-P02-S07]]'
  - '[[2026-07-17-post-release-distribution-P02-S08]]'
  - '[[2026-07-17-post-release-distribution-P02-S09]]'
  - '[[2026-07-17-post-release-distribution-P05-S26]]'
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

### plan

- `2026-07-17-post-release-distribution-plan` - `post-release-distribution` plan

### reference

- `2026-07-19-post-release-distribution-reference` - Cadrumo release & orchestration pipeline — holistic review
- `2026-07-24-post-release-distribution-operator-action-list-reference` - `post-release-distribution` reference: `Operator action list for the 19 externally-blocked steps`
