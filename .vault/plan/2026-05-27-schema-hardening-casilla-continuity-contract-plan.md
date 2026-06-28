---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-research]]'
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---



# `schema-hardening` `casilla-continuity-contract` plan

Implement the accepted generic casilla continuity/evolution contract without
adding M100-specific template semantics. The work adds additive schema support,
opt-in hard validation, real-behavior tests, and a first evidence-grounded data
rollout path. Template expansion remains out of scope.

## Proposed Changes

The registry will gain explicit continuity metadata that identifies a casilla
as part of a cross-revision legal concept chain. Evolution records will explain
allowed non-identical annual changes, including label changes, legal-reference
changes, repurposing, and retirement. The hard validator will remain opt-in for
non-overlapping revisions so the current corpus can migrate with evidence
instead of sudden broad failures.

## Steps

### Phase `P01` - Schema and loader surface

Add additive runtime schema and fragment support for the generic continuity
contract while preserving current registry object loading semantics.

- [x] `P01.S01` - Add continuity identifiers, evolution declarations, and opt-in flags; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - Add fragment-loader support for continuity record arrays without special-casing modelos; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P01.S03` - Export only stable public continuity report types and keep helper modules private; `src/aeat/domain/calculations/registry`.

### Phase `P02` - Validator and tests

Wire the continuity contract into cross-revision validation with advisory mode
unchanged for non-opted-in modelos and hard failures for opted-in surfaces.

- [x] `P02.S04` - Extend cross-revision drift analysis with continuity and evolution metadata; `src/aeat/domain/calculations/registry/_validate_cross_revision.py`.
- [x] `P02.S05` - Wire opt-in continuity validation into registry-scope validation; `src/aeat/domain/calculations/registry/_validate_registry_scope.py`.
- [x] `P02.S06` - Add real-behavior schema, loader, advisory, and opt-in hard-failure tests; `src/aeat/domain/calculations/registry`.

### Phase `P03` - Evidence-grounded data rollout

Start corpus adoption from evidence instead of template generation, keeping
M100 explicit and fragmented until continuity decisions are authored.

- [x] `P03.S07` - Produce a committed M100 continuity inventory with sampled continuous, evolved, repurposed, and retired buckets; `.vault/research`.
- [x] `P03.S08` - Author the first minimal continuity metadata slice for an evidence-grounded M100 annual chain; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `P03.S09` - Enable opt-in hard validation only for continuity-covered M100 surfaces; `src/aeat/_data/registry/aeat/modelos/100`.

### Phase `P04` - Gates and closeout

Lock the new substrate against regression and record the implementation state
for the next agent before any template ADR is considered.

- [x] `P04.S10` - Add committed-corpus regression gates for continuity advisory and opt-in enforcement behavior; `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`.
- [x] `P04.S11` - Record execution evidence, verification commands, and remaining template blockers; `.vault/exec`.

## Parallelization

`P01.S01` must land before all other implementation steps. `P01.S02` and
`P01.S03` can proceed after the schema surface exists. `P02.S04` and
`P02.S05` are ordered because registry-scope wiring depends on validator
semantics. `P02.S06` can be developed alongside `P02.S04` after the schema
surface exists, but it lands with or after the validator behavior it proves.
`P03` depends on `P02` because data rollout must use the real validator.
`P04` closes the plan after implementation and data rollout evidence exists.

## Verification

The plan is complete when every step is closed and these checks pass:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`

No M100 template compiler may be implemented under this plan.
