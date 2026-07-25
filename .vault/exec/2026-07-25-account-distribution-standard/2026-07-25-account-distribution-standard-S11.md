---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S11'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE 2026-07-25, the merged community-Windows submission is vaultspec-dashboard, decided by reading the published manifests directly rather than inferring from the ambiguous name. Four independent fields converge, InstallerUrl names nevenincs/vaultspec-dashboard releases download v0.1.0 vaultspec-cli-x86_64-pc-windows-msvc.zip, PackageUrl names that repository, PublisherSupportUrl names its issue tracker, and ShortDescription reads Unified dashboard UI for the vaultspec ecosystem. Corroborated because that release really does carry an asset of exactly that name, and vaultspec-core is excluded because its assets are all named vaultspec-core and no field references it. One version 0.1.0 is published and it is the only identifier in the namespace. IMPORTANT REFINEMENT, the defect is narrower than this plan assumed, the identifier nevenincs.vaultspec is already publisher-qualified and it is the package-name half carrying the family name that is wrong, so the correction replaces the family name with the product name rather than adding qualification

## Scope

- `microsoft/winget-pkgs manifests/n/nevenincs/vaultspec`

## Description

- List the account's publisher namespace in the community Windows package repository.
- Read all three submitted manifests for the single published version.
- Cross-check the installer URL against the assets that actually exist at the named release.
- Compare against both candidate products' asset naming.

## Outcome

The referent is `vaultspec-dashboard`, decisively. Four independent fields of the submitted manifests converge on it: the installer URL names that repository's release asset, the package URL names the repository, the support URL names its issue tracker, and the short description reads as the dashboard's.

Corroborated rather than merely plausible: the named release really does carry an asset of exactly that filename. `vaultspec-core` is excluded because its assets are uniformly prefixed with its own name and no submitted field references it.

One version is published, and it is the only identifier in the namespace.

## Notes

The step's framing turned out to be slightly wrong, and correcting it changes what the follow-on correction actually is. The plan described the submission as unqualified and the fix as submitting under an account-qualified identifier. The published identifier is already publisher-qualified; what carries the family name is the package-name half. So the correction replaces the family name with the product name rather than adding qualification, and the follow-on step was restated accordingly.

This submission is technically sound, unlike the same product's Scoop manifest: its digest is real and its URL resolves. It is a naming defect only, which is why the correction is forward-only and why it is worth sequencing before the next release rather than after.

The question was initially delegated to a subagent, which did not return findings before the queries above settled it directly. The answer here rests on the manifests read in this session, not on that delegation.
