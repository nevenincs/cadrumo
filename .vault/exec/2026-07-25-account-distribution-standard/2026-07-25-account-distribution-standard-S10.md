---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S10'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---

# DONE as reviewed instructions, nothing pushed. Reference authored for vaultspec-dashboard, which the derived matrix places at the full channel set because its users cannot be assumed to hold the toolchain, so its bucket manifest DOES migrate into the shared repository. It opens with a blocking user-facing defect found during the review, the committed bucket/vaultspec.json is unusable three ways over, its hash is sixty-four zeros, the asset its URL names has never existed at that release because the real assets carry no version in their filename, and it pins 0.1.2 while the newest release v0.1.4 carries zero assets, so an install fails at download. The manifest also claims the unqualified family name, matching the winget defect. Its backward-bump guard is preserved as the shared tested module rather than only as intent

## Scope

- `.vault/reference/2026-07-25-account-distribution-standard-vaultspec-dashboard-migration-reference.md`

## Description

- Read the dashboard's layout, workflows, committed bucket manifest, and every release's assets through structured queries.
- Evaluate the derived matrix, which places this product at the full channel set.
- Cross-check the manifest's pinned asset against the assets that actually exist at that release.
- Author the migration reference, leading with the defect because it is live and user-facing.

## Outcome

Reviewed instructions exist, nothing was pushed. The dashboard's bucket manifest DOES migrate into the shared repository, because its users cannot be assumed to hold the toolchain, and that single property is the entire difference from the developer CLIs.

The review surfaced a blocking user-facing defect that was not the object of the step. The committed manifest is unusable three independent ways: its digest is sixty-four zeros, the asset its URL names has never existed at that release because the real assets carry no version in their filenames, and it pins a version two releases behind while the newest release carries no assets at all. An install from that bucket fails at download.

The reference therefore opens with the defect and says plainly that withdrawing the manifest is legitimate, since an unclaimed channel blocks nothing under the standard and a broken claim is strictly worse than an absent one.

## Notes

The defect is exactly the class this campaign was told to avoid creating: a manifest pins a version and a digest, so a placeholder is a claim a user can act on and fail against. Finding one already committed in a sibling product is why the instruction to fix or withdraw it precedes every other instruction in that document.

The manifest also claims the unqualified family name, matching the community-Windows defect, which is what first connected the two and pointed at the referent later confirmed under S11.

The backward-bump guard is preserved as the shared tested module rather than as intent. This product reinvented the guard independently of its sibling, and the reference is explicit that porting only the shell idiom would drop the properties the tested version adds, in particular refusing an unreadable pointer instead of treating it as absent.

Three things could not be verified from public data and are named as unverified: whether the dashboard's release workflow declares a tag trigger, whether its channel gate currently passes, and whether any user has added the broken bucket.
