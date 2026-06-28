---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
tier: L2
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-research]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---


# `schema-hardening` `continuity ADR conformance` plan

Conform the landed continuity implementation to the accepted generic
continuity ADR before authoring more corpus continuity metadata.

## Proposed Changes

The current substrate already has generic schema, loader, advisory reporting,
strict opt-in validation, and one M100 data slice. This plan treats those as
implementation under review, not as a reason to improvise new schema. Work must
first record an ADR conformance audit. Code changes are allowed only when the
audit identifies a generic gap in `src/aeat/domain/calculations/registry`, and
data changes are allowed only after validator behavior is proven by tests.

No M100-only schema, loader branch, validator branch, or template compiler is
authorised by this plan.

## Success Signals

- The conformance audit maps each ADR decision D1 through D5 to implemented
  code, tests, and any gap.
- Generic validator behavior covers the accepted evolution kinds, including
  retired or intentionally repurposed continuity boundaries, without relying on
  modelo id checks.
- Registry file-size regression is guarded so a single modelo TOML cannot grow
  back into an unauditable artifact.
- Any M100 continuity additions are explicit data applications of the generic
  contract, not new schema or special-case behavior.

## Failure Signals

- Any code path checks `modelo.id == "100"` to define continuity semantics.
- Any implementation infers continuity from repeated numeric casilla id alone.
- Any strict corpus rollout lacks source and legal grounding.
- Any test passes by faking, monkeypatching, skipping, or mirroring validator
  logic instead of exercising real schema or registry objects.

## Steps

### Phase `P01` - implementation conformance audit

Compare the landed continuity schema, loader, validator, tests, and M100 data slice against the accepted generic continuity ADR before any further data rollout.

- [x] `P01.S01` - Audit implemented continuity substrate against ADR D1-D5 and record mismatches; `.vault/research`.

### Phase `P02` - generic validator conformance

Close generic continuity-validator gaps without adding modelo-specific schema or loader branches.

- [x] `P02.S02` - Add generic retirement and unmatched-continuity validation semantics; `src/aeat/domain/calculations/registry/_validate_cross_revision.py`.
- [x] `P02.S03` - Add real-behavior tests for retired repurposed and unmatched continuity decisions; `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`.

### Phase `P03` - corpus and file-size gates

Apply the generic substrate to corpus safety gates only after validator conformance is proven.

- [x] `P03.S04` - Add registry TOML file-size and fragmentation regression gate; `src/aeat/domain/calculations/registry`.
- [x] `P03.S05` - Author the next evidence-grounded M100 continuity slice using only generic continuity records; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `P03.S10` - Add generic completeness-manifest fragment merging and repair discovered file-size gate violations; `src/aeat/domain/calculations/registry, src/aeat/_data/registry/aeat/modelos/100, src/aeat/_data/registry/aeat/modelos/303`.

### Phase `P04` - evidence and closeout

Record execution evidence, residual risks, and explicit pass or fail signals for the conformance slice.

- [x] `P04.S06` - Record verification evidence residual risks and next-step decision points; `.vault/exec`.

### Phase `P05` - ADR language and governing comments

Tighten accepted ADR language and mark the clean implementation files with governing ADR cross-reference comments before validator behavior changes.

- [x] `P05.S07` - Add governing ADR comments to clean continuity loader and validator modules; `src/aeat/domain/calculations/registry`.
- [x] `P05.S08` - Tighten continuity ADR language for staged surface-scoped strictness and corpus-strict blockers; `.vault/adr/2026-05-27-schema-hardening-casilla-continuity-contract-adr.md`.
- [x] `P05.S09` - Record rollout evidence for ADR language and governing-comment pass; `.vault/exec`.

## Parallelization

`P01.S01` must land before any code or data change. `P05.S07`,
`P05.S08`, and `P05.S09` are now the next required work despite appearing
after P04 for append-only step ordering. `P02.S02` and `P02.S03` must not
start until P05 resolves the governing ADR language and code comments. `P03.S04`
can start after P05 if it does not depend on validator changes. `P03.S05` must
wait for P02 to pass because corpus rollout must use proven validator
semantics. P04 is closeout only.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-28-schema-hardening-continuity-conformance-plan.md`

If any command fails, the Step Record must state the failing command and whether
the failure is authored by this plan or pre-existing shared-worktree state.
