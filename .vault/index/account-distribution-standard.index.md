---
generated: true
tags:
  - '#index'
  - '#account-distribution-standard'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:960cb2374e1889c4847cd97d12587cb812df5f829b38dde4d0f0d3b8358d5c8e'
related:
  - '[[2026-07-25-account-distribution-standard-adr]]'
  - '[[2026-07-25-account-distribution-standard-plan]]'
  - '[[2026-07-25-account-distribution-standard-research]]'
  - '[[2026-07-25-account-distribution-standard-vaultspec-cli-migration-reference]]'
  - '[[2026-07-25-account-distribution-standard-vaultspec-dashboard-migration-reference]]'
---

# `account-distribution-standard` feature index

Auto-generated index of all documents tagged with `#account-distribution-standard`.

## Documents

### adr

- `2026-07-25-account-distribution-standard-adr` - `account-distribution-standard` adr: `One account distribution standard: one shared channel repository, a derived channel matrix, and evidence proportional to claims` | (**status:** `accepted`)

### exec

- `2026-07-25-account-distribution-standard-S02` - DONE in this tree, BLOCKED externally. The publication authority now lands both the cadrumo formula and the cadrumo bucket manifest in the one shared account repository, each push staging exactly its own product-scoped path, so a second product is one more formula file plus one more manifest file and creates nothing. Proven by a conformance predicate over the parsed workflow with a real negative control, the predicate rejects the pre-change in-repository push on its content and five substantive properties are rejected against the pre-change workflow, so the gate is not vacuous. The files cannot actually land until the operator creates nevenincs/homebrew-tap, which returned 404 on a structured query at 2026-07-25
- `2026-07-25-account-distribution-standard-S03` - DONE. The channel matrix is now derived data rather than a per-product list, the descriptor carries a matrix block holding the three product properties and every channel declares its tier, and derived_tiers evaluates the account rule over them. The descriptor refuses at load when the declared channels disagree with the derived set, in either direction, so neither dropping a channel nor acquiring one the rule excludes can pass unseen. Cadrumo evaluates to registry plus standalone-executable plus the three managed installers plus host-extension, and the two tiers it does not yet ship are declared in pending_tiers so the gap is visible data rather than a silent absence
- `2026-07-25-account-distribution-standard-S04` - DONE. The required evidence set now derives from the channels a release actually claims, computed as the union of those channels' declared evidence rows, floored at the language-native registry so it can never collapse to nothing and leave the readiness gate measuring zero. No gate was weakened and no row was removed, all eleven rows survive as ALL_DISTRIBUTION_ROWS and a channel still cannot be claimed without its passing row, what changed is only that an unclaimed channel no longer blocks a claimed one. The documentation claims gate was deliberately re-anchored on the FULL set rather than the claimed subset, because a documentation claim is itself the act of claiming a channel, and it gained an anti-vacuity test asserting every declared row is reachable by some claim pattern
- `2026-07-25-account-distribution-standard-S05` - DONE, with a finding. No cadrumo workflow declares a tag trigger, verified by parsing the trigger block of all fourteen workflow files rather than grepping them, so there was nothing to remove here and this step closes as already-conformant rather than as work performed. Converted into a regression gate so it stays true, publication must be dispatch-only and a tag filter on the publication authority now fails the suite. The defect this step was written for lives in the sibling products, and the removal instruction is carried in their migration references
- `2026-07-25-account-distribution-standard-S06` - DONE. Both committed release pointers, the bucket manifest and the tap formula, are guarded against a backward bump before the push commits, because ordinary merge semantics can otherwise resurrect an older pointer and un-publish a newer version with no workflow failing. Ported from the sort -V shell idiom that vaultspec-core and vaultspec-dashboard each reinvented independently, into a tested module handling both pointer shapes, reading the formula version from its release-asset URL since the generated formula carries no version stanza, comparing numerically so 0.2.10 correctly beats 0.2.9, and refusing an unreadable pointer rather than treating it as absent, which is the failure mode that would silently disable the guard exactly when repository state is unexpected. Twenty-nine real-behaviour tests over real files, and the workflow gate pins that the guard reads the clone before the copy, since checking after would compare the file with itself
- `2026-07-25-account-distribution-standard-S08` - DONE. The day-one checklist a new product follows is written as a numbered sequence covering the version authority, the two workflows and the no-tag-trigger requirement, the three-property channel-set evaluation, the two shared-repository files, workload identity federation, and the name-derivation rule. Placed in RELEASING.md rather than under docs/ deliberately, on two grounds, it is maintainer rather than taxpayer-facing documentation and docs/ is the taxpayer surface, and the fail-closed documentation claims gate scans docs/ for acquisition claims so a checklist quoting install commands there would correctly red the gate
- `2026-07-25-account-distribution-standard-S09` - DONE as reviewed instructions, nothing pushed to either repository. Reference authored covering both developer CLIs, grounded in structured API reads of the live repositories on 2026-07-25 and attributing every fact to what it was read from. The consequential finding is that the derived matrix does NOT select the managed installers for these two, because their users can be assumed to hold the toolchain, so vaultspec-core's existing in-repository bucket is RETIRED rather than migrated into the shared repository, which is the opposite of the dashboard instruction and easy to get backwards. vaultspec-rag needs only the standalone-executable tier it currently lacks. Neither product declares a tag trigger, verified
- `2026-07-25-account-distribution-standard-S10` - DONE as reviewed instructions, nothing pushed. Reference authored for vaultspec-dashboard, which the derived matrix places at the full channel set because its users cannot be assumed to hold the toolchain, so its bucket manifest DOES migrate into the shared repository. It opens with a blocking user-facing defect found during the review, the committed bucket/vaultspec.json is unusable three ways over, its hash is sixty-four zeros, the asset its URL names has never existed at that release because the real assets carry no version in their filename, and it pins 0.1.2 while the newest release v0.1.4 carries zero assets, so an install fails at download. The manifest also claims the unqualified family name, matching the winget defect. Its backward-bump guard is preserved as the shared tested module rather than only as intent
- `2026-07-25-account-distribution-standard-S11` - DONE 2026-07-25, the merged community-Windows submission is vaultspec-dashboard, decided by reading the published manifests directly rather than inferring from the ambiguous name. Four independent fields converge, InstallerUrl names nevenincs/vaultspec-dashboard releases download v0.1.0 vaultspec-cli-x86_64-pc-windows-msvc.zip, PackageUrl names that repository, PublisherSupportUrl names its issue tracker, and ShortDescription reads Unified dashboard UI for the vaultspec ecosystem. Corroborated because that release really does carry an asset of exactly that name, and vaultspec-core is excluded because its assets are all named vaultspec-core and no field references it. One version 0.1.0 is published and it is the only identifier in the namespace. IMPORTANT REFINEMENT, the defect is narrower than this plan assumed, the identifier nevenincs.vaultspec is already publisher-qualified and it is the package-name half carrying the family name that is wrong, so the correction replaces the family name with the product name rather than adding qualification

### plan

- `2026-07-25-account-distribution-standard-plan` - `account-distribution-standard` plan

### reference

- `2026-07-25-account-distribution-standard-vaultspec-cli-migration-reference` - `account-distribution-standard` reference: `Migration instructions for vaultspec-core and vaultspec-rag`
- `2026-07-25-account-distribution-standard-vaultspec-dashboard-migration-reference` - `account-distribution-standard` reference: `Migration instructions for vaultspec-dashboard`

### research

- `2026-07-25-account-distribution-standard-research` - `account-distribution-standard` research: `What each nevenincs product actually publishes, measured against what its workflows claim`
