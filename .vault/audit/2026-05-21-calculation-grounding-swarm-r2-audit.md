---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
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

## Findings

### F1 — Google Sheets calc CLI emits formula entries without `legal_refs`/`source_refs`

Pathway: `src/aeat/entrypoints/cli/_config/_google.py` lines 1200-1207.

The `_compute_casillas_from_pull` helper returns a plain dict per entry with only
`casilla_id`, `value`, and `formula_id`. The `legal_refs` and `source_refs` fields available on
`RegistryCalculationEntry` are silently dropped. Contrast with the main modelo calculation CLI
payload (`_modelo_payloads.py`, `ObservationPayload`) which does surface both fields.

Data lost / risk: Operators reading the Google Sheets calc output (via `aeat config google sync
calc pull --compute`) receive formula provenance without regulatory grounding. This is an
operator-facing JSON surface the grounding rule requires to carry `legal_refs` and `source_refs`.

Remediation: Extend the per-entry dict in `_compute_casillas_from_pull` to include
`"legal_refs": list(entry.legal_refs)` and `"source_refs": list(entry.source_refs)`.
A `SheetsCalcEntryPayload` OutputSchema mirroring `ObservationPayload` would enforce the
contract and enable JSON-contract test coverage.

---

### F2 — `registry_observation_from_filed_declaration` produces `CasillaObservation` with empty provenance (undocumented external-boundary exception)

Pathway: `src/aeat/adapters/outbound/aeat/sede/_declarations.py` line 1480.

`registry_observation_from_filed_declaration` converts AEAT-scraped
`FiledDeclaracionObservation` into a `RegistryModeloObservation` by building
`CasillaObservation` items with no `legal_refs` or `source_refs`. The function has no inline
comment explaining this is an external-API boundary exception. The produced observations are
consumed by `resolve_previous_filing_binding_values` and `resolve_relation_values_from_observations`
purely as a value-lookup source for binding resolution; they are not persisted as the typed
observations tuple on a `CalculationRevision` and do not flow through the CLI provenance chain.

Data lost / risk: The grounding rule states every casilla observation carries provenance. The
binding-resolution consumer reads only `casilla_values` (the computed property), never
`legal_refs`/`source_refs`, so the semantic gap is latent rather than causing an active
calculation error. However, the boundary is not documented, which creates risk that a future
consumer of these observations assumes provenance is present and silently receives empty tuples.

Remediation: Add an inline comment on `registry_observation_from_filed_declaration`
explicitly labelling this as an external-API boundary — the AEAT Sede does not expose
legal-normative grounding; consumers must look up registry casilla provenance from the snapshot
if they need it. Optionally, the function could accept an optional `RegistrySnapshot` and
backfill provenance from `snapshot.revision.casillas` where available to close the gap fully.

---

### F3 — Completeness-manifest gate not fail-closed for manifestless calculation-bearing revisions (known staged rollout; gate-liveness test enforces the invariant)

Pathway: `src/aeat/domain/calculations/registry/_validate_revision_identity.py` lines 180-191.

`_emit_completeness_gate_failures` returns immediately when
`revision.completeness_manifest is None`. A calculation-bearing revision with no manifest
passes validation silently. This is the documented staged-rollout design.

Current state: The gate-liveness test
`test_calculation_completeness_gate_is_live_for_every_calculation_bearing_modelo`
(in `test_record_design.py` line 390) enforces that every non-empty calculation closure has a
manifest, and asserts `dormant == 4` (M308, M347, M360, M840). All 26 modelos passed
`RegistryValidator.validate_modelo` in live execution. The M347/M840 erroneous manifests were
removed in commit `67ea2b0e7`. The gate is therefore live for the current corpus.

Risk going forward: New modelos or new revisions added without a manifest will pass validation
silently until the liveness test catches them. The fail-closed flip should land once every
calculation-bearing modelo carries a manifest.

Remediation: Once the liveness test has been stable across a full sprint, flip the gate: treat a
`None` manifest on a calculation-bearing revision as a validation failure.

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

## Recommendations

1. Fix F1 first (low effort, high grounding impact): add `legal_refs`/`source_refs` to the
   Google Sheets calc CLI entry dict in `_config/_google.py`. A two-line fix; adding a
   `SheetsCalcEntryPayload` schema enables JSON-contract coverage.

2. Document F2 boundary (low effort, prevents future breakage): add a one-line inline comment
   on `registry_observation_from_filed_declaration` labelling the external-API boundary
   exception so the next reader understands why provenance is empty.

3. Schedule the completeness-manifest fail-closed flip (F3): one-line change in
   `_emit_completeness_gate_failures` to fail on `manifest is None` for a non-empty closure;
   land once the current corpus has been stable for a full sprint.
