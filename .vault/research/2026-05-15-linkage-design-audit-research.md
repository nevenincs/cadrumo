---
tags:
  - '#research'
  - '#linkage-design-audit'
date: '2026-05-15'
modified: '2026-06-29'
related: []
---

# `linkage-design-audit` research: `Cross-domain linkage design — raw multi-agent audit record`

Raw, untriaged record of multi-agent audit findings on the cross-domain
linkage design of the AEAT codebase. Eleven agents were dispatched in
three waves (pattern enumeration, structural concerns from multiple
angles, CLI surface exposure) to triangulate convergent gaps in how
modelos, casillas, formulas, bindings, relations, legal references,
export targets, evidence records, and CLI outputs cross-reference each
other.

Scope estimate at time of capture: approximately 5 percent of total
linkage surface mapped. Pydantic-model-consistency-across-internal-
domains audit identified as the natural next target.

This document preserves the verbatim summary each agent returned. It is
the source record. Triage, convergence analysis, and ADR-shaping
synthesis live separately.

## Status

Treat the codebase as fragmented. Not ready for even local use until
the linkage surface has been mechanically verified end-to-end. Scope
mapped at time of capture: approximately 5 percent. This document is
the continuously-expandable reference. Every new finding, every site
flagged for investigation, every name that needs canonicalisation lands
here as a per-row entry. Triage and ADR-shaping happen against this
record.

Audit posture: LLM-driven audits are the discovery layer; mechanical
checks (registry validators, structural tests, lint rules) are the
verification layer. No number of agents produces empirical certainty.
Coverage is measured by `mechanical_checks_written / surface_elements`,
not by `agents_run`. Findings here are inputs to writing those checks.

## Actionable suggestions

Derived from triangulated convergent findings. Ordered by blast radius.

1. Stop the bleed at the canonical drop site. `_actions.py:817`
   discards `engine_result.entries` (the full typed formula trace
   carrying `legal_refs`, `source_refs`, `operand_refs`,
   `operand_values`) before persistence. Persist the entries inside
   `CalculationRevision`. This single change rescues most of the
   downstream linkage erasure called out by F1, F6, F12, F14.
2. Replace the remaining cross-boundary value envelopes.
   Current-state correction on 2026-06-29: the prior-filing
   observation path is now `RegistryModeloObservation.observations:
   tuple[CasillaObservation, ...]` with `modelo: ModeloId` and a
   derived `Mapping[CasillaId, Decimal]` view. The unresolved surfaces
   are `RegistryCalculationResult.values` and
   `CalculationRevision.casilla_values`, plus the relation fold-in
   boundary where typed source observations collapse to bare `Decimal`
   relation values.
3. Promote validation from deferred to load-time. Current-state
   correction on 2026-06-29: snapshot-local typed-ID checks now run
   during `_snapshot.py` construction. Cross-model relation closure is
   intentionally a full-registry gate because a single-model snapshot
   does not carry the source-modelo tree; production authority loads
   run `validate_registry` before snapshots are served.
4. Discriminated unions for every selector. Current-state correction on
   2026-06-29: relation revision and period-alignment selectors are typed
   schema surfaces, binding-derived export record selectors now project
   through typed fixed-field/row-field models, Detalle row-set consumers
   now project through `BindingRowSetSelector`, and
   `DataBindingDefinition.selector` now stores the hydrated source-family
   selector model rather than the raw `BindingSelectorMap` authoring shape.
5. Adopt the typed JSON envelope that already exists. `SchemaEnvelope`
   / `register_schema` / `emit_json_success` in
   `core/json_contract.py` are written but unused. Apply them to every
   modelo work-lifecycle command. Add typed `context` keys to
   `RegistryValidationError` / `RegistrySnapshotError` carrying the
   failing casilla/formula/binding id.
6. Currentized 2026-06-29: the Renta first-slice finding no longer
   matches the old unvalidated-import shape. The routing table now
   lives in `domain/renta/_first_slice_routing.py`, `_ledger_expenses`
   re-exports the same object, and snapshot construction installs a
   `CrossDomainSnapshotCheck` before `check_all_id_references` runs.
   The registry consumes Renta observations through a Protocol, not a
   direct `domain.renta` import.
7. Canonicalise CCAA. Pick one of `RentaCCAA` 3-letter codes,
   `domain/profile/_ccaa.CCAA` full names, or the dispatch-table
   lowercase strings. Delete the other two. Add a converter only at
   the profile binding resolution point.
8. Add referential-integrity sweep at load. For every ID type in
   `_ids.py` (21 currently), declare which field-of-which-model
   references it, then walk all references on snapshot build and
   assert existence. `validation_refs` must be checked.
9. Schema-attach sensitivity classification. `ModeloDefinition`
   and/or `CasillaDefinition` declare `output_sensitivity:
   SensitivityClass`. Repositories assert at write time.
10. Surface linkage state to operators. `aeat app modelo formulas`
    and `aeat app review view` must print `legal_refs` / `source_refs`
    in text mode. Add a registry-integrity diagnostic to `aeat config
    repair`.

These map onto the umbrella-ADR scope proposed by Wave 2 Agent 11.

## Convergent findings (synthesis)

Each finding is tagged with the number of independent witnesses (agents
landing on it from different framings). Findings with ≥3 witnesses are
treated as high-confidence; ≥2 as strong; single-witness items are
captured here for visibility but require additional triangulation
before promotion.

### Tier 1 — ≥3 witnesses

- F1. `Mapping[str, Decimal]` is the universal cross-boundary value
  envelope. Witnesses: cross-modelo · schema↔registry · end-to-end
  trace · CLI inventory · CLI JSON contract · CLI command trace (6).
  Root drop site: `_actions.py:817`.
- F2. Validation was historically deferred, conditional, and
  operationally invisible. Current-state correction on 2026-06-29:
  production registry access flows through `ValidatedRegistryAuthority`,
  which runs full `validate_registry`; remaining F2 work should target
  standalone diagnostics and selector-shape gaps, not relation closure
  through the production snapshot path.
- F3. Untyped selector sub-schemas. Witnesses: cross-modelo ·
  schema↔registry · end-to-end trace · type-system escapes (4).
  `DataBindingDefinition.selector` acts as 10+ sub-schemas keyed by
  `source`.
- F4. Sensitivity classification has no schema attachment point.
  Witnesses: secure storage · ADR coverage · new-modelo stress (3).
  Hard-coded at repository write sites only.
- F5. No registry-wide referential integrity gate. Witnesses:
  schema↔registry · cross-modelo · new-modelo stress · TOML data
  layer · type-system escapes (5). `CasillaDefinition.validation_refs`
  has no `_missing_refs` call.
- F6. Legal/source refs exist but never reach the operator.
  Witnesses: schema↔registry · CLI inventory · CLI JSON contract ·
  operator surface (4).

### Tier 2 — 2 witnesses

- F7. `domain/calculations/registry/_bindings.py:12` imports from
  `domain/renta/`. Witnesses: renta drift · pattern sweep.
- F8. Currentized 2026-06-29: the old unvalidated
  `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` finding is closed as a
  defect. The current design keeps a Renta-owned first-slice routing
  table and validates its casilla targets at snapshot construction.
- F9. `SchemaEnvelope` typed JSON contract exists but is never used.
  Witnesses: CLI inventory · CLI JSON contract (2, both grep-
  confirmed).
- F10. Form numeric casilla number is unrepresented in the type
  system. Witnesses: end-to-end trace · CLI inventory · ADR coverage
  (3).
- F11. CLI cannot supply relation/prior-filing values for cross-
  modelo calculation. Witnesses: CLI end-to-end trace · new-modelo
  stress · cross-modelo (3).
- F12. Two parallel mechanisms for cross-modelo dependency, no
  disambiguator. Witnesses: cross-modelo · new-modelo stress · ADR
  coverage (3).
- F13. Three competing CCAA enums coexist. Witness: renta drift (1
  agent, but concrete and grep-verifiable).

### Tier 3 — single-witness signals worth ADR mention

- F14. Linkage error context is untyped — failing IDs only inside
  `ErrorEnvelope.message` free text. Witness: CLI JSON contract.
- F15. M100 has zero per-casilla `export_refs`; entire export is an
  opaque `xml_dictionary` blob. Witness: renta drift.
- F16. `cross_model_output` relations for retenciones exist only in
  M100 2025; 2020–2024 lack them despite same legal obligation.
  Witness: renta drift.
- F17. Three independent coordinate systems for the same casilla
  (`ExportFieldDefinition` byte-offset, `SheetCellAddress` A1,
  `RecordFieldSpec` BOE byte-offset). Witness: export linkage.
- F18. BOE fichero specs (`_RECORD_SPECS` tuples in
  `_formats/modelo_*_*.py`) are hand-authored from BOE PDFs, no
  structural test coupling. Witness: export linkage.
- F19. `_borrador_binding.py:_MODELO_100 = "100"` is a permanent
  exclusive gate. Witness: export linkage.
- F20. No typed link `FilingDraft ↔ Justificante ↔ Attachment`.
  Witness: secure storage.
- F21. `work_unit_id` is bare `str` through 5 layers;
  `str(work_unit.modelo)` required to call `authority.snapshot()`.
  Witness: CLI end-to-end trace.

### Audits already named for the next round

- A1. Pydantic-model-consistency / same-semantic-concept-multiple-
  shapes catalogue.
- A2. Enum proliferation across the codebase.
- A3. Domain ↔ application ↔ adapter directionality.
- A4. Repository / persistence shape vs domain entity shape.
- A5. Test contract shape vs production validator coverage.
- A6. Identifier-existence-check coverage per ID type.

## Per-row inventory of sites needing investigation

Running reference. Each row is a single concrete site, symbol, or
artifact that has been named by at least one audit. New rows append
as audits surface more. Status column tracks promotion to mechanical
check or fix. Defect-class abbreviations:

- A. Untyped string keys at cross-boundary value envelopes
- B. Untyped selector sub-schemas
- C. Deferred or absent validation
- D. Multi-shape concept (same semantic, different types)
- E. Hard-coded constants outside registry
- F. Architecture boundary violation
- G. CLI / operator output erasure
- H. Documentation drift or missing implementation
- I. Missing existence check for typed ID
- J. Hard-wired per-modelo gate
- K. Type-system escape (cast, Any, type: ignore)
- L. Hand-authored data with no schema coupling

Status legend: `open`, `check-written`, `fixed`, `wontfix-document`,
`regressed` (claimed fixed but re-audit found the anti-pattern still
present), `partial` (some of the claim landed; the full structural
fix did not), `unverified` (the symbol moved or was renamed in a way
the re-audit script could not match).

A late re-audit found that several "fixed" claims were optimistic.
The verdicts below reflect the re-audit run at `scratch/out/reaudit_inventory.json`
where it produced a definitive result; rows the re-audit did not
check carry their original execution-time status with a `(unverified
by re-audit)` qualifier.

| Row | Site | Symbol / concept | Class | Witnesses | Status |
|-----|------|------------------|-------|-----------|--------|
| R001 | `src/aeat/application/modelo/_actions.py:817` | `dict(engine_result.values)` discards `engine_result.entries` | A | F1, F12, F14| verified (re-audit) — no dict-cast of engine_result.values |
| R002 | `domain/calculations/registry/_bindings.py:278-329` | `RegistryModeloObservation.observations: tuple[CasillaObservation, ...]` with derived `Mapping[CasillaId, Decimal]` view | A | F1 (6)| verified/currentized (2026-06-29) — typed observation envelope and typed `modelo: ModeloId` |
| R003 | `domain/calculations/registry/_formula_runtime.py:36-47` | `RegistryCalculationResult.values: Mapping[str, Decimal]` | A | F1| regressed (re-audit) — RegistryCalculationResult.values still Mapping[str, Decimal] |
| R004 | `domain/calculations/registry/_formula_runtime.py:43` | `values` map merges bound/computed/informational casillas | A | F1| regressed (re-audit) — RegistryCalculationResult.values still Mapping[str, Decimal] |
| R005 | `domain/modelos/_calculation_revision.py:148,202` | `CalculationRevision.casilla_values` keys `str` | A | F1| regressed (re-audit) — CalculationRevision.casilla_values still Mapping[str, Decimal] |
| R006 | `entrypoints/cli/_modelo.py:851-892` | `_calculation_revision_payload` serialises `dict[str, str]` | A,G | F1, F6| partial (re-audit) — no clear payload model match |
| R007 | `domain/calculations/registry/_schema.py:839` | `DataBindingDefinition.selector: BindingSelector` | B | F3| closed (2026-06-29 current-state recheck) — raw selector maps are authoring/input payloads only; constructed bindings store hydrated per-source selector models, all 1,060 bundled bindings scan as concrete selector model instances, and binding-derived export records, Detalle row-set consumers, and public binding query rows use typed projections |
| R008 | `domain/calculations/registry/_schema_surfaces.py` | `RelationDefinition.source_revision_selector: RelationRevisionSelector` | B | F3| closed (2026-06-29 current-state recheck) — relation source revision selector is a typed model; legacy `revision`/`revision_id` aliases and mixed absolute/relative selectors are rejected at construction |
| R009 | `domain/calculations/registry/_schema_surfaces.py` | `RelationDefinition.period_alignment: RelationPeriodAlignment` | B | F3| closed (2026-06-29 current-state recheck) — period alignment is a typed model; empty maps and retired `same_period` mode are rejected at construction |
| R010 | `domain/calculations/registry/_bindings.py:884,1047,1147` | `model_validate(dict(binding.selector))` at handler call only | B,C | F3| verified (re-audit) — no model_validate(dict(...)) pattern |
| R011 | `domain/calculations/registry/_schema_surfaces.py:472-484` | `RelationDefinition.source_casilla_id: CasillaId`; legacy `source_output` rejected | I | F1| closed (2026-06-29 current-state recheck) — no `RelationDefinition.source_output` field or production `relation.source_output` access remains |
| R012 | `domain/calculations/registry/_schema.py:923-929` | `AlgorithmBindingDefinition.target/inputs/outputs` accept bare `str` | I | F3, F5| verified (re-audit) — typed IDs only |
| R013 | `domain/calculations/registry/_relations.py:40-60` | `RegistryFoldRequirement.source_modelo: ModeloId`, `source_casilla_ids: tuple[CasillaId, ...]` | A | F1| closed (2026-06-29 current-state recheck) — retired `RegistryRelationSourceRequirement`/`source_output` shape replaced by unified typed fold requirement; previous-filing/relation-prefill source selectors and filed/applicability modelo records now use `ModeloId` |
| R014 | `domain/calculations/registry/_relations.py:118-139` | relation requirements group by `relation.source_casilla_id` without `str(source_output)` coercion | A,D | F1| closed (2026-06-29 current-state recheck) — exact production grep finds no `relation.source_output`; legacy `source_output` hits are rejection tests/helpers only |
| R015 | `domain/calculations/registry/_relations.py` / `_validate_relation_periods.py` | typed `RelationRevisionSelector` attributes replace raw `selector.get("year")` / `.get("filing_year_delta")` dict probes | B,C | F3| closed (2026-06-29 current-state recheck) — no production `relation.source_revision_selector.get(...)` path remains |
| R016 | `domain/calculations/registry/_record_design_coverage.py:104` and `domain/calculations/registry/_bindings.py:459` | record-design closure asks `binding_source_modelo(binding)` instead of peeking at `binding.selector.get("source_modelo")` | B,C | F3| closed (2026-06-29 current-state recheck) — no production `.get("source_modelo")` lookup remains; exact hits are test-only |
| R017 | `domain/calculations/registry/_validate_relation_sources.py:45` and `domain/calculations/registry/_authority.py:256` | relation closure runs at full-registry validation, and production authority validates the full tree at load | C | F2, F5| closed (2026-06-29 current-state recheck) — single-model `build_snapshot` cannot validate cross-model closure by design; production snapshots are served only after `ValidatedRegistryAuthority.load` runs `validate_registry` |
| R018 | `domain/calculations/registry/_snapshot.py:174` | snapshot build runs `check_all_id_references` after legal/source ref collection | C | F2, F5| closed (2026-06-29 current-state recheck) — missing legal/source refs now fail snapshot construction rather than only `validate_modelo` |
| R019 | `domain/calculations/registry/_schema.py:831` | `CasillaDefinition.validation_refs` has no `_missing_refs` call | C,I | F5| closed (2026-06-29 current-state recheck) — the dead `validation_refs` field has been removed; exact grep finds it only in historical vault prose |
| R020 | `domain/calculations/registry/_schema.py:533` | `WorkbookParityReference.fixture_id: WorkbookFixtureId` has typed shape but no fixture-catalogue lookup | I | F5| partial (2026-06-29 current-state recheck) — the bare-string finding is closed; fixture IDs are pattern-constrained and still not resolved against a declared fixture catalogue |
| R021 | `domain/calculations/registry/_snapshot.py:174` | `check_all_id_references(snapshot)` is wired into snapshot construction | I | F5| closed (2026-06-29 current-state recheck) — `_snapshot.py` installs cross-domain checks, builds the `RegistrySnapshot`, and runs the 21-typed-ID integrity gate before returning |
| R022 | `application/filing/runtime.py:78` | `RegistryCasillaSchema` dataclass — `str` IDs, `float\|int\|None` bounds | D | schema↔registry| partial (re-audit) — RegistryCasillaSchema name still present |
| R023 | `domain/filing/_protocols.py:38,103` | `CasillaSchema` Protocol — duck-typed, no legal_refs | D,G | schema↔registry, F6| verified (re-audit) — Protocol declares legal_refs |
| R024 | `domain/calculations/registry/_schema.py:882` vs `application/filing/runtime.py:78` vs `domain/filing/_protocols.py:38` | Three shapes of "casilla schema" | D | schema↔registry| regressed (re-audit) — 2 schemas still: [('runtime.py', 'RegistryCasillaSchema'), ('_protocols.py', 'Ca |
| R025 | `domain/renta/_first_slice_routing.py:26-67` | Renta-owned first-slice routing table | E | F8| closed/accepted current design (2026-06-29 recheck) — table is the canonical Renta routing source and snapshot-time integrity asserts every target casilla exists on Modelo 100 |
| R026 | `domain/renta/_ledger_expenses.py:240` | Observation validator checks against the canonical first-slice routing table | E | F8| closed/accepted current design (2026-06-29 recheck) — `_ledger_expenses` re-exports the same table object and tests guard against forked mappings |
| R027 | `domain/calculations/registry/_bindings.py:1160` | Re-validates `target_casilla` against the constant | E | F8| verified (re-audit) — no cross-package constant reference |
| R028 | `domain/calculations/registry/_bindings.py:12` | Registry imports from `domain/renta/` | F | F7| verified (re-audit) — renta import inverted |
| R029 | `domain/renta/_substrate.py:49-83` | `RentaCCAA` 3-letter codes | D | F13| verified (re-audit) — RentaCCAA migrated |
| R030 | `domain/profile/_ccaa.py:13` | `CCAA` full names | D | F13| verified (re-audit) — factory methods present |
| R031 | `registry/aeat/modelos/100/revisions/2025.toml:6430` | Dispatch table uses `madrid`/`andalucia`/`cataluna` lowercase | D | F13| verified (re-audit) — no lowercase CCAA labels in M100 2025 dispatch |
| R032 | `registry/aeat/modelos/100/revisions/2025.toml` | Zero per-casilla `export_refs`; XML dictionary only | L | F15| verified (re-audit) — export_refs present |
| R033 | `registry/aeat/modelos/100/revisions/2025.toml:8249-8386` vs `2020-2024.toml` | `cross_model_output` relations only in 2025 | L | F16| verified (re-audit) — cross_model_output present for 2020-2024 |
| R034 | `application/modelo/_borrador_binding.py:27,79,98,179` | `_MODELO_100 = "100"` exclusive gate | J | F19| verified (re-audit) — capability flag used |
| R035 | `application/aggregation/_renta_ledger.py:91` | `modelo: str = Field(default="100", ...)` | J | export| verified (re-audit) — default removed or capability-driven |
| R036 | `core/classification/__init__.py:30` | `SensitivityClass` enum, no schema-side attachment | C | F4| verified (re-audit) — schema-side sensitivity field present |
| R037 | `domain/justificante/_repository.py:82` | `SensitivityClass.AUDIT` hardcoded | C,J | F4| verified (re-audit) — reads output_sensitivity from schema |
| R038 | `domain/attachments/_repository.py:90` | `SensitivityClass.FINANCIAL` hardcoded | C,J | F4| unverified (re-audit script could not match symbol) — neither pattern present |
| R039 | `domain/justificante/_schema.py:30` | `Justificante` — no link to `FilingDraft` | D | F20| wontfix-document (re-audit confirmed) — no filing draft link |
| R040 | `domain/attachments/_models.py:69,114` | `Attachment` — no link to `FilingDraft` or `Justificante` | D | F20| wontfix-document (re-audit confirmed) — no filing draft link |
| R041 | `domain/filing/_schema.py:136,158` | `FilingDraft.schema_version: str` bare string | A,I | F20| wontfix-document (re-audit confirmed) — still bare str schema_version |
| R042 | `domain/calculations/registry/_filed_state.py:22,33` | `RegistryFiledStateComparison`/`Drift` — no artifact key | D | secure storage| wontfix-document (re-audit confirmed) — no artifact key |
| R043 | `core/json_contract.py:75,167,259-274` | `SchemaEnvelope` / `emit_json_success` — zero callers | H | F9| verified (re-audit) — 20 register_schema sites |
| R044 | `entrypoints/cli/_modelo.py` (all `_emit` sites) | Ad-hoc `dict` payloads bypass `SchemaEnvelope` | G,H | F9| verified (re-audit) — no raw dict emits |
| R045 | `domain/calculations/registry/_errors.py` | `RegistryValidationError` / `RegistrySnapshotError` — no typed `context` | G | F14| regressed (re-audit) — no typed context |
| R046 | `entrypoints/cli/_modelo.py:500-518` | `aeat app modelo formulas` text omits `legal_refs` | G | F6| partial (re-audit) — formulas command exists but no legal_refs in body |
| R047 | `entrypoints/cli/_review.py:16-37,40-63` and `_operator.py:126-182` | `review queue/view` strips `FilingValidationFinding.source` | G | F6| partial (re-audit) — no clear surfacing |
| R048 | `application/diagnostics.py:144-217` | `aeat config repair` five checks, zero cross-domain | C,G | F2| partial (re-audit) — still secure-objects scope only |
| R049 | `application/repair_integrity.py:1-180` | Repairs only `secure_objects` decryptability; no linkage repair | C,H | F2| open (re-audit confirmed) — still secure_objects only |
| R050 | `entrypoints/cli/_modelo.py:1044+` | CLI work calculate accepts no `--relation` flag | H | F11| regressed (re-audit) — --relation flag absent on work_calculate |
| R051 | `entrypoints/cli/_modelo.py:1000` and `application/modelo/_actions.py:785` | `relation_values` defaults to empty dict | H | F11| verified (re-audit) — relation_values param present |
| R052 | `entrypoints/cli/_config/_google.py:664-740` | Export CLI docstring documents `--prefill-relations`; flag absent in code | H | F11| verified (re-audit) — flag/param present |
| R053 | `entrypoints/cli/_config/_google.py:643-661` | `_load_snapshot` does not catch `RegistrySnapshotError` | C | CLI trace| regressed (re-audit) — RegistrySnapshotError not handled in google export |
| R054 | `application/modelo/_actions.py:752` | `str(work_unit.modelo)` coercion required at registry boundary | D | F21| regressed (re-audit) — still str() coercion of work_unit.modelo |
| R055 | `entrypoints/cli/_modelo.py:933-940` | `work_unit_id` and `--casilla` parsed as bare `str` | A | F21| verified (re-audit) — validator wraps parse |
| R056 | `domain/calculations/registry/_loader.py:73,77,167,172` | `model_validate` over raw TOML `dict[str, Any]` | K | type escapes| verified (re-audit) — no dict[str, Any] |
| R057 | `adapters/persistence/storage/bucket/_manifest_io.py:115,120` | `tomllib.loads()` → `dict[str, Any]` before `model_validate` | K | type escapes| regressed (re-audit) — still dict[str, Any] from tomllib.loads |
| R058 | `adapters/outbound/aeat/auth/_session_store.py:26-27,43` | `storage_state: dict[str, Any]` | K | type escapes| regressed (re-audit) — storage_state still dict[str, Any] |
| R059 | `adapters/outbound/aeat/auth/_authenticator.py:317,920` | Same storage_state cast | K | type escapes| regressed (re-audit) — still dict[str, Any] |
| R060 | `adapters/outbound/aeat/browser/session.py:69`, `_factory.py:76,176` | Browser context storage_state untyped | K | type escapes| partial (re-audit) — 4 dict[str, Any] sites in browser context |
| R061 | `adapters/outbound/aeat/auth/_providers.py:135,147` | `build_context_kwargs() -> Mapping[str, Any]` | K | type escapes| verified (re-audit) — build_context_kwargs typed |
| R062 | `application/aggregation/_iva_ledger.py:165` | `issue_common: dict[str, Any]` spread into pydantic ctor | K | type escapes| verified (re-audit) — issue_common typed |
| R063 | `application/aggregation/_renta_ledger.py:199` | Same spread pattern | K | type escapes| verified (re-audit) — renta_ledger issue_common typed |
| R064 | `adapters/outbound/google/_calc_sheets_apply.py:292-606` | Google Sheets API request bodies raw dicts | K | type escapes| partial (re-audit) — 22 dict[str, Any] in google apply |
| R065 | `adapters/outbound/google/_calc_sheets_pull.py:221-231` | 9 magic-key extractions from spreadsheet metadata | K,L | type escapes| verified (re-audit) — magic-key extraction count below threshold |
| R066 | `adapters/outbound/storage/_local.py:252-337` | Sidecar TOML navigated by magic keys; defaults empty silently | K,L | type escapes| verified (re-audit) — no obvious magic-key markers |
| R067 | `adapters/outbound/storage/_google_drive.py:229-680` | Drive file metadata navigated as raw dicts | K | type escapes| partial (re-audit) — 6 dict[str, Any] sites |
| R068 | `adapters/outbound/aeat/sede/_declarations.py:621-623` | `action_indexes.get("justificante")` / `submitted_file` / `declaration_pdf` magic keys | K,L | type escapes| regressed (re-audit) — still raw .get() magic keys |
| R069 | `adapters/outbound/llm/_cache.py:148,264,277,288` | LLM cache payload cast + magic-key navigation | K | type escapes| partial (re-audit) — type escapes still present |
| R070 | `adapters/persistence/storage/master_key/_master_key.py:586` | `preview.get("version")` magic key | K | type escapes| regressed (re-audit) — preview.get('version') still raw |
| R071 | `domain/calculations/registry/_schedules.py:71` | `_resolve_profile_fact` dotted-string traversal | C | type escapes top-10| partial (re-audit) — still dotted-string traversal |
| R072 | `application/aggregation/_registry_provider.py:161` | `# type: ignore[arg-type]` on `source_kind: str` | K | type escapes| verified (re-audit) — no type-ignore on source_kind |
| R073 | `domain/calculations/registry/_bindings.py:1242` | `CounterpartAggregationObservation.source_kind: str`, no Literal | I | type escapes| regressed (re-audit) — source_kind still bare str |
| R074 | `domain/calculations/registry/_queries.py:368,378` | `_public_mapping` recursive type erasure | K,G | type escapes| partial (re-audit) — _public_mapping still present |
| R075 | `domain/calculations/registry/_queries.py:99` | Public query exposes `selector: Mapping[str, object]` | G | type escapes| regressed (re-audit) — public query selector still Mapping[str, object] |
| R076 | `domain/calculations/registry/_legal.py:15` | Module-level `cast(...)` on legal source table | K | type escapes| verified (re-audit) — no module-level cast() |
| R077 | `application/registry/_corpus.py:846` | `cast(RuleKind, kind)` after manual membership check | K | type escapes| regressed (re-audit) — cast(RuleKind, ...) still present |
| R078 | `adapters/outbound/aeat/sede/_renta_web_open.py:106,363` | Playwright result `cast(Any, ...)` | K | type escapes| verified (re-audit) — no cast(Any, ...) |
| R079 | `domain/modelos/_calculation_revision.py:337,346` | `# type: ignore[override]` on `__iter__` + `isinstance(key, str)` discrimination | K | type escapes| verified (re-audit) — no type-ignore overrides |
| R080 | `domain/modelos/_work_unit.py:198,268,277` | Coerce validator + cast + type: ignore[override] | K | type escapes| verified (re-audit) — no type-ignore overrides |
| R081 | `domain/modelos/_filing_record.py:169,282` | Same pattern | K | type escapes| verified (re-audit) — no type-ignore overrides |
| R082 | `domain/modelos/_verification_report.py:201` | Same pattern | K | type escapes| verified (re-audit) — no type-ignore overrides |
| R083 | `application/aggregation/_models.py:88,127,129,146,160,174` | Period parse isinstance + computed_field type: ignore | K | type escapes| verified (re-audit) — no type-ignores |
| R084 | `application/aggregation/_service.py:178` | computed_field type: ignore | K | type escapes| verified (re-audit) — no type-ignores |
| R085 | `adapters/persistence/storage/_rotation.py:333,446` | `settings: Any` parameter | K | type escapes| verified (re-audit) — rotation settings typed |
| R086 | `adapters/outbound/google/_calc_sheets_pull.py:202,261,468,491,504` | `isinstance(value, str)` discrimination on sheet cells | K | type escapes| verified (re-audit) — discriminations replaced |
| R087 | `application/storage/calc_sheets/_layout.py:105-136` | `SheetCellAddress` — workbook coords for Google sheet path | L | export| verified (re-audit) — SheetCellAddress typed address class exists |
| R088 | `adapters/outbound/aeat/export/_formats/_record_spec.py` (all per-modelo modules) | `_RECORD_SPECS` hand-authored from BOE PDFs | L | F18| open (re-audit confirmed) — 2 hand-authored spec files, no legal_refs |
| R089 | `domain/calculations/registry/_export.py:31` | `fields_by_casilla: Mapping[str, ...]` — str key | A,I | F17| regressed (re-audit) — fields_by_casilla still bare Mapping[str, ...] |
| R090 | `domain/calculations/registry/_export.py:130-148` | `_ROW_FIELD_CASILLA_BY_RECORD` static dict, returns None silently | E,L | export| verified (re-audit) — row_field_casillas read from schema |
| R091 | `domain/calculations/registry/_export.py:163-166` | `_export_field_from_row_binding()` returns None on missing | C | export| verified (re-audit) — raises on missing or removed |
| R092 | `domain/calculations/registry/_schema.py:429` | `WorkbookParityReference.output_cells: Mapping[str, str]` | A,I | F17| verified (re-audit) — output_cells typed |
| R093 | `application/storage/calc_sheets/_parity_tapes.py:34-65` | `ParityScenario` manually curated; cell refs hand-typed | L | export| verified (re-audit) — ParityScenario schema-coupled or removed |
| R094 | `core/identity/` | Identity is validation primitive only — no propagation into filing records | D,G | CLI JSON| verified (re-audit) — identity imported by filing |
| R095 | `domain/filing/_schema.py:151` | `FilingDraft` has no `subject_tax_id` field | D | F14| partial (re-audit) — only profile_tax_id present (bare str) |
| R096 | `domain/filing/_schema.py` | `FilingDraft.schema_version` participates in `draft_id` hash as bare string | A | F20| regressed (re-audit) — still schema_version: str |
| R097 | `application/workflow/_models.py:297` | `WorkflowStep.details: str` — typed linkage objects not threaded | G | operator | regressed (`details: dict[str, str] \| regressed (re-audit) — details still dict[str, str] |
| R098 | Form numeric casilla numbers (e.g. M303 "46") | Not present in any registry data — only semantic IDs | D,H | F10| verified (re-audit) — form_number declared on M303 |
| R099 | `domain/calculations/registry/_snapshot.py:110-112,140-142` | `LiveCrossReferenceDecision` policy metadata vs `DependencyClassificationDefinition` treatment | D | F12| verified (re-audit) — both types exist; policy/treatment separated |
| R100 | `registry/aeat/modelos/232.toml` + `test_modelo_232_registry.py:62-67` | Per-modelo test enforces `relations == ()`; not a registry-wide invariant | C | F12| verified (re-audit) — informative-class invariant in validator |
| R101 | `domain/calculations/registry/_schema.py:281-420` | `LiveCrossReferenceDecision.oracle_id: str \| None` — not `OracleId` typed | I | cross-modelo | regressed (`oracle_id: str \| regressed (re-audit) — still str | None |
| R102 | (no file) | No `OracleFilingObservation` subtype to mark oracle-originated vs locally computed values | D | cross-modelo| regressed (re-audit) — no OracleFilingObservation subtype |

Inventory will expand row-by-row as additional audits land. New rows
append to the end; the `Row` column is stable once issued. Status
updates happen in place.

## Surface enumeration (denominators)

Programmatic codebase census (1126 `.py` files under `src/aeat/`) to establish quantitative denominators for linkage-defect coverage metrics. Each query enumerates a specific surface class. Counts are exact; samples are representative excerpts. No analysis — pure enumeration. Scope: `src/aeat/` unless otherwise specified.

### 1. Pydantic-model ID type declarations (`= Annotated[str, Field(`)

**Count: 1 file, 21 type declarations**
**Location:** `src/aeat/domain/calculations/registry/_ids.py`

All 21 ID types use `Annotated[str, Field(pattern=...)]` except `ModeloId` which uses `min_length=1`. Sample:
- `ModeloId = Annotated[str, Field(pattern=r"^\d{3}$")]`
- `RevisionId = Annotated[str, Field(min_length=1, max_length=128, pattern=...)]`
- `CasillaId`, `FormulaId`, `ParameterId`, `BindingId`, `RelationId`, `LegalRefId`, `SourceRefId`, `ExtractionProfileId`, `CrossReferenceId`, `WorkbookParityRefId`, `VerificationExpectationId`, `ApplicationLinkId`, `DeadlineWindowId`, `SupportRemovalDecisionId`, `ConstructId`, `DependencyClassificationId`, `ExportLayoutId`, `RecordId`, `ExportFieldId` (19 more at same location).

### 2. `Mapping[str, ...]` field declarations in domain models

**Count: 116 occurrences across 19 files**
**Location:** `src/aeat/domain/` with heaviest concentration in `calculations/registry/`

Samples (10 of 116):
- `src/aeat/domain/buckets/_event.py:241:    events: Mapping[str, BucketEvent]`
- `src/aeat/domain/modelos/_calculation_revision.py:197:    inputs_snapshot: Mapping[str, str]`
- `src/aeat/domain/modelos/_calculation_revision.py:202:    casilla_values: Mapping[str, Decimal]`
- `src/aeat/domain/invoices/_models.py:485:    invoices: Mapping[str, Invoice]`
- `src/aeat/domain/transactions/_models.py:748:    transactions: Mapping[str, Transaction]`
- `src/aeat/domain/calculations/registry/_formula_runtime.py:43:    values: Mapping[str, Decimal]`
- `src/aeat/domain/calculations/registry/_formula_runtime.py:50:    inputs: Mapping[str, Decimal]`
- `src/aeat/domain/calculations/registry/_bindings.py:74:    casilla_values: Mapping[str, Decimal]`
- `src/aeat/domain/calculations/registry/_schema.py:817:    selector: Mapping[str, str|int|...]`
- `src/aeat/domain/calculations/registry/_export.py:30:    fields_by_id: Mapping[str, ExportFieldDefinition]`

### 3. `dict[str, Any]` / `Dict[str, Any]` declarations

**Count: 33 files**

Grouped by package:
- **adapters**: 16 files (auth, google sheets, AEAT browser/sede, storage, persistence, outbound services)
- **application**: 8 files (workflow, invoices, ledger, filing, aggregation, test)
- **domain**: 6 files (transactions, invoices, calculations/registry, deadlines, vat)
- **core**: 2 files (logging, observability)
- **entrypoints**: 1 file (CLI tests)

Notable: 15 distinct `dict[str, Any]` usages; most in outbound adapters and persistence layer.

### 4. `Mapping[str, Any]` declarations

**Count: 50 files**

Heaviest in:
- `domain/calculations/registry/`: 18 files (oracle tests, formula runtime, export, schema definition, workbook parity, validation)
- `domain/vat/`, `domain/categories/`: parsing utilities
- `adapters/outbound/aeat/`: auth/sede provider queries

Usage: mostly function parameters accepting untyped dict or mapping at boundaries (TOML load, API response, browser context store).

### 5. `cast(` calls

**Count: 100 total occurrences** (27 files)

Grouped by context:
- Type narrowing after runtime checks: ~45 (legal catalog, rule kind cast after membership check)
- Browser/playwright cast to Any: ~15
- Tuple casting in __iter__ overrides: ~12
- Model constructor spread coercion: ~10
- Miscellaneous narrowing: ~18

Top files: `_legal.py`, `_corpus.py`, `_renta_web_open.py`, aggregation models.

### 6. `# type: ignore` comments

**Count: 85 occurrences** (71 files)

Breakdown by error code (observed in brackets):
- `[misc]`: 32 (forced field mutation in frozen models for testing)
- `[override]`: 9 (__iter__ + isinstance(key, str) patterns)
- `[attr-defined]`: 6 (accessing private attributes in tests)
- `[prop-decorator]`: 6 (computed_field decorator on @property)
- `[arg-type]`: 6 (raw dict or untyped values to typed constructors)
- `[index]`, `[assignment]`, `[type-arg]`: 1 each

Primary use: testing (field mutation with frozen=True) and computed_field decorator type annotation issues.

### 7. `isinstance(x, str)` discriminations

**Count: 15 occurrences**

Samples (10 of 15):
- `src/aeat/locales/_ast_scanner.py:67,85,100`: isinstance checks on AST Constant values in string literal scanning
- `src/aeat/domain/_identifiers.py:23`: modelo validation
- `src/aeat/application/calculations/_binding_prefill.py:89,154`: source periods discriminator
- `src/aeat/application/filing/__init__.py:308,353`: row key / value dispatch
- `src/aeat/entrypoints/cli/_modelo.py:492`: None or empty-string check
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py:215,226,233`: TOML field dispatch

### 8. `model_validate(` call sites

**Count: 86 occurrences** (41 files)

Breakdown (rough):
- **Typed value (model/pydantic obj)**: ~35 (fixture data, schema transitions, model upconversion)
- **Untyped dict/mapping**: ~45 (TOML load, API response, browser context, fixture builders)
- **Raw `dict(...)` constructor**: ~6 (discarding from mapping, transformation)

Notable: 11 sites use `model_validate` on `dict[str, Any]` directly after deserialization with zero prior validation.

### 9. Cross-package imports inside `src/aeat/domain/`

**Count: 424 cross-package imports** (imports from outside `domain/`)

Breakdown by target:
- **from ...core**: ~180 (errors, i18n, logging, paths, identity)
- **from ...adapters**: ~120 (storage, persistence, outbound services)
- **from ...application**: ~70 (filing, workflow, aggregation)
- **from ..submission** (sibling domain): ~30
- **from ..core.errors**: ~24

Current-state correction (2026-06-29): the old F7 import path is gone.
The registry-side Renta resolver in `_ledger_bindings.py` consumes a
structural Protocol and does not import `domain.renta`; the concrete
Renta first-slice integrity check is registered through the
`CrossDomainSnapshotCheck` extension point.

### 10. TOML key access via `.get("magic_string")` patterns

**Count: 34 occurrences** (7 files)

Locations:
- `adapters/outbound/google/_calc_sheets_pull.py`: 9 (spreadsheet metadata: "values", "data", "userEnteredValue", etc.)
- `adapters/outbound/aeat/sede/_declarations.py`: 3 ("justificante", "submitted_file", "declaration_pdf")
- `adapters/outbound/llm/_cache.py`: 4 ("model", "usage", "content", etc.)
- `adapters/outbound/storage/_google_drive.py`: 6 (drive file metadata)
- `adapters/persistence/storage/master_key/_master_key.py`: 1 ("version")
- `adapters/outbound/storage/_local.py`: 3+ (sidecar TOML)
- Persistence bucket manifest: 2 (load/save roundtrip)

All silently default to None on missing key with no schema validation.

### 11. Pydantic models: `extra="forbid"` vs without

**Count: 360 with `extra="forbid"`**
**Count: 411 with `ConfigDict(`**

All 360 occurrences of `extra="forbid"` appear as inline `ConfigDict(extra="forbid")` or standalone `ConfigDict`. No models detected with `extra="allow"` or `extra="ignore"` explicitly set. Default behavior varies by pydantic v2 placement.

### 12. Discriminated-union usages

**Count: 5 total** (Discriminator or `discriminator=` keyword)

Locations:
- `domain/calculations/registry/_schema.py`: discriminated union definitions (query expressions, selector types)
- `domain/filing/_schema.py`: filing finding union
- Test fixtures and oracle models

Use: minimal. Most polymorphism handled via `Literal[...]` enums without discriminator, or raw `str` fields.

### 13. `Literal[` declarations (discriminator candidates)

**Count: 195 occurrences**

Spread across domain, application, adapters. High concentration in:
- Registry schema (parameter kind, binding type, output type, selector operator, filing status)
- CLI command enums (filing status, workflow step, diagnostic code)
- Validation error kinds

Most unattached to discriminated unions; used as field type constraints only.

### 14. Modelo number string literals (hardcoded gates)

**Count: 1005 total occurrences** (including registry data files)

Representative sample (non-registry candidates):
- `src/aeat/application/modelo/_borrador_binding.py:27,79,98,179`: `_MODELO_100 = "100"` (exclusive gate for export binding)
- `src/aeat/application/aggregation/_renta_ledger.py:91`: `modelo: str = Field(default="100")`
- `src/aeat/core/errors/registry/_application.py`: M100 error codes
- `src/aeat/adapters/persistence/storage/sql/_test_constraints.py`: M100 test fixture
- Test files: ~20 occurrences in registry tests

Hardcoded M100 gates: 3 concrete sites (borrador binding + renta ledger default).

### 15. CLI command count & emit path usage

**Count: 153 `@app.command()` / `@*_app.command()` decorators**

Emit path usage:
- `register_schema`: 0 (defined in `core/json_contract.py` but never called)
- `emit_json_success`: 0 (same)
- Ad-hoc `dict` payloads in CLI: all 153 commands (typo-prone, untyped)

Notable: `SchemaEnvelope` framework exists but untouched. All CLI JSON output uses direct `print(json.dumps(dict(...)))`.

### 16. `Annotated[str, Field(pattern=...)]` for regex-only ID types

**Count: 20 of 21** (all except `ManualId`/`ManualPart` enums)

Confirmed at `src/aeat/domain/calculations/registry/_ids.py`. All use pattern validation only; none have existence checks tied to model construction.

### 17. `_ids.py` file inventory

**Count: 2 files**
- `src/aeat/domain/calculations/registry/_ids.py`: 21 ID types (ModeloId, CasillaId, FormulaId, etc.)
- `src/aeat/domain/manuals/_ids.py`: 2 enum classes (ManualId, ManualPart — closed enums, not Annotated types)

### 18. `_MODELO_100` / `MODELO_100` hard-wired gates

**Count: 4 files**
- `src/aeat/application/modelo/_borrador_binding.py:27,79,98,179`: `_MODELO_100 = "100"`
- `src/aeat/application/aggregation/_renta_ledger.py:91`: default="100" on campo
- `src/aeat/core/errors/registry/_application.py`: M100-specific error codes
- `src/aeat/adapters/persistence/storage/sql/_test_constraints.py`: test fixture

### 19. `SensitivityClass` references

**Count: 299 occurrences** (multiple files)

Usage:
- Direct field-level hardcoding: `SensitivityClass.AUDIT`, `SensitivityClass.FINANCIAL` (6 sites)
- Enum comparison in repository write paths (persist-time enforcement)
- No schema-side attachment: `ModeloDefinition` / `CasillaDefinition` have no `output_sensitivity` field

### 20. Pydantic `BaseModel` subclass count

**Count: 580 total** (across all packages)

Grouped by package:
- **domain**: ~280 (registry schema, filing, invoice, transaction, calculation models)
- **application**: ~150 (workflow, aggregation, filing, ledger, diagnostic models)
- **adapters**: ~100 (persistence, outbound, inbound adapter models)
- **entrypoints**: ~30 (CLI command models)
- **core**: ~20 (errors, identity, observability)

All use frozen=True by default; many have ConfigDict(extra="forbid").



### Wave 1 — Agent 1 — Pattern sweep: linkage mechanisms (Haiku)

Programmatic inventory of every cross-reference mechanism. No design
analysis, pure enumeration.

#### 1. Registry binding and relation files

Non-test files:

- `src/aeat/domain/calculations/registry/_bindings.py` — public models:
  `RegistryModeloObservation`, `CasillaObservation`,
  `InvoiceObservation`, `InvoiceObservationRequirement`,
  `CounterpartAggregationObservation`, `OssIossLedgerObservation`,
  `IvaLedgerObservation`.
- `src/aeat/domain/calculations/registry/_relations.py` — public models:
  `RegistryFoldRequirement`.

#### 2. Pydantic models with cross-reference fields

Registry schema (`_schema.py`):

- `LegalReference` (line 146): `id: LegalRefId`, `authority:
  "boe"|"aeat"|...`, `corpus_ref: str`, `document_id: str`.
- `SourceReference` (line 188): `id: SourceRefId`, `corpus_path: str`,
  `evidence_tier`, `kind`.
- `LiveCrossReferenceDecision` (line 272): `id: CrossReferenceId`,
  `oracle_id: str|None`, `applicability_predicates`.
- `WorkbookParityReference` (line 414): `id: WorkbookParityRefId`,
  `workbook_source: SourceRefId`.
- `ApplicationLinkDefinition` (line 462): `id: ApplicationLinkId`,
  fields for guard policy.
- `DataBindingDefinition` (line 789): `id: BindingId`, `source:
  Literal[ledger|invoice|rental|...]`, `selector: Mapping`.
- `FormulaDefinition` (line 817): `id: FormulaId`, `target: CasillaId`,
  `legal_refs`, `source_refs`.
- `CasillaDefinition` (line 882): `id: CasillaId`, `binding:
  BindingId|None`, `formula: FormulaId|None`, `export_refs:
  tuple[ExportFieldId, ...]`.
- `AlgorithmBindingDefinition` (line 923): `inputs: Mapping[str,
  BindingId|CasillaId|ParameterId|RelationId]`.
- `RelationDefinition` (line 934): `id: RelationId`, `kind:
  "previous_period"|"annual_summary"|"cross_model_output"`.
- `DependencyClassificationDefinition` (line 586): `source_modelo:
  ModeloId`, `relation_refs: tuple[RelationId, ...]`.

Bindings (`_bindings.py`):

- `RegistryModeloObservation`: `modelo: ModeloId`, canonical
  `observations: tuple[CasillaObservation, ...]`, derived
  `casilla_values: Mapping[CasillaId, Decimal]`.
- `InvoiceObservation`: `intracommunity_clave: str`, classifier fields
  for IVA.
- `CounterpartAggregationObservation`: aggregation over counterpart
  transactions.

Renta (`renta/_ledger_expenses.py`):

- `RentaDeductibleExpenseFact` (line 100): `category: SpendingCategory`,
  `direction: RentaExpenseDirection`, `invoice_id|None`.

#### 3. Modelo ID references

Type definition (`_ids.py`):

- `ModeloId = Annotated[str, Field(pattern=r"^\d{3}$")]` — strictly
  3-digit decimal string.

Usage patterns across codebase:

- String literals: the old `RegistryFilingObservation.modelo` drift is
  closed in current code; `RegistryModeloObservation.modelo` now uses
  `ModeloId`.
- Type alias: `ModeloId` in schema
  (`DependencyClassificationDefinition.source_modelo`).
- Event codes: event type strings like `"MODELO_CALCULATION_CREATED"`
  in `buckets/_event.py`.
- No enum class `Modelo303` or `ModeloClass` — only typed-string
  discipline.

#### 4. Casilla code type representation

Canonical type (`_ids.py`):

`CasillaId = Annotated[str, Field(min_length=1, max_length=64,
pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]`.

Usage:

- Schema fields use `CasillaId` type (strict).
- Bindings use `Mapping[str, Decimal]` for observed values
  (`casilla_values`).
- Renta mapping: `FIRST_SLICE_EXPENSE_CASILLAS:
  Mapping[SpendingCategory, CasillaId]` in `_first_slice_routing.py`.
  `_ledger_expenses.py` re-exports the same object as
  `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` for the observation
  validator; snapshot construction validates every target casilla
  against the Modelo 100 registry.

#### 5. Workbook and Sheets linkage

Export model (`application/export/_tabular.py`):

- `TabularExportResult` — wraps serialized export.
- No cell-level mapping types exposed; export surface abstracts to
  format-agnostic `ExportSerializationFormat`.

Schema references:

- `WorkbookParityReference.workbook_source: SourceRefId` → points to
  workbook source reference record (not a cell).
- `CasillaDefinition.export_refs: tuple[ExportFieldId, ...]` → indirect
  binding to export field IDs.

#### 6. Secure storage linkage

Attachment domain (`domain/attachments/_models.py`):

- `Attachment.attachment_id: str` (64-char SHA-256 hex).
- `Attachment.bucket_id: str` (owner profile bucket).
- Content-addressed: `attachment_id == sha256` of bytes enforced.
- No direct formula-to-attachment reference in registry; attachment
  catalogue is separate evidence layer.

Registry-to-Evidence:

- Bindings reference `"purchase_invoice_evidence"` as source (line 806,
  `_schema.py`).
- Attachment lifecycle managed via `AttachmentStore` and
  `AttachmentCatalogue` — decoupled from calculation registry.

#### 7. Renta (Modelo 100) specifics

Files under `domain/renta/`:

- `__init__.py`, `_ledger_expenses.py`, `_substrate.py`, `errors.py`,
  test files.

Renta-specific linkage primitives:

- `RentaExpenseDirection`, `RentaDeductibilityStatus`,
  `RentaInvoiceEvidenceStatus`, `RentaReconciliationStatus` (enums).
- `RentaDeductibleExpenseFact` → casilla mapping via the canonical
  `FIRST_SLICE_EXPENSE_CASILLAS` routing table, re-exported by
  `_ledger_expenses.py` for validator compatibility and checked at
  snapshot construction through `CrossDomainSnapshotCheck`.
- `SpendingCategory` enum (from `categories` package) — domain link to
  expense classification.
- No separate modelo-100-specific binding schema; reuses generic
  `DataBindingDefinition.source = "ledger_renta_expense_aggregation"`
  selector.

Total cross-reference types: 14 ID types (ModeloId, CasillaId,
FormulaId, BindingId, RelationId, LegalRefId, SourceRefId,
CrossReferenceId, WorkbookParityRefId, ApplicationLinkId,
DependencyClassificationId, ExportFieldId, ConstructId, ParameterId)
plus 8 schema classes with explicit legal_refs/source_refs fields.

### Wave 1 — Agent 2 — Schema↔registry binding shape

#### A. Canonical casilla-within-modelo shape

No single canonical pydantic model. Three coexisting shapes:

- `CasillaDefinition` (`_schema.py:882`) — authoritative registry
  shape. Holds `id: CasillaId`, `formula: FormulaId | None`, `binding:
  BindingId | None`, `input_kind`, `constraints: CasillaConstraints |
  None`, `legal_refs`, `source_refs`. Embedded in
  `ModeloRevision.casillas`.
- `RegistryCasillaSchema` (`application/filing/runtime.py:78`) — frozen
  dataclass (not pydantic) projected from `CasillaDefinition` at
  runtime. Carries `id: str`, `value_type: str`, `required: bool`,
  `formula_inputs: tuple[str, ...]`, untyped `min_value: float | int |
  None`.
- `CasillaSchema` (`domain/filing/_protocols.py:38`) — `typing.Protocol`
  (structural, not pydantic). Used by `CasillaSchemaProvider` and all
  filing application consumers.

The registry owns `CasillaDefinition`; the filing layer duck-types
against `CasillaSchema` Protocol; `RegistryCasillaSchema` is the bridge
but is a plain dataclass with degraded types (`str` instead of typed
IDs, `float | int | None` instead of `Decimal | None`).

#### B. Cross-modelo dependency shape

Two distinct mechanisms:

- `RelationDefinition` (`_schema_surfaces.py:472`) — primary typed
  mechanism. `source_modelo: ModeloId`, `source_casilla_id:
  CasillaId`, `target_binding: BindingId`, `kind:
  Literal["previous_period", "annual_summary", "cross_model_output"]`.
  The legacy `source_output` key is no longer a model field and is
  rejected by schema tests.
- `RegistryModeloObservation` (`_bindings.py:278`) — runtime resolution
  observation shape. `modelo: ModeloId`, `filing_year: int`, `period:
  str`, and canonical `observations: tuple[CasillaObservation, ...]`.
  The derived `casilla_values` view is keyed by `CasillaId`.

`RegistryFoldRequirement` (`_relations.py:40`) is the unified fold-in
requirement for relation and direct previous-filing carries. Its source
modelo and source-casilla fields are now typed as `ModeloId` and
`tuple[CasillaId, ...]`. Relation selector shape is currentized:
`RelationDefinition.source_revision_selector` stores
`RelationRevisionSelector`, and `period_alignment` stores
`RelationPeriodAlignment`. The remaining cross-modelo shape gap is not
`source_output` or relation selector maps; it is the loss of source
observation provenance once relation values enter formulas as bare
`Decimal` values.

#### C. Legal grounding attachment points

Attaches at all three levels with uneven shape:

- Modelo (`ModeloDefinition:1108`): `legal_refs: LegalRefs`,
  `source_refs: SourceRefs`.
- Revision (`ModeloRevision:1073`): same.
- Casilla (`CasillaDefinition:894`): same.
- Formula (`FormulaDefinition:820`): plus `source_citations`.
- Binding (`DataBindingDefinition:810`): plus `source_citations`.
- Constraints (`CasillaConstraints:848`): same.
- Parameter (`ParameterDefinition:748`): plus `source_citations`.

Shape (`LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]`)
is uniform across all of these, enforced by pydantic. However the
`RegistryCasillaSchema` projection (`runtime.py:78`) discards all legal
refs — they do not propagate to the filing consumer layer. The
filing-layer `CasillaSchema` Protocol has no legal grounding slot at
all.

#### D. Contract enforcement: duck typing vs pydantic

Registry layer is fully pydantic-enforced at load time.
`_loader.py:73` calls `ModeloRevision.model_validate(payload)` and
`_schema.py:90` uses `ConfigDict(strict=True, frozen=True,
extra="forbid")` on `RegistryModel`.

Schema→registry linkage in the filing application layer relies on duck
typing via Protocol. `CasillaSchemaProvider` (`_protocols.py:103`) is
structural; `RegistryCasillaSchema` satisfies it by attribute
coincidence. The projection in `runtime.py:365` performs a string
lookup and builds a dataclass — no pydantic validation occurs.

#### E. Renta canonical or parallel?

Renta uses the canonical registry contract plus one Renta-specific side
channel that partially bypasses it.

Canonical: modelo 100 is declared as a `ModeloDefinition` with
`CasillaDefinition` entries and `FormulaDefinition` entries exactly
like any other modelo.

Current state (2026-06-29): the old side-channel wording is stale.
`FIRST_SLICE_EXPENSE_CASILLAS` is the canonical Renta-domain routing
table, typed as `Mapping[SpendingCategory, CasillaId]`. The
`_ledger_expenses.py` validator re-exports that same object, while
`_first_slice_routing_integrity.py` registers a snapshot-time check
that fails Modelo 100 builds when a routed casilla is absent from the
registry revision. The registry-side resolver accepts only the four
declared first-slice targets through its own selector model and no
longer imports `domain.renta`.

#### F. Drift: same concept, different shapes

- Cross-modelo source identifier drift is closed in current code:
  `RelationDefinition.source_casilla_id`,
  `RegistryFoldRequirement.source_casilla_ids`,
  previous-filing/relation-prefill selector
  source casillas, and `RegistryModeloObservation.modelo` all use the
  typed registry aliases. Legacy `source_output` is rejected.
- Modelo ID in filed-state and applicability records was currentized
  on 2026-06-29: `RegistryModeloObservation.modelo`,
  `RegistryFiledStateComparison.modelo`, `ModeloApplicability.modelo`,
  and `ModeloApplicabilityRule.modelo` now use `ModeloId`.
- Casilla schema for filing consumers: pydantic `CasillaDefinition`
  with `Decimal` bounds vs `RegistryCasillaSchema` dataclass with
  `float | int | None` bounds.
- Casilla-to-formula linkage: `CasillaDefinition.formula: FormulaId |
  None` (by ID) vs `RegistryCasillaSchema.formula_inputs: tuple[str,
  ...]` (extracted from expression tree).
- Legal grounding attachment: present on registry models but absent
  from `CasillaSchema` Protocol and `RegistryCasillaSchema` projection.
- Renta first-slice authority is now a typed Renta-domain routing table
  (`Mapping[SpendingCategory, CasillaId]`) with snapshot-time
  validation against the Modelo 100 registry revision.

#### Top 5 unresolved linkage-design gaps (no ADR)

1. Loss of typed IDs at the filing application boundary
   (`runtime.py:78`). `RegistryCasillaSchema` converts `CasillaId` to
   `str`, `Decimal` bounds to `float | int | None`, and drops
   `legal_refs`/`source_refs` entirely.
2. `RegistryCalculationResult.values` and
   `CalculationRevision.casilla_values` remain flat maps rather than
   the canonical typed observation envelope.
3. Relation fold-in values lose source-observation provenance before
   formula evaluation: `resolve_relation_values_from_observations`
   returns relation-id keyed `Decimal` values, not an observation
   envelope carrying source modelo, period, filing year, and casilla.
4. `DataBindingDefinition.selector` now stores the hydrated per-source
   selector model; raw `BindingSelectorMap` payloads are confined to
   TOML/dict authoring input and serialization projection.
5. Selector consumer projections are narrowed for binding-derived export
   records, Detalle row-set consumers, and public binding query rows
   (`BindingSelectorQueryProjection`).

### Wave 1 — Agent 3 — Cross-modelo linkages

#### A. Distinct mechanisms

1. Registry Relations + `RelationDefinition` (`_relations.py:23–94`,
   `_schema.py:934–983`). Each `ModeloRevision` carries `relations:
   tuple[RelationDefinition, ...]`. Examples:
   `modelo-200-2024-rel-202-pagos-fraccionados`,
   `renta-2025-rel-130-pagos-fraccionados`.
2. Previous-Filing Bindings (`_bindings.py:135–205`).
   `DataBindingDefinition` with `source="previous_filing"` carries a
   `selector` dict that includes `source_modelo`, `filing_year_delta`,
   `source_casillas`, and `period`/`source_periods`.
3. Live Cross-Reference Decisions (`_schema.py:272–398`,
   `_snapshot.py:110–112`). `LiveCrossReferenceDecision` per revision
   describes an AEAT portal surface a modelo can query (GROI, IXVI,
   OSS). Not calculation inputs; policy metadata for oracle adapter
   dispatch.
4. Counterpart Aggregation Bindings
   (`_bindings.py:resolve_counterpart_binding_values`,
   `test_counterpart_bindings.py:22–26`).
   `DataBindingDefinition` with `source` in `{"ledger_transaction",
   "payable_invoice", ...}`. Used by Modelos 347 and 349.
5. Dependency Classifications (`_schema.py:586–612`,
   `_snapshot.py:140–142`). `DependencyClassificationDefinition` with
   `treatment` enum: `direct_annual_settlement`, `factual_evidence`,
   `non_dependency`.

#### B. Unification

No single unified resolver. Two parallel resolution paths exist:

- Calculation-grade (relations): `resolve_relation_values_from_observations`
  → `relation_source_requirements` → `RegistryModeloObservation` →
  Decimal values injected as `relation_values` into
  `calculate_registry_snapshot`.
- Binding-grade (previous_filing): `resolve_previous_filing_binding_values`
  → `_PreviousModeloSelector` → `RegistryModeloObservation` →
  `binding_values` dict.

Both are application-orchestrated; neither is called internally by the
formula engine. The `LiveCrossReferenceDecision` path is a third,
fully separate mechanism governing oracle adapter dispatch.

#### C. Cross-period modelling and provenance

Prior-year and prior-period values are modelled through
`RegistryModeloObservation` (`_bindings.py:278`): `modelo: ModeloId`,
`filing_year: int`, `period: str`, canonical typed
`CasillaObservation` rows, and a derived
`casilla_values: Mapping[CasillaId, Decimal]` view.

Typed at observation level: modelo, year, period, and casilla id are
explicit. `_PreviousModeloSelector.filing_year_delta` encodes the year
offset (`-1`) in the binding selector itself.

Provenance preserved at observation level but resolved scalar entering
the formula engine (`relation_values: dict[str, Decimal]`) drops all
provenance — keyed only by relation id string
(`renta-2025-rel-130-pagos-fraccionados`).
`RegistryCalculationEntry.operand_refs` records only the relation id
string.

#### D. Oracle vs locally computed

Distinction encoded architecturally but not in the type system at value
level. The oracle ADR explicitly acknowledges this gap: `oracle_id`
field is `str | None`, not a typed `OracleId` alias. No
`OracleFilingObservation` type exists.

#### E. String-key lookups

Several places use dict-key string lookup on selector mappings:

- Currentized 2026-06-29: the old production
  `binding.selector.get("source_modelo")` path is closed. Record-design
  closure now calls `binding_source_modelo(binding)`, which dispatches
  through the typed previous-filing and relation-prefill selector helpers.
- `test_modelo_chain_cohesion.py:81`: same.
- `test_relation_consistency.py:62`: same.
- Relation revision selector helpers still use mapping lookups for
  `year` / `filing_year_delta`; these belong to the residual
  relation-selector surface, not R016.
- `test_cross_dependency_contract.py:172–174`:
  `selector.get("source_modelo")` / legacy `selector.get("source_output")` /
  `selector.get("source_casillas")`.

`_PreviousFilingSelector` pydantic model (`_bindings.py:208–250`)
partially mitigates this by validating at resolution time, but the
selector field itself remains `Mapping[str, Any]` at schema level.

#### F. Test separation

Cross-reference vs cross-dependency distinction is principled:

- `test_cross_reference_*.py`: `LiveCrossReferenceDecision` — oracle
  binding, applicability predicates, profile gates. Read surfaces.
- `test_cross_dependency_*.py`: `RelationDefinition` +
  `resolve_relation_values*` — dependency graph role contracts,
  aggregation ops, period requirements. Calculation wiring.
- `test_counterpart_bindings.py`: ledger-aggregation binding path
  (347/349). Distinct from both.

#### Top 5 governance gaps for cross-modelo linkage

1. Resolved relation values lose all provenance at the formula
   boundary. `resolve_relation_values` returns `dict[str, Decimal]`
   keyed by relation id. Source modelo, source period, filing year,
   and casilla id are irrecoverable from inside the formula trace.
2. Oracle-originated observations are not distinguishable from locally
   computed ones. No `OracleFilingObservation` subtype.
3. `DataBindingDefinition.selector` now stores the hydrated per-source
   selector model; raw selector maps remain only the registry authoring and
   serialization shape.
4. Selector consumer projections are narrowed for binding-derived export
   records, Detalle row-set consumers, and public binding query rows
   (`BindingSelectorQueryProjection`).
5. Currentized 2026-06-29: relation selector shape and the old
   registry-level `source_output`
   existence gap is closed. Relations now declare `source_casilla_id`,
   `source_revision_selector: RelationRevisionSelector`, and
   `period_alignment: RelationPeriodAlignment`; full-registry
   validation checks the source casilla against matching source
   revisions before production authority serves snapshots.

### Wave 1 — Agent 4 — Export and workbook linkages

#### A. Canonical casilla → sheet cell mapping

Two separate mapping formats:

- Google Sheets (calc-sheets engine): `SheetCellAddress` — `{tab:
  TabName, row: int, column: int, a1: str}`. Computed dynamically by
  `plan_layout()` in
  `src/aeat/application/storage/calc_sheets/_layout.py:105–136`. No
  workbook name or sheet-tab is hardcoded per-modelo.
- BOE fichero export (AEAT fixed-width): `RecordFieldSpec` in
  `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`,
  with fields `{offset, length, field_id, casilla_id, kind, …}`.
  Byte-offset mapping, hand-authored from BOE Diseño de registros.

A third internal path: domain-level registry export layouts
(`_export.py`) use `ExportFieldDefinition` with `offset`/`length` into
fixed-width records, indexed by `fields_by_casilla: Mapping[str,
tuple[ExportFieldDefinition, ...]]`. Schema-declared in TOML, resolved
at load time.

#### B. Schema-driven vs hand-wired

Mixed. Domain registry path is entirely data-driven. Google Sheets
path is also data-driven — tab structure fixed, cell positions
algorithmic. BOE fichero path is hand-wired per-modelo-year:
`_RECORD_SPECS` tuples authored once per module (e.g.
`modelo_130_2024.py`).

#### C. Inverse direction — parsing workbook → casilla values

Same mapping, inverse traversal, independently re-derived for Google
Sheets pull. For BOE fichero parse, the same `SegmentSpec` /
`RecordFieldSpec` table drives `deserialise()`. For domain registry
parse, `parse_export_payload()` walks the same `ExportLayoutDefinition`
records.

#### D. Parity test shape

`_workbook_parity.py` operates against official AEAT formula workbooks.
Trusts neither schema nor export code directly: works by running
inputs through LibreOffice/Excel COM, reading output cells by explicit
`WorkbookCellRef {sheet, coordinate}` supplied by the test scenario.
Casilla→cell pairing declared in scenario JSON, not derived from
registry schema.

#### E. Modelo 100 (Renta)

Modelo 100 has its own application-layer glue that bypasses the
generic calc-sheets path for one specific concern: borrador binding
resolution. `src/aeat/application/modelo/_borrador_binding.py` is
modelo-100-exclusive (`_MODELO_100 = "100"`, line 27;
`resolve_modelo_100_borrador_bindings()`, line 79), hard-gating on
`target_modelo != _MODELO_100` at line 98.

#### F. Ad-hoc per-modelo export glue

- `src/aeat/application/modelo/_borrador_binding.py` lines 27, 98–100,
  179: hard-coded `"100"` gate in the application layer.
- `src/aeat/application/aggregation/_renta_ledger.py` line 91: `modelo:
  str = Field(default="100", …)` — renta ledger hardcodes modelo 100.
- `src/aeat/adapters/outbound/aeat/export/_formats/` modules: planned
  per-modelo-year modules, hand-authored `_RECORD_SPECS` tuples.
- `_export.py` lines 130–148: `_ROW_FIELD_CASILLA_BY_RECORD` —
  hard-coded dict mapping record types to casilla string ids.

#### Top 5 export-linkage governance gaps

1. BOE fichero specs hand-authored, not schema-derived. Casilla
   renumbering in registry will not propagate.
2. No single canonical casilla→export-surface registry. Three
   independent coordinate systems for the same casilla.
3. Workbook parity scenarios manually curated and cell-reference
   fragile.
4. Modelo 100 borrador binding permanently hard-wired.
5. `_ROW_FIELD_CASILLA_BY_RECORD` static domain-layer dict with no
   schema backing.

### Wave 1 — Agent 5 — Secure storage and evidence linkages

#### A. Prior filing as evidence reference

No single type. Three distinct shapes:

1. `RegistryModeloObservation` (`_bindings.py:278`): pydantic model
   carrying `modelo: ModeloId`, `filing_year: int`, `period: str`, and
   canonical typed `CasillaObservation` rows. No persistence key, no
   SHA-256, no encryption metadata.
2. `RegistryFiledStateComparison` / `RegistryFiledStateDrift`
   (`_filed_state.py:22,33`): Comparison verdict objects. No opaque ID
   linking to stored artifact.
3. `FilingDraft.schema_version: str` (`_schema.py:158`): bare string,
   not a typed reference to a `RegistrySnapshot` or `LegalReference`.

`Justificante` model (`_schema.py:30`) carries `csv: str` and
`source_pdf_path: Path` and `source_pdf_sha256: str`. Closest to a
stable artifact reference for a prior filing, but is a parsed receipt
— not the filing draft itself.

No model carrying `(filing_draft_id, justificante_csv, attachment_id)`
as a unified tuple. Linkage assembled ad hoc in application code.

#### B. Sensitivity classification

External to every linkage shape. `SensitivityClass` enum
(`core/classification/__init__.py:30`) lives in persistence adapter
layer. Domain models (`Justificante`, `Attachment`, `FilingDraft`,
`RegistryModeloObservation`) carry no `sensitivity` or `classification`
field. Repositories construct `Envelope` with hard-coded classes —
e.g. `JustificanteRepository` hard-codes `SensitivityClass.AUDIT`,
`AttachmentRepository` hard-codes `SensitivityClass.FINANCIAL`.

#### C. Registry persistence boundary

Clean at the registry's computation surface. `calculate_registry_snapshot`
takes `inputs: Mapping[str, Decimal]` and `binding_values`, emits a
`RegistryCalculationResult` carrying only computed `Decimal` values
and formula trace entries.

Frays at the input side: `RegistryModeloObservation` carries typed
prior-filing observations, but no typed protocol defines how those rows
are retrieved from the encrypted store. Registry cannot reject a
fabricated observation on storage provenance alone.

#### D. Evidence vs justificante vs attachment vs filing-record

Four distinct typed concepts with no shared base type:

- `Justificante` (`_schema.py:30`): AEAT submission receipt. Keyed by
  `csv`. Persisted at `SensitivityClass.AUDIT`.
- `Attachment` (`_models.py:69`): content-addressed byte-manifest
  (SHA-256 = attachment_id). Persisted at `SensitivityClass.FINANCIAL`.
  Links to transactions and invoices via `linked_transaction_ids` /
  `linked_invoice_ids`. No link to `FilingDraft` or `Justificante`.
- `FilingDraft` (`_schema.py:136`): typed casilla-value record with
  `schema_version`, `status`, `approval_basis`. No link to
  `Attachment` or `Justificante`.
- "Evidence" (registry tier): not a persisted model. In registry
  schema, evidence is expressed as `EvidenceTier:
  Literal["legal_authority", "official_source_guidance",
  "executable_parity_evidence", "layout_authority"]` on
  `SourceReference` and `LegalReference` objects.

No base type. The term "evidence" is used in three different senses
with no shared type surface.

#### E. Calculation record references

- Schema version: `FilingDraft.schema_version: str` — bare string
  included in `draft_id` hash.
- Legal-source citation snapshot: `RegistryCalculationEntry.legal_refs:
  tuple[str, ...]` and `source_refs: tuple[str, ...]`. Stable symbolic
  IDs but no snapshot of resolved `LegalReference` bodies frozen.
- Input data blob: no reference at all. `calculate_registry_snapshot`
  accepts `inputs: Mapping[str, Decimal]` and discards provenance.

#### Top 5 storage-linkage governance gaps

1. No typed link from `FilingDraft` to `Justificante`.
2. `RegistryModeloObservation` is typed at the registry boundary but
   still unverified for storage provenance.
3. No input-data blob reference in `RegistryCalculationResult`.
4. `Attachment` has no link to `FilingDraft` or `Justificante`.
5. Classification is not stamped on domain records, only at the
   repository layer.

### Wave 1 — Agent 6 — Renta drift vs canonical patterns

#### A. Casilla→formula linkage

Canonical side: `registry/aeat/modelos/100/revisions/2025.toml`
declares every casilla, formula, and binding using the identical
schema contract used by 303, 130, 115, etc. Schema at `_schema.py` is
shared; no renta-specific subclass of `RegistryModel`.

Bespoke side: `domain/renta/` (`_ledger_expenses.py`, `_substrate.py`,
`_first_slice_routing.py`) introduces domain types with no parallel in
any other modelo domain package. Current-state recheck on 2026-06-29
found the old direct registry→Renta import and unvalidated first-slice
constant closed: the registry resolver uses a Protocol, and the
Renta-owned routing table registers a snapshot-time integrity check.
The remaining design fact is intentional cross-domain routing, not a
silent split of casilla authority.

#### B. Sub-schedules

Encoded as section tags on casillas (40+ distinct section paths in
2025.toml), and as constructs ("mini-models") which are formula
groupings within the construct system. Not peer modelos; flat sections
within a single oversized revision file (25,486 lines for 2025 alone vs
1,486 for 130). `mini-model` construct label has no schema enforcement.

#### C. Per-CCAA variation

All three (schema, formula, runtime context) interact through different
mechanisms without a unified contract:

- Schema (binding): `renta-2025-profile-tax-residence-ccaa` is a
  `source = "profile"` binding with `typed_enum = "RentaCCAA"`.
- Formula runtime: `lookup_bracket_by_ccaa` and
  `lookup_parameter_by_entity_type` ops consume the binding value at
  evaluation time via `enum_binding_values`.
- Runtime context: `calculate_registry_snapshot` takes
  `enum_binding_values: Mapping[str, str]`, a separate Decimal-free
  channel used only for CCAA routing.

`RentaCCAA` (`_substrate.py:49`) uses 3-letter ISO-like codes (AND,
ARA, AST) while `domain/profile/_ccaa.py:CCAA` uses full Spanish names
(ANDALUCIA, ARAGON). Dispatch tables use yet another set of keys
(madrid, andalucia, cataluna). Three CCAA representations coexist
with no declared canonical source.

#### D. Renta vs Modelo 303

Common: both use `load_registry_tree → build_snapshot →
calculate_registry_snapshot`. Both bind ledger observations via
`source = "ledger_*_aggregation"`. Both attach `legal_refs` and
`source_refs`. Both carry `workbook_source` at the revision level.

Divergent:

- Export format: 303 uses fixed-width record `export_layouts` with
  per-casilla `export_refs`. Modelo 100 uses zero per-casilla
  `export_refs`; export is exclusively via an `xml_dictionary` layout.
- Ledger binding domain model: 303's resolver consumes
  `IvaLedgerObservation` objects from `_iva_ledger.py`. Renta's
  resolver consumes `RentaDeductibleExpenseObservation` objects where
  deductibility evaluation lives inside `domain/renta/` itself —
  domain-layer business logic embedded in what should be a data
  boundary type.
- Cross-model relations: 303 has none; 100 introduces 10
  `cross_model_output` relations in 2025 revision only.
- Profile bindings: 303 has none. Modelo 100 has 20+.

#### E. Substrate and ledger_expenses promotion

`_substrate.py` contains `RentaIncomeType`, `RentaCCAA`,
`EstimacionDirectaModalidad`. `RentaCCAA` duplicates
`domain/profile/_ccaa.py:CCAA` with different value space. Most
concrete promotion candidate.

`_ledger_expenses.py` contains deductibility evaluation logic plus a
re-export of the canonical first-slice routing table. Deductibility
evaluator is renta-specific business logic. `RentaDeductibleExpenseObservation`
remains a binding-ready observation, but the registry consumes it
structurally through `RentaExpenseObservationProtocol` in
`_ledger_bindings.py`; the old direct `domain/calculations` →
`domain/renta` import is closed.

Evidence pattern is ad-hoc: no other domain package is imported
directly by `domain/calculations/registry/`. IVA ledger observation
types live in `application/aggregation/_models.py`. Renta's
observation type lives in `domain/renta/` — wrong layer.

#### F. Clearest pattern violations

1. Currentized 2026-06-29: the old registry→Renta import violation is
   closed; `_ledger_bindings.py` uses a Protocol and the Renta check is
   registered through `CrossDomainSnapshotCheck`.
2. Currentized 2026-06-29: the first-slice routing table is a typed
   `SpendingCategory → CasillaId` Renta-domain table with snapshot-time
   integrity, not an unvalidated hard-coded duplicate.
3. `src/aeat/domain/renta/_substrate.py:49–83` — `RentaCCAA` duplicates
   `src/aeat/domain/profile/_ccaa.py:13` `CCAA` with incompatible
   value spaces.
4. `registry/aeat/modelos/100/revisions/2025.toml` — zero `export_refs`
   at casilla level vs all other modelos.
5. `registry/aeat/modelos/100/revisions/2025.toml:8249–8386` vs
   `2020–2024.toml:0 relations` — `cross_model_output` relations
   exist only in 2025 revision.

#### Renta-specific governance gaps

- Dual CCAA enum problem must be collapsed to one canonical enum.
- The old `RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` migration demand is
  superseded by the current accepted design: Renta owns category routing
  and the registry validates target casillas at snapshot construction.
- Observation-type layer assignment: `RentaDeductibleExpenseObservation`
  should live in `application/aggregation`, not in `domain/renta/`.
- Cross-model relations backfill across revisions for 2020–2024.
- Export linkage for XML-format modelos: per-casilla `export_refs` are
  currently optional.
- Constructs as sub-schedule proxies: must decide whether constructs
  should be promoted to a first-class `sub_schedule` concept.

### Wave 2 — Agent 7 — End-to-end casilla trace

#### Trace 1: Modelo 303, casilla `iva.resultado-regimen-general`

The AEAT form uses numeric casilla numbers (46 = cuota a ingresar); this
registry uses semantic string IDs throughout. The numeric "46" does
not appear in `303.toml`. SHAPE TRANSITION #1 (form numeric → semantic
string ID).

Schema declaration: TYPED at `registry/aeat/modelos/303.toml:219` via
`CasillaDefinition`. Fields:
`id="iva.resultado-regimen-general"`,
`input_kind="computed"`,
`formula="modelo-303-iva-resultado-regimen-general"`. No numeric
`number` field matching the form's "46" — only a semantic alias.

Formula definition: TYPED at `303.toml:267`. Expression: `{op="subtract",
args=[{casilla="iva.cuota-devengada-total"},
{casilla="iva.cuota-deducible-total"}]}`.

Inputs: `iva.cuota-devengada-total` is computed (formula sums 4
`bound` casillas). Each bound casilla links to a
`DataBindingDefinition` with `source="ledger_iva_aggregation"` and a
`selector` that is `Mapping[str, str|int|DecimalValue|bool|tuple[str,...]]`.
UNTYPED SEAM at `_schema.py:817`.

Cross-period edge (303 → 390): currentized 2026-06-29. The fold-in
requirement is `RegistryFoldRequirement` (`_relations.py:40`) carrying
`source_modelo: ModeloId` and `source_casilla_ids: tuple[CasillaId,
...]`. Observation folding extracts
`requirement.source_casilla_ids[0]` from the
`RegistryModeloObservation.casilla_values` view, which is keyed by
`CasillaId` (`_observation_fold.py:38-53`). The old `source_output`
string-key seam is closed. Provenance still does not survive the hop
into formula evaluation — the value enters as a bare `Decimal`.

Legal grounding: attached at casilla, formula, and relation levels.
All three reference `rd-439-2007:art-109` but this overlap is
coincidental — no cross-check exists.

Persistence: TYPED at `_formula_runtime.py:36`: `values: Mapping[str,
Decimal]` keyed by casilla id. UNTYPED SEAM #3 at line 43: `values`
map loses distinction between `bound`, `computed`, and
`informational` casillas.

Export: 303 TOML does not declare `export_refs` on
`iva.resultado-regimen-general`. UNTYPED SEAM #4 at `_export.py:31`:
key is `str`, not `CasillaId`.

#### Trace 2: Modelo 100 casilla 0604 — pagos fraccionados (cross-modelo dependency on Modelo 130)

Casilla `0604` is "Total pagos fraccionados ingresados" in Modelo 100,
grounded through relation `renta-2025-rel-130-pagos-fraccionados`
pulling from M130 casilla "19" across four quarters.

Schema declaration: TYPED at
`registry/aeat/modelos/100/revisions/2025.toml`. `id="0604"`,
`input_kind="computed"`,
`formula="renta-2025-pagos-fraccionados-ingresados"`.

Formula definition: TYPED at `2025.toml:6134`. Expression: `{op="sum",
args=[{relation="renta-2025-rel-130-pagos-fraccionados"},
{relation="renta-2025-rel-131-pagos-fraccionados"}]}`. Both args are
`FormulaExpression` leaves with `relation` field typed as
`RelationId`.

Inputs: `relation_values: Mapping[str, Decimal]` assembled by
`resolve_relation_values_from_observations` at `_relations.py:133`.

Cross-modelo edge: relation `renta-2025-rel-130-pagos-fraccionados`
(`2025.toml`) declares `kind="cross_model_output"`,
`source_modelo="130"`, `source_casilla_id="19"`. Current schema uses
`source_modelo: ModeloId` and `source_casilla_id: CasillaId`
(`_schema_surfaces.py:482-484`), and the registry validator checks the
source casilla against matching source revisions. The legacy
`source_output` key is rejected.

By the time the value reaches formula evaluation, the casilla-id type
has survived the fold-in lookup, but the source filing provenance has
not: the formula receives a `Decimal` relation value, not the observed
source modelo/period/year/casilla envelope that produced it.

Return is `Decimal`; no provenance link back to the M130 period or
formula that produced it.

Legal grounding: relation declares same legal_refs as M100 formula
(TYPED but independently). No runtime enforcement.

Persistence: same as Trace 1. `RegistryCalculationResult.values:
Mapping[str, Decimal]`.

Export: `CasillaDefinition.export_refs: tuple[ExportFieldId,...]`
links to `ExportFieldDefinition` records by ID. UNTYPED SEAM #6 at
`_schema.py:429`: both key and value are plain `str`.

#### Ranked untyped seams and shape transitions

1. VALUE-PROVENANCE SEAM — relation fold-in resolves typed
   source-casilla observations to bare `Decimal` relation values before
   formula evaluation. Source modelo, filing year, period, source
   casilla, and observation provenance are no longer carried as a typed
   value envelope.
2. SHAPE TRANSITION #1 — Form numeric casilla number vs semantic
   registry ID.
3. UNTYPED SEAM #3 — `RegistryCalculationResult.values: Mapping[str,
   Decimal]` (`_formula_runtime.py:43`).
4. UNTYPED SEAM #1 — `DataBindingDefinition.selector: Mapping[str, str
   | int | DecimalValue | bool | tuple[str,...]]` (`_schema.py:817`).
5. UNTYPED SEAM #4 — `ResolvedExportLayout.fields_by_casilla:
   Mapping[str, tuple[ExportFieldDefinition,...]]` (`_export.py:31`).
6. PARITY-FIXTURE RESOLUTION — `WorkbookParityReference.fixture_id` is
   now typed as `WorkbookFixtureId`, and `output_cells` is keyed by
   `WorkbookOutputId`; the remaining gap is that fixture IDs do not
   resolve against a declared fixture catalogue.
7. RELATION-SELECTOR SHAPE — closed on 2026-06-29:
   `RelationDefinition.source_revision_selector` and `period_alignment`
   now store typed selector models.

### Wave 2 — Agent 8 — New-modelo onboarding stress test (Modelo 232)

Modelo 232 already exists in the codebase
(`registry/aeat/modelos/232.toml`,
`test_modelo_232_registry.py`), which means some decisions are already
settled.

1. Schema entry. One TOML file per modelo:
   `registry/aeat/modelos/232.toml`. Directory-mode loading
   auto-discovers any `*.toml` under `registry/aeat/modelos/` —
   convention-based, not typed registration. For large modelos (M100),
   a `manifest.toml` + `revisions/` subdirectory pattern exists; 232
   uses the single-file pattern. Nothing forces the implementer to
   choose.
2. Casilla codes. `CasillaId` regex (`_ids.py:16`) accepts any
   length up to 64 chars. `test_schema_hygiene.py:72-84` enforces
   uniqueness within a single revision only. No cross-modelo
   uniqueness check anywhere.
3. Cross-modelo dependency on Modelo 200. `test_modelo_232_registry.py:62-67`
   asserts `revision.relations == ()`. Dependency is classified as
   `factual_evidence` via `DependencyClassificationDefinition`, not
   `RelationDefinition`. Nothing in the type system prevents an
   implementer from using `RelationDefinition` with `kind =
   "cross_model_output"` and `dependency_role = "factual_evidence"`.
4. Counterpart aggregation from invoices.
   `CounterpartAggregationObservation` (`_bindings.py:1231-1294`)
   exists. Known source kinds: `{"invoice", "payable_invoice",
   "collectible_invoice", "ledger_transaction",
   "purchase_invoice_evidence"}`. The €100k threshold filter is a
   pre-aggregation step; existing shape has no `threshold` or
   `relationship_kind` field. Committed M232 chose full manual
   declaration sidestepping new source kinds.
5. Legal grounding. Legal citations live in shared TOML files under
   `registry/aeat/legal/`. Each entry has stable `id` of form
   `"ley-27-2014:art-18"`. No deduplication-by-`permalink` check.
6. AEAT oracle / portal surface. `LiveCrossReferenceDecision.oracle_id`
   is `str | None`. M232 declares two cross-references per revision:
   one `static_official_documentation` (no oracle) and one
   `authenticated_read_surface` (no oracle, read-only portal). No
   registry-wide test enforces what informative modelos without an
   oracle must do.
7. Workbook export. Each revision inline-declares `export_layouts`.
   `WorkbookParityReference.fixture_id` is a `WorkbookFixtureId`
   pattern-constrained alias, not a free string. No fixture-catalogue
   lookup exists at registry level.
8. Persistence. `RegistryCalculationEntry` does not exist as a named
   type. Persistence goes through generic `Envelope` + `blob_store`
   infrastructure. Caller assigns `SensitivityClass` at write time.
9. Sensitivity classification. No field in `ModeloDefinition`,
   `ModeloRevision`, or any schema object that declares the
   sensitivity class of the modelo's output.
10. Tests. Modelo-specific tests must be added by the implementer.
    No scaffolding tool or checklist.

#### Decisions implementer would make without ADR guidance

- Single-file vs manifest+revisions layout: no rule. Blast radius:
  single modelo, naming drift.
- Cross-modelo dependency classification: `RelationDefinition` vs
  `DependencyClassificationDefinition` for informative modelos.
- New `source` literal vs `manual_input` fallback for related-party
  invoice aggregation.
- Oracle absence representation: `oracle_id = None` inside a decision
  vs omitting the decision entirely.
- Sensitivity class for modelo outputs: no schema field, no validator.
- Citation key format for shared BOE articles: no
  deduplication-by-permalink check.
- Casilla id namespace strategy (semantic vs numeric): `CasillaId`
  regex accepts both; cross-modelo collision not tested.

### Wave 2 — Agent 9 — Type-system escape hatches

#### Pass 1 — All type escapes (grouped)

`dict[str, Any]` / `Mapping[str, Any]` surfaces:

- `src/aeat/adapters/outbound/aeat/auth/_session_store.py:26-27` —
  Playwright storage_state blob typed only as arbitrary JSON.
- `src/aeat/adapters/outbound/aeat/auth/_session_store.py:43` — save()
  passes unvalidated metadata dict.
- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py:317` —
  Caller-supplied storage_state for session replay.
- `src/aeat/adapters/outbound/aeat/browser/session.py:69` — Browser
  context storage_state kwarg.
- `src/aeat/adapters/outbound/aeat/browser/_factory.py:76,176` — Same
  storage_state.
- `src/aeat/adapters/outbound/aeat/auth/_providers.py:135,147` —
  build_context_kwargs() returns Mapping[str, Any].
- `src/aeat/application/aggregation/_iva_ledger.py:165` — issue_common
  collects constructor kwargs via spread.
- `src/aeat/application/aggregation/_renta_ledger.py:199` — Same.
- `src/aeat/adapters/outbound/google/_calc_sheets_apply.py:292-606` —
  Google Sheets API request bodies as raw dicts.
- `src/aeat/adapters/outbound/google/_calc_sheets_pull.py:221-231` —
  Spreadsheet developer-metadata pairs extracted by string keys.
- `src/aeat/adapters/outbound/storage/_google_drive.py:229,322,387,491,517`
  — Drive API response entries.
- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py:115` —
  tomllib.loads() result.
- `src/aeat/adapters/outbound/llm/_cache.py:148,264` — LLM cache
  payload cast.
- `src/aeat/domain/calculations/registry/_schema.py:817-818` —
  DataBindingDefinition.selector and .aggregation.
- `src/aeat/domain/calculations/registry/_queries.py:368,378` —
  _public_mapping accepts and returns untyped mapping.
- `src/aeat/adapters/persistence/storage/_rotation.py:333,446` — Any
  param.

cast() with no runtime check:

- `_authenticator.py:920` — Playwright storage_state() blindly cast.
- `_queries.py:378` — Internal recursive mapping walker.
- `_work_unit.py:268` — Cast after isinstance branch.
- `_legal.py:15` — Registry's legal source table.
- `_corpus.py:846` — RuleKind cast after membership check.
- `_renta_web_open.py:106,363` — Playwright page and input_value
  results.

# type: ignore:

- `_calculation_revision.py:337` — __iter__ override.
- `_work_unit.py:277` — WorkUnitMap.__iter__.
- `_filing_record.py:282` — FilingRecordMap.__iter__.
- `_verification_report.py:201` — VerificationReportMap.__iter__.
- `_registry_provider.py:161` — source_kind str passed where narrower
  type expected.
- `_models.py:146,160,174` — @computed_field on @property.
- `_service.py:178` — Same.

isinstance(x, str) discrimination:

- `_work_unit.py:198` — Coerce validator branches on string.
- `_filing_record.py:169` — Same.
- `_calculation_revision.py:346` — __getitem__.
- `_models.py:88,127,129` — Period._parse_raw_period.
- `_calc_sheets_pull.py:202,261,468,491,504` — Spreadsheet cell values.

dict.get("magic_key") string-keyed access:

- `_calc_sheets_pull.py:221-231` — 9 magic string keys for Google
  metadata.
- `_local.py:252,263,269,324,329,334,337` — Sidecar TOML magic keys.
- `_google_drive.py:247,272,353,358,459,531,660-680` — Drive file
  metadata.
- `_declarations.py:621-623` — Filing action index dict.
- `_cache.py:277,288` — Cache payload by magic key.
- `_master_key.py:586` — Master key TOML preview.

model_validate with untyped upstream:

- `_loader.py:73,77` — TOML data["modelo"] raw dict before pydantic.
- `_loader.py:167,172` — Legal/source refs from raw TOML spread.
- `_bindings.py:884,1047,1147` — Selector coerced via dict() then
  model_validate.
- `_iva_ledger.py:158` — Period.model_validate.
- `_manifest_io.py:120` — BucketManifest.model_validate.

selector as untyped sub-schema:

- `_schema.py:817` — DataBindingDefinition.selector for 10+ binding
  sources.
- Currentized 2026-06-29 — relation `source_revision_selector` and
  `period_alignment` are now typed models in `_schema_surfaces.py`.
- `_queries.py:99` — Public query row exposes selector as opaque
  mapping.

ID types — Annotated[str, ...] with format-only check, no existence
cross-reference:

- `_ids.py:14-34` — All 21 ID types. Regex enforces format but no
  field anywhere cross-checks existence in the registry index at
  validation time.

#### Pass 2 — Top 10 by severity

1. `DataBindingDefinition.selector` (registry/_schema.py:817). Single
   field acting as 10+ sub-schemas. Misspelled selector key returns
   None silently from extra=ignore default.
2. `_resolve_profile_fact` (registry/_schedules.py:71). Profile
   condition fields resolved by dotted string traversal at runtime.
3. `PersistedBrowserSession.storage_state: dict[str, Any]` +
   cast(dict[str, Any]) (auth/_session_store.py:26,
   _authenticator.py:920).
4. `build_context_kwargs() -> Mapping[str, Any]` on
   `BrowserContextProvider`.
5. Google Sheets developer-metadata `pairs.get("aeat_filing_year")`
   etc. (calc_sheets_pull.py:221-231).
6. `issue_common: dict[str, Any]` spread into
   `IvaLedgerAggregationIssue(**issue_common, ...)`.
7. `model_validate(dict(binding.selector))` for binding selector
   handlers (registry/_bindings.py:884,1047,1147).
8. `source_kind: str` on `CounterpartAggregationObservation` plus `#
   type: ignore[arg-type]` at call site.
9. `_public_mapping(value: Mapping[str, Any]) -> dict[str, object]`
   (registry/_queries.py:368). Erases all type information.
10. All 21 ID types with no cross-reference existence check
    (registry/_ids.py:14-34).

### Wave 2 — Agent 10 — TOML data layer vs pydantic schema

Registry TOML files live at `registry/aeat/` (not under `src/`):

- `registry/aeat/modelos/<id>.toml` — single-file modelos.
- `registry/aeat/modelos/100/manifest.toml` +
  `registry/aeat/modelos/100/revisions/<year>.toml` — directory-mode
  (modelo 100 only).
- `registry/aeat/legal/*.toml` — shared legal-reference catalogue.
- `src/aeat/core/external_constants.toml` — runtime constants.

No YAML or JSON definition files; TOML is the sole on-disk format.

#### On-disk shape (modelo 130)

```
[modelo]
id = "130"

[revisions."2019-y-siguientes"]
valid_from = 2019-01-01

[[revisions."2019-y-siguientes".casillas]]
id = "01"
...
```

Casillas are a list (TOML array-of-tables), not a map. Revisions are a
map keyed by revision id string.

#### Cross-modelo references

Encoded as string IDs in `RelationDefinition.source_modelo: ModeloId`.
Validator checks relation closure across the full registry in
`_validate_relation_closure` (`_validate.py:215`), so unresolvable
cross-modelo refs are caught at full-registry validation time, not at
parse time.

`AlgorithmBindingDefinition.inputs: Mapping[str, BindingId | CasillaId
| ParameterId | RelationId]` uses union string aliases. Structural
integrity checked in `_validate_revision`, not in pydantic
validators.

#### Legal references

First-class typed entities with their own TOML files
(`registry/aeat/legal/*.toml`) parsed into `LegalReference` pydantic
models. Modelos carry only the ID. `corpus_ref` field
(`_schema.py:160`) holds repository-relative path + anchor.

#### Loader parsing

`_loader.py:_build_modelo_definition_from_data`:

1. `_reject_local_catalogues` — enforces source/sources/legal keys not
   present in modelo files.
2. Manually stitches `{"id": revision_id, **raw_revision}` before
   calling `ModeloRevision.model_validate(payload)`.
3. `ModeloDefinition.model_validate(...)`.

Base class `RegistryModel` (`_schema.py:90–93`) sets `extra="forbid"`,
`strict=True`, `frozen=True`. Every TOML key maps to a declared typed
field or the document is rejected.

#### Typo detection

Caught at load time via `extra="forbid"`. A typo (e.g. `lable` instead
of `label`) causes `ModeloRevision.model_validate` to raise
`ValidationError`, re-raised as `RegistryLoadError`.

#### Duplicate casilla declarations

Loader enforces uniqueness at directory-mode level (duplicate revision
id), within-revision (`_validate.py:248`), and registry-tree level
(duplicate modelo ids).

#### Workbook fixture data

`WorkbookParityReference` declared inline in revision TOML.
`output_cells: Mapping[WorkbookOutputId, WorkbookCellRefStr]` maps
scenario output label to workbook cells. In data files (TOML),
`fixture_id: WorkbookFixtureId` is pattern-constrained, but there is
still no registry-side check that a fixture with that id actually
exists at load time.

#### Legal corpus referential integrity

`_validate.py:993–1001` — `_missing_refs` iterates every `legal_refs`
tuple and checks each ID against `RegistryCatalogues.legal`. Runs
during `RegistryValidator.validate_modelo`. Validation is deferred —
does not fire at TOML parse time. There is no validation at
`ModeloRevision.model_validate` time that legal ref strings resolve to
known catalogue entries.

`verify_legal_reference` in `_legal.py:29–52` optionally checks
`required_text` strings are present in the actual corpus file when
`source_root` is provided.

#### Data-layer governance gaps

1. Legal and source ref IDs are plain strings at parse time. Typo
   passes parse time and is only caught during explicit
   validate_modelo / validate_registry calls.
2. `fixture_id` on `WorkbookParityReference` is a `WorkbookFixtureId`
   alias, but it is never resolved against a declared fixture catalogue.
3. Currentized 2026-06-29: the old `validation_refs` field on
   `CasillaDefinition` has been removed, so this specific silent-reference
   channel is closed. Exact grep now finds `validation_refs` only in
   historical vault prose.
4. `AlgorithmBindingDefinition.inputs` and `outputs` are `Mapping[str,
   str]`-like unions with no intra-revision resolution at load time.
5. Currentized 2026-06-29: cross-modelo `source_modelo` references are
   validated during full `validate_registry`, not `validate_modelo`.
   This is the intended boundary because the source-modelo tree is not
   available to a single-model validator; `ValidatedRegistryAuthority`
   runs the full gate at load before production snapshots are served.
6. Directory-mode revision files can be loaded partially without
   duplicate-check coverage.

### Wave 2 — Agent 11 — Existing ADR coverage map

#### Step 1 — ADR corpus relevant to linkage concerns

Key ADRs:

- `2026-04-12-casilla-db-adr.md` — original casilla corpus shape.
- `2026-04-17-modelo-formulas-adr.md` — formula engine.
- `2026-04-17-attachment-service-adr.md` — content-addressed evidence.
- `2026-04-21-casilla-schema-completeness-adr.md` — casilla schema with
  provenance fields.
- `2026-04-22-ruleset-architecture-adr.md` — registry key grammar.
- `2026-04-22-aeat-fichero-boe-export-adr.md` — fichero BOE serialiser.
- `2026-04-17-export-first-adr.md` — export-first pipeline charter.
- `2026-05-03-calculation-truth-registry-pending-adr.md` — central
  TOML registry.
- `2026-05-04-calculation-authority-evidence-tiering-adr.md` —
  four-tier authority model.
- `2026-05-06-cross-reference-oracle-binding-adr.md` — oracle_id
  binding.
- `2026-05-06-modelo-chain-tier-passage-adr.md` — three-tier chain
  passage.
- `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`
  — bindings discovery.
- `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr.md` —
  registry CLI boundary.
- `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr.md`
  — aggregation pipeline.
- `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr.md` —
  ModeloFilingRecord.
- `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr.md` —
  EvidenceBundle.
- `2026-04-30-secure-persistence-foundation-adr.md` plus waves —
  filing/submission persistence.
- `2026-05-13-cli-workflow-redesign-explain-legal-ref-convention-adr.md`
  — `--explain` flag.

#### Step 2 — Coverage matrix

| Cell | Description | Rating |
|------|-------------|--------|
| L1 | Casilla declaration shape | explicit |
| L2 | Casilla→formula binding within a modelo | explicit |
| L3 | Casilla→legal-reference attachment shape | partial |
| L4 | Cross-modelo same-period dependency (relation) | explicit |
| L5 | Cross-modelo prior-period dependency | partial |
| L6 | AEAT oracle / portal cross-reference | explicit |
| L7 | Counterpart / ledger aggregation binding | partial |
| L8 | Modelo→workbook cell export mapping | partial |
| L9 | Modelo→AEAT fichero export mapping | explicit |
| L10 | Calculation result → persisted record shape | explicit |
| L11 | Calculation result → evidence linkage | partial |
| L12 | Sensitivity classification attachment | explicit |

#### Step 3 — Absent / implicit cells

- L3: `CasillaSource.citation: str` is free-form; no typed FK to
  `LegalReference` catalogue.
- L5: Tier 3 outcomes specified but no ADR specifies the TOML binding
  shape.
- L7: Aggregation pipeline boundary accepted but pydantic shape not
  locked.
- L8: No ADR specifies the typed record linking `ModeloRevision` to a
  workbook cell.

#### Step 4 — ADR overlap

- cross-reference-oracle-binding vs modelo-chain-tier-passage —
  cross-modelo terminology. Orthogonal concerns but no umbrella
  document.
- app-modelo-bindings-shape vs app-registry-boundary — application↔
  registry seam. Neither explicitly specifies which Python type
  crosses the seam.
- casilla-schema-completeness vs modelo-formulas — same shape,
  different framing. No ADR states canonical merge.

#### Step 5 — Umbrella ADR outline

Proposed title: Linkage surface contract —
modelo-casilla-formula-evidence binding governance.

Scope:

1. Declare canonical typed join between `CasillaDefinition` and
   `LegalReference` catalogue entries (resolves L3).
2. Specify TOML shape and Pydantic runtime type for `previous_filing`
   bindings (resolves L5).
3. Lock typed output contract of aggregation providers (resolves L7).
4. Specify workbook cell mapping record (resolves L8).
5. Resolve terminology collision between `live_cross_references /
   oracle_id` and `relations / dependency_role`.
6. State registry validation gate requiring every casilla id
   referenced by a formula to have a provenanced entry.

### Wave 3 — Agent 12 — CLI surface: linkage exposure inventory

Command tree (`__init__.py:216-228`):

- `aeat config` → init, profile, auth, repair.
- `aeat app` → overview, ledger, live, modelo, registry, review.

`aeat app modelo` is the primary linkage surface with sub-trees: list,
describe, casillas, formulas, aggregate, bindings list/preview, work
create/list/status/rename/discard/calculate/revisions/history/verify/file/resume/amend,
filing-record list/view/import, verification-report list/view, audit
view/check/export/replay, history.

No standalone `aeat app calculate`, `aeat app export`, or `aeat app
filing` surface — these live under `aeat app modelo work <verb>` and
`aeat app modelo filing-record`.

#### Inputs and validation

- Modelo ID: accepted as `str` everywhere. No `ModeloId` typed
  wrapper. Validation deferred to `RegistryQueryService` /
  `parse_modelo_period`.
- Casilla codes: accepted as raw `str` via `KEY=VALUE` string splits
  (`:933-934`). `_parse_casilla_override` / `_parse_kv_spec` checks
  only that `=` is present.
- Period / year: `str` and `int`. `_resolve_year_period` normalises
  user aliases.
- Evidence kind: cast from `str` to `ExternalEvidenceKind` enum at CLI
  boundary.
- Amendment kind: cast from `str` to `CalculationRevisionAmendmentKind`.
- Binding overrides: remain raw `(str, str)` pairs at CLI; Decimal
  coercion in handler. Key never validated against `BindingId` type.
- File paths: validated by Click/Typer decorators.

#### Internal dispatch

- `PerModeloAggregationCommand` (pydantic) is constructed via
  `model_validate_json` — only case where CLI side explicitly builds
  a typed command object.
- All other handlers pass raw `str` / `int` / `Decimal` / `dict`
  scalars directly into application functions.
- `_service()` builds `RegistryQueryService` from
  `ValidatedRegistryAuthority`.

#### Outputs

`_emit` calls `render_command_output` with both a payload (pydantic
model or ad-hoc dict) and pre-formatted text lines. JSON path calls
`emit_json_document` / `emit_json_success` from
`core/json_contract.py`.

`_jsonable_payload` walks the payload and calls `model_dump(mode="json")`
on pydantic `BaseModel` instances. However, most `_modelo.py` handlers
pass ad-hoc dicts rather than typed `OutputSchema` instances. The
`SchemaEnvelope` / `register_schema` infrastructure exists but is not
used by `_modelo.py`.

`CalculationRevision` rendering: `casilla_values` serialised as
`{str: str}` (Decimal converted via `str(v)`). The casilla key is plain
string.

`VerificationReport` rendering: findings include `casilla_id: str |
None`, `expectation_id`, `message`, `next_action`. No cross-modelo
dependency or legal_ref in the rendered finding shape.

#### Cross-references in output

- Casilla values: `dict[str, str]`. No formula provenance, no
  legal_ref, no cross-modelo relation.
- Bindings list: exposes `binding_id`, `source`, `readiness`,
  `typed_enum`. The referred modelo or filing record id not surfaced.
- Verification report findings: no legal_ref in CLI output shape.
- Registry inspect/verify: emits aggregate counts but no individual
  legal_ref detail.
- `audit-oracles`: emits per-cross-reference oracle applicability
  declarations.
- No command surfaces `legal_refs` per casilla, formula expression
  detail, or input provenance.

#### Failure modes

All errors converted to `typer.BadParameter` with exception's `str()`.
No structured error envelope reaches `--json` output.

#### Linkage Concept Exposure Table

| Concept | Exposed by | Typing | Typing lost at |
|---------|-----------|--------|----------------|
| casilla | modelo casillas, work calculate --casilla, work verify/file | raw str | _parse_casilla_override; casilla_values: dict[str, str] |
| modelo | all modelo verbs, registry inspect/verify | raw str | passed to RegistryQueryService as string |
| formula | modelo formulas | str fields | Formula expression/AST never reaches CLI |
| binding | modelo bindings list/preview, work calculate --binding | str | No BindingId type; validated only by set membership |
| relation/cross-modelo dep | registry audit-oracles only | strings in dict | Referred model's revision/casilla not exposed |
| legal_ref | registry inspect/verify (count only) | integer | Individual legal_ref never surfaced |
| export_field | modelo audit export | pydantic-driven | Typed at service return |
| attachment/evidence | filing-record import, audit verbs | str / enum | evidence_reference_id passed as untyped string |
| justificante | no dedicated CLI command found | N/A | Not exposed at CLI surface |
| input provenance | work revisions output (inputs_snapshot field in dict) | ad-hoc dict | dict(rev.inputs_snapshot); no typed schema |

Key finding: SchemaEnvelope / register_schema typed JSON-contract
system exists in core/json_contract.py but _modelo.py passes ad-hoc
dicts to _emit for almost every command — the typed envelope path is
unused in the modelo work lifecycle.

### Wave 3 — Agent 13 — CLI command trace end-to-end

#### Command A — aeat app modelo work calculate <work_unit_id>

CLI entry point: `src/aeat/entrypoints/cli/_modelo.py:937–1020`.
Framework: Typer (wrapping Click). Arguments declared as plain Python
types annotated with `Annotated[str, typer.Argument]` /
`Annotated[list[str] | None, typer.Option]`. No custom Click param
types. All coercion is ad-hoc string splitting in the handler body.

Application layer: `_modelo.py:1000` calls
`calculate_modelo_revision(work_unit_id, ...)`. Function signature
accepts `work_unit_id: str`. No typed ID wrapper crosses this
boundary.

Domain layer: `_actions.py:732–755`. Work unit fetched by
`work_units.get(work_unit_id)` (dict keyed on str). Registry authority
loaded via `ValidatedRegistryAuthority.load(...)` then
`authority.snapshot(str(work_unit.modelo), ...)` — note explicit
`str(work_unit.modelo)` coercion, suggesting `work_unit.modelo` is a
typed ID that must be stringified to cross into the registry query
API.

Domain → registry runtime: `_actions.py:799–806`:

```
engine_result = calculate_registry_snapshot(
    snapshot,
    inputs=resolved_inputs,           # dict[str, Decimal]
    date_context={"filing_period": period_date},
    binding_values=resolved_bindings,
    enum_binding_values=resolved_enum_bindings,
    relation_values=resolved_relations,
)
```

All four dictionaries are str-keyed.

Cross-modelo / prior-period: CLI passes `None` for `relation_values`.
Default resolved at line 785 is `dict(relation_values or {})` —
empty dict. **The CLI work calculate command has no mechanism to
supply prior-period values for relation-bearing modelos.**

Result construction: `engine_result` is a `RegistryCalculationResult`
— typed, frozen pydantic model with `values: Mapping[str, Decimal]`
and `entries: tuple[RegistryCalculationEntry, ...]`. Each entry
carries `legal_refs`, `source_refs`, `operand_refs`,
`operand_values`.

At `_actions.py:817`, only `engine_result.values` is extracted:
`casilla_values: dict[str, Decimal] = dict(engine_result.values)`.
**The entries tuple containing every formula's legal_refs, source_refs,
operand_refs, operand_values is not persisted in `CalculationRevision`.**
The count `len(engine_result.entries)` is emitted to the bucket event
payload as a string (`_actions.py:874`) and then discarded.

Output rendering: `_modelo.py:1015–1020` builds plain `dict[str, Any]`.
Casilla values serialised as `{k: str(v) for k, v in
rev.casilla_values.items()}`. JSON payload contains no `legal_refs`,
no `source_refs`, no `operand_refs`, no formula trace.

#### Command B — aeat config google sync calc export

CLI entry point: `src/aeat/entrypoints/cli/_config/_google.py:664–740`.
Typer. `--modelo`: raw str, no custom type. `--period`: raw str.
`--year`: int with min/max Typer validator.

Snapshot load: line 691 calls `_load_snapshot(modelo, period, year)`.
Module-private function does plain string equality scan: `next((c for
c in modelos if c.id == modelo), None)`. If string doesn't match,
raises `CliRefusedBoundaryError`.

`RegistrySnapshotError` from `_authority.py:47` or `_temporal.py:33`
**not caught** in `_load_snapshot` — propagates unguarded through
`google_sync_calc_export`, which only catches `GoogleAuthError` and
`StorageError`.

Adapter selection: no runtime dispatch between export adapters.
`build_export_plan` consumes the `RegistrySnapshot` generically.
Only adapter is Google Sheets.

Prior-period / relation lookup: `build_export_plan` accepts a
`relation_resolver: RelationResolver | None`. This command does NOT
pass a resolver: always calls `build_export_plan(snapshot,
operator_inputs=OperatorInputs(), relation_values=RelationValues())`,
unconditionally leaving relation cells blank. **The --prefill-relations
flag and the call to resolve_relations_from_local_store described in
the docstring do not appear in the current code — documented
capability is absent from implementation.**

Result construction: `apply_export_plan` returns
`CalcSheetsApplyResult` pydantic model. Payload uses
`snapshot.modelo.id` (str) and `snapshot.revision.id` (str). Typed
model objects are downcast to string .id fields before rendering.

#### Seam degradations (ranked)

1. `work_unit_id` enters and traverses the full stack as bare `str`.
2. `str(work_unit.modelo)` required to call `authority.snapshot()`.
3. All casilla, binding, and relation dict keys are `str`.
4. `RegistryCalculationResult.entries` discarded at `_actions.py:817`.
5. `CalculationRevision.casilla_values` keys are `str`, not typed IDs.
6. CLI output serialises casilla values as `str(v)` in plain `dict[str,
   Any]`.
7. Export CLI `--modelo` and `--period` are raw `str` options.
8. `RegistrySnapshotError` not caught in `_load_snapshot` or export
   handler.
9. Export result payload uses `snapshot.modelo.id` (str) and
   `snapshot.revision.id` (str) — typed model objects downcast.

### Wave 3 — Agent 14 — CLI JSON contract and identity propagation

#### A. JSON contract envelope shape

`SchemaEnvelope` (`json_contract.py:75`) defines intended canonical
shape: `{ schema_version, command, result: <OutputSchema subclass>,
warnings: [] }`.

`emit_json_success` (`json_contract.py:167`) emits this envelope.
However, **no production command actually calls `emit_json_success` or
`@register_schema` today** — both grep searches return empty.
`SCHEMA_REGISTRY` dict exists and is populated by the decorator at
import time, but zero command schemas have been registered.

All commands reach the user via `_emit(ctx, payload, lines)` →
`render_command_output`, which for JSON emits a raw `json.dumps` of
the payload with no envelope at all — no `schema_version`, no
`command`, no `warnings`. ADR `2026-04-25` explicitly acknowledges
this as Phase 1 only (foundations, no command bindings).

Two different serialisation paths co-exist:

- `output_rendering.py`: `render_command_output` (untyped `dict[str,
  Any]`, no envelope, used by all current commands).
- `json_contract.py`: `emit_json_success` / `SchemaEnvelope`
  (envelope-wrapped, zero current callers).

#### B. Linkage ID rendering

Minimum-typed (current reality): `_calculation_revision_payload`
(`_modelo.py:851`) renders casilla values as `{k: str(v)}` — raw
`dict[str, str]`. No display name, formula reference, or legal refs
travel with the value.

Maximum-typed (query layer provides, CLI discards): `ModeloCasillaRow`
(`_queries.py:67`) carries `casilla_id`, `label`, `section`,
`data_type`, `input_kind`, `required`, `formula` (as plain ID
string), `binding` (plain ID string), `legal_refs: tuple[str, ...]`,
`source_refs: tuple[str, ...]`. When `_emit(ctx, report, lines)` is
called on a `ModeloCasillasReport`, full pydantic object passed as
`payload` does appear in JSON output.

#### C. Identity propagation

Identity (`core/identity/`) is a pure validation primitive — not a
linkage dimension in JSON output. Validates NIF/NIE/CIF strings and
returns canonical form. `bucket_id` carries bucket linkage, but NIF
of taxpayer owning that bucket is not surfaced in any CLI JSON
response. No `FilingDraft` JSON shape includes the subject's tax
identity.

#### D. Internationalisation

Casilla `label` values in `ModeloCasillaRow` are plain strings sourced
from registry YAML — registry-defined Spanish labels, not i18n keys.
`tr()` function drives CLI help text and error messages only. In JSON
mode:

- Canonical `casilla_id` travels alongside the label — downstream CI
  tooling can anchor on the ID.
- No language negotiation: `label` always registry's native Spanish.
- `legal_refs` tuple emits ID strings (e.g., `"lirpf.art-99"`), not
  resolved textual citations.

#### E. Error surfaces

`ErrorEnvelope` (`errors/_registry.py:79`) is the machine-readable
stderr shape: `{schema_version, code, category, message, suggestion,
retryable, runbook_id, context, trace_id}`. Seven categories map to
seven exit codes. Error code is stable string slug per `AeatError`
subclass.

For linkage failures (unknown casilla, missing binding, registry
snapshot errors), domain raises `RegistryValidationError` or
`RegistrySnapshotError`. These carry a `message` string but **not a
structured `context` dict with the failing linkage ID** — the failing
casilla/formula/binding ID is embedded in the exception message text,
not in a typed `context["casilla_id"]` field. **Error parsing by
downstream automation must regex the message string.**

#### F. CLI-to-machine vs CLI-to-human duality

Duality via `OutputFormat`: `--json` activates JSON, default activates
tab-separated text. JSON path calls `jsonable_output_payload` which
walks full pydantic model via `model_dump(mode="python")`. Fields
present in pydantic but omitted from human lines list are included in
JSON. No envelope wraps the JSON.

#### CLI JSON contract gaps for linkage exposure

1. No canonical envelope on any command today. SCHEMA_REGISTRY is
   empty at runtime.
2. Casilla values in `CalculationRevision` carry IDs without formula
   provenance.
3. Linkage error context is untyped. Failing casilla/formula/binding
   ID lives only in free-text message field.
4. Formula `expression` is a raw `Mapping[str, object]` in
   `ModeloFormulaRow`. No type tag or schema version.
5. Filing record JSON carries no subject tax-identity.

### Wave 3 — Agent 15 — CLI operator surface and diagnostics

#### Inventory command

`aeat app ledger inventory` is not a modelo inventory — stock-movement
ledger. The closest thing to a modelo registry listing is `aeat app
modelo list` which renders `code`, `title`, `cadence`, `tax_domain`,
and `revision_count` only — no casilla count, no formula count, no
cross-modelo relation count. `describe` adds counts for one
modelo/period.

No single command that shows all revisions of all modelos with their
casilla counts together. `revision_ids` is carried internally but
the rendered text for `aeat config repair` only says "N modelos, M
casillas" — no revision-level breakdown.

#### Diagnostics command (aeat config repair)

`build_config_repair_report` runs five checks:

- `environment.python` — Python version.
- `package.version` — package semver.
- `logging.file` — log directory presence.
- `registry.load` — registry loads and returns `RegistryVersionSummary`
  (modelo count, casilla count, formula count).
- `secure_state.load` — profile/auth readiness.

The `RegistryVersionSummary` counts modelos, revisions, casillas,
formulas — but **no check is performed on cross-domain linkage**:

- No check verifies every `RelationDefinition.source_modelo` maps to
  actually-present modelo in authority.
- No check verifies every `legal_refs` entry maps to known
  `NormativeReference`.
- No check verifies every `source_refs` entry resolves to known
  source.
- No orphaned-binding detection.
- `repair_integrity.py` is entirely limited to `secure_objects` table
  decryptability.

#### Verification / review surface

`aeat app review queue` (`_review.py:16-37`) renders per-item:
`item_id`, `kind`, `source_kind`, `affected_object_id`, `bucket_id`,
`period`, `severity.value`, `canonical_next_command`. `_to_row`
strips all internal `FindingReviewItem` or `TransactionReviewItem`
fields to these eight columns.

The `source` field — which carries a `FilingValidationFinding`
containing structured error codes and the formula that produced the
finding — is completely dropped in projection.

The formulas renderer outputs only `formula_id`, `target`, `inputs` —
`legal_refs` and `source_refs` are absent from the text output.

#### Workflow surface

`WorkflowEngine` walks the pipeline: profile check → site health →
deadline check → filing draft build → casilla calculation →
submission preflight. Each stage returns `WorkflowResult` /
`WorkflowStep` carrying a `WorkflowAbortReason`. The typed linkage
objects (registry snapshot, binding resolution results, relation
requirements) are not persisted to `WorkflowStep`. `WorkflowStage`
carries `details: str`.

#### Operator vs expert duality

Operator tier (`aeat app`) commands expose UX-level fields: severity,
period, state, canonical next command. No linkage provenance.

Engineer tier (`aeat app registry`): JSON payload for `registry
inspect/verify` does carry `legal_reference_count`,
`source_reference_count`, `cross_reference_count`, and `modelos`. The
report carries `legal_refs`/`source_refs` per-revision in JSON but
the text renderer does not echo them — JSON-only.

ADR `2026-05-12-aeat-cli-config-vs-setup-namespace-adr.md` governs
namespace consolidation but makes no explicit statement about what
linkage state is allowed to be surfaced at which tier.

#### repair_integrity.py

The module repairs nothing about cross-domain linkage. It is purely a
cryptographic row-readability checker for the local secrets store.

#### Linkage state operator cannot currently observe

- `legal_refs` and `source_refs` tuples on every formula, binding, and
  casilla (domain contains them; no operator-facing text command).
- Which `RelationDefinition` objects link which modelos.
- The `source_modelo` field of each `RelationDefinition` and whether
  it resolves.
- The relation chain behind a `FindingReviewItem`.
- The `WorkflowStep` binding-resolution results.
- Per-casilla formula grounding (`formula_id → legal_refs`).
- Whether `source_refs` entries cross-validate against the normatives
  catalogue.

#### Linkage drift diagnostics should catch but doesn't

- `RelationDefinition.source_modelo` dangling reference.
- `legal_refs` orphan check.
- `source_refs` orphan check.
- Binding source availability mismatch.
- Cross-modelo filing-year alignment.
- Registry formula count drift between package versions.

---

## Re-audit verdict (post-execution honesty pass)

A scripted re-audit at `scratch/reaudit_inventory.py` re-walked a
35-row sample of the inventory against current code. The sample
focused on rows that had been claimed `fixed` during execution
plus the rows tagged `open` or `wontfix-document`. Results:

| verdict           | count | meaning                                         |
|-------------------|-------|-------------------------------------------------|
| verified          | 14    | re-audit confirms the anti-pattern is gone      |
| regressed         | 11    | claim of `fixed` was wrong; anti-pattern remains |
| partial           | 3     | structural ingredient landed; full fix did not  |
| open              | 2     | matches the inventory's `open` label             |
| wontfix-confirmed | 4     | matches the inventory's `wontfix-document` label |
| unverified        | 1     | script could not produce a definitive verdict   |

The historical 11 regressed rows in that re-audit sample (`R007`,
`R008`, `R009`, `R011`, `R025`, `R050`, `R053`, `R096`, `R097`,
`R101`, `R102`) reset the headline closure number at the time. The
earlier "98 / 102 closed (96%)"
figure is wrong in two ways: (a) it was extrapolated from
inventory edits rather than verified, and (b) the sample shows
~31% of claimed-fixed rows in this set are not actually fixed.
67 rows in the full 102 were not visited by the script and carry
their original execution-time status with a `(unverified by
re-audit)` qualifier.

Current-state correction (2026-06-29): `R008`, `R009`, `R011`, and
`R025` no longer belong in the live regressed set. `R008` and `R009`
are closed because `RelationDefinition` now declares
`source_revision_selector: RelationRevisionSelector` and
`period_alignment: RelationPeriodAlignment`, rejecting legacy revision
aliases, empty alignment maps, and retired `same_period` mode at schema
construction. `R011` is closed because `RelationDefinition` now declares
`source_casilla_id: CasillaId`, legacy `source_output` is rejected, and
production code has no `relation.source_output` access. `R025` is
closed because the first-slice Renta routing table is typed, canonical
within the Renta domain, and validated against Modelo 100 casillas at
snapshot construction.

Honest headline: **structural delivery is mixed.** Concrete typed-
envelope work (CasillaObservation, relation selector models, capability
flags, OracleId field on schema, typed CLI payloads, registry data
backfill for M100 cross_model_output, M303 form_number) did land. The
broad stored binding-selector alias, workflow-step typed details, the
FilingDraft typed identity and snapshot reference, the `--relation` CLI
surface, and the OracleFilingObservation subtype did not.

Current-state correction (2026-06-29): `_check_all_id_references`
is wired into snapshot construction at `_snapshot.py:174`, so R021 is
closed for the production snapshot path. Relation closure is also
closed for production access: `ValidatedRegistryAuthority.load` runs
full-tree `validate_registry`, whose registry-scope gate calls
`validate_relation_closure`. Remaining validation-order questions
should be scoped to standalone diagnostics and selector-shape surfaces,
not to `build_snapshot`.

### Wontfix-document rationale

The five rows tagged `wontfix-document` are deliberate non-fixes
recorded so future readers do not re-discover them as bugs.

`R038 — domain/attachments/_repository.py:90 hardcodes
SensitivityClass.FINANCIAL`. The repository persists attachments
whose sensitivity is set by the operator at upload time and is not
derived from a modelo schema (attachments are not modelo-scoped in
the same way justificantes are). The hardcoded default reflects
the actual policy: financial-grade until proven otherwise. Moving
this to a schema-attached field would require introducing
attachment categories and is out of scope for the linkage epic.

`R039 — domain/justificante/_schema.py has no link to FilingDraft`.
Justificantes are issued by AEAT after a successful submission;
the local app never holds both a FilingDraft and its corresponding
justificante in a state where a structural link would prevent a
real defect. The link does exist informally via shared
`work_unit_id` / submission references. A formal foreign-key style
field would require migration work whose payoff is documentation,
not correctness — recorded as documentation debt.

`R040 — domain/attachments/_models.py has no link to FilingDraft
or Justificante`. Same reasoning as R039 plus: attachments are
upload-side artifacts that exist before any filing draft; back-
linking would invert the natural lifecycle. Operator UI handles
the association at retrieval time via search rather than via a
typed reference field.

`R041 — FilingDraft.schema_version: str bare string`. The field
is part of the content-addressed `draft_id` hash. Replacing it
with a typed `RegistrySnapshotRef` would change every previously
persisted `draft_id`, invalidating local stores. The cost of the
migration outweighs the typing benefit for a field whose value is
already constrained by the registry-loader (any drift surfaces as
a `RegistrySnapshotError` at draft re-build time, not as a silent
mis-typing). Documented and left as-is.

`R042 — RegistryFiledStateComparison/Drift has no artifact key`.
Filed-state comparison is currently in-memory only; the comparison
records are not persisted to the secure store under a stable key.
Adding an artifact key implies a versioning contract this code
does not yet have. The structural fix is to first promote
RegistryFiledStateComparison to a stored artifact (separate ADR);
adding the key field on the current in-memory record would create
a field that nothing reads.
