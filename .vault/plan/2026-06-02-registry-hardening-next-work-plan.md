---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-06-02'
tier: L2
related:
  - '[[2026-06-02-registry-hardening-next-work-health-audit]]'
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `schema-hardening` `registry hardening next work` plan

### Phase `P01` - file-size gate stabilization

Make the existing file-size and row-size gate boring by splitting near-threshold registry artifacts before they become failures.


Plan the next registry-hardening substrate after continuity conformance reached
100 percent completion.

- [x] `P01.S01` - Audit current TOML fragment and row-size headroom; `.vault/audit`.
- [x] `P01.S02` - Split M100 2024 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024`.
- [x] `P01.S03` - Split M100 2023 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2023`.
- [x] `P01.S04` - Split M100 2022 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2022`.
- [x] `P01.S05` - Split M100 2021 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2021`.
- [x] `P01.S06` - Split M100 2020 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2020`.
- [x] `P01.S07` - Audit M200 export fragments near the reviewability ceiling; `.vault/audit`.
- [x] `P01.S08` - Split the largest M200 export fragment if audit confirms safe boundaries; `src/aeat/_data/registry/aeat/modelos/200`.
- [x] `P01.S09` - Audit M303 casilla and export fragments near the reviewability ceiling; `.vault/audit`.

### Phase `P02` - continuity rollout

Extend continuity metadata only through small source-grounded slices after the reviewability gate is stable.

- [x] `P02.S10` - Research the next M100 legal-reference-only continuity candidate; `.vault/research`.
- [x] `P02.S11` - Author one M100 legal-reference-only continuity slice; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `P02.S12` - Research the next M100 label-and-legal-reference continuity candidate; `.vault/research`.
- [x] `P02.S13` - Author one M100 label-and-legal-reference continuity slice; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `P02.S14` - Add committed-corpus regression coverage for M100 1038 continuity; `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`.

### Phase `P03` - semantic role edge verification

Resolve the known role-taxonomy edges with focused real-registry checks instead of broad role rewrites.

- [x] `P03.S15` - Re-audit M347 singleton marker state after shared-worktree changes; `src/aeat/_data/registry/aeat/modelos/347`.
- [x] `P03.S16` - Verify M349 base_intracomunitaria role coverage; `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`.
- [x] `P03.S17` - Verify signed cuota role coverage for IRPF and IS; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `P04` - monolithic registry module refactors

Treat every large registry production module as an explicit refactor target, with audit-first extraction boundaries and no behavioral rewrite until seams are proven by focused tests.

- [x] `P04.S18` - Audit registry Python module size and ownership boundaries; `.vault/audit`.
- [x] `P04.S19` - Assess loader fragment-compiler extraction boundaries; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P04.S20` - Assess binding resolver extraction boundaries; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P04.S21` - Assess schema model extraction boundaries and ADR need; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P04.S22` - Assess record-design extraction boundaries; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `P04.S23` - Assess applicability extraction boundaries; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `P04.S24` - Assess workbook parity extraction boundaries; `src/aeat/domain/calculations/registry/_workbook_parity.py`.
- [x] `P04.S25` - Assess formula runtime extraction boundaries; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `P04.S26` - Audit oversized registry test module decomposition; `src/aeat/domain/calculations/registry`.
- [ ] `P04.S27` - Audit M123 revision file for directory-mode fragmentation need; `src/aeat/_data/registry/aeat/modelos/123`.

### Phase `P05` - fragment pressure follow-ups

Track residual TOML fragment pressure discovered during P01 audits after the first stabilization pass completes.

- [ ] `P05.S28` - Split remaining M200 export fragments that stay near the reviewability ceiling; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export`.
- [ ] `P05.S29` - Split M303 casilla and export fragments if P01 audit confirms safe boundaries; `src/aeat/_data/registry/aeat/modelos/303`.
- [ ] `P05.S30` - Re-run corpus fragment headroom audit after residual pressure splits; `.vault/audit`.

## Description

The next work should protect reviewability first, then extend continuity data
in small source-grounded slices, then audit semantic-role edges and break down
monolithic registry modules. Module decomposition is a first-class health
target, not optional cleanup, but every extraction must be audit-first and
behavior-preserving. No new schema architecture is authorised by this plan.
Work uses the accepted fragment authoring compiler and continuity contract.

## Steps

## Parallelization

File-fragmentation Steps can run in parallel only when they touch different
modelo directories and each agent commits explicit paths. Continuity data
Steps must run after the registry file-size gate is clean. Role taxonomy and
module-size audit Steps can run after the file-size audit is recorded.

## Verification

The plan is complete when every Step is closed and these checks pass:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-02-registry-hardening-next-work-plan.md`

If broad registry ruff remains blocked by unrelated pre-existing lint debt,
Step Records must use touched-file ruff and explicitly record the broader
blocker.
