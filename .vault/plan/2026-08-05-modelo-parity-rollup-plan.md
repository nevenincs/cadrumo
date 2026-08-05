---
tags:
  - '#plan'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_hash: 'sha256:94b2c14a2bd8b1fe138c249a7fe9aea75ad88b8a064e68da24b4c474f307a5bd'
tier: L3
related:
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-denominator-research]]'
---

<!-- RETIRED: W02, P02 -->

# `modelo-parity-rollup` plan

## Description

Execute the accepted five-domain parity contract from `2026-08-05-modelo-parity-rollup-five-domain-contract-adr`. The plan separates the 73-modelo/90-revision portfolio ledger from a finite annual behavioral matrix, measures schema, formula and provenance, legal and source, cross-model handoff, and behavioral verification divergences, and dispatches only bounded Luna Max work.

## Steps

## Wave `W01` - Measure and expose parity divergences

Build the exact portfolio and annual ledgers for all five parity domains. This wave is the evidence boundary for downstream implementation and must classify missing, unsupported, deferred, manual, upstream, and not-yet-measured populations.

### Phase `W01.P03` - Build exact schema coordinate matrix

Enumerate exact modelo, exercise, and period coordinates and compare each year-specific official form or layout without using a newest-revision baseline.

- [x] `W01.P03.S01` - Enumerate validated modelo, exercise, period, and law-selected revision coordinates; `dev/registry/conformance/manager.py`.
- [x] `W01.P03.S02` - Compare each annual casilla population and attributes with its official form or layout source; `src/cadrumo/application/registry/_conformance.py`.
- [x] `W01.P03.S03` - Classify unsupported, open-ended, manual, upstream, deferred, and not-yet-measured coordinates without omission; `dev/registry/conformance/manager.py`.

### Phase `W01.P04` - Measure formula and provenance closure

Inventory typed producers, formula targets, reverse casilla declarations, manual and upstream reasons, and construct-level provenance while preserving honest non-computed values.

- [x] `W01.P04.S04` - Inventory deterministic producers, formula targets, and casilla declarations across the validated registry; `src/cadrumo/domain/calculations/registry/_schema.py`.
- [x] `W01.P04.S05` - Enforce reverse formula-target and casilla-kind parity in the registry validator; `src/cadrumo/domain/calculations/registry/_validate.py`.
- [x] `W01.P04.S06` - Trace manual, upstream, relation, and computed reasons with their source and provenance fields; `src/cadrumo/domain/calculations/registry/_schema.py`.

### Phase `W01.P05` - Reconcile legal and source parity

Map every schema construct, formula, parameter, binding, relation, selector, and producer to its applicable authoritative source and separate revision evidence floors from construct proof.

- [x] `W01.P05.S07` - Build construct-level legal and source evidence rows for formulas, parameters, bindings, relations, and selectors; `src/cadrumo/domain/calculations/registry/_coverage.py`.
- [x] `W01.P05.S08` - Separate revision evidence-floor results from per-casilla provenance results in conformance output; `src/cadrumo/application/registry/_conformance.py`.
- [x] `W01.P05.S09` - Validate source references through the registry authority flow and classify unresolved construct gaps; `src/cadrumo/domain/calculations/registry/_validate.py`.

### Phase `W01.P06` - Measure cross-model handoff parity

Inventory canonical relations and aggregation paths with source and target coordinates, period applicability, clean-state behavior, and provenance.

- [ ] `W01.P06.S10` - Inventory canonical relation and aggregation declarations with source and target identities; `src/cadrumo/domain/calculations/registry`.
- [ ] `W01.P06.S11` - Measure period applicability and clean-state behavior for each cross-model handoff; `src/cadrumo/domain/calculations/registry/_snapshot.py`.
- [ ] `W01.P06.S12` - Detect parallel or non-canonical handoff paths and preserve their provenance classifications; `src/cadrumo/domain/calculations/registry/_validate.py`.

### Phase `W01.P07` - Certify behavioral verification parity

Define the finite annual matrix, map only exact existing oracle evidence, and prove claimed producers and handoffs through the real registry and runtime.

- [ ] `W01.P07.S13` - Define the finite annual matrix from law-selected revisions and official layout sources; `dev/registry/conformance/manager.py`.
- [x] `W01.P07.S14` - Extract exact existing oracle coordinate and payload mappings without adding unsupported claims; `src/cadrumo/domain/calculations/registry/_external_grounding.py`.
- [ ] `W01.P07.S15` - Prove real runtime verification expectations and independent-value projections for certified mappings; `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py`.

## Wave `W03` - Resolve bounded semantic decisions

Adjudicate M100 0150, 0613, and 1481 with focused legal, profile, aggregation, and independent numeric evidence. No production change is allowed until each decision returns from SOL.

### Phase `W03.P08` - Adjudicate M100 semantic focus rows

Prepare and obtain focused SOL decisions for M100 0150, 0613, and 1481 before any manual-to-computed, profile, or cross-model production change.

- [ ] `W03.P08.S16` - Adjudicate M100 0150 against the 2025 profile and applicable legal evidence; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025`.
- [ ] `W03.P08.S17` - Adjudicate M100 0613 against monthly facts, profile capability, and applicable legal evidence; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025`.
- [ ] `W03.P08.S18` - Adjudicate M100 1481 against Modelo 131 relation and aggregation semantics; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025`.

## Wave `W04` - Execute accepted closure work

Implement only accepted, evidence-backed parity gaps, then run real registry and behavioral verification and close the report without converting unmeasured or deferred rows into passes.

### Phase `W04.P09` - Implement accepted schema and producer closure

Apply only accepted schema and reverse-wiring findings with disjoint ownership and real invariant tests; leave deferred semantic rows untouched.

- [ ] `W04.P09.S19` - Implement accepted schema and reverse formula invariants in the registry validator; `src/cadrumo/domain/calculations/registry/_validate.py`.
- [ ] `W04.P09.S20` - Add real failure tests for accepted cross-revision formula wiring divergences; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W04.P09.S21` - Run targeted M100 and registry conformance checks for the accepted invariant findings; `dev/registry/conformance/manager.py`.

### Phase `W04.P10` - Implement accepted source and handoff closure

Apply only accepted legal/source and canonical cross-model handoff findings with their grounded provenance and clean-state tests.

- [ ] `W04.P10.S22` - Implement accepted construct-level legal and source evidence projections; `src/cadrumo/domain/calculations/registry/_coverage.py`.
- [ ] `W04.P10.S23` - Implement accepted canonical relation and cross-model handoff checks; `src/cadrumo/domain/calculations/registry/_validate.py`.
- [ ] `W04.P10.S24` - Add clean-state, period, and provenance tests for accepted handoffs; `src/cadrumo/domain/calculations/registry/tests`.

### Phase `W04.P11` - Close behavioral evidence and parity report

Run the real conformance, coverage, oracle, and focused test gates, complete code review, and publish an honest closure report with open and deferred populations.

- [ ] `W04.P11.S25` - Record exact oracle enrollment only for certified coordinate and payload mappings; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W04.P11.S26` - Run full conformance, coverage, oracle, and audit gates and capture their exact outputs; `dev/registry/conformance/manager.py`.
- [ ] `W04.P11.S27` - Complete code review and record the final parity closure report with open and deferred populations; `.vault/audit/2026-08-05-modelo-parity-rollup-audit.md`.

## Parallelization

W01 phases may run in parallel only when their owned files and coordinate sets are disjoint. The semantic-decision wave follows the complete measurement baseline. The implementation wave follows accepted decisions and focused reviews. No worker may overwrite peer WIP or share an actively edited file without one declared owner.

## Verification

The plan is complete only when every step is closed and the final checks show a validated registry, a reproducible five-domain ledger, exact annual-coordinate classifications, reverse formula wiring, construct-level source and legal provenance, canonical cross-model handoffs, and real behavioral evidence. Deferred M100 rows must remain visibly deferred until their addenda and SOL approvals exist.
