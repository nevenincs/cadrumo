---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# `codebase-health` audit: `cross-domain-handoffs-swarm-audit-r2`

## Scope


## Findings


## Recommendations



## Context

## Scope

Audit axis: cross-domain handoffs. Branch `chore/eliminate-shims`. Reviewed after ~136 commits from four concurrent campaigns: schema-hardening (registry data), three-axis taxpayer-model wizard, declaración-extraction-architecture, and cli-workflow-redesign / state-architecture.

Pathways traced:

- Registry authority → RegistrySnapshot → formula execution → `CalculationRevision.observations` → CLI JSON emit: `legal_refs` / `source_refs` / `formula_id` provenance preserved end-to-end.
- New taxpayer-type wizard section (`entity_type` / `legal_entity_form` / `irpf_income_categories`) → `SetupAnswers` → `TaxpayerProfile` → profile-sourced calculation bindings → applicability routing.
- Modelo work-unit create → calculate → revision: registry validation enforced; every casilla reaches the persisted revision; ledger-preflight blockers surfaced.
- Cross-domain routing tables and binding endpoints reference real entities on the snapshot.

Authoritative rule: `aeat-roundtrip-discipline.md`. Existing roundtrip tests referenced: `test_calculation_repository_roundtrip.py`, `test_cross_boundary_roundtrip.py`, `test_typed_observation_provenance.py`, `test_taxpayer_axes_roundtrip.py`.

---

## Findings

### F1 — CLEAN: registry → snapshot → observations → CLI emit provenance chain is intact

**Pathway:** `ValidatedRegistryAuthority.load` → `authority.snapshot(...)` → `calculate_registry_snapshot(...)` → `_build_typed_observations` → `CalculationRevision.observations` → CLI `_modelo.py` JSON serialize.

**Files:** `src/aeat/application/modelo/_actions.py:2307-2371`, `src/aeat/entrypoints/cli/_modelo.py:1547-1563`, `src/aeat/domain/calculations/registry/_bindings.py:71-99`, `src/aeat/domain/modelos/_calculation_revision.py:204-211`.

`CasillaObservation` carries `legal_refs`, `source_refs`, `formula_id`, `operand_refs`, `operand_values`. The `_build_typed_observations` function hard-fails (`CasillaProvenanceMissingError`) if a casilla in `engine_result.values` is absent from the snapshot revision — it never emits an observation with empty provenance. Input/bound casillas pull `legal_refs`/`source_refs` from the registry `CasillaDefinition`; computed casillas pull from the engine entry. The CLI serializer at `_modelo.py:1547-1563` explicitly iterates `rev.observations` and includes every provenance field in the JSON output. The `CalculationRevisionPayload` / `ObservationPayload` schemas in `_modelo_payloads.py` carry `legal_refs` and `source_refs` as tuple fields.

Roundtrip test: `test_calculation_repository_roundtrip.py` — populates `legal_refs`/`source_refs` with non-default values, saves through encrypted SQL, reloads, asserts strict equality. Anti-tautology proof deletes the `observations` key on disk and asserts the regression surfaces.

**Data lost / risk:** None identified. The chain is wired and tested.

---

### F2 — CLEAN: amendment observations path preserves provenance

**Pathway:** `amend_modelo_revision` → `_amendment_observations` → `CalculationRevision(observations=...)`.

**File:** `src/aeat/application/modelo/_actions.py:2374-2426`.

For non-overridden casillas the baseline revision's typed observation is carried verbatim (value + formula provenance). For overridden casillas the registry `CasillaDefinition.legal_refs`/`source_refs` are pulled from the snapshot. A casilla absent from the snapshot raises `CasillaProvenanceMissingError`. A baseline revision with an empty `observations` tuple (pre-feature revision imported externally) falls back to the registry path for every casilla — legal provenance is rebuilt, not silently dropped. This fallback path is validated by `test_amend_flow.py:454-473` which seeds an empty-observations baseline.

**Data lost / risk:** None identified.

---

### F3 — CLEAN: externally-imported revision observations path

**Pathway:** `_external_filing_observations` → `CalculationRevision(observations=...)`.

**File:** `src/aeat/application/modelo/_actions.py:1923-1939`.

Externally imported casilla values use `_external_filing_observations`, which calls `_casilla_observation_for(entry=None, registry_casilla=...)` for every casilla. Since `entry=None`, it always takes the registry-casilla branch and pulls `legal_refs`/`source_refs` from the registry. Same `CasillaProvenanceMissingError` guard applies for orphan casilla ids.

**Data lost / risk:** None identified.

---

### F4 — CLEAN: typed-observations storage boundary (encrypted SQL roundtrip)

**Pathway:** `CalculationRevisionCatalogueRepository.save` → `SecureObjectRepository` (AES-GCM encrypted JSON) → `.load()`.

**Files:** `src/aeat/domain/modelos/_calculation_repository.py`, `src/aeat/domain/modelos/test_calculation_repository_roundtrip.py`.

The pydantic v2 serialisation of `CalculationRevision.observations: tuple[CasillaObservation, ...]` persists the full typed envelope as a JSON array under the `observations` key. The anti-tautology proof in `test_calculation_repository_roundtrip.py:164-231` deletes the key from the encrypted payload and asserts either a `ValidationError` or strict inequality on reload. The test is a real-adapter test with `EphemeralMasterKeyProvider` and SQLite — no mocks.

**Data lost / risk:** None identified.

---

### F5 — CLEAN: taxpayer-type wizard section → SetupAnswers → TaxpayerProfile projection

**Pathway:** Wizard CLI flags (`--entity-type`, `--legal-entity-form`, `--irpf-income-categories`, `--irpf-estimation-regime`) → `SETUP_FLOW` catalogue → `project_answers` → `SetupAnswers` → `serialise_answers` → profile facts under `taxpayer_type.*` keys → `taxpayer_profile_from_mapping` → `TaxpayerProfile`.

**Files:** `src/aeat/application/wizard/_setup_answers.py`, `src/aeat/application/wizard/_catalogue.py:261-287`, `src/aeat/domain/deadlines/_profiles.py:83-141`, `src/aeat/application/wizard/test_taxpayer_axes_roundtrip.py`.

`SetupAnswers` fields `entity_type`, `legal_entity_form`, `irpf_income_categories`, `irpf_estimation_regime` are validated against the canonical `EntityType`, `LegalEntityForm`, `IrpfIncomeCategory`, `IrpfEstimationRegime` enums. The catalogue maps each question to a `profile_key` under `taxpayer_type.*`. `taxpayer_profile_from_mapping` reads these keys back and projects them onto `TaxpayerProfile.entity_type`, `.legal_entity_form`, `.irpf_income_categories`, `.irpf_estimation_regime`.

Roundtrip test: `test_taxpayer_axes_roundtrip.py` — full `serialise_answers → project_answers` cycle plus `taxpayer_profile_from_mapping`, strict equality. Anti-tautology proof deletes a key and confirms the field re-defaults.

**Data lost / risk:** None identified.

---

### F6 — CLEAN: taxpayer-type data → model applicability routing

**Pathway:** `TaxpayerProfile.entity_type` + `.irpf_income_categories` → `derive_modelo_applicability` → `ModeloApplicabilityRule.decide` → `ModeloApplicability` (verdict + `legal_refs`).

**File:** `src/aeat/application/overview/_applicability.py:132-232`.

`ModeloApplicabilityRule.decide` gates on `entity_type` and `irpf_income_categories`. An undeclared `entity_type` (None) returns the `INCOMPLETE` verdict with grounded `legal_refs` rather than silently defaulting to any persona. The seed rule table covers modelos 100, 130, 200, 303, 111, 115, 123. Tests: `test_applicability.py` and `test_explain.py` assert `APPLICABLE` / `NOT_APPLICABLE` verdicts plus `legal_refs` presence.

**Data lost / risk:** None identified.

---

### F7 — GAP (MEDIUM): no registry binding with `source="profile"` consumes the new `taxpayer_type.*` profile selector namespace for calculation purposes

**Pathway:** `taxpayer_type.entity_type` / `taxpayer_type.legal_entity_form` / `taxpayer_type.irpf_income_categories` written to the profile store → `resolve_profile_sourced_bindings` → calculation engine binding channels.

**Files:** `src/aeat/_data/registry/aeat/user_profile/schema.toml:239-275`, `src/aeat/application/modelo/_profile_binding.py:119-194`.

The user-profile schema declares `taxpayer_type.entity_type`, `taxpayer_type.legal_entity_form`, and `taxpayer_type.irpf_income_categories` with `model_selectors = ["taxpayer.entity_type"]` etc., but no currently-registered modelo binding (`source = "profile"`) references these selectors. A grep across all binding TOML files confirms zero occurrences of `taxpayer.entity_type`, `taxpayer.legal_entity_form`, or `taxpayer.irpf_income_categories` in any binding `selector` field.

The only formula that references `lookup_parameter_by_entity_type` is M100 formula `0082-renta-2025-minimo-contribuyente-autonomica.toml`, which dispatches by CCAA key (`renta-2025-profile-tax-residence-ccaa`), not by entity type.

The planned model 200 `parameters.toml` comments reference a `lookup_parameter_by_entity_type` op driven by an entity_type binding, but no such binding exists yet in any revision.

**Consequence:** The three-axis taxpayer model is correctly wired through the wizard → profile → `TaxpayerProfile` → applicability chain. However, no formula engine calculation currently consumes `entity_type`, `legal_entity_form`, or `irpf_income_categories` via a profile binding. The data flows to the profile store correctly; the calculation-engine consumption half of the wiring is not yet authored in any TOML registry binding. This is expected for the current campaign scope but should be documented as a gap.

**Remediation:** This is a known planned-work gap, not a regression. When model 200 (Impuesto sobre Sociedades) or IRPF regime-gated calculations require the entity type, author a binding TOML with `source = "profile"` and `selector = { profile_model = "taxpayer", field = "entity_type" }`. The profile schema's `model_selectors` entry is ready. No production code change is needed — only TOML registry data.

---

### F8 — CLEAN: ledger-preflight blockers surface before calculation

**Pathway:** `calculate_modelo_revision` → `_raise_if_ledger_preflight_blocks_calculation` → `preflight_ledger_tax_readiness` → raises `LedgerPreflightBlocksCalculationError`.

**File:** `src/aeat/application/modelo/_actions.py:1248-1265`.

The preflight runs when any binding in the snapshot revision carries a source in `_LEDGER_PREFLIGHT_BINDING_SOURCES`. Test: `test_file_flow.py` and the fixture update at `@ #90 fix stale ledger-preflight fixtures to exercise expense blockers`.

**Data lost / risk:** None identified.

---

### F9 — GAP (LOW): `LiveCrossReferenceDecision.oracle_id` typed-alias assertion in test_cross_boundary_roundtrip.py may not pass yet

**Pathway:** `test_live_cross_reference_decision_oracle_id_is_typed` (line 153-170) asserts `"OracleId"` appears in `repr(get_type_hints(LiveCrossReferenceDecision)["oracle_id"])`.

**File:** `src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py:153-170`.

`oracle_id` is declared as `OracleId | None` where `type OracleId = Annotated[str, Field(...)]` (Python 3.12 `type` statement). Under Python 3.12 `get_type_hints` resolves `type` aliases; the repr of `OracleId | None` includes `OracleId` in its string form when the alias is preserved. However, the behavior depends on Python version and whether `include_extras=True` is sufficient to preserve the alias name in the repr string. The test is written as a forward-looking structural assertion ("fails today" comment in a prior version, now potentially passing after the `_ids.py` `type OracleId =` declaration landed).

**Consequence:** If the test still fails under the runtime Python version, the oracle-id typed alias is not visible at the boundary. This is low-risk: the underlying storage and computation use `str` regardless.

**Remediation:** Run the test suite and confirm the test passes. If it fails, the underlying typing was not yet promoted to a named alias and the test's assertion needs to be verified against the actual Python version in use.

---

### F10 — CLEAN: cross-domain routing tables reference real entities

**Pathway:** `ModeloApplicabilityRule.legal_refs` → registered legal IDs in registry.

**File:** `src/aeat/application/overview/test_applicability.py:303-328`.

`test_seed_legal_refs_resolve_against_the_registry` loads all legal-ref IDs from the registry authority and asserts every key in `_MODELO_APPLICABILITY_RULES` and `_INCOMPLETE_LEGAL_REFS` resolves. This test guards against stale or invented citation keys in the routing table.

**Data lost / risk:** None identified.

---

### F11 — CLEAN: schema-hardening M100 retenciones_pagos_fraccionados cluster does not break provenance

**Pathway:** 90 new `semantic_role` and `legal_refs`/`source_refs` declarations across M100 revisions 2020–2025.

**Files:** `src/aeat/_data/registry/aeat/modelos/100/revisions/*/casillas/0176-0592.toml` (and 89 sibling files).

Each hardened casilla carries `legal_refs` and `source_refs` fields. Since `_build_typed_observations` reads `registry_casilla.legal_refs` and `registry_casilla.source_refs` directly from the `CasillaDefinition`, these newly-assigned provenance fields will be automatically included in typed observations for any M100 calculation that touches the retenciones cluster casillas. The `semantic_role` field is informational at schema level; it does not affect calculation engine behavior.

**Data lost / risk:** None identified.

---

### F12 — GAP (LOW): `_amendment_observations` silently degrades for non-overridden casillas when baseline observations are empty and the casilla is absent from the snapshot

**Pathway:** `_amendment_observations` → casilla not in `overrides`, `baseline_by_id.get(casilla_id)` returns `None` (empty baseline), falls through to `casillas_by_id.get(casilla_id)` which also returns `None` → raises `CasillaProvenanceMissingError`.

**File:** `src/aeat/application/modelo/_actions.py:2408-2423`.

This case is correctly handled — a missing-snapshot casilla raises rather than silently emitting empty provenance. However, there is no dedicated test that exercises this specific three-way path: (a) non-overridden casilla, (b) empty baseline observations, (c) casilla absent from snapshot. The existing `test_amend_flow.py:454` only covers non-overridden casillas with a populated registry snapshot. An orphan-casilla amendment test is absent.

**Consequence:** Confidence gap, not a live bug. The error path exists but is untested against the specific combination.

**Remediation:** Add a test to `test_amend_flow.py` that constructs a corrected-values map including a casilla id absent from the registry snapshot and asserts `CasillaProvenanceMissingError` is raised — mirroring the existing `test_unknown_casilla_raises_instead_of_emitting_empty_provenance` test in `test_typed_observation_provenance.py`.

---

## Recommendations

1. **F7 (registry bindings for `taxpayer_type.*`)** — Author binding TOML files under the relevant modelo revisions when entity-type-gated calculations land (model 200 IS rate schedule, IRPF regime splits). The profile schema `model_selectors` are in place; only the TOML binding selectors need authoring. No code change needed.

2. **F9 (oracle_id typed-alias test)** — Run `pytest src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py::test_live_cross_reference_decision_oracle_id_is_typed -xvs` to confirm it passes under the live Python version. If it fails, investigate whether `type OracleId = ...` resolves correctly under `get_type_hints(include_extras=True)` in the project's Python version.

3. **F12 (amendment orphan-casilla test gap)** — Add one test to `src/aeat/application/modelo/test_amend_flow.py` asserting `CasillaProvenanceMissingError` when an amendment's corrected-values map references a casilla absent from the snapshot. This mirrors the existing provenance-guard test in `test_typed_observation_provenance.py` and closes the confidence gap.

4. **No regressions found on the primary provenance chain** — The registry → snapshot → formula engine → `CalculationRevision.observations` → CLI JSON path is intact, storage-tested with a non-tautological anti-forgery proof, and carries `legal_refs`/`source_refs`/`formula_id` provenance end to end. The three-axis taxpayer wizard data flows correctly through to `TaxpayerProfile` and applicability routing. The ledger-preflight gate and amendment observations path are wired and tested.

