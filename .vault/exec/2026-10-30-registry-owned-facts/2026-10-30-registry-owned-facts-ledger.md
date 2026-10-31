---
tags:
  - '#exec'
  - '#registry-owned-facts'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:081f45c6c649ff542ca71403ed4567e1744dc28707663f6d284e2c2147fe2c7e'
related:
  - "[[2026-10-30-registry-owned-facts-plan]]"
---

# `registry-owned-facts` ledger

## Changes

- `S01` `M` `src/cadrumo/application/modelo/dt12_advisory.py`
- `S01` `M` `src/cadrumo/application/filing/m190_context_validation.py`
- `S01` `M` `src/cadrumo/application/filing/m280_context_validation.py`
- `S01` `verify:` `pytest focused dt12 m190 m280` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/projection.py`
- `S02` `M` `src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/m303_orden_constants.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/ledger_binding_validation.py`
- `S02` `verify:` `pytest focused registry and consumer suites` -> `pass`
- `S02` `verify:` `lint-imports` -> `fail`
- `S03` `M` `src/cadrumo/domain/contribuyente/renta_codes.py`
- `S03` `M` `src/cadrumo/domain/calculations/registry/descendant_disability_catalogue.py`
- `S03` `M` `src/cadrumo/application/wizard/catalogue.py`
- `S03` `M` `src/cadrumo/application/wizard/command_parameters.py`
- `S03` `verify:` `lint-imports` -> `pass`
- `S05` `A` `src/cadrumo/_data/registry/aeat/facts/0163-modelo-202-instalment-payment-months.toml`
- `S05` `M` `src/cadrumo/domain/period.py`
- `S05` `M` `src/cadrumo/domain/renta/maritime_exemption.py`
- `S05` `M` `src/cadrumo/domain/renta/tests/test_maritime_exemption.py`
- `S05` `verify:` `test_maritime_exemption` -> `pass`
- `S04` `A` `src/cadrumo/_data/registry/aeat/facts/0160-withholding-modelo-routing.toml`
- `S04` `A` `src/cadrumo/_data/registry/aeat/facts/0161-modelo-applicability-routes.toml`
- `S04` `A` `src/cadrumo/_data/registry/aeat/facts/0162-deadline-shift-exempt-modelos.toml`
- `S04` `A` `src/cadrumo/_data/registry/aeat/facts/0165-modelo-role-routing.toml`
- `S04` `A` `src/cadrumo/_data/registry/aeat/facts/0166-rebeca-eligible-vessel-registries.toml`
- `S04` `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/form_codes.py`
- `S04` `verify:` `test_tax_literal_sweep` -> `pass`
- `S07` `M` `src/cadrumo/domain/calculations/registry/actividad_asset_disposal_bindings.py`
- `S07` `M` `src/cadrumo/application/modelo/work_form_records.py`
- `S07` `M` `dev/registry/form_layout/page_sections.py`
- `S07` `verify:` `application_modelo_and_aggregation_tests` -> `pass`
- `S06` `M` `dev/quality/tests/test_tax_literal_sweep.py`
- `S06` `M` `dev/registry/tests/test_form_row_slots_follow_the_registry.py`
- `S06` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S06` `M` `src/cadrumo/_data/registry/aeat/facts/0126-nif-iva-country-format-catalogue.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/facts/0167-form-row-codes.toml`
- `S06` `M` `src/cadrumo/adapters/outbound/aeat/sede/notifications.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_evidence_draft.py`
- `S06` `M` `src/cadrumo/application/filing/export_envelope.py`
- `S06` `M` `src/cadrumo/application/filing/producer_snapshot_m296.py`
- `S06` `M` `src/cadrumo/application/filing/producer_snapshot_m360.py`
- `S06` `M` `src/cadrumo/application/filing/tests/test_modelo_360_producer_facts.py`
- `S06` `M` `src/cadrumo/application/filing/tests/test_registry_owned_snapshot_widths.py`
- `S06` `M` `src/cadrumo/core/identity/aeat_certificado.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/_formula_runtime_m131.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/export_record_components.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/formula_runtime_m100.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/tax_id_format.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/tests/test_long_tail_data_types.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_owned_identifier_widths.py`
- `S06` `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `S06` `M` `src/cadrumo/domain/contribuyente/descendant_record.py`
- `S06` `M` `src/cadrumo/domain/filing/software_identity.py`
- `S06` `M` `src/cadrumo/domain/invoices/business_premises.py`
- `S06` `M` `src/cadrumo/domain/invoices/tests/test_business_premises_lease.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/period_parsing.py`
- `S06` `verify:` `dev/quality/tests/test_tax_literal_sweep.py` -> `pass`
- `S06` `verify:` `lint-imports` -> `pass`
- `S06` `verify:` `operation_contract_manifest --check` -> `pass`
- `S07` `verify:` `publish-authority digest ba831103bc412fcf3a9f4b78cb1ff2b228a34ab225575efc759f18794759f0e2` -> `pass`
- `S07` `verify:` `test_export_xml_dictionary_repeated_rows and test_modelo_bindings_asset_disposal and M360 widths, 100 tests` -> `pass`
- `S07` `verify:` `test_form_row_slots_follow_the_registry` -> `pass`

## Notes

- `S01` Modelo 190 incapacity clave rule, Modelo 280 extinction key and Modelo 720 per-class subclaves move to S03, which adds their registry source
- `S02` lint-imports stops on a syntax error at `dev/tests/test_import_quality_gate.py:727,` outside this Step
- `S06` Commits aee54940ab ab3b795e53 afbb705350 940a6ab1f8. AEAT certificate, CSV and expediente shapes have no official source and stay in their technical owners.
- `S06` Correction: the commit in the earlier note is 38c4d81ca8, not 940a6ab1f8, which is a peer's commit; rows from that commit's paths are not this Step's work.
