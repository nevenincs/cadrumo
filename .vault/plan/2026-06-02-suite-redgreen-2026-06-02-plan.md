---
tags:
  - '#plan'
  - '#suite-redgreen-2026-06-02'
date: '2026-06-02'
modified: '2026-06-02'
tier: L2
related:
  - '[[2026-04-21-calc-verification-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
  - '[[2026-06-04-suite-redgreen-2026-06-02-adr]]'
  - '[[2026-06-04-suite-redgreen-2026-06-02-research]]'
---


# `suite-redgreen-2026-06-02` `Suite red-green burndown 2026-06-02` plan

### Phase `P01` - CLI work-calculate envelope cluster

Resolve the 14-test work-calculate empty-envelope cluster (peer signature drift around casilla_inputs)

- [x] `P01.S01` - Diagnose work-calculate empty-envelope; `Reproduce on test_modelo_discovery_defects[1P]; identify where _emit_envelope is silenced; document the precise call path in a comment`.
- [x] `P01.S02` - Restore envelope emission for work-calculate; `Production fix in CLI handler + service so success/refusal always emits the SchemaEnvelope; cite the 14 failing test ids`.
- [x] `P01.S03` - Verify 14-test cluster passes; `Run all 14 listed CLI tests isolated; commit when green`.

### Phase `P02` - IVA wallet decision routing

Fix the prior-filing-history and prior-year-history wallet decision injection so casilla 87 (compensacion aplicada) gets the persisted 1200/450 from the wallet decision (currently returns 0)

- [x] `P02.S04` - Trace iva_compensation_decision binding into engine inputs; `From calculate_modelo_revision through _apply_iva_compensation_decision_binding into resolved_bindings; instrument with _log.debug at each hand-off`.
- [x] `P02.S05` - Fix prior-filing-history routing; `Wire the wallet decision's applied_periodo through modelo-303-compensacion-aplicada-periodo binding so casilla 87 receives 1000 not 0`.
- [x] `P02.S06` - Verify both IVA wallet integration tests pass; `test_wallet_capture_decision_feeds_real_modelo_303_engine_from_{prior_filing_history,prior_year_history}`.

### Phase `P03` - Storage encrypted persistence policy

Restore encryption-at-rest for filing history + attachments manifest so plaintext does not appear in SQLite bytes

- [x] `P03.S07` - Audit attachment manifest field encryption; `Restore EncryptedString or equivalent on Justificante.source_pdf_sha256 et al so the hex digest does not appear in raw SQLite bytes`.
- [x] `P03.S08` - Restore filing_history TestClassificationGate encryption; `test_database_payload_is_encrypted_audit_data - re-enable column-level encryption for AUDIT classification rows`.
- [x] `P03.S09` - Verify storage encryption suite; `test_blob_and_manifest_round_trip_without_plaintext_files + test_database_payload_is_encrypted_audit_data`.

### Phase `P04` - Registry parity + coverage

Catalogue-verification, formula-modelo parity, modelo-parity coverage, ledger-iva 390 binding chain

- [x] `P04.S10` - Catalogue verification; `test_committed_registry_tree_has_required_model_law_coverage - identify missing model/law pair; either supply or relax with rationale`.
- [x] `P04.S11` - Formula-modelo parity; `test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces - wire missing formula→construct ownership`.
- [x] `P04.S12` - Modelo parity coverage; `test_formula_bearing_modelos_have_constructs_and_model_specific_tests - list bare formula-bearing modelos`.
- [x] `P04.S13` - M390 IVA binding chain; `Supply missing modelo-303-autoconsumo-promotor-base binding for the 390 annual pipeline test`.
- [x] `P04.S28` - Fix M714 empty formula fragment load blocker; `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/formulas/0001-formulas.toml`.

### Phase `P05` - Structural ratchets

Identity-primitive sibling-domain enum cycle, exception base hygiene, monkeypatch + cross-module imports + relative-imports drift

- [x] `P05.S14` - IvaRate sibling-domain cycle; `Relocate IvaRate out of invoices._enums into a leaf module (core or domain/iva) so iva._invoice_classification can import from public surface without cycle`.
- [x] `P05.S15` - Exception base hygiene; `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots - register or remove unregistered root`.
- [x] `P05.S16` - Monkeypatch + cross-module + relative-imports inventories; `Bring the three inventory ratchets back to zero (likely peer additions need rationale comments or removal)`.

### Phase `P06` - CLI surface contract

cli_workflow_verification retired-surface suggestions, operator_surface help_documents, backend_boundary, lazy_command_tree state-free general

- [x] `P06.S17` - Retired-surface canonical suggestions; `test_root_contract_service_rejects_retired_surfaces_with_canonical_suggestions - supply the suggestion map peer drift removed`.
- [x] `P06.S18` - Help documents backend-owned; `test_help_documents_are_backend_owned_and_current_surface_only - re-source help text from backend, remove stale entries`.
- [x] `P06.S19` - Backend boundary test xfail language; `test_cli_unit_tests_do_not_contain_process_state_or_xfail_language - find and remove the forbidden language`.
- [x] `P06.S20` - Lazy-command-tree state-free general; `test_state_free_surface_does_not_import_registry (non-help parametrize) - chase the registry leak path that --help-fix did not cover`.

### Phase `P07` - Setup + custody + Google

config_custody profile lifecycle, profile-create taxpayer-type paths, google sheets pull/export, fichero BOE golden sha

- [x] `P07.S21` - Config custody profile lifecycle; `test_profile_create_provisions_file_custody_and_switch_reopens_it - investigate why switch does not reopen`.
- [x] `P07.S22` - Legal-entity profile create; `test_legal_entity_profile_creates_non_interactively_without_spouse_flags`.
- [x] `P07.S23` - Google worksheet export-pull roundtrip; `test_workbook_input_values_survive_export_pull_compute_loop`.
- [x] `P07.S24` - Pull adapter classify_metadata empty pairs; `test_classify_metadata_returns_missing_for_empty_pairs (post sentinel + M347 fix; verify suite-level cleared)`.
- [x] `P07.S25` - Fichero BOE golden sha; `test_modelo_303_golden_sha_fichero_boe - recompute golden sha if peer registry change altered output`.

### Phase `P08` - Filing + date routing

test_date_relation_routing non-iso rejection, test_binding_prefill modelo 390 prefill

- [x] `P08.S26` - Date relation routing non-iso reject; `test_date_inputs_for_ids_rejects_non_iso_value - re-derive non-iso rejection path post _parse_iso8601_date routing`.
- [x] `P08.S27` - Modelo 390 prefill binding-prefill; `test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations`.

### Phase `P09` - M303 verification_chain 47-red cluster

Land architect Route A spec — synthetic-PDF primitive encoding + extraction profile + anti-tautology test

- [x] `P09.S29` - Land synthetic-PDF generator primitive encoding per ADR 2026-06-03-m303-synthetic-generator-primitive-spec; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `P09.S30` - Update M303 extraction_profile to parse primitives drop totals 27 and 45; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`.
- [x] `P09.S31` - Author anti-tautology proof test mutate iva.repercutido.general and assert engine total tracks; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.

### Phase `P10` - any-return rationale 23-red cluster

Sweep test_any_return_rationale_markers reds — add rationale marker tokens or replace Any with concrete type

- [x] `P10.S32` - Sweep test_any_return_rationale_markers 23 reds add rationale tokens or replace Any; `src/aeat`.

### Phase `P11` - CLI workflow verification 15-red cluster

Diagnose + fix test_cli_workflow_verification failures

- [x] `P11.S33` - Diagnose then fix test_cli_workflow_verification 15-red cluster; `src/aeat/entrypoints/cli/test_cli_workflow_verification.py`.

### Phase `P12` - M100 tarifa_real 14-red cluster

Diagnose + fix test_modelo_100_tarifa_real failures

- [x] `P12.S34` - Diagnose then fix test_modelo_100_tarifa_real 14 reds; `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`.

### Phase `P13` - M200 cuota chain 16-red cluster

M200 cuota_integra_lanes + tipo_gravamen_dispatch reds

- [x] `P13.S35` - Diagnose then fix M200 cuota_integra_lanes 9 reds; `src/aeat/domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py`.
- [x] `P13.S36` - Diagnose then fix M200 tipo_gravamen_dispatch 7 reds; `src/aeat/domain/calculations/registry/test_modelo_200_tipo_gravamen_dispatch.py`.

### Phase `P14` - M100 renta chain 28-red cluster

tarifa_real + ahorro_base + settlement + retenciones + renta_chain_behaviour + reduccion_art_84 + minimo_contribuyente

- [x] `P14.S37` - Diagnose then fix M100 ahorro_base_chain 6 reds; `src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py`.
- [x] `P14.S38` - Diagnose then fix M100 settlement_chain 6 reds; `src/aeat/domain/calculations/registry/test_modelo_100_settlement_chain.py`.
- [x] `P14.S39` - Diagnose then fix M100 retenciones_binding_wiring 5 reds; `src/aeat/domain/calculations/registry/test_modelo_100_retenciones_binding_wiring.py`.
- [x] `P14.S40` - Diagnose then fix reduccion_art_84_conjunta 8 reds; `src/aeat/domain/calculations/registry/test_reduccion_art_84_conjunta.py`.
- [x] `P14.S41` - Diagnose then fix minimo_contribuyente_age_increment 8 reds; `src/aeat/domain/calculations/registry/test_minimo_contribuyente_age_increment.py`.
- [x] `P14.S42` - Diagnose then fix renta_chain_behaviour 5 reds; `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`.
- [x] `P14.S43` - Diagnose then fix M100 cripto_1812_propagation 5 reds; `src/aeat/domain/calculations/registry/test_modelo_100_cripto_1812_propagation.py`.

### Phase `P15` - modelo_discovery_defects 14-red cluster

Diagnose + fix CLI modelo discovery cluster

- [x] `P15.S44` - Diagnose then fix modelo_discovery_defects 14 reds; `src/aeat/entrypoints/cli/test_modelo_discovery_defects.py`.

### Phase `P16` - cli_surface 13-red cluster

Diagnose + fix CLI surface tests

- [x] `P16.S45` - Diagnose then fix cli_surface 13 reds; `src/aeat/entrypoints/cli/test_cli_surface.py`.

## Description


## Steps







## Parallelization


## Verification
