---
tags:
  - '#plan'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_hash: 'sha256:ec0f1e71a832b05e14bfb695c91a16f846d60c4cb50955c061a44000ea9ee097'
tier: L3
related:
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-denominator-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-0150-oracle-addendum-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s18-1481-oracle-addendum-research]]'
  - '[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-third-adjudication-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-oracle-code-review-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-source-contract-research]]'
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

- [x] `W01.P06.S10` - Inventory canonical relation and aggregation declarations with source and target identities; `src/cadrumo/domain/calculations/registry`.
- [x] `W01.P06.S11` - Measure period applicability and clean-state behavior for each cross-model handoff; `src/cadrumo/domain/calculations/registry/_snapshot.py`.
- [x] `W01.P06.S12` - Detect parallel or non-canonical handoff paths and preserve their provenance classifications; `src/cadrumo/domain/calculations/registry/_validate.py`.

### Phase `W01.P07` - Certify behavioral verification parity

Define the finite annual matrix, map only exact existing oracle evidence, and prove claimed producers and handoffs through the real registry and runtime.

- [x] `W01.P07.S13` - Define the finite annual matrix from law-selected revisions and official layout sources; `dev/registry/conformance/manager.py`.
- [x] `W01.P07.S14` - Extract exact existing oracle coordinate and payload mappings without adding unsupported claims; `src/cadrumo/domain/calculations/registry/_external_grounding.py`.
- [x] `W01.P07.S15` - Prove real runtime verification expectations and independent-value projections for certified mappings; `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py`.

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

- [x] `W04.P09.S19` - Implement accepted schema and reverse formula invariants in the registry validator; `src/cadrumo/domain/calculations/registry/_validate.py`.
- [x] `W04.P09.S20` - Add real failure tests for accepted cross-revision formula wiring divergences; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W04.P09.S21` - Run targeted M100 and registry conformance checks for the accepted invariant findings; `dev/registry/conformance/manager.py`.

### Phase `W04.P10` - Implement accepted source and handoff closure

Apply only accepted legal/source and canonical cross-model handoff findings with their grounded provenance and clean-state tests.

- [x] `W04.P10.S22` - Implement accepted construct-level legal and source evidence projections; `src/cadrumo/domain/calculations/registry/_coverage.py`.
- [x] `W04.P10.S23` - Implement accepted canonical relation and cross-model handoff checks; `src/cadrumo/domain/calculations/registry/_validate.py`.
- [x] `W04.P10.S24` - Add clean-state, period, and provenance tests for accepted handoffs; `src/cadrumo/domain/calculations/registry/tests`.

### Phase `W04.P11` - Close behavioral evidence and parity report

Run the real conformance, coverage, oracle, and focused test gates, complete code review, and publish an honest closure report with open and deferred populations.

- [x] `W04.P11.S25` - Record exact oracle enrollment only for certified coordinate and payload mappings; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W04.P11.S26` - Run full conformance, coverage, oracle, and audit gates and capture their exact outputs; `dev/registry/conformance/manager.py`.
- [x] `W04.P11.S27` - Complete code review and record the final parity closure report with open and deferred populations; `.vault/audit/2026-08-05-modelo-parity-rollup-audit.md`.

## Wave `W05` - Ground remaining producer contracts and parity closures

Execute the actionable semantic findings that remain open after the initial parity closure, with SOL-bounded contracts, VaultSpec-RAG evidence, Luna Max implementation, and honest non-promotion gates when authoritative numeric semantics are incomplete.

### Phase `W05.P12` - Close 0613 evidence contract before promotion

Adjudicate the exact per-child qualifying-month cap, effective non-subsidized spend semantics, decimal precision, and rounding stage with independent grounded evidence before any 2025 registry producer is authorized.

- [x] `W05.P12.S28` - Build and verify an evidence-only 2025 0613 cap and rounding addendum without changing production schema wiring; `src/cadrumo/domain/contribuyente/tests and .vault/research/2026-08-05-modelo-parity-rollup-s17-0613-cap-oracle-research.md`.

## Wave `W06` - Execute SOL-authorized evidence gates

Advance S16 source-contract grounding, S17 independent cap and rounding oracle acquisition, and S18 annual shared-engine mapping without changing unresolved production producers.

### Phase `W06.P13` - Ground source contracts and annual engine mapping

Create only research, proposed ADR content, and independent real-runtime oracle evidence authorized by SOL; retain all unresolved M100 2025 producers as manual.

- [x] `W06.P13.S29` - Draft the SOL-bounded S16 rental source-contract research and a proposed ADR without changing fincas models, persistence, source readiness, or M100 0150 wiring; `src/cadrumo/domain/fincas; src/cadrumo/application/aggregation; .vault/research; .vault/adr`.
- [x] `W06.P13.S30` - Build and verify an evidence-only 2025 0613 source-capability tranche without changing 2025 schema or formula wiring; `src/cadrumo/domain/contribuyente/tests; src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md; .vault/research`.
- [x] `W06.P13.S31` - Ground the annual shared-engine 2025 per-activity path for M100 1481 and produce only an independent oracle or research artifact without adding an M131 casilla-01 relation; `src/cadrumo/domain/calculations/registry/tests; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025; .vault/research`.
- [ ] `W06.P13.S32` - Acquire the complete authoritative 2025 0613 cap and rounding oracle matrix and return it to SOL before any producer promotion; `src/cadrumo/_data/corpus/manual_oracles; src/cadrumo/domain/contribuyente/tests; .vault/research`.

## Parallelization

W01 phases may run in parallel only when their owned files and coordinate sets are disjoint. The semantic-decision wave follows the complete measurement baseline. The implementation wave follows accepted decisions and focused reviews. No worker may overwrite peer WIP or share an actively edited file without one declared owner.

## Verification

The plan is complete only when every step is closed and the final checks show a validated registry, a reproducible five-domain ledger, exact annual-coordinate classifications, reverse formula wiring, construct-level source and legal provenance, canonical cross-model handoffs, and real behavioral evidence. Deferred M100 rows must remain visibly deferred until their addenda and SOL approvals exist.
