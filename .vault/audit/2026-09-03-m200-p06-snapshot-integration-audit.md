---
tags:
  - '#audit'
  - '#m200-p06-snapshot-integration'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:2eb82e7e18b90e7d6f5bb1fde4c7a437a5aa3b47058b5513e2b83cce2befe1e5'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace m200-p06-snapshot-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `m200-p06-snapshot-integration` audit: `reviewed promotion snapshot integration`

## Scope

Read-only independent review of the Modelo 200/2024 reviewed-promotion snapshot, the S13 and S14/S15 authority compilers, the blocker worklist, source-rebind reconciliation and recovery paths, and their focused tests. The review considered invocation-local caching and fail-closed source, label, legal, semantic-map, and canonical-byte protections. No production code or tests were changed.

## Findings

### forged-snapshot-authority | high | caller-supplied promotion snapshots bypass compiler receipt replay

`verified_promoted_candidate_ids` accepts an arbitrary public `M200ReviewedPromotionSnapshot`, takes its IDs directly, and calls only the three canonical-byte render comparisons. It does not invoke the cohorts' `promoted_candidate_ids` methods, which are the methods that recompile and equality-check each source, label, legal, map, reviewer, and receipt authority. `reconcile_bundled_m200_2024` and `build_m200_source_rebind_plan` both accept and forward that snapshot. Consequently a hand-constructed snapshot with matching rendered declarations can bypass fresh evidence compilation at the reconciliation and planning boundaries. The focused snapshot test verifies call count and byte checks but has no forged-snapshot refusal detector.

### standalone-blocker-s12-byte-closure | medium | direct blocker compilation trusts S12 membership without its declaration bytes

`compile_m200_2024_blocker_authority` uses the S12 compiler only to compare its four IDs while settling the S12/S13/S14/S15 partition. Neither that standalone compile path nor blocker `promoted_candidate_ids` verifies S12 canonical declaration bytes. The integrated promotion union does verify all three cohorts, so the reconciliation, apply, and recovery route is protected. A direct S14/S15 authority caller, however, can receive a successful blocker receipt while a settled S12 declaration is stale or hand-authored. The blocker tests prove blocker-byte drift, but not S12-byte drift through the direct blocker API.

### cli-apply-snapshot-replay | medium | the apply CLI does not retain one invocation-owned evidence snapshot

`main` first calls `reconcile_bundled_m200_2024` without a snapshot and, for `--apply-source-rebinds`, then calls `build_m200_source_rebind_plan` without one. Each boundary independently builds the costly promotion evidence; apply later rechecks current-design bytes again during preflight. This defeats the explicit one-invocation cache contract and permits evidence state to differ between census and plan. `build_bundled_m200_source_rebind_plan` correctly carries one snapshot, but the public CLI route does not, and no CLI test asserts single snapshot construction.

## Recommendations

- For `forged-snapshot-authority`, make the cache capability private or attest the supplied snapshot by replaying every cohort's `promoted_candidate_ids` equality check before its IDs can authorize a collision. Add a forged-snapshot detector at reconciliation and source-rebind planning boundaries.
- For `standalone-blocker-s12-byte-closure`, have the direct blocker route verify the S12 canonical receipt, while preserving the union's single compilation through an explicitly verified invocation capability. Add an S12-byte mutation test through blocker `promoted_candidate_ids`.
- For `cli-apply-snapshot-replay`, construct one reviewed-promotion snapshot in the CLI invocation and pass it to census and plan construction. Add a focused CLI-boundary call-count detector.
