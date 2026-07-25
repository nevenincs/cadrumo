---
tags:
  - '#plan'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-25-account-distribution-standard-adr]]'
  - '[[2026-07-25-distribution-repo-topology-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
  - '[[2026-07-25-account-distribution-standard-research]]'
---
# `account-distribution-standard` plan

- [ ] `S01` - Create the single shared public distribution repository holding Formula for Homebrew and bucket for Scoop, named so Homebrew reaches it as an account tap, OPERATOR-GATED because repository creation is outward-facing and was deliberately left undone; `operator action, gh repo create nevenincs/homebrew-tap --public`.
- [ ] `S02` - Land the cadrumo formula and bucket manifest in the shared repository once it exists, proving a product is one formula file plus one manifest file and creates nothing, blocked on the repository above; `.github/workflows/publish-release.yml, dev/packaging/`.
- [ ] `S03` - Derive each product channel set from the two ADR properties, whether the artifact exposes a user-invoked command and whether that user holds the language toolchain, and record the resulting matrix as data rather than a per-product list; `docs/_data/download_channels.toml`.
- [ ] `S04` - Make the required evidence row set derive from the channels a release actually claims rather than a fixed list spanning every channel, so an unclaimed channel no longer blocks a claimed one, weakening no gate and removing no row; `dev/packaging/evidence.py, dev/packaging/release_cohort.py`.
- [ ] `S05` - Remove the declared tag trigger the dispatch path masks, because a tag created by a workflow token does not fire tag-triggered workflows and a dead trigger is misleading weight; `.github/workflows/publish-release.yml`.
- [ ] `S06` - Carry the monotonic backward-bump guard on every committed release-pointer manifest, because ordinary merge semantics can otherwise un-publish a newer version with no workflow failing, porting the guard vaultspec-dashboard scoop-bump already proves; `dev/packaging/, .github/workflows/`.
- [ ] `S07` - Correct the unqualified winget submission forward by submitting subsequent versions under the account-qualified publisher identifier and leaving the released version orphaned, since a published identifier cannot be renamed in place; `operator action, microsoft/winget-pkgs submission`.
- [ ] `S08` - Write the day-one checklist a new product follows into contributor documentation, covering release-please configuration and manifest, the two workflows, the channel-set evaluation, the two shared-repository files, and workload identity federation registration; `docs/`.
- [ ] `S09` - Produce reviewed migration instructions for vaultspec-core and vaultspec-rag, which ship to the registry today and gain executables under the derived matrix, without pushing to those repositories from this worktree; `.vault/reference/, cross-repo instructions only`.
- [ ] `S10` - Produce reviewed migration instructions for vaultspec-dashboard, reconciling its existing in-repo bucket and its pending winget publish against the shared-repository ruling, preserving its hard-won backward-bump guard; `.vault/reference/, cross-repo instructions only`.
- [ ] `S11` - Determine which product the merged unqualified winget submission actually corresponds to, because vaultspec-core and vaultspec-dashboard are both candidates and the manifest name is ambiguous, since getting this wrong poisons the namespace correction above; `microsoft/winget-pkgs manifests/n/nevenincs/vaultspec`.
- [ ] `S12` - Retire the three superseded distribution repositories once a green publication proves the shared repository serves every claimed channel, OPERATOR-GATED because deletion is irreversible; `operator action, cadrumo-dist and scoop-cadrumo and homebrew-cadrumo`.

## Description

## Steps

## Parallelization

## Verification

## Context

Tracks implementation of the accepted account-wide distribution standard. The ADR is accepted and unimplemented: no plan, no exec records existed before this document. Scope spans five products (cadrumo, vaultspec-core, vaultspec-rag, vaultspec-dashboard, vaultspec-a2a); only cadrumo is editable from this worktree, so per-product migration lands as reviewed instructions plus operator-executed steps. Blocked at the head on operator creation of the shared public repository.
