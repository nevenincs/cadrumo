---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:40b13f4376e90e9715ab2cdb5b1a332bfa1f8e3e19c8510727913af84df6a957'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

# `bindings-interface-hardening` ledger

## Changes

- `S01` `T` `src/aeat/core/aggregation.py`
- `S01` `T` `src/aeat/domain/calculations/registry/_schema.py`
- `S02` `T` `src/aeat/domain/calculations/registry/_bindings.py`
- `S02` `T` `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `S02` `T` `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
- `S03` `T` `src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py`
- `S04` `T` `src/aeat/core/aggregation.py`
- `S05` `T` `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `S05` `T` `src/aeat/domain/calculations/registry/_invoice_bindings.py`
- `S05` `T` `src/aeat/core/aggregation.py`
- `S06` `T` `src/aeat/domain/calculations/registry/_schema.py`
- `S07` `T` `src/aeat/domain/calculations/registry/tests/test_binding_source_taxonomy.py`
- `S08` `T` `src/aeat/domain/calculations/registry/_bindings.py`
- `S09` `T` `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `S09` `T` `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
- `S09` `T` `src/aeat/domain/calculations/registry/_binding_selector_utils.py`
- `S10` `T` `src/aeat/domain/calculations/registry/_counterpart_bindings.py`
- `S10` `T` `src/aeat/domain/calculations/registry/_invoice_bindings.py`
- `S11` `T` `src/aeat/domain/calculations/registry/_bindings.py`
- `S12` `T` `src/aeat/domain/calculations/registry/tests/test_binding_build_validation.py`
- `S13` `T` `src/aeat/_data/registry/aeat/modelos/`
- `S14` `T` `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `S14` `T` `src/aeat/application/aggregation/_source_mesh.py`
- `S15` `T` `src/aeat/application/modelo/_calculation_actions.py`
- `S16` `T` `src/aeat/application/modelo/tests/test_unrouted_observation_screen.py`
- `S18` `T` `src/aeat/application/calculations/_relation_prefill.py`
- `S19` `T` `src/aeat/application/calculations/tests/test_carry_gate_parity.py`
- `S20` `T` `src/aeat/domain/filing/_schema.py`
- `S21` `T` `src/aeat/application/filing/__init__.py`
- `S22` `T` `src/aeat/domain/filing/tests/test_binding_value_provenance_roundtrip.py`
- `S23` `T` `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `S23` `T` `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `S24` `T` `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`
- `S25` `T` `src/aeat/application/modelo/_calculate_input.py`
- `S25` `T` `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- `S26` `T` `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
- `S26` `T` `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `S27` `T` `src/aeat/adapters/outbound/google/_profile_binding.py`
- `S28` `T` `src/aeat/application/modelo/_decimal_binding_value.py`
- `S29` `T` `src/aeat/domain/iva/tests/test_legal_basis_binding.py`
- `S30` `T` `src/aeat/application/modelo/_profile_binding.py`
- `S30` `T` `src/aeat/application/modelo/_borrador_binding.py`
- `S30` `T` `src/aeat/application/modelo/_binding_resolution.py`
- `S31` `T` `.vaultspec/rules/rules/registry-resolver-family-extraction.md`
- `S31` `T` `.vaultspec/rules/rules/registry-formula-runtime-facade.md`
- `S32` `T` `.vaultspec/rules/rules/binding-validation-single-contract.md`
- `S32` `T` `.vaultspec/rules/rules/binding-aggregation-is-typed.md`
- `S32` `T` `.vaultspec/rules/rules/binding-source-kind-single-taxonomy.md`
- `S32` `T` `.vaultspec/rules/rules/binding-values-carry-provenance.md`
- `S32` `T` `.vaultspec/rules/rules/binding-names-reserved-for-registry-input.md`
- `S33` `T` `.vault/audit/2026-06-15-bindings-interface-hardening-close-audit.md`
