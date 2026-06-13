---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# calculation-grounding-swarm-audit

## Scope

Axis: calculation-engine grounding and registry authority flow.
Branch: `chore/eliminate-shims` (worktree `chore-476-restructure-execution`).
Focus: post-schema-hardening-campaign coherence of M100/M200 casilla clusters, provenance chain from registry source to operator-facing CLI surface, engine_result coverage, referential integrity, and tautological-test hygiene.

Files examined: `_formula_runtime.py`, `_constructs.py`, `_schema.py`, `_validate.py`, `_bindings.py`, `_calculation_revision.py`, `_actions.py`, `_modelo_payloads.py`, `_modelo.py`, `_observations_repository.py`, `test_secure_storage_roundtrip.py`, `test_observations_repository_roundtrip.py`, `test_referential_integrity.py`, `test_formula_runtime.py`, `test_modelo_200_registry.py`, `test_renta_escala_estatal_bracket_resolution.py`, `test_renta_escala_estatal_ahorro_bracket_resolution.py`, `test_casilla_observation.py`, `test_renta_cuota_chain_contract.py`, `test_modelo_369_registry.py`, registry TOML fragments.

---

## Findings

### F1 — Silent grounding-drop path in `_casilla_observation_for` (logically unreachable but unguarded)

**Pathway:** `application/modelo/_actions.py:1816–1836`

**Detail:** `_casilla_observation_for` accepts `registry_casilla` as an untyped parameter (both the function and its caller carry `# type: ignore[no-untyped-def]`). The guard at line 1834–1835 silently falls back to empty `legal_refs = ()` / `source_refs = ()` when `registry_casilla is None`. The logic is that `engine_result.values` derives from `_initial_values` (which iterates `revision.casillas`) so every casilla_id in `values` must have a registry entry — the `None` branch is not reachable in the current implementation. However, the lack of static typing and the defensive `if registry_casilla is not None else ()` pattern means a future refactor that alters the provenance of `engine_result.values` (e.g. a new formula op that injects virtual casilla ids) could silently produce zero-grounded observations with no runtime error. The observation would persist to the encrypted SQL store with empty legal_refs, and the anti-tautology roundtrip test would not catch it because the test populates legal_refs explicitly in its fixture.

**Data lost / risk:** Empty `legal_refs` / `source_refs` on input or bound casilla observations if the unreachable branch is ever reached. No current regression — risk is latent.

**Remediation:** Add a typed signature to both `_build_typed_observations` and `_casilla_observation_for` (replace `# type: ignore[no-untyped-def]` with proper `RegistryCalculationResult` / `RegistryCalculationEntry | None` / `CasillaDefinition | None` annotations). Replace the silent `if registry_casilla is not None else ()` with an explicit `RegistrySnapshotError` raise: if `casilla_id` is in `engine_result.values` but absent from `snapshot.revision.casillas`, the snapshot is incoherent and calculation must fail loudly. This is a cross-campaign concern (the schema-hardening campaign introduced `_build_typed_observations`).

---

### F2 — Tautological bracket-resolution arithmetic in `test_renta_escala_estatal_bracket_resolution.py`

**Pathway:** `domain/calculations/registry/test_renta_escala_estatal_bracket_resolution.py:59–89`

**Detail:** Tests `test_escala_estatal_resolves_for_30k_base_general`, `test_escala_estatal_resolves_in_top_bracket_post_2021`, and `test_escala_estatal_2020_top_bracket_uses_pre_amendment_22_5_rate` assert the output of `_resolve_bracket` against Decimal values computed by the test author using the same `fixed_addition + marginal_rate * (base - lower_bound)` formula that the function executes. The docstring for `test_escala_estatal_resolves_for_30k_base_general` shows `cuota = 2112.75 + 0.15 * (30000 - 20200) = 3582.75` — the expected value is derived by the author from the same formula, not read from an AEAT publication. These tests would pass even if the registry bracket parameters were wrong against the AEAT-published tariff table (so long as the parameters and the formula are internally consistent). This violates the `no-tautological-calculation-tests.md` rule.

The companion file `test_renta_escala_estatal_ahorro_bracket_resolution.py` correctly cites AEAT Manual práctico de Renta 2025 Parte 1 (page 953) and BOE-A-2006-20764 as the authority for its expected values and is clean.

**Data lost / risk:** A wrong bracket parameter value (e.g. wrong `fixed_addition` or `lower_bound` transcribed from the tariff table) would not be caught by these three tests. The bug would only surface in the workbook-parity / oracle-replay layer — but that layer is optional and not exercised in CI without live oracle access.

**Remediation:** Replace the hand-computed expectations with values transcribed from the AEAT-published escala estatal table (same source the ahorro companion uses: AEAT Manual de Renta, section on gravamen de la base liquidable general). For example, the AEAT Manual for each ejercicio publishes the cuota íntegra at the 30.000 EUR threshold as a printed figure; use that published figure, not the author's arithmetic. Add a source citation in the docstring matching the pattern in `test_renta_escala_estatal_ahorro_bracket_resolution.py`.

---

### F3 — M369 importación `cuota-total` test exercises a degenerate single-summand formula

**Pathway:** `domain/calculations/registry/test_modelo_369_registry.py:663–677`

**Detail:** `test_modelo_369_esquema_importacion_cuota_total_resolves_end_to_end` supplies one binding pair (`DE` / 21%) and asserts `result.values["iva.importacion.cuota-total"] == expected_cuota`. The registry formula is `add([iva.importacion.de.low-value-cuota])` — a single-element add. The assertion is therefore `identity_output == input` which holds for any value, including 0 or a wrong value produced by a formula bug. The test comment at line 670–674 attempts to justify this: "Asserting each against the binding fact (rather than against the other SUT output) means a broken cuota-total formula cannot hide by collapsing both casillas to the same wrong value." This reasoning holds for two-argument sums but not for single-argument identity. A mismatch in the formula's operand set (e.g. forgetting to sum an additional country slot) would be invisible.

The M369 union-scheme companion test (`test_modelo_369_union_scheme_cuota_total_resolves_end_to_end`, around line 570–605) is stronger: it supplies three country/rate slots and checks operand_refs, so the aggregation is exercised for real.

**Data lost / risk:** Low direct risk to the current single-binding registry shape. Risk elevates if the M369 importación revision acquires additional binding slots (additional country × rate combinations) — the test would still pass with a formula that only sums DE/21% rather than all slots.

**Remediation:** Extend the test fixture to supply at least two country/rate binding slots (e.g. DE/21% and FR/21%) and assert that `cuota-total` equals the algebraic sum of both, sourced from the resolver output. Alternatively add a structural assertion that `cuota-total_entry.operand_refs` contains all bound casilla ids (matching the pattern of the union companion test).

---

### F4 — No `completeness_manifest` on M100 or M200 revisions (staged gate, not yet fail-closed)

**Pathway:** `_data/registry/aeat/modelos/100/revisions/2025/revision.toml` and `_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml`

**Detail:** Neither the M100 2025 revision nor the M200 2024-y-siguientes revision declares a `completeness_manifest`. The `_emit_completeness_gate_failures` validator (line 261 in `_validate.py`) explicitly skips revisions with `manifest is None`: "manifest authoring is a staged migration, and a casilla-bearing revision is allowed to load while its manifest is still being authored." So this is not a current CI failure.

However, M100 is the most critical calculation-bearing modelo in the codebase (full IRPF cuota chain, 90 CCAA × ejercicio cells), and M200 is the focus of the schema-hardening campaign's page-14 cuota chain work. Without a completeness manifest, the gate that enforces `legal_refs` + `source_refs` on every calculation-closure casilla is bypassed for these two modelos. Casillas added during the hardening campaign that lack grounding would not be caught at validation time.

Spot-check of the M200 pagos-fraccionados casillas (e.g. `liquidacion-00601-pago-fraccionado-1.toml`) confirms they carry `legal_refs` and `source_refs`. The M100 cluster `0592` also carries grounding. Manual spot-check is not a substitute for the automated gate.

**Data lost / risk:** Medium. An ungrounded casilla in the cuota chain for M100 or M200 would not be caught at registry build time, only at the completeness-gate check (which is bypassed). The risk is that the schema-hardening campaign added casillas without grounding and the current test suite would not surface the gap.

**Remediation (cross-campaign):** Author `completeness_manifest` entries for M100 2025 and M200 2024-y-siguientes. The manifest need only list casillas in the calculation closure (formula targets, formula operands, binding endpoints, relation endpoints). Once the manifest is declared, the existing `_emit_completeness_gate_failures` gate enforces grounding automatically at `RegistryValidator.validate_modelo` time.

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

## Recommendations

1. **Type the `_build_typed_observations` / `_casilla_observation_for` private functions** (F1). Remove the `type: ignore[no-untyped-def]` suppression and replace the defensive `None` fallback with an explicit error. This is a low-effort, high-value safety improvement.

2. **Rewrite three tautological bracket tests in `test_renta_escala_estatal_bracket_resolution.py`** (F2). The fix is straightforward: read the expected cuota from the same AEAT manual source the ahorro companion already cites.

3. **Extend the M369 importación cuota-total test** (F3) to cover at least two country/rate slots and check operand_refs structurally.

4. **Author completeness manifests for M100 2025 and M200 2024-y-siguientes** (F4). This should be coordinated with the schema-hardening campaign maintainer. The gate machinery is in place; only the TOML manifest declaration is missing.

