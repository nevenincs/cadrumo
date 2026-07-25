---
tags:
  - '#reference'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-25-shared-distribution-repository-adr]]"
  - "[[2026-07-25-account-distribution-standard-plan]]"
---

# `account-distribution-standard` reference: `Migration instructions for vaultspec-dashboard`

Reviewed migration instructions for the dashboard, reconciling its existing
in-repository bucket and its pending community-Windows publish against the
shared-repository ruling. Nothing here has been applied: the product lives in a
repository this worktree must not push to. Every fact was read from the live
repository through structured API queries on 2026-07-25 and is attributed to what
it was read from, because the code index was degraded throughout and no conclusion
here rests on a semantic-search result.

**This document opens with a defect, because it is user-facing and live.**

## Summary

### Blocking defect: the committed bucket manifest is unusable

`vaultspec-dashboard` commits `bucket/vaultspec.json`. As read, it is broken in
three independent ways, any one of which makes an install fail:

1. **The digest is a placeholder.** The `hash` field is sixty-four zeros. A bucket
   manifest pins a version and a digest, so a placeholder digest is a claim a user
   can act on and fail against — Scoop downloads, verifies, and refuses.
2. **The pinned asset does not exist.** The manifest names
   `vaultspec-0.1.2-x86_64-pc-windows-msvc.zip` under release `v0.1.2`. The assets
   actually attached to `v0.1.2` are named `vaultspec-cli-x86_64-pc-windows-msvc.zip`
   and siblings — no asset carries the version in its filename. The URL therefore
   404s before the digest is ever checked.
3. **The pinned version is stale, and the current release is empty.** The manifest
   pins `0.1.2` while the newest release is `v0.1.4`, and `v0.1.4` carries **zero**
   assets. So there is no newer asset to point at either.

The practical consequence: a user who adds this bucket and installs gets a failed
download, not a working tool. **Fix or withdraw this manifest before anything else
in this document.** Withdrawing is legitimate — an unclaimed channel blocks
nothing under the account standard, and a broken claim is strictly worse than an
absent one.

### What the derived matrix says this product ships

The dashboard is a served interface rather than an imported library, and its
bucket manifest confirms it exposes a shimmed `vaultspec` command on PATH. Its
users are not assumed to be developers holding the toolchain. Evaluating the rule:

- `exposes_user_invoked_command = true`
- `assumes_language_toolchain = false`
- `extends_host_application = false`

Selected tiers: **registry**, **standalone-executable**, and the three managed
installers — **shared-tap**, **shared-bucket**, **community-windows**. This is the
full set, and it is why the dashboard's bucket **does** migrate into the shared
repository where `vaultspec-core`'s is retired: the two products differ on exactly
one property, the toolchain assumption, and that one property is what the managed
installers answer.

### Current state, as read

Public repository carrying `.release-please-manifest.json`, `pyproject.toml`, and
`bucket/`. Workflows: `product-release.yml`, `channel-publish-gate.yml`,
`release-please.yml`, `quality-gates.yml`, `engine-ci.yml`, `a2a-product-contract.yml`,
`a2a-channel-feasibility.yml`, `ci-runner-probe.yml`.

`product-release.yml` builds per-target archives named
`vaultspec-<version>-<target>` with a sibling `.sha256`, resolves the release
version, and drives a phase-zero gate over the channels `scoop winget` before
publication. So the community-Windows channel is already modelled here, not
hypothetical — which makes the naming correction below urgent rather than
speculative.

### The naming correction, and why it is the priority

The committed bucket manifest is `bucket/vaultspec.json` — the **unqualified
family name**, not the product's own name. The sibling `vaultspec-core` correctly
uses `bucket/vaultspec-core.json`. Under the account naming rule every user-facing
identifier derives from the product name, qualified by the account as publisher
where the ecosystem requires it, and no unqualified family name is ever claimed.

This matters beyond tidiness because the same unqualified name has already been
submitted to the community Windows package repository under the account's
publisher namespace. A published identifier cannot be renamed in place, so that
correction is forward-only and strands the released version permanently. Every
further release under the unqualified name adds one more stranded version. **Stop
claiming the unqualified name before the next release, not after.**

A caution on that correction: `vaultspec-core` and `vaultspec-dashboard` are both
plausible referents for a bare `vaultspec` submission, and getting it wrong
poisons the correction. The evidence available from this repository points at the
dashboard — it is the product whose Scoop manifest claims the bare name and whose
shimmed command is literally `vaultspec.exe`, while `vaultspec-core` uses its own
name throughout — but that is corroboration, not proof. Confirm against the
submitted manifest's own installer URL before submitting any correction.

### The instructions, in order

1. **Fix or withdraw the broken manifest** (see the defect section). Nothing below
   is worth doing while a live manifest points at an asset that has never existed.
2. **Rename the manifest to the product's own name** and stop claiming the
   unqualified family name in every channel — bucket, community Windows, and any
   tap formula added later.
3. **Move the manifest into the shared account distribution repository** under
   `bucket/`, and delete the in-repository `bucket/` directory. The shared
   repository already exists for Homebrew's sake, so this creates nothing. Two
   costs disappear with the move: the per-product bucket-add a user would otherwise
   repeat, and the release-time write to this public repository's default branch.
4. **Stage exactly the product's own path in the push.** A sibling product's
   manifest lives beside it in the shared repository, so the push must name its own
   file and must carry no stage-everything form and no wholesale delete of the
   checkout. Cadrumo pins this with a conformance gate over the parsed workflow
   that is proven to reject the pre-change shape; port the gate, not just the
   intent.
5. **Preserve the backward-bump guard — it is this product's contribution to the
   shared mechanism.** The dashboard reinvented it independently of
   `vaultspec-core`, and a guard two teams reinvent belongs to the mechanism rather
   than to either product. Cadrumo's ported version
   (`dev/packaging/release_pointer_guard.py`) is the tested form: it handles both
   the Scoop JSON and Homebrew formula shapes, compares numerically so `0.2.10`
   beats `0.2.9`, and refuses an unreadable pointer instead of treating it as
   absent — the failure mode that would silently disable the guard exactly when
   repository state is unexpected. Take that module; do not port only the shell.
6. **Add the shared tap formula.** The rule selects the Homebrew tier for this
   product and the account's tap already exists, so this is one more formula file.
7. **Derive the required evidence rows from the claimed channels.** With five tiers
   selected, this product has the most to gain from proportional evidence: it can
   claim and prove the registry first, then add each further channel as its own
   proof passes, instead of blocking the first release on five channels at once.

### What is unverified from here

- Whether `product-release.yml` declares a tag trigger. Its trigger block was not
  read in full, so the dead-trigger defect is neither confirmed nor excluded here.
  Check before assuming either.
- Whether the `channel-publish-gate.yml` phase-zero gate currently passes or is
  itself blocked on the broken manifest.
- Whether any user has added the in-repository bucket. Given that installing from
  it cannot have succeeded, the migration cost is probably nil, but that is an
  inference from the defect, not a measurement.

### Resolved: the community-Windows submission is this product

The ambiguity flagged above was settled by reading the submitted manifests
directly on 2026-07-25. It is **vaultspec-dashboard**, decisively, and the
evidence converges on four independent fields of the published manifest:

- `InstallerUrl` names
  `nevenincs/vaultspec-dashboard/releases/download/v0.1.0/vaultspec-cli-x86_64-pc-windows-msvc.zip`
- `PackageUrl` names the `vaultspec-dashboard` repository
- `PublisherSupportUrl` names that repository's issue tracker
- `ShortDescription` reads "Unified dashboard UI for the vaultspec ecosystem"

Corroborated independently: the `v0.1.0` release of `vaultspec-dashboard` really
does carry an asset named exactly `vaultspec-cli-x86_64-pc-windows-msvc.zip`, so
the installer URL resolves rather than merely being plausible. `vaultspec-core` is
excluded: its assets are all named `vaultspec-core-*` and no submitted field
references it.

**The defect is narrower than the plan wording suggests, and that changes the
correction.** The published identifier is `nevenincs.vaultspec`. Its *publisher*
half is already correctly account-qualified; what is wrong is the *package-name*
half, which carries the family name `vaultspec` rather than this product's own
name. `PackageName` is likewise `vaultspec`. So the correction is not to add
account qualification — that is present — but to replace the family name with the
product name, giving `nevenincs.vaultspec-dashboard`.

One published version exists, `0.1.0`, and it is the only identifier in the
account's publisher namespace. Unlike the Scoop manifest, this submission is
technically sound: its `InstallerSha256` is a real digest and its URL resolves. It
is a *naming* defect only, which is why the correction is forward-only — submit
subsequent versions under `nevenincs.vaultspec-dashboard` and leave `0.1.0`
orphaned under the family name, since a published identifier cannot be renamed in
place. Each further release under the family name adds one more stranded version,
which is why this precedes the next release rather than following it.

Submitting the correction is an outward-facing action against a repository the
account does not own. It is an operator action and is not performed here.
