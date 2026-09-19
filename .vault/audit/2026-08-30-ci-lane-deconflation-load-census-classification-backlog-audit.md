---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:8cae78b106a86b04922beeb472e320e4cda57876ef54046ecddfe345906ef3b6'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `Load census classification backlog`

## Scope

The registry load census at HEAD 2026-08-30, after `facade_symbol_owners()` was deleted and `build_reference_map()` rebuilt on real import edges (commit `bcb72f39`). Measured through the census's own `build_runtime_graph`, `census_universe`, `classify_universe` and `static_load_closure`, with grimp caching disabled. No production code was modified by this audit.

## Findings

### 108 modules in the census universe carry no classification | `dev/registry/analysis/load_census_classification.py`

Universe 384, classified 276, leaving **108 unclassified**; 103 of them are `cadrumo.domain.calculations.registry` submodules. These were invisible until now: `test_every_reachable_module_carries_exactly_one_classification` died inside `build_reference_map` on the retired facade, so it never reached its own assertion. The backlog is not new, it was preempted.

What is lost: the reviewed table is the project's record of which registry modules execute on a load, which execute only under a condition, and which are dead. With 108 modules outside it, that record no longer describes the package, and the gate cannot tell a genuinely dead module from an unreviewed one.

### the backlog splits cleanly on measured load reachability, 80 against 28

**80 of the 108 are inside the static load closure** — they execute on a registry load and are `live` by the same evidence the existing `live` rules cite.

**28 are outside it**, and they are NOT dead: they are the post-load public surface plus the oracle and parity tiers.

`registry.aeat_nif_iva_oracle`, `applicability_modelo202`, `censo_modelos`, `checker_oracle_flow`, `classification_coherence`, `coverage`, `external_grounding`, `filed_state`, `groi_oracle`, `handoffs`, `live_parity`, `m303_differentiated_deduction_projection`, `m303_exonerado_390_projection`, `m303_orden_resolution`, `m303_prorrata_activity_projection`, `m303_regimen_simplificado_projection`, `profile_grounding`, `queries`, `query_reports`, `rate_box_partition`, `remote_state_guard`, `renta_web_open_oracle`, `schedules`, `snapshot`, `snapshot_coordinate`, `support_matrix`, `validate_temporal_coherence`, `verification_tolerance`.

`snapshot` sitting outside the LOAD closure is correct rather than alarming — snapshot construction happens after load — but it shows why this set needs review per module rather than a bulk verdict.

### the oracle and parity modules lost the mechanism that made them visible

The retired `_LAZY_EXPORTS` table existed precisely so the oracle and live-parity modules, published only lazily, were seen as referenced; the old code says so in as many words. Inerting the namespace removed that mechanism. The rebuilt reference map reads direct import edges instead, which is correct, but it means these modules' referencedness now depends on consumers naming them directly — and that is exactly the property the adjudication must check rather than assume.

## Recommendations

1. Do NOT close this with one bulk `live` rule over the 80. A bulk membership list is what produced the duplicate claim on `_validate_cross_revision_contiguity`, where a broad `live` list and a specific `conditionally_reachable` rule both claimed the module and the census refused. Bulk rules collide with the specific ones that follow.

2. Classify the 80 in-closure modules against the existing `ValidatedRegistryAuthority.load` rules, extending their membership where the module genuinely belongs to that trigger, and give a module its own rule wherever its reachability differs from the group's stated reason.

3. Review the 28 out-of-closure modules INDIVIDUALLY. They are the post-load surface and the oracle tier, not dead candidates, and a `dead` verdict on any of them needs the consumer check the rebuilt reference map now supports — not the absence-from-closure signal alone.

4. Re-run the census immediately before adjudicating. The registry package is being actively split (six relocations landed on 2026-08-30 alone), so the universe grows between measurements and a list fixed today will be short tomorrow.

5. Treat the count as evidence, never as the deliverable: the gate asserts every module carries exactly one classification, so a partial sweep leaves it red and indistinguishable from no sweep at all.
