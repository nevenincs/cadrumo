---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-08-25'
body_hash: 'sha256:693a7d7adc3e2a1d77f0f0d7b6f58e944124dcf990f43f2c44d6de49b402e764'
tier: L3
related:
  - '[[2026-06-02-registry-hardening-next-work-health-audit]]'
  - '[[2026-06-02-schema-hardening-m100-label-legal-continuity-candidate-research]]'
  - '[[2026-06-02-schema-hardening-m100-legal-ref-continuity-candidate-research]]'
  - '[[2026-08-05-schema-hardening-aeip-event-keyed-continuity-research]]'
  - '[[2026-08-05-schema-hardening-compiled-casilla-order-research]]'
  - '[[2026-06-04-registry-hardening-next-work-adr]]'
---
# `schema-hardening` `registry hardening next work` plan

## Wave `W01` - reviewability and continuity stabilization

Complete the first registry-hardening pass: reviewability pressure, continuity rollout, semantic-role edge checks, module-boundary audits, and residual TOML fragment splits.

### Phase `W01.P01` - file-size gate stabilization

Make the existing file-size and row-size gate boring by splitting near-threshold registry artifacts before they become failures.

Plan the next registry-hardening substrate after continuity conformance reached
100 percent completion.

- [x] `W01.P01.S01` - Audit current TOML fragment and row-size headroom; `.vault/audit`.
- [x] `W01.P01.S02` - Split M100 2024 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024`.
- [x] `W01.P01.S03` - Split M100 2023 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2023`.
- [x] `W01.P01.S04` - Split M100 2022 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2022`.
- [x] `W01.P01.S05` - Split M100 2021 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2021`.
- [x] `W01.P01.S06` - Split M100 2020 completeness manifest into fragments; `src/aeat/_data/registry/aeat/modelos/100/revisions/2020`.
- [x] `W01.P01.S07` - Audit M200 export fragments near the reviewability ceiling; `.vault/audit`.
- [x] `W01.P01.S08` - Split the largest M200 export fragment if audit confirms safe boundaries; `src/aeat/_data/registry/aeat/modelos/200`.
- [x] `W01.P01.S09` - Audit M303 casilla and export fragments near the reviewability ceiling; `.vault/audit`.

### Phase `W01.P02` - continuity rollout

Extend continuity metadata only through small source-grounded slices after the reviewability gate is stable.

- [x] `W01.P02.S10` - Research the next M100 legal-reference-only continuity candidate; `.vault/research`.
- [x] `W01.P02.S11` - Author one M100 legal-reference-only continuity slice; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `W01.P02.S12` - Research the next M100 label-and-legal-reference continuity candidate; `.vault/research`.
- [x] `W01.P02.S13` - Author one M100 label-and-legal-reference continuity slice; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `W01.P02.S14` - Add committed-corpus regression coverage for M100 1038 continuity; `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`.

### Phase `W01.P03` - semantic role edge verification

Resolve the known role-taxonomy edges with focused real-registry checks instead of broad role rewrites.

- [x] `W01.P03.S15` - Re-audit M347 singleton marker state after shared-worktree changes; `src/aeat/_data/registry/aeat/modelos/347`.
- [x] `W01.P03.S16` - Verify M349 base_intracomunitaria role coverage; `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`.
- [x] `W01.P03.S17` - Verify signed cuota role coverage for IRPF and IS; `src/aeat/domain/calculations/registry/test_semantic_role.py`.

### Phase `W01.P04` - monolithic registry module refactors

Treat every large registry production module as an explicit refactor target, with audit-first extraction boundaries and no behavioral rewrite until seams are proven by focused tests.

- [x] `W01.P04.S18` - Audit registry Python module size and ownership boundaries; `.vault/audit`.
- [x] `W01.P04.S19` - Assess loader fragment-compiler extraction boundaries; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W01.P04.S20` - Assess binding resolver extraction boundaries; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W01.P04.S21` - Assess schema model extraction boundaries and ADR need; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P04.S22` - Assess record-design extraction boundaries; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `W01.P04.S23` - Assess applicability extraction boundaries; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `W01.P04.S24` - Assess workbook parity extraction boundaries; `src/aeat/domain/calculations/registry/_workbook_parity.py`.
- [x] `W01.P04.S25` - Assess formula runtime extraction boundaries; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P04.S26` - Audit oversized registry test module decomposition; `src/aeat/domain/calculations/registry`.
- [x] `W01.P04.S27` - Audit M123 revision file for directory-mode fragmentation need; `src/aeat/_data/registry/aeat/modelos/123`.

### Phase `W01.P05` - fragment pressure follow-ups

Track residual TOML fragment pressure discovered during P01 audits after the first stabilization pass completes.

- [x] `W01.P05.S28` - Split remaining M200 export fragments that stay near the reviewability ceiling; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export`.
- [x] `W01.P05.S29` - Split M303 casilla and export fragments if P01 audit confirms safe boundaries; `src/aeat/_data/registry/aeat/modelos/303`.
- [x] `W01.P05.S30` - Re-run corpus fragment headroom audit after residual pressure splits; `.vault/audit`.

## Wave `W02` - validation module decomposition

Break the monolithic registry validator into generic, reusable validation components without changing validation semantics or weakening registry-load safety.

### Phase `W02.P06` - validator boundary extraction

Audit and extract cohesive validator responsibilities behind the existing public validator surface before moving any enforcement semantics.

- [x] `W02.P06.S31` - Audit validation module responsibilities and extraction boundaries; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `W02.P06.S33` - Extract cross-revision advisory summary helpers; `src/aeat/domain/calculations/registry/_validate_cross_revision.py`.
- [x] `W02.P06.S34` - Extract cross-revision strict continuity helpers; `src/aeat/domain/calculations/registry/_validate_cross_revision.py`.
- [x] `W02.P06.S32` - Verify validator decomposition regression surface; `src/aeat/domain/calculations/registry`.

## Wave `W03` - reviewability gate tightening

Convert the achieved post-fragmentation registry corpus shape into explicit regression gates so future modelo work cannot drift back toward monolithic TOML artifacts.

### Phase `W03.P07` - post-fragmentation hard-cap enforcement

Measure current registry TOML headroom and tighten committed reviewability tests around the achieved corpus baseline without changing loader or schema semantics.

- [x] `W03.P07.S35` - Audit current committed registry TOML file-size and row-width headroom; `.vault/audit`.
- [x] `W03.P07.S36` - Tighten committed registry TOML file-size and row-width regression gates; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.
- [x] `W03.P07.S37` - Verify tightened reviewability gates against the committed registry corpus; `src/aeat/domain/calculations/registry`.

## Wave `W04` - validator baseline repair

Close the validator-module reviewability regression exposed while tightening TOML gates, preserving validation behavior and avoiding baseline inflation.

### Phase `W04.P08` - relation-period validator reviewability

Bring the relation-period validator module back under its committed reviewability baseline without changing validation semantics.

- [x] `W04.P08.S38` - Audit validator module reviewability baseline failure; `.vault/audit`.
- [x] `W04.P08.S39` - Reduce relation-period validator module below its reviewability baseline; `src/aeat/domain/calculations/registry/_validate_relation_periods.py`.
- [x] `W04.P08.S40` - Verify registry reviewability tests after validator baseline repair; `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.

## Wave `W05` - M200 calculation completeness repair

Close the M200 record-design completeness regression surfaced after internal-only casilla discipline work, keeping repairs source-grounded and limited to registry declaration data.

### Phase `W05.P09` - M200 closure identity alignment

Audit and repair M200 calculation closure identities so every calculated casilla maps to the committed completeness manifest and full Diseño coverage with the correct segment identity.

- [x] `W05.P09.S41` - Audit M200 closure-only calculation completeness drift and segment ownership; `.vault/audit`.
- [x] `W05.P09.S42` - Repair M200 calculation completeness declarations for the audited closure-only identities; `src/aeat/_data/registry/aeat/modelos/200`.
- [x] `W05.P09.S43` - Verify M200 record-design completeness after the repair and record the remaining cross-modelo gate blocker; `src/aeat/domain/calculations/registry/test_record_design.py`.

## Wave `W06` - M303 completeness manifest blocker

Close the Modelo 303 manifest-only completeness drift that blocks the full record-design gate after the M200 repair.

### Phase `W06.P10` - M303 stale total-row manifest cleanup

Audit and repair stale M303 completeness-manifest rows for totals that no longer participate in the calculation closure.

- [x] `W06.P10.S44` - Audit M303 manifest-only completeness drift for totals 27 and 45 across both revisions; `.vault/audit`.
- [x] `W06.P10.S45` - Remove stale M303 total rows from completeness manifests after closure derivation proves they are no longer calculated; `src/aeat/_data/registry/aeat/modelos/303`.
- [x] `W06.P10.S46` - Verify full record-design completeness and committed-registry gates after the M303 cleanup; `src/aeat/domain/calculations/registry/test_record_design.py`.

## Wave `W07` - legal and official-source grounding check

Close the legal-sensitivity review for the M200 and M303 registry definition edits by proving every changed declaration remains backed by committed legal references and official AEAT/BOE source artifacts.

### Phase `W07.P11` - post-repair legal grounding

Audit the completed completeness repairs against the registry legal/source catalogues, official Diseño coverage, export layouts, and real committed modelo revision setup.

- [x] `W07.P11.S47` - Audit M200 and M303 completeness repairs for legal refs, source refs, official Diseño/export backing, and calculation-closure consistency; `.vault/audit`.
- [x] `W07.P11.S48` - Verify legal-grounding audit with registry gates and close the post-repair legal-sensitivity check; `src/aeat/domain/calculations/registry`.

## Wave `W08` - remaining registry hardening wireframe

Persist the remaining and previously out-of-scope registry/schema hardening directions as an ordered execution wireframe before selecting the next implementation slice.

### Phase `W08.P12` - sequential follow-up map

Turn the discovered remaining directions into an auditable sequence, separating immediate gates from future ADR/plan work.

- [x] `W08.P12.S49` - Persist the remaining registry/schema hardening execution wireframe and next-slice ordering; `.vault/audit`.

## Wave `W09` - generic revision and fragmentation contract audit

Prove the current schema and loader revision/fragmentation support is generic across modelos, and identify any remaining special-case or accidental-coverage gaps before new implementation.

### Phase `W09.P13` - schema/loader genericity

Audit the loader, schema, and committed modelo corpus for cross-modelo revision and fragment support without editing dirty schema WIP owned by concurrent workers.

- [x] `W09.P13.S50` - Audit generic schema/loader revision and fragmentation contract across M100, M200, M303, and non-fragmented modelos; `.vault/audit`.
- [x] `W09.P13.S51` - Add or tighten real-behavior regression coverage only if the audit exposes a generic-contract gap; `src/aeat/domain/calculations/registry`.
- [x] `W09.P13.S52` - Verify generic revision/fragmentation contract gates and review the slice; `src/aeat/domain/calculations/registry`.

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
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-02-registry-hardening-next-work-plan.md`

If broad registry ruff remains blocked by unrelated pre-existing lint debt,
Step Records must use touched-file ruff and explicitly record the broader
blocker.
