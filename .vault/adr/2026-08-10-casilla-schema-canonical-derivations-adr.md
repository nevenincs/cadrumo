---
tags:
  - '#adr'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9000679e31730220d794961acad8f4ded94c08ed4617ca53d21fa15e04d222d5'
related:
  - "[[2026-08-10-casilla-schema-research]]"
  - "[[2026-06-14-bindings-interface-hardening-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
---

# `casilla-schema` adr: `canonical registry derivations for joins, relation consumption and official boxes` | (**status:** `accepted`)

## Problem Statement

Three registry-derivation questions are answered in many places with divergent predicates: the binding-to-casilla join exists 13 ways (one production copy drops alternate bindings on a refusal path), the relation-consumption contract exists only inside a test, and "does this casilla file an official box" has four mechanisms and no union authority (`2026-08-10-casilla-schema-research`, Q1/Q3 and B-03/B-09). Every new consumer built first would mint another copy.

## Considerations

- `bound_casilla_binding_ids` is facade-exported, filters to BOUND, raises on a BOUND casilla without a binding, and includes alternates - the strictest existing predicate.
- `_casillas_by_binding` includes alternates but does not filter to BOUND; corpus-equivalent today, divergent by construction (research: verification epistemics).
- The consumption predicate in the test implements three channels (primary binding, formula-to-relation, formula-to-binding) and omits `alternate_bindings`; it still scores 78/78 because the three alternate-fed relations are `factual_evidence`, filtered before the predicate runs. The binding-only predicate resolves 44/78 and misses all 14 instalment relations.
- 61 of 94 revisions declare no export layout; a boolean box answer fabricates a value for the majority state.
- A-01 (M720 derive-before-scan) and A-02 (digits-only parser) make any box classification untruthful on the outliers until fixed.

## Considered options

- **Join: adopt the `_casillas_by_binding` predicate (no BOUND filter)** - rejected: silently maps a mis-declared casilla instead of surfacing a validation gap.
- **Join: define the reverse join as the exact dual of `bound_casilla_binding_ids`** - chosen: the two cannot disagree.
- **Consumption: reuse `audit_registry_relation_handoffs`** - rejected: its join is the binding channel only and tolerates empty targets by design.
- **Consumption: promote the test predicate into the registry package** - chosen; the test keeps its gate role by importing the production functions.
- **Official box: boolean union** - rejected (61/94 undefined). **Per-mechanism answers only** - rejected: every consumer re-unions. **Typed three-state classification** - chosen.

## Constraints

- Each landing is one atomic relocation commit: canonical site plus every consumer retarget plus facade export together, clean `--collect-only` before commit.
- The official-box classifier is truthful on M720 and M100 2024+ only after the A-01/A-02 registry corrections land; those are plan preconditions, not part of this decision.
- `CasillaProducerInventory` is a different grain and is left untouched.

## Implementation

In `domain/calculations/registry`, four facade-exported derivations. (1) `casillas_by_binding(revision)` - the reverse join defined in terms of `bound_casilla_binding_ids`, returning a mapping from binding id to the ordered, de-duplicated casilla ids that may populate it; because the dual inherits the forward primitive's contract, it raises on a BOUND casilla with no binding (a regression proves the refusal) and drops any non-BOUND casilla carrying a binding (corpus-empty today; a gate keeps it so). Retarget `_rate_box_partition._casillas_by_binding` onto it and replace the last-write-wins mapping in `_calculation_modelo_adjustments` (a live behavioural fix: alternates currently dropped on a refusal path). (2) `relations_by_target_binding(revision)` - one home for the three duplicate grouping loops in `_queries` and `_relation_prefill`. (3) `relation_consumption_index(revision)` / `relation_is_consumed(relation, index)` - promoted from the consumption test, WITH one correction the promotion must make: the test's index reads `casilla.binding` only (three channels - primary binding, formula-to-relation, formula-to-binding), and scores 78/78 only because the three alternate-fed relations are `factual_evidence`, filtered before the predicate runs. The production functions add `alternate_bindings` as the fourth channel, and the gate includes a regression exercising an alternate-binding-fed relation so dropping the channel reds. `audit_registry_relation_handoffs` gains a consumption-channel field so its empty `target_casilla_ids` stops reading as unconsumed, and the `_relation_prefill` unresolved-partition consumes the index. (4) `classify_official_boxes(revision)` returning a mapping to a new core three-state `OfficialBoxStatus` (ADDRESSED / REPRESENTED_VIA_BINDING / UNDEFINED), composed from `fixed_width_record_casilla_ids`, `derive_export_layouts_from_bindings` (run first, so M720 becomes visible) and the xml-dictionary entries. The classifier answers slot declaration only; whether a value provably arrives stays owned by the export completeness gate.

## Rationale

Dual-of-forward makes join disagreement structurally impossible; promotion makes the only complete consumption predicate importable instead of test-trapped; the three-state classification is the only honest shape for a corpus where no-layout is the majority state. Landing all four before the read-model exists is what prevents a fourteenth mapper.

## Consequences

Gains: the joins go 13 -> 1, the consumption contract gains a production home, the box question gets an honest answer including M720. Costs: four relocation commits and two registry-data preconditions. Pitfall: a consumer tempted to call the per-mechanism functions and re-union them - the classifier is the union; the per-mechanism functions keep their existing two callers only.
