---
tags:
  - '#plan'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_hash: 'sha256:675f535c6fa220fcf17a3db4233bef7d8f1183c349ce68d6edb48e5af1824405'
tier: L3
related:
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-source-authority-research]]'
---

<!-- RETIRED: S26 -->

# `aeat-export-fragment-generator-authority` plan

Build and prove the single fail-closed authority that generates complete export-fragment revisions from official AEAT binaries and reviewed semantic maps.

## Description

This L3 plan executes `2026-08-10-aeat-export-fragment-generator-authority-adr`. Wave 1 establishes typed source and semantic-map contracts, Wave 2 implements atomic deterministic generation, Wave 3 supplies adversarial correctness gates, and Wave 4 regenerates representative split revisions and releases the blocked relayout campaign. No generator implementation begins until this plan is explicitly approved.

## Steps

## Wave `W01` - authority contracts

Define the exact official-source, parser intermediate, semantic-map, provenance, and refusal contracts that every later Wave consumes.

### Phase `W01.P01` - source and intermediate representation

Make the exact binary and typed parser output the complete coordinate authority.

- [x] `W01.P01.S01` - Extend the existing validated source catalogue with hash-pinned binary selection and reject inapplicable or drifting sources; `src/cadrumo/_data/registry/aeat/legal/is.toml`.
- [x] `W01.P01.S02` - Define the typed intermediate representation with complete source anchors, coordinates, validation metadata, and declared totals; `dev/registry/`.
- [ ] `W01.P01.S03` - Prove the intermediate representation consumes shipped parser output and never extracted derivatives; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W01.P02` - semantic map and provenance contracts

Separate authored registry meaning from official coordinates and make their join auditable.

- [ ] `W01.P02.S04` - Define the per-modelo per-design semantic-map schema keyed by exact parser anchors; `dev/registry/`.
- [ ] `W01.P02.S05` - Validate mapping bijection and require canonical identifiers, legal references, and source references to resolve through existing registry catalogues while constraining typed anomaly exceptions; `dev/registry/`.
- [ ] `W01.P02.S06` - Define the adjacent non-loader provenance manifest and normalized loader-semantic digest; `dev/registry/`.

## Wave `W02` - deterministic atomic generator

Implement complete revision generation only after the authority contracts are fixed and reviewed.

### Phase `W02.P03` - generation pipeline

Join exact parser anchors to reviewed semantics and render a complete target revision.

- [ ] `W02.P03.S07` - Implement fail-closed parser-to-semantic-map joining without fuzzy or positional matching; `dev/registry/`.
- [ ] `W02.P03.S08` - Render the complete target export tree with stable partitioning and canonical TOML serialization; `dev/registry/`.
- [ ] `W02.P03.S09` - Emit source, map, schema, semantic, and file digests in the provenance manifest; `dev/registry/`.

### Phase `W02.P04` - publication and check mode

Prevent partial publication and turn every generated artifact into a reproducible repository contract.

- [ ] `W02.P04.S10` - Validate generated trees through the real registry loader before publication; `dev/registry/`.
- [ ] `W02.P04.S11` - Publish complete generated trees and provenance atomically from an isolated temporary target; `dev/registry/`.
- [ ] `W02.P04.S12` - Implement check mode that independently regenerates and rejects semantic, provenance, or byte drift; `dev/registry/`.

## Wave `W03` - adversarial correctness proof

Demonstrate that plausible coordinate, mapping, provenance, and publication defects fail loudly before any filing artifact can consume them.

### Phase `W03.P05` - contract and mutation gates

Cover every authority boundary with positive and negative real-behavior tests.

- [ ] `W03.P05.S13` - Prove parser completeness, declared totals, source applicability, and source-hash enforcement; `dev/registry/tests/`.
- [ ] `W03.P05.S14` - Prove missing, duplicate, ambiguous, fuzzy, and illegal-exception mappings refuse the whole design; `dev/registry/tests/`.
- [ ] `W03.P05.S15` - Prove offset, length, source-anchor, target-revision, and generated-file mutations are detected; `dev/registry/tests/`.

### Phase `W03.P06` - repository and byte gates

Verify generated layouts as loadable complete structures and as real emitted filing bytes.

- [ ] `W03.P06.S16` - Prove deterministic double generation and repository check mode on real bundled sources; `dev/registry/tests/`.
- [ ] `W03.P06.S17` - Run extent, overlap, declared-total, applicability, and full-registry-load gates on generated trees; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `W03.P06.S18` - Prove representative fields land at official byte offsets across each regenerated revision boundary; `src/cadrumo/application/filing/tests/`.

## Wave `W04` - regenerate and release relayout waves

Use the proven authority to replace unverified trees, close the blocked split spans, and restore architecture-consistent model bindings.

### Phase `W04.P07` - representative generation and relayout closure

Regenerate the highest-priority calculation-model revisions and discharge the held relayout obligations.

- [ ] `W04.P07.S19` - Author and review semantic maps for the required Modelo 303 design epochs; `dev/registry/mappings/modelo_303/`.
- [ ] `W04.P07.S20` - Generate and validate the complete Modelo 303 revision trees and provenance manifests; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W04.P07.S21` - Author, generate, and validate the blocked Modelo 390 revision trees through the same authority; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.

### Phase `W04.P08` - campaign integration and release

Re-run relayout, binding, calculation, and export proofs before exact-scope delivery.

- [ ] `W04.P08.S22` - Bootstrap explicit Modelo 200 semantic maps, regenerate its held revision trees, and re-key the revision only from generated provenance; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`.
- [ ] `W04.P08.S23` - Reconcile the relayout plan rows and superseded assumptions against generated evidence; `.vault/plan/2026-08-08-aeat-design-relayout-boundary-plan.md`.
- [ ] `W04.P08.S24` - Run formal code review and resolve every high and medium finding; `.vault/audit/`.
- [ ] `W04.P08.S25` - Run focused static, registry, binding, calculation, export, and emitted-byte gates and record exact proof boundaries; `src/cadrumo/`.
- [ ] `W04.P08.S27` - Commit and push only the reviewed generator and relayout payload with clean conflict and status proof; `.`.

## Parallelization

Waves are ordered. Within Wave 1, parser-source modelling and semantic-map schema work may proceed in parallel after the shared intermediate representation is fixed. Within Wave 3, mutation-gate groups may run in parallel against the landed generator. Revision generation in Wave 4 is serialized per target tree to keep provenance and review boundaries exact.

## Verification

Completion requires every Step closed; deterministic double generation and repository `--check`; complete parser, bijection, applicability, provenance, extent, overlap, load and emitted-byte gates; formal code review with no unresolved high or medium findings; the relayout span gate green for regenerated revisions; focused static analysis and tests green; and exact-scope commit and push evidence.
