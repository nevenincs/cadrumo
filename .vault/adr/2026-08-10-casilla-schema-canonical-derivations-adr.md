---
tags:
  - '#adr'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5e5176532fc8d0bf5607a12f1e39e00cef0c4f1a8bab781fef3d6353542ee10b'
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
- `_casillas_by_binding` includes alternates but does not filter to BOUND, so the two diverge on any non-BOUND casilla that declares a binding. **AMENDED 2026-08-11: this record previously called that population corpus-empty and the two predicates corpus-equivalent. Both statements were false.** Measured over the authoring tree with stdlib `tomllib` and no registry loader, deliberately, so a broken registry load could not silence it - 12,682 casilla fragment files, 16,360 casilla tables, 0 parse failures - the population is **50 casillas, every one of them `M232 2018-y-siguientes`, every one `input_kind = informational`**, each declaring a fixed-width layout binding. The reverse population - a BOUND casilla with no primary binding, which the dual would RAISE on - is genuinely **0 corpus-wide**, and that is the half that makes the retarget safe: the dual introduces no new refusal anywhere.
- The retarget is nonetheless output-equivalent, but **contingently, on a second fact this record has to state because nothing else protects it**. `_rate_box_partition` acts only on ledger-IVA bindings; `M232` carries none of them (434 `manual_input`, 6 `related_party_operation`); and the helper's real population is 10 revisions - `M390 2010-y-siguientes`, all six `M303` revisions, `M322`, `M353`, `M309` - which does not intersect the 50. The equivalence holds because the divergent rows sit where the helper never looks, not because the predicates agree. Left unstated, the first casilla to go `informational`-with-a-binding in a ledger-IVA revision silently drops out of the rate-box mapping.
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

In `domain/calculations/registry`, four facade-exported derivations. (1) `casillas_by_binding(revision)` - the reverse join defined in terms of `bound_casilla_binding_ids`, returning a mapping from binding id to the ordered, de-duplicated casilla ids that may populate it; because the dual inherits the forward primitive's contract, it raises on a BOUND casilla with no binding (a regression proves the refusal, and the corpus carries zero such casillas today so the regression is the only place that path fires) and drops any non-BOUND casilla carrying a binding.

**AMENDED 2026-08-11 - the gate. This record originally specified "corpus-empty today; a gate keeps it so". That gate cannot be written**: the population is 50, not 0 (see Considerations), so an emptiness assertion reds on its first run, and the obvious repair is an `M232` allowlist - the honor-system list `aeat-quality-gates` exists to forbid. **The gate is instead: no revision carrying ledger-IVA bindings contains a non-BOUND casilla declaring a binding.** It is green today, it is the actual invariant the retarget rests on, and it bites at exactly the moment the retarget would begin silently dropping a rate box's money - which is what the emptiness gate was reaching for and could not express. An emptiness gate over the whole corpus asserts a property of a set the helper never reads.

Retarget `_rate_box_partition._casillas_by_binding` onto the dual and replace the last-write-wins mapping in `_calculation_modelo_adjustments` (a live behavioural fix: alternates currently dropped on a refusal path). (2) `relations_by_target_binding(revision)` - one home for the three duplicate grouping loops in `_queries` and `_relation_prefill`. (3) `relation_consumption_index(revision)` / `relation_is_consumed(relation, index)` - promoted from the consumption test, WITH one correction the promotion must make: the test's index reads `casilla.binding` only (three channels - primary binding, formula-to-relation, formula-to-binding), and scores 78/78 only because the three alternate-fed relations are `factual_evidence`, filtered before the predicate runs. The production functions add `alternate_bindings` as the fourth channel, and the gate includes a regression exercising an alternate-binding-fed relation so dropping the channel reds. `audit_registry_relation_handoffs` gains a consumption-channel field so its empty `target_casilla_ids` stops reading as unconsumed, and the `_relation_prefill` unresolved-partition consumes the index. (4) `classify_official_boxes(revision)` returning a mapping to a new core three-state `OfficialBoxStatus` (ADDRESSED / REPRESENTED_VIA_BINDING / UNDEFINED), composed from `fixed_width_record_casilla_ids`, `derive_export_layouts_from_bindings` (run first, so M720 becomes visible) and the xml-dictionary entries. The classifier answers slot declaration only; whether a value provably arrives stays owned by the export completeness gate.

## Rationale

Dual-of-forward makes join disagreement structurally impossible; promotion makes the only complete consumption predicate importable instead of test-trapped; the three-state classification is the only honest shape for a corpus where no-layout is the majority state. Landing all four before the read-model exists is what prevents a fourteenth mapper.

## Consequences

Gains: the joins go 13 -> 1, the consumption contract gains a production home, the box question gets an honest answer including M720. Costs: four relocation commits and two registry-data preconditions. Pitfall: a consumer tempted to call the per-mechanism functions and re-union them - the classifier is the union; the per-mechanism functions keep their existing two callers only.

**Amendment record, 2026-08-11.** Two statements in this record were measurably false and the gate one of them specified could not be written. Corrected above rather than carried forward in an execution record, because a carry-forward does not reach the next implementer and this record does: left as written, it would have produced the same failing gate a second time.

**How it was caught, and why nothing downstream could have caught it.** The implementing step carried a disconfirming clause - *if defining the reverse join as the dual changes behaviour for the existing callers, stop and report rather than retarget, because that would mean the retarget is a behaviour change wearing a dedup's clothes* - and the measurement fired it before any code was written. Had it not, the work would have been **correct against its brief**: the dual would have been implemented exactly as specified, the retarget would have been output-equivalent, the tests would have passed, and the execution record would have been honest. The only artefact that was wrong was this one. A gate asserting an empty set would then have reddened on its first run against `M232`, and the cheapest repair in the moment - an allowlist - would have converted a structural invariant into an honor-system list while leaving the checkbox green.

**The general form, for the next record that states a corpus fact.** A decision record's Considerations are unverified by anything in this repository. Code has tests, the vault has `check`, the CLI reference has `--check`, locales have a parity gate; a number written into an ADR's Considerations has none, and it is *load-bearing* the moment an Implementation section derives a gate from it. Any ADR asserting a corpus is empty, equivalent, or exhaustive should carry the query that produced the claim, so a later reader can re-run it instead of inheriting it. The four measures that made this census trustworthy are worth repeating: it read the authoring tree directly rather than through the loader, so a broken registry load could not silence it; it reported the full `input_kind` histogram rather than only the queried classes, so the result was not a pattern whose form encoded the answer; it was re-run as an aggregation because the first output was a truncated head, and a head cannot support "the rest is `M232`"; and it measured both directions, which is how the reverse population being 0 - the fact that actually makes the retarget safe - was established rather than assumed.
