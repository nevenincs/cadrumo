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

# `account-distribution-standard` reference: `Migration instructions for vaultspec-core and vaultspec-rag`

Reviewed migration instructions for the two developer CLIs. Nothing here has been
applied: both products live in repositories this worktree must not push to, so
each adopts these under its own review. Every fact below was read from the live
repositories through structured API queries on 2026-07-25 and is stated with what
it was read from, because the code index was degraded throughout (serving roughly
a fifth of the tree while reporting itself healthy) and no conclusion here rests
on a semantic-search result.

## Summary

### What the derived matrix says these two products ship

Both are developer CLIs: each exposes a command a user invokes, and each user can
be assumed to hold the language toolchain, because the tools exist to be used
while developing. Neither extends a host application. Evaluating the rule gives:

- `exposes_user_invoked_command = true`
- `assumes_language_toolchain = true`
- `extends_host_application = false`

Selected tiers: **registry** (the floor) and **standalone-executable**. The
managed installers — shared tap, shared bucket, community Windows — are **not
selected**, because they exist to remove a toolchain prerequisite these users do
not have.

This is the rule evaluated, not a per-product exception, and it produces one
consequential result that is easy to get backwards: `vaultspec-core`'s existing
in-repository Scoop bucket is **out of the derived set entirely**. It is retired,
**not migrated into the shared repository**. Migrating it would move a channel the
rule does not select into the account's shared surface and teach the next
developer CLI to do the same.

### Current state, as read

**vaultspec-core** (public). Carries `.release-please-manifest.json`,
`pyproject.toml`, and an in-repository `bucket/` holding
`bucket/vaultspec-core.json`. Workflows: `binaries.yml`, `publish.yml`,
`release-please.yml`, `ci.yml`, `bootstrap-branch.yml`, `add-to-project.yml`.
Both `publish.yml` and `binaries.yml` are `workflow_dispatch`-only — neither
declares a tag trigger, so the dead-trigger defect does **not** apply here.

Its committed bucket manifest is an explicitly-labelled placeholder skeleton: its
own `"##"` comment block states that version, url, and hash are rewritten by the
`scoop-bump` step in `binaries.yml` once a release publishes Windows assets, and
that the hash field is deliberately absent because the assets did not exist when
it was committed. It currently pins `0.1.51` and names the two Windows executables
from that release.

Release assets are real but recent: `vaultspec-core-v0.1.50` and
`vaultspec-core-v0.1.51` each carry four `vaultspec-core-*` platform binaries,
four `vaultspec-mcp-*` binaries, and `SHA256SUMS`. Every earlier release back
through `v0.1.40` carries **zero** assets. So the standalone-executable tier is
already satisfied for the two most recent versions and unsatisfied historically.

**vaultspec-rag** (public). Carries `.release-please-manifest.json` and
`pyproject.toml`, and **no** `bucket/` directory. Workflows: `publish.yml`,
`release-please.yml`, `ci.yml`, `claude.yml`, `bootstrap-branch.yml`. It ships to
the registry today and has no standalone executables, so it is the product with
the most straightforward gap: it needs the executable tier and nothing else.

### The instructions

**Both products.**

1. Add the `[matrix]` block to a channel descriptor with the three booleans above,
   so the channel set is derived rather than asserted. Declare
   `pending_tiers = ["standalone-executable"]` for `vaultspec-rag` until its
   executables ship, so the gap is declared data rather than a silent absence.
2. Declare each channel's `evidence_rows` in the same descriptor, and derive the
   required evidence set from the channels the release actually claims. The
   registry rows are the floor and are always required, so the set can never
   collapse to nothing.
3. Confirm no publication workflow declares a tag trigger. Verified absent in both
   products as of this reading; the check is cheap and the failure mode — an inert
   trigger that reads as a second automatic publication path — is expensive.

**vaultspec-core specifically.**

4. **Retire `bucket/` and its `scoop-bump` step.** The rule does not select the
   shared-bucket tier for this product. Delete the in-repository bucket directory,
   remove the manifest-rewrite-and-commit step from `binaries.yml`, and drop the
   `contents: write` the step needs on `main`. This also removes the last
   release-time write to this product's own default branch.
5. **Preserve the backward-bump guard as a reusable component, not as dead code.**
   `binaries.yml` carries the guard as a shell idiom — it reads the manifest's
   current version, compares with `sort -V`, and refuses when the current version
   sorts last. That logic is correct and was independently reinvented in
   `vaultspec-dashboard`, which is what earned it a place in the shared mechanism.
   It is ported to a tested Python module in cadrumo
   (`dev/packaging/release_pointer_guard.py`), covering both the Scoop JSON and
   Homebrew formula pointer shapes, refusing an unreadable pointer rather than
   reading it as absent, and comparing numerically so `0.2.10` is correctly newer
   than `0.2.9`. If `vaultspec-core` ever regains a committed release pointer, take
   that module rather than re-deriving the shell.
6. **Backfill or accept the asset gap.** Releases before `v0.1.50` carry no assets.
   Under the derived matrix the standalone-executable tier is claimed, so either
   the historical gap is accepted explicitly (the channel is claimed only from
   `v0.1.50` forward) or the older releases are left unclaimed. Do not document the
   executable channel as available for versions whose assets do not exist.

**vaultspec-rag specifically.**

7. **Add the standalone-executable tier.** It ships to the registry alone today.
   The rule selects executables because it exposes a user-invoked command, and
   `vaultspec-core`'s `binaries.yml` is the working template — a dispatched build
   per platform, assets plus `SHA256SUMS` attached to the release. Until they ship,
   declare the tier in `pending_tiers`.
8. **Do not add a bucket or a tap.** The rule does not select them. If the audience
   assumption ever changes — if `vaultspec-rag` acquires non-developer users — the
   change is to flip `assumes_language_toolchain` in one descriptor and let the
   matrix re-derive, not to add a channel by hand.

### What is unverified from here

- Whether either product's registry publication uses workload identity federation
  or a stored credential. Not readable without inspecting each `publish.yml` in
  full and the registry-side publisher configuration, which is account state the
  tree cannot evidence.
- Whether `vaultspec-core`'s `scoop-bump` step has ever actually run to completion
  against a real release. The committed manifest still carries its placeholder
  comment block while pinning `0.1.51`, which is consistent with both a successful
  version rewrite and a partial one; deciding it needs that workflow's run history.
- Whether any user has added `vaultspec-core`'s in-repository bucket. If some have,
  retiring it breaks their `scoop update`, which is a migration cost this document
  cannot size from public data.
