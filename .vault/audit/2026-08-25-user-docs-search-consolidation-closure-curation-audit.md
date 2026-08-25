---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7943c9e03311b444f72f4de20785fe3f005c6e5fd205f723705419ecb5b5d081'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-07-27-canonical-release-pipeline-adr]]"
  - "[[2026-08-02-release-pipeline-full-automation-adr]]"
---

# `user-docs-search-consolidation` audit: `Retire non-executable deployment rows and close the implementation plan`

## Scope

Fresh curation of the August 1 implementation plan's only two open rows against the accepted search and release decisions, the current publisher, the release workflow, the built-site behavioral gates, both historical execution records, and the August 13 split-closure audit. Semantic discovery covered both vault and code; exact-symbol inspection confirmed the owning implementation sites.

## Findings

### non-executable-deploy-rows | medium | two operational observations were stranded as permanent implementation steps

`P04.S13` asked this implementation plan to perform an operator-authorized deployment. The capability is already delivered: the publisher validates before upload, uploads, invalidates, verifies every public destination, and compares every served Pagefind entry with the built artifact. The release workflow is the operational trigger and the canonical release decisions own its remaining deploy-role provisioning. A one-time deployment is external state, not missing implementation.

`P03.S40` decomposed the same operation into a manual deployed-root query replay. Built multilingual recall is already enforced by the behavioral gates, while post-publish reachability and artifact identity are enforced by the publisher. Replaying queries against one deployment would produce dated operational evidence, not another product capability.

Both identifiers were retired rather than checked. Their execution records were archived intact, preserving the 2026-08-13 stale-root and HTTP 404 observations as historical findings without pretending the operation ran.

### stale-plan-prose | medium | completion criteria still described retired architecture and manual deployment work

The plan still required an int8 Rung-2 matrix after the accepted ruling retired that experiment, and still made manual live probes a campaign completion condition. Its structural rows and verification prose were reconciled to the shipped lexical boundary, built-site behavioral contract, and release-owned post-publish verification without restating the release decisions.

### redeclaration-check | none | operational and implementation authority remain single-homed

Semantic and exact-symbol discovery found no second product action or schema authority. Search behavior remains owned by the docs tests and controller; delivery verification remains owned by the publisher; release timing and credentials remain owned by the release workflow and canonical release decisions.

## Recommendations

- Treat a future successful deployment as release evidence, not as a reason to reopen this implementation plan.
- Keep OP-3 provisioning in the canonical release corpus and workflow; do not copy it back into feature plans.
- Archive the completed feature only after the archive preview confirms every incoming cross-feature reference remains valid or is deliberately retained.
