---
tags:
  - '#plan'
  - '#linkage-design-audit'
date: '2026-05-18'
modified: '2026-05-18'
tier: L2
related:
  - '[[2026-05-15-linkage-design-audit-research]]'
  - '[[2026-05-15-linkage-design-audit-reference]]'
  - '[[2026-05-17-linkage-design-audit-plan]]'
  - '[[2026-05-26-linkage-design-audit-adr]]'
---
# `linkage-design-audit` `Wave 4: operator surfaces, identity, registry data backfill (Phase 4 of linkage epic)` plan

### Phase `P01` - CLI relation / prior-filing values

Add operator-facing mechanisms to supply prior-period relation values
to `aeat app modelo work calculate` and to export commands. Closes
F11.

- [x] `P01.S01` - add `--relation KEY=VALUE` flag to work calculate; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P01.S02` - thread relation_values through calculate_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [x] `P01.S03` - implement `--prefill-relations` flag on export command per its docstring; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `P01.S04` - catch RegistrySnapshotError in _load_snapshot and surface as CliRefusedBoundaryError; `src/aeat/entrypoints/cli/_config/_google.py`.

### Phase `P02` - CLI typed IDs at the boundary

Replace bare `str` work_unit_id and casilla-code parsing with typed
wrappers at the CLI ingress.

- [x] `P02.S05` - declare typed WorkUnitId alias and validate at CLI option; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P02.S06` - parse --casilla as CasillaId-validated str at ingress; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `P03` - schema-attached sensitivity classification

Add `output_sensitivity: SensitivityClass` field on ModeloDefinition.
Repositories assert the declared sensitivity matches schema at write
time instead of hard-coding.

- [x] `P03.S07` - add output_sensitivity field to ModeloDefinition; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S08` - read sensitivity from schema in JustificanteRepository; `src/aeat/domain/justificante/_repository.py`.
- [x] `P03.S09` - read sensitivity from schema in AttachmentRepository; `src/aeat/domain/attachments/_repository.py`.
- [x] `P03.S10` - declare sensitivity for every modelo in registry TOML; `registry/aeat/modelos/`.

### Phase `P04` - capability-driven modelo gates

Replace hard-wired `_MODELO_100 = "100"` gates with capability flags
on ModeloDefinition.

- [x] `P04.S11` - add capabilities field to ModeloDefinition; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P04.S12` - migrate _borrador_binding to capability lookup; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `P04.S13` - migrate renta ledger default to capability; `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `P04.S14` - declare borrador capability for modelo 100 in registry TOML; `registry/aeat/modelos/100/manifest.toml`.

### Phase `P05` - Modelo 100 registry data backfill

Add per-casilla export_refs and backfill cross_model_output relations
for 2020-2024 revisions.

- [x] `P05.S15` - add per-casilla export_refs to Modelo 100 revision 2025; `registry/aeat/modelos/100/revisions/2025.toml`.
- [x] `P05.S16` - backfill cross_model_output relations for retenciones in 2024 revision; `registry/aeat/modelos/100/revisions/2024.toml`.
- [x] `P05.S17` - backfill cross_model_output relations for 2023 revision; `registry/aeat/modelos/100/revisions/2023.toml`.
- [x] `P05.S18` - backfill cross_model_output relations for 2022 revision; `registry/aeat/modelos/100/revisions/2022.toml`.
- [x] `P05.S19` - backfill cross_model_output relations for 2021 revision; `registry/aeat/modelos/100/revisions/2021.toml`.
- [x] `P05.S20` - backfill cross_model_output relations for 2020 revision; `registry/aeat/modelos/100/revisions/2020.toml`.

### Phase `P06` - identity propagation into filing records

Propagate validated tax identity from the profile substrate into
persistence records.

- [x] `P06.S21` - add subject_tax_id field to FilingDraft; `src/aeat/domain/filing/_schema.py`.
- [x] `P06.S22` - link Attachment to FilingDraft via typed reference; `src/aeat/domain/attachments/_models.py`.
- [x] `P06.S23` - link Justificante to FilingDraft via typed reference; `src/aeat/domain/justificante/_schema.py`.
- [x] `P06.S24` - replace schema_version str with typed RegistrySnapshotRef in draft_id hash; `src/aeat/domain/filing/_schema.py`.

### Phase `P07` - workflow step typed details

Replace WorkflowStep.details: str with a typed union per step kind.

- [x] `P07.S25` - declare WorkflowStepDetails discriminated union; `src/aeat/application/workflow/_models.py`.
- [x] `P07.S26` - thread typed details through WorkflowEngine; `src/aeat/application/workflow/_engine.py`.

### Phase `P08` - form-numeric ↔ semantic casilla bridge

Add a form_number field alongside semantic CasillaId so operators and
machine consumers can reference BOE form numbers.

- [x] `P08.S27` - add optional form_number field to CasillaDefinition; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P08.S28` - backfill form_number values for every BOE-printed casilla; `registry/aeat/modelos/`.
- [x] `P08.S29` - add CLI lookup --form-number on modelo casillas; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `P09` - cross-modelo dependency mechanism unification

Resolve the LiveCrossReferenceDecision vs DependencyClassificationDefinition
parallel-mechanism gap. Type OracleId. Introduce OracleFilingObservation.

- [x] `P09.S30` - declare OracleId typed alias; `src/aeat/domain/calculations/registry/_ids.py`.
- [x] `P09.S31` - tighten LiveCrossReferenceDecision.oracle_id to OracleId | None; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P09.S32` - declare OracleFilingObservation subtype carrying oracle provenance; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `P09.S33` - promote per-modelo relations-empty test contract to registry-wide invariant; `src/aeat/domain/calculations/registry/_validate.py`.

### Phase `P10` - residual export hand-authored coverage

Promote remaining hand-authored export coordinate systems and silent
fallback returns.

- [x] `P10.S34` - convert _ROW_FIELD_CASILLA_BY_RECORD to schema declaration; `src/aeat/domain/calculations/registry/_export.py`.
- [x] `P10.S35` - tighten _export_field_from_row_binding to raise on missing instead of returning None; `src/aeat/domain/calculations/registry/_export.py`.
- [x] `P10.S36` - replace WorkbookParityReference.output_cells str-keyed mapping with typed shape; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P10.S37` - replace fields_by_casilla str key with CasillaId-typed mapping; `src/aeat/domain/calculations/registry/_export.py`.
- [x] `P10.S38` - declare ParityScenario as registry-driven shape - tightened `ParityScenario.registry_outputs` value type from free-form `str` to the typed `CasillaId` (annotated pattern, length bounds); pydantic now rejects malformed casilla identifiers at scenario construction rather than at downstream consumption. File path on disk is `src/aeat/domain/calculations/registry/_parity_tapes.py` (the plan's `application/storage/calc_sheets/` location is stale — the parity-tape model lives in the registry domain). 16 parity-tape tests green.

### Phase `P11` - close-out

TODO: Phase intent paragraph required by the convention ADR.

- [x] `P11.S39` - re-run linkage health dashboard and capture final state; `scratch/out/linkage_health.json`.
- [x] `P11.S40` - update Issue Taxonomy v1 reference with final coverage; `.vault/reference/2026-05-15-linkage-design-audit-reference.md`.
- [x] `P11.S41` - write Wave 4 close-out audit; `.vault/audit/`.
