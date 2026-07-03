---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-06-29'
related: []
---

# calculation-grounding-swarm-audit

## Scope

Axis: calculation-engine grounding and registry authority flow.
Branch: `chore/eliminate-shims` (worktree `chore-476-restructure-execution`).
Focus: post-schema-hardening-campaign coherence of M100/M200 casilla clusters, provenance chain from registry source to operator-facing CLI surface, engine_result coverage, referential integrity, and tautological-test hygiene.

Files examined: `_formula_runtime.py`, `_constructs.py`, `_schema.py`, `_validate.py`, `_bindings.py`, `_calculation_revision.py`, `_actions.py`, `_modelo_payloads.py`, `_modelo.py`, `_observations_repository.py`, `test_secure_storage_roundtrip.py`, `test_observations_repository_roundtrip.py`, `test_referential_integrity.py`, `test_formula_runtime.py`, `test_modelo_200_registry.py`, `test_renta_escala_estatal_bracket_resolution.py`, `test_renta_escala_estatal_ahorro_bracket_resolution.py`, `test_casilla_observation.py`, `test_renta_cuota_chain_contract.py`, `test_modelo_369_registry.py`, registry TOML fragments.

---

## Current State — 2026-06-29

All four findings are closed on the current implementation path:

- F1 is closed: typed observation projection now raises `CasillaProvenanceMissingError`
  instead of emitting observations without `legal_refs` / `source_refs`.
- F2 is closed: the IRPF escala estatal tests assert published breakpoint cuotas from
  BOE/AEAT authority and use structural checks for open-bracket selection.
- F3 is closed: the M369 importación total test now exercises real resolver aggregation
  into the single bound casilla and asserts the cuota-total formula's `operand_refs`.
- F4 is closed: M100 2025 and M200 2024-y-siguientes carry completeness manifests, and
  manifestless calculation-bearing revisions fail validation.

## Findings

### F1 — CLOSED: typed observations fail on missing provenance source

**Pathway:** `application/modelo/_actions.py:1816–1836`

**Original detail:** `_casilla_observation_for` accepted `registry_casilla` as an untyped parameter and silently fell back to empty `legal_refs = ()` / `source_refs = ()` when `registry_casilla is None`. The logic was that `engine_result.values` derived from `_initial_values` (which iterates `revision.casillas`) so every casilla_id in `values` must have a registry entry, making the `None` branch unreachable in normal operation. The defensive fallback still left a future provenance-erasure path.

**Current closure:** `src/aeat/application/modelo/_calculation_helpers.py` now projects observations through typed helpers and raises `CasillaProvenanceMissingError` if a casilla in `engine_result.values` or amendment overrides is absent from the registry snapshot. Regression coverage: `src/aeat/application/modelo/tests/test_typed_observation_provenance.py`.

**Verification:** `test_typed_observations_built_for_real_snapshot_carry_provenance`, `test_unknown_casilla_raises_instead_of_emitting_empty_provenance`, and `test_amendment_override_orphan_casilla_raises_instead_of_emitting_empty_provenance`.

---

### F2 — CLOSED: escala estatal tests use published breakpoint oracles

**Pathway:** `domain/calculations/registry/test_renta_escala_estatal_bracket_resolution.py:59–89`

**Original detail:** Tests `test_escala_estatal_resolves_for_30k_base_general`, `test_escala_estatal_resolves_in_top_bracket_post_2021`, and `test_escala_estatal_2020_top_bracket_uses_pre_amendment_22_5_rate` asserted `_resolve_bracket` against Decimal values computed by the test author using the same `fixed_addition + marginal_rate * (base - lower_bound)` formula that the function executes. These tests would pass even if the registry bracket parameters were wrong against the AEAT-published tariff table.

The companion file `test_renta_escala_estatal_ahorro_bracket_resolution.py` correctly cites AEAT Manual práctico de Renta 2025 Parte 1 (page 953) and BOE-A-2006-20764 as the authority for its expected values and is clean.

**Current closure:** `src/aeat/domain/calculations/registry/tests/test_renta_escala_estatal_bracket_resolution.py` now asserts at statutory breakpoints whose cuota íntegra values are transcribed from the BOE/AEAT table: 12.450 -> 1.182,75; 20.200 -> 2.112,75; 35.200 -> 4.362,75; 60.000 -> 8.950,75; and 300.000 -> 62.950,75 for post-2021 years. Open-bracket behavior is checked structurally rather than with manufactured mid-bracket arithmetic.

**Verification:** the updated test module documents the external oracle in its module docstring and no longer asserts the old 30.000 EUR hand-computed value.

---

### F3 — CLOSED: M369 importación total test asserts formula wiring

**Pathway:** `domain/calculations/registry/test_modelo_369_registry.py:663–677`

**Original detail:** `test_modelo_369_esquema_importacion_cuota_total_resolves_end_to_end` supplied one binding pair (`DE` / 21%) and asserted `result.values["iva.importacion.cuota-total"] == expected_cuota`. The registry formula is `add([iva.importacion.de.low-value-cuota])`, a single-element add, so the assertion was an identity check.

The M369 union-scheme companion test (`test_modelo_369_union_scheme_cuota_total_resolves_end_to_end`, around line 570–605) is stronger: it supplies three country/rate slots and checks operand_refs, so the aggregation is exercised for real.

**Current closure:** the importación test now feeds two real IOSS ledger observations into the resolver, proving aggregation into the single bound casilla, and mirrors the union-scheme structural assertion by checking the cuota-total formula entry's `op == "add"` and `operand_refs == {"iva.importacion.de.low-value-cuota"}`.

**Verification:** `test_modelo_369_esquema_importacion_cuota_total_resolves_end_to_end`.

---

### F4 — CLOSED: M100/M200 manifests and fail-closed completeness gate

**Pathway:** `_data/registry/aeat/modelos/100/revisions/2025/revision.toml` and `_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml`

**Original detail:** Neither the M100 2025 revision nor the M200 2024-y-siguientes revision declared a `completeness_manifest`. The completeness validator skipped revisions with `manifest is None`, so the gate that enforces `legal_refs` + `source_refs` on every calculation-closure casilla was bypassed for those two calculation-bearing modelos.

**Current closure:** `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml` and `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/completeness-manifest.toml` exist. `src/aeat/domain/calculations/registry/_validate_completeness.py` now fails validation when a calculation-bearing revision has no manifest, naming the closure casilla ids.

**Verification:** `test_calculation_bearing_revision_without_manifest_fails_closed`, `test_calculation_completeness_gate_is_live_for_every_calculation_bearing_modelo`, `test_calculation_completeness_manifests_match_their_calculation_surface`, and `test_calculation_completeness_manifest_legal_refs_match_calculation_closure`.

---

## Areas Found Clean

**Provenance chain (registry → calculation → persistence → CLI):** The full chain is intact. `_formula_runtime.py` carries `legal_refs` / `source_refs` per entry. `_build_typed_observations` in `_actions.py` correctly iterates `engine_result.values.items()` (all casillas — input, bound, computed) and pulls registry casilla grounding for non-computed casillas. `CalculationRevision.observations` persists the typed tuple. The CLI `_calculation_revision_payload` emits the full `observations` list with `legal_refs` / `source_refs` per casilla. The `_modelo_payloads.py` schemas expose `ObservationPayload` with typed provenance fields.

**engine_result.values coverage:** `RegistryCalculationResult.values` covers every casilla — the docstring is accurate and the `_initial_values` builder confirms this. The `entries` / `values` asymmetry is clearly documented. No code path was found that consumes only `entries` when building the typed observation tuple.

**Referential integrity at snapshot build:** `_check_all_id_references` is comprehensive (21 typed-ID categories). `test_committed_registry_passes_referential_integrity` runs against the live committed registry. The M200 segment-qualified casilla identity model is correctly enforced by `_emit_casilla_identity_failures` which keys on `(segmento, number)` pairs, not bare `number`.

**M200 cuota-chain tests (oracle-grounded):** `test_modelo_200_cuota_integra_chain_applies_manual_rate_to_post_nivelacion_base` and `test_modelo_200_page_014_cuota_diferencial_calculation_grounds_against_manual_example` cite the Manual práctico de Sociedades 2024 (pages 399/401) as the oracle. Expected values (250.000, -20.000, -30.000) are transcribed from the published manual, not author-computed. These tests are clean.

**M200 segment-qualified casillas carry grounding:** Spot-checked `liquidacion-00601-pago-fraccionado-1.toml` (ley-27-2014 legal refs, aeat-dr-200-2025 source ref), `liquidacion-00611-cuota-diferencial.toml`, and M100 cluster casilla `0176-0592.toml`. All carry non-empty `legal_refs` and `source_refs`.

**Secure-storage roundtrip:** `test_secure_storage_roundtrip.py` (domain/filing) and `test_observations_repository_roundtrip.py` (application/calculations) both carry anti-tautology proof tests that mutate the encrypted payload and assert detection. The `test_calculation_observation_dropped_legal_refs_surfaces_at_load` test explicitly verifies that `legal_refs` deletion is caught. Both tests use real SQLite + real encryption.

**`CalculationRevision.observations` default-to-empty is non-breaking:** The field defaults to `()` for backward compat with pre-observation revisions. This is documented in the model docstring and does not suppress grounding for newly-created revisions (which always populate from `_build_typed_observations`).

**Filing path:** No production code path writes a filed revision without going through `calculate_modelo_revision` → `_build_typed_observations`. The `file_modelo_revision` action requires `VERIFICADO_COMPLETO` state, which can only be reached from a revision that was persisted by `calculate_modelo_revision`. The observation chain is end-to-end.

---

## Closure Record

1. **F1 closed:** observation projection hard-fails rather than emitting empty provenance.
2. **F2 closed:** escala estatal tests use BOE/AEAT breakpoint oracles and structural open-bracket checks.
3. **F3 closed:** M369 importación total checks real resolver aggregation and formula `operand_refs`.
4. **F4 closed:** M100/M200 manifests exist and manifestless calculation-bearing revisions fail validation.

Current verification on 2026-06-29: typed-observation provenance tests, escala estatal bracket tests, M369 registry tests, referential-integrity tests, and record-design tests pass in the current tree or were exercised by the focused suites recorded in the R2 closure.
