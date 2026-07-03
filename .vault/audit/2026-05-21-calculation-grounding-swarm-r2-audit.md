---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-06-29'
related: []
---

# calculation-engine + registry grounding swarm audit r2

## Scope

Axis: calculation-engine and registry grounding. Read-only inspection of branch
`chore/eliminate-shims` after the M100/M200 schema-hardening campaign, completeness-manifest
rollout, extraction-profile migration to typed `ExtractionTargetDefinition`, and the M347/M840
manifest-removal hotfix (commit `67ea2b0e7`). Verified 26 modelos across all formula-bearing
revisions (31 total revision × modelo combinations).

Scope items checked:

- Provenance chain: `legal_refs`/`source_refs`/`formula_id` on `CasillaObservation` from
  engine through persistence to CLI JSON emit.
- `engine_result.values` coverage: input, bound, and computed casillas.
- Referential integrity at snapshot build.
- Completeness manifests: match against calculation closure; M347/M840 hotfix outcome.
- Extraction profiles: correct use of `ExtractionTargetDefinition` objects.
- Tautological calculation tests.
- Registry internal coherence after M100 hardening (90 casilla declarations, 15 ids x 6 revisions).

## Current State — 2026-06-29

All three original findings are closed on the current implementation path:

- Google Sheets calculation output emits computed rows through `GoogleSyncCalcComputeCasillaPayload`,
  which requires non-empty `legal_refs` and `source_refs`.
- Filed-declaration observations are converted through the registry snapshot; non-canonical casillas,
  justificante metadata, incomplete extraction coverage, and incomplete registry grounding all fail
  closed.
- The calculation-completeness validator is fail-closed for calculation-bearing revisions with no
  manifest. Informative/no-calculation revisions remain valid without an empty manifest.
- Modelo 100 revision 2021 completeness manifest now includes `ley-35-2006:art-75`, matching the
  closure legal refs for casilla `0527` and formula
  `renta-2021-anualidades-alimentos-hijos-suma`.

## Findings

### F1 — CLOSED: Google Sheets calc CLI carries legal/source refs

Original pathway: `src/aeat/entrypoints/cli/_config/_google.py` lines 1200-1207.

Original gap (2026-05-21): The `_compute_casillas_from_pull` helper returned a plain dict per
entry with only `casilla_id`, `value`, and `formula_id`. The `legal_refs` and `source_refs`
fields available on `RegistryCalculationEntry` are silently dropped. Contrast with the main
modelo calculation CLI payload (`_modelo_payloads.py`, `ObservationPayload`) which does surface
both fields.

Original risk: Operators reading the Google Sheets calc output (via `aeat config google sync
calc pull --compute`) receive formula provenance without regulatory grounding. This is an
operator-facing JSON surface the grounding rule requires to carry `legal_refs` and `source_refs`.

Current closure (2026-06-29): `src/aeat/entrypoints/cli/_config/_google_sync_calc.py` now builds
`GoogleSyncCalcComputeCasillaPayload` rows with `legal_refs=list(entry.legal_refs)` and
`source_refs=list(entry.source_refs)`. `src/aeat/entrypoints/cli/_config/_google_payloads.py`
requires both fields with `Field(min_length=1)`. Regression coverage:
`src/aeat/entrypoints/cli/tests/test_google_payloads.py::test_google_calc_compute_payload_rejects_computed_rows_without_provenance`.

---

### F2 — CLOSED: filed-declaration conversion backfills registry provenance

Original pathway: `src/aeat/adapters/outbound/aeat/sede/_declarations.py` line 1480.

Original gap (2026-05-21): `registry_observation_from_filed_declaration` converted AEAT-scraped
`FiledDeclaracionObservation` into a `RegistryModeloObservation` by building
`CasillaObservation` items with no `legal_refs` or `source_refs`. The function has no inline
comment explaining this is an external-API boundary exception. The produced observations are
consumed by `resolve_previous_filing_binding_values` and `resolve_relation_values_from_observations`
purely as a value-lookup source for binding resolution; they are not persisted as the typed
observations tuple on a `CalculationRevision` and do not flow through the CLI provenance chain.

Original risk: The grounding rule states every casilla observation carries provenance. The
binding-resolution consumer reads only `casilla_values` (the computed property), never
`legal_refs`/`source_refs`, so the semantic gap is latent rather than causing an active
calculation error. However, the boundary is not documented, which creates risk that a future
consumer of these observations assumes provenance is present and silently receives empty tuples.

Current closure (2026-06-29):
`src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py::registry_observation_from_filed_declaration`
resolves the current registry snapshot, validates every observed casilla against
`casillas_by_id(snapshot.revision)`, refuses justificante metadata as registry input, refuses
incomplete extraction coverage, and emits `CasillaObservation` rows with `legal_refs` and
`source_refs` copied from the registry casilla definition. Regression coverage:
`src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_part1.py` and
`src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_part2.py::TestFiledObservationBindings`.

---

### F3 — CLOSED: completeness manifest gate is fail-closed for calculation-bearing revisions

Original pathway: `src/aeat/domain/calculations/registry/_validate_revision_identity.py` lines 180-191.

Original gap (2026-05-21): `_emit_completeness_gate_failures` returned immediately when
`revision.completeness_manifest is None`. A calculation-bearing revision with no manifest
passed validation silently. This was the documented staged-rollout design.

Current closure (2026-06-29): `src/aeat/domain/calculations/registry/_validate_completeness.py`
derives `calculation_closure_casilla_ids(revision, modelo_id)` when `completeness_manifest` is
absent. If the closure is non-empty, validation fails with the closure casilla ids named.
`src/aeat/domain/calculations/registry/_validate_revision_sections.py` passes the current
`modelo.id` into the gate so cross-modelo selectors remain scoped correctly. No-calculation
revisions still validate without empty manifests. Regression coverage:
`test_calculation_bearing_revision_without_manifest_fails_closed`,
`test_revision_without_calculation_closure_passes_without_completeness_manifest`, and the full
`test_record_design.py` suite.

Current dormant count is `5`: M308, M347, M360, M840, and M721 have no calculation closure and no manifest. Modelo 714 is calculation-bearing and manifest-gated.

## Clean Areas

**Provenance chain (engine to persistence to CLI):** `_build_typed_observations` in
`src/aeat/application/modelo/_actions.py` correctly builds `CasillaObservation` for every
casilla in `engine_result.values`: computed casillas pull from `RegistryCalculationEntry`
(formula_id, operand_refs, operand_values, legal_refs, source_refs); input and bound casillas
pull `legal_refs`/`source_refs` from the registry casilla definition. A missing registry casilla
raises `CasillaProvenanceMissingError` rather than yielding an observation with empty provenance.
The amendment path (`_amendment_observations`) carries the same guarantee. The main `calculate`
CLI payload (`_modelo_payloads.py`, `ObservationPayload`) surfaces all provenance fields.

**engine_result.values full coverage:** `_initial_values` in `_formula_runtime.py` seeds all
non-computed casillas so every casilla on the revision appears in `values`. The `entries` tuple
covers only formula-computed casillas — the `_build_typed_observations` pattern is the canonical
fix and is applied in all production paths.

**Referential integrity at snapshot build:** `_check_all_id_references` runs on every
`RegistrySnapshot`. Live validation of all 26 modelos passed without error.

**Extraction profiles — typed targets:** All `extraction_profiles` in the registry now use
`ExtractionTargetDefinition` objects (`casilla_id`, `match_strategy`, `value_kind`). The
modelo-111 bare-string migration (commit `9a6ace27`) and the multi-modelo migration (commit
`80cd753c`) are complete. No bare-string targets remain.

**Completeness manifests — M347/M840 hotfix:** Commit `67ea2b0e7` correctly removed erroneous
manifests from M347 and M840, restoring `dormant == 4` in the liveness gate. Both models now
join M308 and M360 as informative declarations with empty calculation closures and no manifest.

**M100 schema-hardening coherence:** All 6 M100 revisions (2020-2025) carry full `legal_refs`
and `source_refs` on the newly-added casilla declarations (90 declarations across 15 casilla ids).
The 0598 casilla-id reuse was correctly disambiguated by two distinct semantic roles.
No duplicate casilla numbers introduced.

**No tautological calculation tests found:** The `test_formula_runtime.py` sign-propagation test
explicitly self-documents that it asserts no hand-computed Decimal. M200 tests in
`test_modelo_200_registry.py` cite AEAT Manual de Sociedades 2024 worked-example figures
(pages 399/401). M303 tests assert structural invariants (balance conservation) not hand-computed
values. No new tautological tests introduced in the recent churn.

**Schema-hardening validator refactors coherent:** All extracted validator modules
(`_validate_algorithms.py`, `_validate_application_links.py`, `_validate_constructs.py`,
`_validate_dependency_sections.py`, `_validate_evidence.py`, `_validate_exports.py`,
`_validate_extraction_profiles.py`, `_validate_formulas.py`, `_validate_record_sections.py`,
`_validate_references.py`, `_validate_relation_sources.py`, `_validate_revision_identity.py`,
`_validate_revision_rules.py`, `_validate_semantic_roles.py`, `_validate_surfaces.py`) are all
imported and wired in `_validate.py`. Live validation of all 26 modelos confirms no dead import
paths or unreachable validator branches.

## Closure Record

1. **F1 closed**: Google Sheets computed rows carry typed legal/source refs and reject empty provenance.
2. **F2 closed**: filed-declaration conversion emits registry-grounded observations or fails closed.
3. **F3 closed on 2026-06-29**: manifestless calculation-bearing revisions fail validation; M100 2021 manifest legal refs were restamped to include Art. 75.

Current verification on 2026-06-29: Google payload tests, filed-declaration observation tests, referential-integrity tests, and record-design tests passed.
