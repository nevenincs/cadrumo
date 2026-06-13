---
tags:
  - '#reference'
  - '#core-authority-duplicates-v2'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# core-authority-duplicates-v2 reference: AST duplicate-name audit

AST-based exhaustive scan of every class, module-scope def, UPPER_SNAKE constant,
lower-snake module assignment, and annotated module assignment across all 1,655 .py
files under src/aeat/. No filtering applied. Previous audit (first pass) filtered
356 function duplicates as acceptable test fixtures and reported 10 classes + 9 constants.
This audit reports all 449 duplicate names unfiltered and classifies each.

## Methodology

- Python ast.iter_child_nodes on every file; SyntaxError files skipped (0 skipped).
- 1,655 files scanned; 449 names appear in 2+ files.
- Classification per-name:
  - semantic-identical: same kind + matching signature/fingerprint across all sites.
  - sig-collision: same kind, differing signatures or values.
  - name-collision: different domain or kind across sites.
- Cross-layer: name whose sites span 2+ top-level layer directories.

## Summary Statistics

| Metric | Count |
|--------|-------|
| Files scanned | 1,655 |
| Total duplicate names | **449** |
| -- function | 361 |
| -- class | 43 |
| -- annotated_assign | 23 |
| -- constant | 12 |
| -- module_assign | 9 |
| -- mixed (cross-kind) | 1 |
| Semantic-identical | **251** |
| Signature-collision | **170** |
| Name-collision | **28** |
| Cross-layer duplicates | **152** |

Delta vs first audit: first pass reported 10 classes + 9 constants + 356 filtered functions
= 375 total (functions mostly suppressed). This audit surfaces 449 total (74 additional
names surfaced, plus full unfiltered function enumeration).

## Layer Distribution Histogram

| Layer | Occurrences in duplicate-name sites |
|-------|-------------------------------------|
| application | 193 |
| domain | 174 |
| adapters | 141 |
| entrypoints | 70 |
| core | 38 |
| tests | 13 |
| diagnostics | 10 |
| locales | 5 |
| root-level inventory test files | 29 |
## Top 50 Most-Duplicated Names

| Rank | Name | Sites | Kind | Classification |
|------|------|-------|------|----------------|
| 1 | pytestmark | 842 | module_assign | sig-collision |
| 2 | __all__ | 466 | mixed | sig-collision |
| 3 | _log | 59 | module_assign | name-collision |
| 4 | _logger | 51 | module_assign | sig-collision |
| 5 | ENTRY | 42 | constant | sig-collision |
| 6 | _isolated_backend | 28 | function | sig-collision |
| 7 | secure_objects | 22 | function | name-collision |
| 8 | cli_runner | 21 | function | name-collision |
| 9 | _transaction | 17 | function | sig-collision |
| 10 | _isolated_cli_backend | 16 | function | name-collision |
| 11 | _invoice | 14 | function | sig-collision |
| 12 | _profile | 13 | function | sig-collision |
| 13 | _payload | 13 | function | sig-collision |
| 14 | runtime_profile | 13 | function | name-collision |
| 15 | logger | 11 | module_assign | sig-collision |
| 16 | _invoke | 11 | function | sig-collision |
| 17 | log | 10 | module_assign | name-collision |
| 18 | _STRICT_FROZEN | 10 | annotated_assign | sig-collision |
| 19 | app | 10 | module_assign | sig-collision |
| 20 | _runtime_profile | 8 | function | name-collision |
| 21 | TestDelete | 8 | class | name-collision |
| 22 | TestClassificationGate | 8 | class | name-collision |
| 23 | _database_bytes | 8 | function | sig-collision |
| 24 | _raw_transaction | 8 | function | sig-collision |
| 25 | schema | 8 | function | name-collision |
| 26 | _question | 8 | function | sig-collision |
| 27 | _load_modelo | 8 | function | name-collision |
| 28 | _modelo_130_snapshot | 7 | function | name-collision |
| 29 | _revision | 7 | function | sig-collision |
| 30 | _observation | 7 | function | sig-collision |
| 31 | TestBucketIsolation | 7 | class | name-collision |
| 32 | _modelo | 7 | function | sig-collision |
| 33 | _service | 7 | function | sig-collision |
| 34 | repos | 7 | function | name-collision |
| 35 | _seed_work_unit | 7 | function | sig-collision |
| 36 | _scrub_value | 7 | function | name-collision |
| 37 | _call_name | 6 | function | name-collision |
| 38 | TestEmptyState | 6 | class | name-collision |
| 39 | TestSaveLoad | 6 | class | name-collision |
| 40 | TestShow | 6 | class | name-collision |
| 41 | _repositories | 6 | function | sig-collision |
| 42 | _seed_profile | 6 | function | sig-collision |
| 43 | runner | 6 | function | name-collision |
| 44 | _binding | 6 | function | sig-collision |
| 45 | _casilla_with | 6 | function | sig-collision |
| 46 | _create_profile | 6 | function | sig-collision |
| 47 | _RecordingPage | 5 | class | name-collision |
| 48 | _RecordingBrowserSession | 5 | class | name-collision |
| 49 | main | 5 | function | name-collision |
| 50 | _parse_date | 5 | function | sig-collision |
## Section 1 -- Full Duplicate-Name Table

All 449 names with 2+ declarations, sorted by site count descending.
Sites truncated at 8 per name. Fingerprint: sig=function-params, value=constant/assign value, bases=class bases.

### pytestmark

count=842  kind=module_assign  class=sig-collision

layers: _data, adapters, application, core, diagnostics, domain, entrypoints, locales, test_cast_rationale_inventory.py, test_clock_enrollment_inventory.py, test_coverage_inventory.py, test_decimal_enrollment_inventory.py, test_hardcoded_constants_inventory.py, test_locale_coverage_inventory.py, test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_bare_except.py, test_no_skip_xfail.py, test_no_tautology.py, test_parsing_enrollment_inventory.py, test_roundtrip_coverage.py, test_roundtrip_fixture_saturation.py, test_semantic_intent_sampler.py, test_utc_validator_enrollment_inventory.py, test_w04_p22_cleanup.py, test_w05_p23_locale_coverage.py, test_w05_p24_exceptions.py, tests

- _data\corpus\test_corpus_provenance.py:26 [_data]  [pytest.mark.unit, pytest.mark.domain_model]
- adapters\inbound\borrador\test_modelo_100_summary.py:13 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound]
- adapters\inbound\borrador\test_verification_chain_borrador.py:78 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound]
- adapters\inbound\declaracion\test_detect_template_revision.py:27 [adapters]  [pytest.mark.unit, pytest.mark.domain_application]
- adapters\inbound\declaracion\test_exception_hygiene.py:10 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound]
- adapters\inbound\declaracion\test_parser_boundary.py:19 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound, pytest.mark.f
- adapters\inbound\declaracion\test_shared_model_boundaries.py:13 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound]
- adapters\inbound\declaracion\test_verification_chain.py:131 [adapters]  [pytest.mark.unit, pytest.mark.domain_inbound]
  ... (834 more sites)

### __all__

count=466  kind=mixed  class=sig-collision

layers: adapters, application, core, diagnostics, domain, entrypoints, locales, tests

- adapters\inbound\borrador\__init__.py:31 [adapters]  ['ArtefactKind', 'BorradorExtractionProfile', 'BorradorObser
- adapters\inbound\borrador\_extractors\__init__.py:53 [adapters]  ['ArtefactKind', 'get_extractor']
- adapters\inbound\borrador\_extractors\modelo_100_summary_v2025.py:171 [adapters]  ['Modelo100ObservedV2025Extractor']
- adapters\inbound\borrador\_parser.py:79 [adapters]  ['parse_borrador']
- adapters\inbound\borrador\_parsers\__init__.py:12 [adapters]  ['extract_pages_text']
- adapters\inbound\declaracion\__init__.py:29 [adapters]  ['DeclaracionObservation', 'DeclaracionParseError', 'Extract
- adapters\inbound\declaracion\_parsers\__init__.py:13 [adapters]  ['extract_pages_text', 'extract_pages_text_from_bytes']
- adapters\inbound\financial\__init__.py:30 [adapters]  ['BankStatementParseError', 'CorpusVerificationSource', 'Csv
  ... (458 more sites)

### _log

count=59  kind=module_assign  class=name-collision

layers: adapters, application, core, domain, entrypoints, locales

- adapters\outbound\aeat\sede\_adapter_utils.py:24 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_parse.py:29 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\test_renta_web_open_explore_dom.py:57 [adapters]  get_logger(__name__)
- adapters\outbound\llm\_cache.py:25 [adapters]  get_logger(__name__)
- adapters\outbound\storage\test_google_drive_live.py:42 [adapters]  get_logger(__name__)
- adapters\persistence\profile\assets.py:24 [adapters]  get_logger(__name__)
- adapters\persistence\profile\inventory.py:24 [adapters]  get_logger(__name__)
- adapters\persistence\storage\_rotation.py:52 [adapters]  get_logger(__name__)
  ... (51 more sites)

### _logger

count=51  kind=module_assign  class=sig-collision

layers: adapters, application, core, domain, test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py

- adapters\inbound\borrador\_parser.py:25 [adapters]  get_logger(__name__)
- adapters\inbound\declaracion\_parser.py:34 [adapters]  get_logger(__name__)
- adapters\inbound\declaracion\_parsers\_pdfplumber_backend.py:31 [adapters]  get_logger(__name__)
- adapters\inbound\financial\providers\_csv.py:41 [adapters]  get_logger(__name__)
- adapters\inbound\financial\providers\_detection.py:24 [adapters]  get_logger(__name__)
- adapters\inbound\financial\providers\_ofx.py:34 [adapters]  get_logger(__name__)
- adapters\inbound\financial\providers\_xlsx.py:49 [adapters]  get_logger(__name__)
- adapters\inbound\justificante\_extract.py:31 [adapters]  get_logger(__name__)
  ... (43 more sites)

### ENTRY

count=42  kind=constant  class=sig-collision

layers: domain

- domain\portals\_entries\portal_calendario_contribuyente.py:14 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CALENDARIO_
- domain\portals\_entries\portal_cert_selection.py:16 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CERT_SELECT
- domain\portals\_entries\portal_cert_validation_rest.py:16 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CERT_VALIDA
- domain\portals\_entries\portal_clave_gestiones.py:15 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CLAVE_GESTI
- domain\portals\_entries\portal_clave_idp_root.py:16 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CLAVE_IDP_R
- domain\portals\_entries\portal_clave_sede_entry.py:15 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CLAVE_SEDE_
- domain\portals\_entries\portal_consulta_pagos.py:16 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_CONSULTA_PA
- domain\portals\_entries\portal_dnie_sede_entry.py:15 [domain]  :PortalMetadata=build_entry(portal=Portal.PORTAL_DNIE_SEDE_E
  ... (34 more sites)

### _isolated_backend

count=28  kind=function  class=sig-collision

layers: application, diagnostics, entrypoints

- application\auth\test_operator.py:93 [application]  (tmp_path)
- application\modelo\test_reconcile.py:42 [application]  (tmp_path)
- application\wizard\test_commands.py:35 [application]  (tmp_path)
- diagnostics\test_profile.py:37 [diagnostics]  (tmp_path)
- entrypoints\cli\test_audit_verbs.py:39 [entrypoints]  (tmp_path)
- entrypoints\cli\test_business_invoice_verbs.py:23 [entrypoints]  (tmp_path, monkeypatch)
- entrypoints\cli\test_cli_surface.py:32 [entrypoints]  (tmp_path)
- entrypoints\cli\test_config_setter.py:37 [entrypoints]  (tmp_path)
  ... (20 more sites)

### secure_objects

count=22  kind=function  class=name-collision

layers: application

- application\aggregation\test_fx_conversion.py:125 [application]  (tmp_path)
- application\aggregation\test_iva_ledger.py:44 [application]  (tmp_path)
- application\aggregation\test_modelo_source_mesh_ledger.py:65 [application]  (tmp_path)
- application\aggregation\test_renta_income_aggregation.py:45 [application]  (tmp_path)
- application\aggregation\test_renta_ledger.py:48 [application]  (tmp_path)
- application\ledger\test_actions.py:91 [application]  (tmp_path)
- application\ledger\test_business_operation_invoice.py:36 [application]  (tmp_path)
- application\ledger\test_evidence.py:30 [application]  (tmp_path)
  ... (14 more sites)

### cli_runner

count=21  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_audit_verbs.py:34 [entrypoints]  ()
- entrypoints\cli\test_business_invoice_verbs.py:38 [entrypoints]  ()
- entrypoints\cli\test_config_setter.py:32 [entrypoints]  ()
- entrypoints\cli\test_inventory_verbs.py:38 [entrypoints]  ()
- entrypoints\cli\test_ledger_link_check_verbs.py:22 [entrypoints]  ()
- entrypoints\cli\test_ledger_preflight_verb.py:22 [entrypoints]  ()
- entrypoints\cli\test_ledger_verb_spine.py:56 [entrypoints]  ()
- entrypoints\cli\test_live_notifications_verbs.py:38 [entrypoints]  ()
  ... (13 more sites)

### _transaction

count=17  kind=function  class=sig-collision

layers: adapters, application, domain, entrypoints

- adapters\persistence\storage\test_runtime_migrated_repositories.py:192 [adapters]  (label)
- application\aggregation\test_iva_ledger.py:77 [application]  (provider_id, amount, direction, business_classification, business_pct, booked_date, value_date, currency, taxable_base, iva_rate, iva_amount, prorrata_reference, lifecycle_state)
- application\aggregation\test_renta_ledger.py:81 [application]  (provider_id, amount, category, purchase_invoice_evidence_id, direction, business_classification, business_pct, booked_date, value_date, currency, taxable_base, iva_rate, iva_amount, lifecycle_state)
- application\invoices\test_linking.py:76 [application]  ()
- application\invoices\test_projection.py:138 [application]  ()
- application\invoices\test_queries.py:116 [application]  ()
- application\invoices\test_reconciliation.py:101 [application]  ()
- application\ledger\test_preflight.py:69 [application]  (provider_id, direction, amount, business_classification, business_pct, category_id, taxable_base, iva_rate, iva_amount, usage_ratio_id, booked_date, currency, lifecycle_state)
  ... (9 more sites)

### _isolated_cli_backend

count=16  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\_config\test_config.py:38 [entrypoints]  (tmp_path)
- entrypoints\cli\_config\test_repair_reset_state.py:28 [entrypoints]  (tmp_path)
- entrypoints\cli\test_apex_workflow_verification.py:24 [entrypoints]  (tmp_path)
- entrypoints\cli\test_modelo_151_stub_refusal.py:32 [entrypoints]  (tmp_path)
- entrypoints\cli\test_modelo_210_stub_refusal.py:33 [entrypoints]  (tmp_path)
- entrypoints\cli\test_modelo_600_stub_refusal.py:31 [entrypoints]  (tmp_path)
- entrypoints\cli\test_modelo_620_stub_refusal.py:30 [entrypoints]  (tmp_path)
- entrypoints\cli\test_modelo_650_stub_refusal.py:32 [entrypoints]  (tmp_path)
  ... (8 more sites)

### _invoice

count=14  kind=function  class=sig-collision

layers: adapters, application, domain

- adapters\persistence\storage\test_runtime_migrated_repositories.py:286 [adapters]  (label)
- application\aggregation\test_modelo_source_mesh_ledger.py:147 [application]  (tx_id, bucket_id)
- application\aggregation\test_renta_ledger.py:122 [application]  (tx_id, bucket_id, kind, issued_at, grand_total, linked_transaction_ids)
- application\invoices\test_linking.py:46 [application]  ()
- application\invoices\test_projection.py:33 [application]  ()
- application\invoices\test_projection_helpers.py:40 [application]  (base_total, iva_total)
- application\invoices\test_queries.py:81 [application]  (invoice_number, issued_at, kind)
- application\invoices\test_reconciliation.py:71 [application]  ()
  ... (6 more sites)

### _profile

count=13  kind=function  class=sig-collision

layers: adapters, application, domain

- adapters\inbound\borrador\test_modelo_100_summary.py:66 [adapters]  (target_casilla_ids, min_coverage)
- application\filing\test_build_draft_identity.py:29 [application]  ()
- application\filing\test_filing.py:40 [application]  ()
- application\filing\test_modelo_303_390.py:24 [application]  ()
- application\modelo\test_export.py:68 [application]  ()
- application\overview\test_agenda.py:22 [application]  ()
- application\overview\test_backlog.py:36 [application]  ()
- application\overview\test_calendar.py:30 [application]  ()
  ... (5 more sites)

### _payload

count=13  kind=function  class=sig-collision

layers: application, entrypoints

- application\auth\_diagnostics.py:215 [application]  (raw)
- entrypoints\cli\test_modelo.py:23 [entrypoints]  (output)
- entrypoints\cli\test_modelo_202_modality.py:51 [entrypoints]  (output)
- entrypoints\cli\test_modelo_calculation_through_real_cli.py:39 [entrypoints]  (output)
- entrypoints\cli\test_modelo_casilla_normalisation.py:34 [entrypoints]  (output)
- entrypoints\cli\test_modelo_compare.py:79 [entrypoints]  (output)
- entrypoints\cli\test_modelo_discovery_defects.py:37 [entrypoints]  (output)
- entrypoints\cli\test_modelo_period_consistency.py:26 [entrypoints]  (output)
  ... (5 more sites)

### runtime_profile

count=13  kind=function  class=name-collision

layers: application, domain, entrypoints

- application\evidence\test_evidence.py:39 [application]  (tmp_path)
- application\user_profile\test_corporate_tax_facts_roundtrip.py:123 [application]  (tmp_path)
- application\user_profile\test_repository_anti_tautology.py:50 [application]  (tmp_path)
- application\user_profile\test_repository_roundtrip.py:62 [application]  (tmp_path)
- domain\attachments\test_repository.py:22 [domain]  (tmp_path)
- domain\justificante\test_repository.py:47 [domain]  (tmp_path)
- domain\submission\test_repository.py:57 [domain]  (tmp_path)
- domain\transactions\test_repository.py:22 [domain]  (tmp_path)
  ... (5 more sites)

### logger

count=11  kind=module_assign  class=sig-collision

layers: adapters, core, entrypoints

- adapters\outbound\aeat\browser\_factory.py:43 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\browser\evasion.py:12 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\browser\health.py:13 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\browser\session.py:36 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_groi_check.py:72 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_nif_iva_check.py:63 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_renta_web_open.py:41 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_renta_web_open_safety.py:46 [adapters]  get_logger(__name__)
  ... (3 more sites)

### _invoke

count=11  kind=function  class=sig-collision

layers: application, entrypoints

- application\setup\test_atomic_create_roundtrip.py:60 [application]  (args)
- entrypoints\cli\test_apex_workflow_verification.py:47 [entrypoints]  (args)
- entrypoints\cli\test_audit_remediation.py:40 [entrypoints]  (args)
- entrypoints\cli\test_cli_surface.py:50 [entrypoints]  (args)
- entrypoints\cli\test_modelo_work_ux.py:43 [entrypoints]  (args)
- entrypoints\cli\test_profile_export_roundtrip.py:49 [entrypoints]  (args)
- entrypoints\cli\test_profile_import_idempotency.py:37 [entrypoints]  (args)
- entrypoints\cli\test_profile_output_language.py:25 [entrypoints]  (args)
  ... (3 more sites)

### log

count=10  kind=module_assign  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\_authenticator.py:81 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\auth\_certificate_backends\_httpx_fallback.py:24 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\auth\_certificate_backends\_playwright_context.py:30 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\auth\_clave_movil.py:73 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\auth\certificate.py:45 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_censo_live.py:50 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_declarations.py:103 [adapters]  get_logger(__name__)
- adapters\outbound\aeat\sede\_iva_compensation_wallet.py:45 [adapters]  get_logger(__name__)
  ... (2 more sites)

### _STRICT_FROZEN

count=10  kind=annotated_assign  class=sig-collision

layers: adapters, application

- adapters\outbound\aeat\sede\_declarations.py:137 [adapters]  :Final[ConfigDict]=ConfigDict(strict=True, frozen=True, extr
- adapters\outbound\aeat\sede\_notifications.py:59 [adapters]  :Final[ConfigDict]=ConfigDict(strict=True, frozen=True, extr
- adapters\outbound\aeat\sede\_schema.py:28 [adapters]  :Final[ConfigDict]=ConfigDict(strict=True, frozen=True, extr
- adapters\persistence\storage\master_key\_recovery.py:52 [adapters]  :Final=ConfigDict(strict=True, frozen=True, extra='forbid')
- application\auth\_catalogue.py:11 [application]  :Final[ConfigDict]=ConfigDict(strict=True, frozen=True, extr
- application\calculations\_binding_prefill.py:79 [application]  :Final=ConfigDict(strict=True, frozen=True, extra='forbid')
- application\calculations\_iva_wallet_balance.py:17 [application]  :Final=ConfigDict(strict=True, frozen=True, extra='forbid')
- application\calculations\_iva_wallet_reconciliation.py:31 [application]  :Final=ConfigDict(strict=True, frozen=True, extra='forbid')
  ... (2 more sites)

### app

count=10  kind=module_assign  class=sig-collision

layers: diagnostics, entrypoints, locales

- diagnostics\__main__.py:17 [diagnostics]  typer.Typer(name='diagnostics', help=tr('cli.diagnostics.app
- entrypoints\cli\__init__.py:66 [entrypoints]  typer.Typer(name='aeat', help=tr('cli.root.app_help'), no_ar
- entrypoints\cli\_app_live.py:44 [entrypoints]  typer.Typer(name='live', help=tr('cli.app.live.app_help'), n
- entrypoints\cli\_config\__init__.py:58 [entrypoints]  typer.Typer(name='config', help=tr('cli.config.app_help'), n
- entrypoints\cli\_ledger.py:90 [entrypoints]  typer.Typer(name='ledger', help=tr('cli.ledger.app_help'), n
- entrypoints\cli\_modelo.py:143 [entrypoints]  typer.Typer(name='modelo', help=tr('cli.app.modelo.app_help'
- entrypoints\cli\_overview.py:28 [entrypoints]  typer.Typer(name='overview', help=tr('cli.overview.app_help'
- entrypoints\cli\_review.py:39 [entrypoints]  typer.Typer(name='review', help=tr('cli.review.app_help'), n
  ... (2 more sites)

### _runtime_profile

count=8  kind=function  class=name-collision

layers: adapters, domain, entrypoints

- adapters\persistence\profile\test_assets.py:26 [adapters]  (tmp_path)
- adapters\persistence\profile\test_inventory.py:27 [adapters]  (tmp_path)
- adapters\persistence\storage\test_submission_repository.py:63 [adapters]  (tmp_path)
- domain\invoices\test_repository.py:38 [domain]  (tmp_path)
- domain\usage_ratios\test_census_refuse_load.py:32 [domain]  (tmp_path)
- domain\usage_ratios\test_service.py:34 [domain]  (tmp_path)
- entrypoints\cli\test_iva_wallet_inspector.py:60 [entrypoints]  (tmp_path)
- entrypoints\cli\test_session_lifecycle_roundtrip.py:76 [entrypoints]  (tmp_path)

### TestDelete

count=8  kind=class  class=name-collision

layers: adapters, application, domain

- adapters\persistence\storage\blob_store\test_blob_store.py:148 [adapters]  []
- adapters\persistence\storage\secret_store\test_secret_store.py:220 [adapters]  []
- adapters\persistence\storage\test_submission_repository.py:126 [adapters]  []
- application\filing\test_complementaria_repository.py:116 [application]  []
- application\filing\test_history_repository.py:85 [application]  []
- application\filing\test_repository.py:118 [application]  []
- domain\justificante\test_repository.py:94 [domain]  []
- domain\submission\test_repository.py:120 [domain]  []

### TestClassificationGate

count=8  kind=class  class=name-collision

layers: adapters, application, domain

- adapters\persistence\storage\envelope\test_envelope.py:144 [adapters]  []
- adapters\persistence\storage\envelope\test_envelope_ciphertext.py:138 [adapters]  []
- adapters\persistence\storage\test_submission_repository.py:139 [adapters]  []
- application\filing\test_complementaria_repository.py:129 [application]  []
- application\filing\test_history_repository.py:97 [application]  []
- application\filing\test_repository.py:131 [application]  []
- domain\justificante\test_repository.py:107 [domain]  []
- domain\submission\test_repository.py:133 [domain]  []

### _database_bytes

count=8  kind=function  class=sig-collision

layers: adapters, application, domain

- adapters\persistence\storage\test_submission_repository.py:68 [adapters]  (profile)
- application\filing\test_complementaria_repository.py:80 [application]  (tmp_path)
- application\filing\test_history_repository.py:38 [application]  (tmp_path)
- application\filing\test_repository.py:60 [application]  (tmp_path)
- application\workflow\test_persistence.py:37 [application]  (tmp_path)
- domain\justificante\test_repository.py:52 [domain]  (runtime_profile)
- domain\submission\test_repository.py:62 [domain]  (runtime_profile)
- domain\usage_ratios\test_service.py:39 [domain]  (profile)

### _raw_transaction

count=8  kind=function  class=sig-collision

layers: application, entrypoints

- application\aggregation\test_iva_ledger.py:49 [application]  (provider_id, booked_date, value_date, amount, currency)
- application\aggregation\test_modelo_source_mesh_ledger.py:75 [application]  (provider_id, booked_date, amount)
- application\aggregation\test_renta_income_aggregation.py:50 [application]  (provider_id, booked_date, value_date, amount, currency)
- application\aggregation\test_renta_ledger.py:53 [application]  (provider_id, booked_date, value_date, amount, currency)
- application\ledger\test_preflight.py:42 [application]  (provider_id, booked_date, amount, currency)
- application\modelo\test_bucket_aggregation_flow.py:57 [application]  (provider_id, booked_date, amount)
- application\transactions\test_import.py:54 [application]  (provider_id, booked_date, value_date, amount, description)
- entrypoints\cli\test_modelo_source_mesh_calculate.py:94 [entrypoints]  (provider_id, booked_date, amount)

### schema

count=8  kind=function  class=name-collision

layers: application, domain

- application\user_profile\test_irpf_special_regime_persistence_roundtrip.py:62 [application]  ()
- application\user_profile\test_lifecycle.py:45 [application]  ()
- application\user_profile\test_marriage_date_persistence_roundtrip.py:52 [application]  ()
- application\user_profile\test_orchestration.py:45 [application]  ()
- application\user_profile\test_services.py:22 [application]  ()
- application\user_profile\test_taxpayer_axes_persistence_roundtrip.py:63 [application]  ()
- domain\user_profile\test_census_schema_fields.py:30 [domain]  ()
- domain\user_profile\test_taxpayer_type_schema_fields.py:20 [domain]  ()

### _question

count=8  kind=function  class=sig-collision

layers: application

- application\wizard\test_commands_helpers.py:45 [application]  (qid, answer_type, widget, required, default, visible_when)
- application\wizard\test_compile.py:39 [application]  (qid, profile_key, required, visible_when)
- application\wizard\test_models.py:38 [application]  (qid, profile_key, widget, prompt, answer_type)
- application\wizard\test_persistence_canonical.py:37 [application]  (answer_type, profile_key, default, choices, widget)
- application\wizard\test_prompter.py:25 [application]  (qid, prompt)
- application\wizard\test_questionary_smoke.py:29 [application]  (widget, choices, answer_type)
- application\wizard\test_runner_condition.py:34 [application]  (qid, visible_when)
- application\wizard\test_widgets.py:37 [application]  (widget, choices, required, visible_when, prompt, answer_type)

### _load_modelo

count=8  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_111_registry.py:29 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_115_registry.py:16 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_123_registry.py:19 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_130_registry.py:40 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_131_registry.py:28 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_180_registry.py:28 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_190_registry.py:28 [domain]  (modelo_id)
- domain\calculations\registry\test_modelo_193_registry.py:27 [domain]  (modelo_id)

### _modelo_130_snapshot

count=7  kind=function  class=name-collision

layers: adapters, domain

- adapters\inbound\declaracion\test_parser_boundary.py:1870 [adapters]  ()
- adapters\outbound\aeat\sede\test_declarations.py:142 [adapters]  ()
- adapters\outbound\google\test_compute_from_pull.py:37 [adapters]  ()
- adapters\outbound\google\test_pull_adapter_helpers.py:90 [adapters]  ()
- adapters\outbound\google\test_worksheet_export_pull_roundtrip.py:46 [adapters]  ()
- domain\calculations\registry\test_filed_state.py:27 [domain]  ()
- domain\calculations\registry\test_registry_schema.py:159 [domain]  ()

### _revision

count=7  kind=function  class=sig-collision

layers: application, domain

- application\aggregation\test_modelo_source_mesh_ledger.py:70 [application]  (modelo, revision_id)
- application\modelo\test_iva_wallet_decision_binding.py:43 [application]  ()
- domain\calculations\registry\test_counterpart_bindings.py:49 [domain]  (*bindings)
- domain\calculations\registry\test_invoice_bindings.py:49 [domain]  (*bindings)
- domain\calculations\registry\test_modelo_chain_resolution.py:26 [domain]  (modelo_id, revision_id)
- domain\calculations\registry\test_registry_schema.py:58 [domain]  (modelo)
- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:70 [domain]  (year)

### _observation

count=7  kind=function  class=sig-collision

layers: application, domain

- application\aggregation\test_renta_ledger_aggregation.py:45 [application]  (transaction_id, category, gross_amount)
- application\calculations\test_binding_prefill.py:40 [application]  (ledger_id, txn_date, flow, iva)
- application\modelo\test_modelo_210_phase1.py:271 [application]  (casilla_id, value)
- domain\calculations\registry\test_counterpart_bindings.py:61 [domain]  (party, country, base, clave, source_kind, is_rectification, previous, period, year)
- domain\calculations\registry\test_invoice_bindings.py:61 [domain]  (party, country, base, clave, is_rectification, previous, period, year)
- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:61 [domain]  (ledger_id, txn_date, category, rate_kind, flow, base, iva)
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:55 [domain]  (ledger_id, txn_date, regime, destination, rate_kind, direction, kind, base, iva)

### TestBucketIsolation

count=7  kind=class  class=name-collision

layers: application

- application\auth\test_apoderado.py:161 [application]  []
- application\evidence\test_evidence.py:268 [application]  []
- application\inventory\test_inventory.py:319 [application]  []
- application\ledger\test_business_operation_invoice.py:314 [application]  []
- application\live\test_expedientes.py:146 [application]  []
- application\live\test_notifications.py:180 [application]  []
- application\live\test_verify.py:240 [application]  []

### _modelo

count=7  kind=function  class=sig-collision

layers: application, domain

- application\calculations\test_detail_record_round_trip.py:48 [application]  (modelo_id, revision_id)
- application\calculations\test_row_set_assembly.py:47 [application]  (modelo_id, revision_id)
- domain\calculations\registry\test_cross_revision_drift.py:63 [domain]  (modelo_id, revs, selectors, evolutions, continuidad_validation)
- domain\calculations\registry\test_modelo_chain_resolution.py:21 [domain]  (modelo_id)
- domain\calculations\registry\test_relation_closure.py:38 [domain]  (modelos, modelo_id)
- domain\calculations\registry\test_required_role_hardflip.py:47 [domain]  (modelo_id, revision_id, casillas)
- domain\calculations\registry\test_semantic_role.py:63 [domain]  (modelo_id, revision_id, casillas)

### _service

count=7  kind=function  class=sig-collision

layers: application, domain, entrypoints

- application\live\test_expedientes.py:30 [application]  (profile)
- application\live\test_notifications.py:33 [application]  (profile)
- application\live\test_verify.py:29 [application]  (profile)
- application\user_profile\test_census_sync.py:50 [application]  (secure_objects)
- application\user_profile\test_lifecycle.py:49 [application]  (secure_objects, schema)
- domain\calculations\registry\test_queries.py:19 [domain]  ()
- entrypoints\cli\_modelo.py:4212 [entrypoints]  ()

### repos

count=7  kind=function  class=name-collision

layers: application

- application\modelo\test_amend_flow.py:77 [application]  (tmp_path)
- application\modelo\test_file_flow.py:143 [application]  (tmp_path)
- application\modelo\test_history.py:34 [application]  (tmp_path)
- application\modelo\test_import_flow.py:76 [application]  (tmp_path)
- application\modelo\test_previous_filing_casilla_override.py:40 [application]  (tmp_path)
- application\modelo\test_verificado_completo_regression.py:80 [application]  (tmp_path)
- application\modelo\test_verification_substance.py:373 [application]  (tmp_path)

### _seed_work_unit

count=7  kind=function  class=sig-collision

layers: application, entrypoints

- application\modelo\test_amend_flow.py:90 [application]  (wu_repo)
- application\modelo\test_file_flow.py:159 [application]  (wu_repo, bucket_id, modelo, filing_year, period, revision_id)
- application\modelo\test_import_flow.py:89 [application]  (wu_repo)
- application\modelo\test_reconcile.py:59 [application]  (modelo, filing_year, period)
- application\modelo\test_source_mesh_calculation.py:45 [application]  (work_unit_repository, modelo, filing_year, period, revision_id)
- entrypoints\cli\test_modelo_reconcile_from_justificante_verb.py:57 [entrypoints]  (modelo, filing_year, period)
- entrypoints\cli\test_modelo_reconcile_verb.py:47 [entrypoints]  (modelo, filing_year, period)

### _scrub_value

count=7  kind=function  class=name-collision

layers: core

- core\logging.py:124 [core]  (value, key)
- core\logging.py:128 [core]  (value, key)
- core\logging.py:132 [core]  (value, key)
- core\logging.py:136 [core]  (value, key)
- core\logging.py:140 [core]  (value, key)
- core\logging.py:144 [core]  (value, key)
- core\logging.py:147 [core]  (value, key)

### _call_name

count=6  kind=function  class=name-collision

layers: adapters, application, entrypoints

- adapters\persistence\storage\test_ephemeral_key_hygiene.py:215 [adapters]  (node)
- adapters\persistence\storage\test_hardening_convention_guards.py:244 [adapters]  (node)
- adapters\persistence\storage\test_namespace_registry.py:691 [adapters]  (node)
- adapters\persistence\storage\test_sensitive_persistence_policy.py:290 [adapters]  (node)
- application\test_namespace_registry_adoption.py:163 [application]  (node)
- entrypoints\cli\test_audit_remediation.py:235 [entrypoints]  (node)

### TestEmptyState

count=6  kind=class  class=name-collision

layers: adapters, application, domain

- adapters\persistence\storage\test_submission_repository.py:72 [adapters]  []
- application\filing\test_complementaria_repository.py:84 [application]  []
- application\filing\test_history_repository.py:42 [application]  []
- application\filing\test_repository.py:64 [application]  []
- domain\justificante\test_repository.py:56 [domain]  []
- domain\submission\test_repository.py:66 [domain]  []

### TestSaveLoad

count=6  kind=class  class=name-collision

layers: adapters, application, domain

- adapters\persistence\storage\test_submission_repository.py:86 [adapters]  []
- application\filing\test_complementaria_repository.py:94 [application]  []
- application\filing\test_history_repository.py:52 [application]  []
- application\filing\test_repository.py:78 [application]  []
- domain\justificante\test_repository.py:66 [domain]  []
- domain\submission\test_repository.py:80 [domain]  []

### TestShow

count=6  kind=class  class=name-collision

layers: application

- application\evidence\test_evidence.py:97 [application]  []
- application\inventory\test_inventory.py:114 [application]  []
- application\live\test_expedientes.py:106 [application]  []
- application\live\test_notifications.py:111 [application]  []
- application\live\test_verify.py:184 [application]  []
- application\portals\test_service.py:55 [application]  []

### _repositories

count=6  kind=function  class=sig-collision

layers: application

- application\ledger\test_actions.py:99 [application]  (objects, bucket_id)
- application\ledger\test_merge.py:56 [application]  (objects, bucket_id)
- application\ledger\test_split.py:62 [application]  (objects, bucket_id)
- application\modelo\test_bucket_aggregation_flow.py:48 [application]  (objects)
- application\modelo\test_declaration_period_binding.py:41 [application]  ()
- application\modelo\test_source_mesh_calculation.py:36 [application]  (objects)

### _seed_profile

count=6  kind=function  class=sig-collision

layers: application, diagnostics, entrypoints

- application\modelo\test_export.py:109 [application]  (tax_id)
- application\modelo\test_simplificado_ledger_bypass.py:102 [application]  (bucket_id, iva_regime)
- diagnostics\test_profile.py:42 [diagnostics]  (profile_id)
- entrypoints\cli\test_errors_boundary.py:64 [entrypoints]  (runtime_profile)
- entrypoints\cli\test_modelo_casilla_normalisation.py:60 [entrypoints]  (runtime_profile)
- entrypoints\cli\test_workflow_surface.py:97 [entrypoints]  (tax_id, name, activity, iva_regime, extra_values)

### runner

count=6  kind=function  class=name-collision

layers: application, diagnostics, entrypoints

- application\wizard\test_commands.py:30 [application]  ()
- diagnostics\test_profile.py:32 [diagnostics]  ()
- diagnostics\test_secure_objects.py:25 [diagnostics]  ()
- entrypoints\cli\_config\test_apoderado.py:17 [entrypoints]  ()
- entrypoints\cli\_config\test_auth_round5_surface.py:77 [entrypoints]  ()
- entrypoints\cli\test_config_profile_surface_inventory.py:26 [entrypoints]  ()

### _binding

count=6  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:38 [domain]  (binding_id)
- domain\calculations\registry\test_export.py:59 [domain]  (selector)
- domain\calculations\registry\test_invoice_bindings.py:38 [domain]  (binding_id)
- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:49 [domain]  (binding_id)
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:43 [domain]  (binding_id)
- domain\calculations\registry\test_selector_shape.py:36 [domain]  (source, selector, binding_id)

### _casilla_with

count=6  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_country_code_data_type.py:23 [domain]  (data_type)
- domain\calculations\registry\test_iban_data_type.py:22 [domain]  (data_type)
- domain\calculations\registry\test_long_tail_data_types.py:30 [domain]  (data_type, label)
- domain\calculations\registry\test_nif_data_type.py:30 [domain]  (data_type)
- domain\calculations\registry\test_period_code_data_type.py:27 [domain]  (data_type)
- domain\calculations\registry\test_year_data_type.py:26 [domain]  (data_type)

### _create_profile

count=6  kind=function  class=sig-collision

layers: entrypoints

- entrypoints\cli\_config\test_config.py:56 [entrypoints]  (name)
- entrypoints\cli\test_ledger_ux_defect_cluster.py:35 [entrypoints]  ()
- entrypoints\cli\test_modelo_discovery_defects.py:58 [entrypoints]  ()
- entrypoints\cli\test_modelo_period_consistency.py:47 [entrypoints]  ()
- entrypoints\cli\test_modelo_source_mesh_calculate.py:51 [entrypoints]  ()
- entrypoints\cli\test_modelo_work_ux.py:66 [entrypoints]  ()

### _RecordingPage

count=5  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:298 [adapters]  []
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:167 [adapters]  []
- adapters\outbound\aeat\auth\test_clave_movil.py:72 [adapters]  []
- adapters\outbound\aeat\sede\test_censo_live.py:37 [adapters]  []
- adapters\outbound\aeat\verify\test_verify.py:39 [adapters]  []

### _RecordingBrowserSession

count=5  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:314 [adapters]  []
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:184 [adapters]  []
- adapters\outbound\aeat\auth\test_clave_movil.py:255 [adapters]  []
- adapters\outbound\aeat\sede\test_censo_live.py:62 [adapters]  []
- adapters\outbound\aeat\verify\test_verify.py:76 [adapters]  []

### main

count=5  kind=function  class=name-collision

layers: adapters, diagnostics, entrypoints, tests

- adapters\outbound\aeat\browser\health.py:48 [adapters]  ()
- diagnostics\__main__.py:27 [diagnostics]  ()
- entrypoints\cli\__init__.py:424 [entrypoints]  ()
- tests\fixtures\financial\n26\_generate.py:294 [tests]  ()
- tests\fixtures\justificantes\_generate.py:2674 [tests]  ()

### _parse_date

count=5  kind=function  class=sig-collision

layers: adapters, core, domain

- adapters\outbound\aeat\sede\_censo.py:250 [adapters]  (raw, field)
- core\parsing\_dates.py:116 [core]  (raw, fmt, on_error)
- core\parsing\_dates.py:125 [core]  (raw, fmt, on_error)
- core\parsing\_dates.py:133 [core]  (raw, fmt, on_error)
- domain\deadlines\_profiles.py:196 [domain]  (raw)

### _record

count=5  kind=function  class=sig-collision

layers: adapters, application, domain

- adapters\outbound\llm\test_usage_roundtrip.py:28 [adapters]  (when, caller, prompt_id, request_id)
- adapters\persistence\storage\master_key\test_recovery_record.py:23 [adapters]  (**overrides)
- application\user_profile\test_aggregate.py:43 [application]  (profile_id, status)
- domain\calculations\registry\test_export_layout_encoding.py:25 [domain]  (record_id, encoding)
- domain\calculations\registry\test_record_spec.py:87 [domain]  (record_id, encoding)

### test_rejects_unknown_keys

count=5  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\bucket\test_export_header.py:39 [adapters]  ()
- adapters\persistence\storage\bucket\test_manifest.py:66 [adapters]  ()
- adapters\persistence\storage\master_key\test_kdf_params.py:107 [adapters]  ()
- adapters\persistence\storage\master_key\test_recovery_record.py:115 [adapters]  ()
- core\test_bucket_pointer.py:42 [core]  ()

### _isolated_storage

count=5  kind=function  class=name-collision

layers: adapters, application, diagnostics, entrypoints

- adapters\persistence\storage\test_runtime_migrated_repositories.py:146 [adapters]  (tmp_path)
- application\test_state_projection.py:58 [application]  (tmp_path)
- diagnostics\test_secure_objects.py:30 [diagnostics]  (tmp_path)
- entrypoints\cli\test_modelo_202_modality.py:246 [entrypoints]  (tmp_path)
- entrypoints\cli\test_profile_import_idempotency.py:32 [entrypoints]  (tmp_path)

### _modelo_100_snapshot

count=5  kind=function  class=sig-collision

layers: application, domain

- application\aggregation\test_source_mesh_profile_live.py:30 [application]  ()
- application\modelo\test_profile_binding.py:71 [application]  ()
- application\modelo\test_profile_binding_real_path.py:59 [application]  ()
- application\modelo\test_typed_observation_provenance.py:50 [application]  ()
- domain\calculations\registry\test_modelo_100_registry.py:52 [domain]  (filing_year)

### _secure_backend

count=5  kind=function  class=name-collision

layers: application

- application\live\test_filed_capture_calculation_history.py:50 [application]  (tmp_path)
- application\live\test_iva_wallet_capture_backend.py:42 [application]  (tmp_path)
- application\modelo\test_declaration_period_binding.py:36 [application]  (tmp_path)
- application\modelo\test_iva_wallet_engine_integration.py:43 [application]  (tmp_path)
- application\modelo\test_profile_binding.py:54 [application]  (tmp_path)

### _snapshot

count=5  kind=function  class=sig-collision

layers: application, domain

- application\live\test_notifications.py:56 [application]  (rows, captured_at, source_url)
- domain\calculations\registry\test_census_modelo_registry_data.py:26 [domain]  (period)
- domain\calculations\registry\test_minimo_contribuyente_age_increment.py:51 [domain]  (filing_year)
- domain\calculations\registry\test_modelo_200_cuota_integra_lanes.py:61 [domain]  ()
- domain\calculations\registry\test_modelo_200_tipo_gravamen_dispatch.py:60 [domain]  ()

### __getattr__

count=5  kind=function  class=name-collision

layers: application, domain

- application\user_profile\__init__.py:298 [application]  (name)
- domain\portals\__init__.py:51 [domain]  (name)
- domain\profile\__init__.py:53 [domain]  (name)
- domain\profile\_keys.py:155 [domain]  (name)
- domain\transactions\__init__.py:98 [domain]  (name)

### _DECLARED_ERROR_CODES

count=5  kind=annotated_assign  class=sig-collision

layers: core

- core\errors\registry\_adapters.py:5 [core]  :tuple[tuple[str, ErrorCode], ...]=(('aeat.adapters.inbound.
- core\errors\registry\_application.py:5 [core]  :tuple[tuple[str, ErrorCode], ...]=(('aeat.application.opera
- core\errors\registry\_core.py:5 [core]  :tuple[tuple[str, ErrorCode], ...]=(('aeat.core.output_rende
- core\errors\registry\_domain.py:5 [core]  :tuple[tuple[str, ErrorCode], ...]=(('aeat.domain.buckets._e
- core\errors\registry\_entrypoints.py:5 [core]  :tuple[tuple[str, ErrorCode], ...]=(('aeat.entrypoints.cli._

### _Holder

count=5  kind=class  class=name-collision

layers: core, domain

- core\identity\test_profile.py:15 [core]  ['BaseModel']
- core\identity\test_snapshot.py:15 [core]  ['BaseModel']
- domain\attachments\test_ids.py:15 [domain]  ['BaseModel']
- domain\invoices\test_ids.py:15 [domain]  ['BaseModel']
- domain\modelos\test_verification_report_id.py:15 [domain]  ['BaseModel']

### TestCasillaDefinitionDataType

count=5  kind=class  class=name-collision

layers: domain

- domain\calculations\registry\test_country_code_data_type.py:74 [domain]  []
- domain\calculations\registry\test_iban_data_type.py:94 [domain]  []
- domain\calculations\registry\test_nif_data_type.py:124 [domain]  []
- domain\calculations\registry\test_period_code_data_type.py:108 [domain]  []
- domain\calculations\registry\test_year_data_type.py:85 [domain]  []

### m100_2024_snapshot

count=5  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_100_ahorro_base_chain.py:66 [domain]  (registry_authority)
- domain\calculations\registry\test_modelo_100_cripto_1812_propagation.py:42 [domain]  (registry_authority)
- domain\calculations\registry\test_modelo_100_retenciones_binding_wiring.py:66 [domain]  (registry_authority)
- domain\calculations\registry\test_modelo_100_settlement_chain.py:140 [domain]  (registry_authority)
- domain\calculations\registry\test_modelo_100_tarifa_real.py:94 [domain]  (registry_authority)

### _discover_test_modules

count=5  kind=function  class=name-collision

layers: test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py, tests

- test_mock_inventory.py:51 [test_mock_inventory.py]  ()
- test_monkeypatch_inventory.py:83 [test_monkeypatch_inventory.py]  ()
- test_no_skip_xfail.py:50 [test_no_skip_xfail.py]  ()
- test_no_tautology.py:42 [test_no_tautology.py]  ()
- tests\test_marker_integrity.py:44 [tests]  ()

### test_discovery_found_modules

count=5  kind=function  class=name-collision

layers: test_mock_inventory.py, test_monkeypatch_inventory.py, test_no_skip_xfail.py, test_no_tautology.py, tests

- test_mock_inventory.py:128 [test_mock_inventory.py]  ()
- test_monkeypatch_inventory.py:197 [test_monkeypatch_inventory.py]  ()
- test_no_skip_xfail.py:135 [test_no_skip_xfail.py]  ()
- test_no_tautology.py:171 [test_no_tautology.py]  ()
- tests\test_marker_integrity.py:237 [tests]  ()

### _spanish_amount

count=4  kind=function  class=name-collision

layers: adapters, application

- adapters\inbound\borrador\test_modelo_100_summary.py:93 [adapters]  (value)
- adapters\inbound\declaracion\test_parser_boundary.py:1904 [adapters]  (value)
- adapters\outbound\aeat\sede\test_declarations.py:397 [adapters]  (value)
- application\modelo\test_iva_wallet_engine_integration.py:87 [application]  (value)

### _parse_decimal

count=4  kind=function  class=sig-collision

layers: adapters, domain, entrypoints

- adapters\inbound\justificante\_extract.py:211 [adapters]  (raw, field)
- domain\calculations\registry\_export_parse.py:402 [domain]  (field, raw)
- domain\deadlines\_profiles.py:203 [domain]  (raw)
- entrypoints\cli\_ledger.py:101 [entrypoints]  (raw, label)

### _

count=4  kind=module_assign  class=sig-collision

layers: adapters, entrypoints

- adapters\inbound\sanitizer\_dynamic.py:256 [adapters]  pikepdf
- adapters\inbound\sanitizer\_streams.py:379 [adapters]  pikepdf
- adapters\outbound\storage\_google_drive.py:700 [adapters]  json
- entrypoints\cli\_config\_google.py:1284 [entrypoints]  (load_token, REQUIRED_SCOPES)

### _isolated_secure_session_backend

count=4  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:65 [adapters]  (tmp_path)
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:69 [adapters]  (tmp_path)
- adapters\outbound\aeat\auth\test_clave_movil.py:64 [adapters]  (tmp_path)
- adapters\outbound\aeat\auth\test_clave_movil_translated_message.py:50 [adapters]  (tmp_path)

### _settings_for

count=4  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:121 [adapters]  (bundle_path)
- adapters\outbound\aeat\auth\test_clave_movil.py:308 [adapters]  (tmp_path, **env)
- adapters\outbound\aeat\auth\test_clave_movil_translated_message.py:55 [adapters]  (tmp_path, **env)
- adapters\persistence\storage\sql\test_engine.py:22 [adapters]  (url)

### _filed_observation

count=4  kind=function  class=sig-collision

layers: adapters, application, domain, entrypoints

- adapters\outbound\aeat\sede\test_declarations.py:402 [adapters]  (modelo, ejercicio, period, casilla_values, source_artefact_kind, extraction_coverage)
- application\calculations\test_iva_compensation_history.py:205 [application]  (modelo)
- domain\calculations\registry\test_filed_state.py:60 [domain]  (calculation)
- entrypoints\cli\test_registry_cli.py:875 [entrypoints]  (modelo, ejercicio, period, casilla_values)

### test_planned_operations_rejects_empty_expected

count=4  kind=function  class=name-collision

layers: adapters, domain

- adapters\outbound\aeat\sede\test_groi_check.py:77 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:64 [adapters]  ()
- domain\calculations\registry\test_aeat_nif_iva_oracle.py:118 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:106 [domain]  ()

### engine

count=4  kind=function  class=sig-collision

layers: adapters, domain

- adapters\persistence\storage\crypto\test_encrypted_columns.py:56 [adapters]  ()
- domain\fincas\test_aggregates.py:37 [domain]  (tmp_path)
- domain\fincas\test_repository.py:38 [domain]  (tmp_path)
- domain\fincas\test_roundtrip_anti_tautology.py:38 [domain]  (tmp_path)

### _session

count=4  kind=function  class=sig-collision

layers: adapters, entrypoints

- adapters\persistence\storage\test_runtime.py:41 [adapters]  (bucket_id, opened_at, idle_minutes, unsecured_backend)
- adapters\persistence\storage\test_runtime_migrated_repositories.py:166 [adapters]  (bucket_id)
- entrypoints\cli\_config\test_auth_round5_surface.py:44 [entrypoints]  ()
- entrypoints\cli\test_registry_cli.py:53 [entrypoints]  ()

### _raw

count=4  kind=function  class=sig-collision

layers: application, domain

- application\aggregation\test_intracom_export.py:50 [application]  (provider_id, amount, direction)
- application\review\test_adapters.py:98 [application]  (source_row_index, description)
- application\review\test_models.py:49 [application]  ()
- domain\transactions\test_repository_roundtrip.py:40 [domain]  (provider_id, amount, description)

### _modelo_349_revision

count=4  kind=function  class=name-collision

layers: application, domain

- application\aggregation\test_per_modelo_registry_provider.py:22 [application]  ()
- application\storage\calc_sheets\test_collect_row_sets.py:23 [application]  ()
- domain\calculations\registry\test_counterpart_bindings.py:33 [domain]  ()
- domain\calculations\registry\test_invoice_bindings.py:33 [domain]  ()

### _settings

count=4  kind=function  class=sig-collision

layers: application, domain

- application\auth\test_acquisition_lock.py:36 [application]  (tmp_path)
- application\auth\test_ensure_session.py:124 [application]  (tmp_path)
- application\auth\test_sessions_storage_state_paths.py:55 [application]  (token_dir)
- domain\manuals\test_verify.py:30 [domain]  (root, review_required)

### _state

count=4  kind=function  class=sig-collision

layers: application, entrypoints

- application\calculations\test_iva_compensation_history.py:36 [application]  (filing_year, period, generated, applied, available)
- application\workflow\test_transaction_catalogue_resolution.py:37 [application]  (profile, bucket_id)
- entrypoints\cli\_common.py:117 [entrypoints]  ()
- entrypoints\cli\test_iva_wallet_inspector.py:34 [entrypoints]  (filing_year, period, generated, applied)

### _finding

count=4  kind=function  class=sig-collision

layers: application

- application\filing\test_calculate.py:71 [application]  (severity, code)
- application\review\test_models.py:112 [application]  ()
- application\wizard\test_situacion_familiar.py:118 [application]  (answers, name)
- application\wizard\test_verifier_checks.py:51 [application]  (answers, name)

### secure_engine

count=4  kind=function  class=name-collision

layers: application

- application\inventory\test_inventory.py:29 [application]  (tmp_path)
- application\live\test_expedientes.py:25 [application]  (tmp_path)
- application\live\test_notifications.py:28 [application]  (tmp_path)
- application\live\test_verify.py:24 [application]  (tmp_path)

### TestSecureStorage

count=4  kind=class  class=name-collision

layers: application

- application\inventory\test_inventory.py:345 [application]  []
- application\live\test_expedientes.py:166 [application]  []
- application\live\test_notifications.py:200 [application]  []
- application\live\test_verify.py:267 [application]  []

### _load

count=4  kind=function  class=sig-collision

layers: application, entrypoints

- application\ledger\_business_operation_invoice.py:288 [application]  (settings, kind, bucket_id)
- application\ledger\_evidence.py:125 [application]  (settings, bucket_id)
- application\user_profile\test_profile_repository.py:103 [application]  (repository, profile_id)
- entrypoints\cli\test_session_lifecycle_roundtrip.py:64 [entrypoints]  (repository)

### _active_bucket_id

count=4  kind=function  class=name-collision

layers: application, entrypoints

- application\review\_operator.py:203 [application]  ()
- entrypoints\cli\_app_live.py:689 [entrypoints]  ()
- entrypoints\cli\_modelo.py:4246 [entrypoints]  ()
- entrypoints\cli\test_cli_surface.py:54 [entrypoints]  ()

### _file_fingerprint

count=4  kind=function  class=name-collision

layers: application, domain

- application\topics\__init__.py:114 [application]  (path)
- domain\categories\_registry.py:96 [domain]  (path)
- domain\iva\_catalogue.py:80 [domain]  (path)
- domain\normatives\_loader.py:59 [domain]  (path)

### _fact_value

count=4  kind=function  class=name-collision

layers: application

- application\user_profile\test_corporate_tax_facts_roundtrip.py:142 [application]  (record, path)
- application\user_profile\test_irpf_special_regime_persistence_roundtrip.py:79 [application]  (record, path)
- application\user_profile\test_marriage_date_persistence_roundtrip.py:70 [application]  (record, path)
- application\user_profile\test_taxpayer_axes_persistence_roundtrip.py:108 [application]  (record, path)

### _EmptyAnswersBase

count=4  kind=class  class=name-collision

layers: application

- application\wizard\test_commands_helpers.py:41 [application]  ['BaseModel']
- application\wizard\test_compile.py:35 [application]  ['BaseModel']
- application\wizard\test_models.py:32 [application]  ['BaseModel']
- application\wizard\test_translations_helpers.py:31 [application]  ['BaseModel']

### PROJECT_ROOT

count=4  kind=constant  class=sig-collision

layers: core, entrypoints, tests

- core\config.py:60 [core]  Path(__file__).resolve().parent.parent.parent.parent
- core\paths.py:23 [core]  Path(__file__).resolve().parent.parent.parent.parent
- entrypoints\cli\test_retired_cli_literals.py:9 [entrypoints]  Path(__file__).resolve().parents[4]
- tests\test_release_config.py:33 [tests]  Path(__file__).resolve().parents[3]

### register

count=4  kind=function  class=sig-collision

layers: core, diagnostics, entrypoints

- core\errors\_registry.py:139 [core]  (code)
- diagnostics\profile.py:85 [diagnostics]  (app)
- diagnostics\secure_objects.py:22 [diagnostics]  (app)
- entrypoints\cli\_config\_profile_census.py:87 [entrypoints]  (profile_app)

### test_accepts_canonical_sha256_hex_digest

count=4  kind=function  class=name-collision

layers: core, domain

- core\identity\test_snapshot.py:19 [core]  ()
- domain\attachments\test_ids.py:19 [domain]  ()
- domain\invoices\test_ids.py:19 [domain]  ()
- domain\modelos\test_verification_report_id.py:19 [domain]  ()

### test_rejects_uppercase_hex

count=4  kind=function  class=name-collision

layers: core, domain

- core\identity\test_snapshot.py:24 [core]  ()
- domain\attachments\test_ids.py:24 [domain]  ()
- domain\invoices\test_ids.py:24 [domain]  ()
- domain\modelos\test_verification_report_id.py:24 [domain]  ()

### test_rejects_non_hex_characters

count=4  kind=function  class=name-collision

layers: core, domain

- core\identity\test_snapshot.py:40 [core]  ()
- domain\attachments\test_ids.py:36 [domain]  ()
- domain\invoices\test_ids.py:37 [domain]  ()
- domain\modelos\test_verification_report_id.py:34 [domain]  ()

### _with_selector

count=4  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:53 [domain]  (binding, **updates)
- domain\calculations\registry\test_invoice_bindings.py:53 [domain]  (binding, **updates)
- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:53 [domain]  (binding, **updates)
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:47 [domain]  (binding, **updates)

### _with_aggregation

count=4  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:57 [domain]  (binding, op)
- domain\calculations\registry\test_invoice_bindings.py:57 [domain]  (binding, op)
- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:57 [domain]  (binding, op)
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:51 [domain]  (binding, op)

### _load_modelo_200

count=4  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_200_cuota_integra_lanes.py:54 [domain]  ()
- domain\calculations\registry\test_modelo_200_registry.py:23 [domain]  ()
- domain\calculations\registry\test_modelo_200_temporal_coverage.py:67 [domain]  ()
- domain\calculations\registry\test_modelo_200_tipo_gravamen_dispatch.py:53 [domain]  ()

### _isolated_state

count=4  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_command_suggestions.py:23 [entrypoints]  (tmp_path)
- entrypoints\cli\test_output_language_parity.py:39 [entrypoints]  (tmp_path)
- entrypoints\cli\test_root_grammar_invariants.py:23 [entrypoints]  (tmp_path)
- entrypoints\cli\test_root_help_shape.py:26 [entrypoints]  (tmp_path)

### _create_work_unit

count=4  kind=function  class=sig-collision

layers: entrypoints

- entrypoints\cli\test_modelo_calculation_through_real_cli.py:161 [entrypoints]  (modelo, year, period, revision)
- entrypoints\cli\test_modelo_compare.py:135 [entrypoints]  (modelo, year, period, revision)
- entrypoints\cli\test_modelo_projection.py:147 [entrypoints]  (modelo, year, period, revision)
- entrypoints\cli\test_modelo_work_ux.py:79 [entrypoints]  ()

### generate

count=4  kind=function  class=name-collision

layers: tests

- tests\fixtures\pdf_corpus\l3_synthetic\_generators\_generic_quarterly_generator.py:69 [tests]  (params)
- tests\fixtures\pdf_corpus\l3_synthetic\_generators\modelo_100_generator.py:138 [tests]  (params)
- tests\fixtures\pdf_corpus\l3_synthetic\_generators\modelo_130_generator.py:95 [tests]  (params)
- tests\fixtures\pdf_corpus\l3_synthetic\_generators\modelo_303_generator.py:111 [tests]  (params)

### LOGGER

count=3  kind=constant  class=name-collision

layers: adapters, application

- adapters\inbound\financial\providers\_base.py:59 [adapters]  get_logger(__name__)
- application\aggregation\_service.py:37 [application]  get_logger(__name__)
- application\operator_surface\_contract.py:27 [application]  get_logger(__name__)

### _RecordingContext

count=3  kind=class  class=sig-collision

layers: adapters

- adapters\outbound\aeat\auth\test_clave_movil.py:214 [adapters]  []
- adapters\outbound\aeat\sede\test_censo_live.py:50 [adapters]  []
- adapters\outbound\aeat\verify\test_verify.py:62 [adapters]  []

### _registry

count=3  kind=function  class=name-collision

layers: adapters, domain

- adapters\outbound\aeat\export\_formats\test_record_specs.py:142 [adapters]  ()
- domain\calculations\registry\test_minimo_contribuyente_age_increment.py:42 [domain]  ()
- domain\calculations\registry\test_modelo_chain_cohesion.py:53 [domain]  ()

### _DEFAULT_VIEWPORT

count=3  kind=annotated_assign  class=sig-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:79 [adapters]  :ViewportSize={'width': _TIMEOUT_DEFAULTS.aeat_browser_viewp
- adapters\outbound\aeat\sede\_nif_iva_check.py:130 [adapters]  :ViewportSize={'width': _TIMEOUT_DEFAULTS.aeat_browser_viewp
- adapters\outbound\aeat\sede\_renta_web_open.py:35 [adapters]  :ViewportSize={'width': _VIEWPORT_DEFAULTS.aeat_browser_view

### _playwright_stage

count=3  kind=module_assign  class=sig-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:120 [adapters]  build_playwright_stage_runner(surface_label='GROI', log_pref
- adapters\outbound\aeat\sede\_nif_iva_check.py:95 [adapters]  build_playwright_stage_runner(surface_label='NIF-IVA', log_p
- adapters\outbound\aeat\sede\_renta_web_open.py:52 [adapters]  build_playwright_stage_runner(surface_label='Renta WEB Open'

### _IsolatedSettings

count=3  kind=class  class=name-collision

layers: adapters, domain

- adapters\outbound\llm\test_client.py:32 [adapters]  ['Settings']
- domain\manuals\test_loader.py:28 [domain]  ['Settings']
- domain\manuals\test_verify.py:19 [domain]  ['Settings']

### fixed_master_key

count=3  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\blob_store\test_blob_store.py:27 [adapters]  ()
- adapters\persistence\storage\crypto\test_encrypted_columns.py:44 [adapters]  ()
- adapters\persistence\storage\secret_store\test_secret_store.py:38 [adapters]  ()

### test_rejects_empty_bucket_id

count=3  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\bucket\test_export_header.py:80 [adapters]  ()
- adapters\persistence\storage\bucket\test_manifest.py:96 [adapters]  ()
- core\test_bucket_pointer.py:31 [core]  ()

### test_rejects_naive_created_at

count=3  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\bucket\test_export_header.py:90 [adapters]  ()
- adapters\persistence\storage\bucket\test_manifest.py:101 [adapters]  ()
- adapters\persistence\storage\master_key\test_recovery_record.py:63 [adapters]  ()

### test_rejects_non_utc_offset_created_at

count=3  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\bucket\test_export_header.py:95 [adapters]  ()
- adapters\persistence\storage\bucket\test_manifest.py:106 [adapters]  ()
- adapters\persistence\storage\master_key\test_recovery_record.py:68 [adapters]  ()

### _patch_master_key

count=3  kind=function  class=sig-collision

layers: adapters

- adapters\persistence\storage\crypto\test_encrypted_columns.py:49 [adapters]  (fixed_master_key)
- adapters\persistence\storage\envelope\test_envelope_ciphertext.py:59 [adapters]  (provider)
- adapters\persistence\storage\test_rotation.py:70 [adapters]  (alice)

### _DummyRepository

count=3  kind=class  class=name-collision

layers: adapters, core

- adapters\persistence\storage\envelope\test_secure_bound_repository.py:46 [adapters]  ['SecureBoundRepository[_DummyPayload]']
- adapters\persistence\storage\envelope\test_secure_bound_repository_contract.py:57 [adapters]  ['SecureBoundRepository[_DummyPayload]']
- core\resources\test_registry.py:60 [core]  ['ResourceCacheRepository[str, _DummyKey

### _engine

count=3  kind=function  class=sig-collision

layers: adapters, domain

- adapters\persistence\storage\sql\test_repository.py:34 [adapters]  (tmp_path)
- adapters\persistence\storage\sql\test_session.py:21 [adapters]  (tmp_path)
- domain\deadlines\test_engine.py:38 [domain]  ()

### _is_test_surface

count=3  kind=function  class=sig-collision

layers: adapters, application

- adapters\persistence\storage\test_hardening_convention_guards.py:142 [adapters]  (relative)
- adapters\persistence\storage\test_namespace_registry.py:544 [adapters]  (path)
- application\test_namespace_registry_adoption.py:59 [application]  (path)

### _hex

count=3  kind=function  class=sig-collision

layers: adapters, domain

- adapters\persistence\storage\test_runtime_migrated_repositories.py:238 [adapters]  (label)
- domain\modelos\test_calculation_repository_roundtrip.py:52 [domain]  (seed)
- domain\modelos\test_filing_record_repository_roundtrip.py:43 [domain]  (seed)

### TestListAndIter

count=3  kind=class  class=name-collision

layers: adapters, application, domain

- adapters\persistence\storage\test_submission_repository.py:104 [adapters]  []
- application\filing\test_repository.py:96 [application]  []
- domain\submission\test_repository.py:98 [domain]  []

### _CANONICAL_SOURCE_KINDS

count=3  kind=annotated_assign  class=sig-collision

layers: application

- application\aggregation\_counterpart.py:27 [application]  :frozenset[AggregationSourceKind]=frozenset({AggregationSour
- application\aggregation\_foreign_assets.py:22 [application]  :frozenset[AggregationSourceKind]=frozenset({AggregationSour
- application\aggregation\_retenciones.py:49 [application]  :tuple[AggregationSourceKind, ...]=(AggregationSourceKind.LE

### _obs

count=3  kind=function  class=sig-collision

layers: application

- application\aggregation\test_counterpart.py:24 [application]  (nif, op_kind, base, invoice_total, name, country, source_kind, source_id, period, accrued)
- application\aggregation\test_foreign_assets.py:22 [application]  (asset_class, valuation, asset_external_id, country, source_kind, source_id, held, acquisition)
- application\aggregation\test_retenciones.py:24 [application]  (nif, scheme, base, retencion, name, source_kind, source_id, accrued)

### TestObservationContract

count=3  kind=class  class=name-collision

layers: application

- application\aggregation\test_counterpart.py:51 [application]  []
- application\aggregation\test_foreign_assets.py:45 [application]  []
- application\aggregation\test_retenciones.py:47 [application]  []

### _wallet

count=3  kind=function  class=sig-collision

layers: application

- application\aggregation\test_source_mesh_profile_live.py:47 [application]  (amount)
- application\calculations\test_iva_compensation_history.py:62 [application]  (amount, generation_year)
- application\calculations\test_iva_wallet_reconciliation.py:41 [application]  (amount, captured_at)

### _active_profile

count=3  kind=function  class=sig-collision

layers: application

- application\auth\test_acquisition_lock.py:29 [application]  ()
- application\auth\test_ensure_session.py:102 [application]  (tmp_path)
- application\auth\test_sessions_storage_state_paths.py:37 [application]  (tmp_path)

### isolated_settings

count=3  kind=function  class=sig-collision

layers: application

- application\auth\test_apoderado.py:30 [application]  (isolated_profile)
- application\ledger\test_business_operation_invoice.py:30 [application]  (tmp_path)
- application\ledger\test_evidence.py:25 [application]  (tmp_path)

### _draft

count=3  kind=function  class=sig-collision

layers: application

- application\filing\test_complementaria.py:67 [application]  (modelo, period, casillas)
- application\filing\test_filing.py:51 [application]  (schema_provider)
- application\review\test_adapters.py:332 [application]  (draft_id, modelo, period, status, findings)

### TestListIter

count=3  kind=class  class=name-collision

layers: application, domain

- application\filing\test_complementaria_repository.py:103 [application]  []
- application\filing\test_history_repository.py:68 [application]  []
- domain\justificante\test_repository.py:82 [domain]  []

### _save

count=3  kind=function  class=sig-collision

layers: application, entrypoints

- application\ledger\_business_operation_invoice.py:302 [application]  (settings, kind, bucket_id, records)
- application\ledger\_evidence.py:138 [application]  (settings, bucket_id, records)
- entrypoints\cli\test_session_lifecycle_roundtrip.py:51 [entrypoints]  (repository)

### _hash_file

count=3  kind=function  class=sig-collision

layers: application, core, domain

- application\ledger\_evidence.py:108 [application]  (source_path)
- core\corpus_manifest\__init__.py:155 [core]  (path)
- domain\calculations\registry\_workbook_parity.py:1000 [domain]  (path)

### _declaration

count=3  kind=function  class=sig-collision

layers: application, entrypoints

- application\live\test_expedientes.py:34 [application]  (modelo, ejercicio, period, expediente_id, estado, presented_at)
- application\live\test_filed_capture_calculation_history.py:412 [application]  (period, expediente_id, estado, presented_at)
- entrypoints\cli\test_registry_cli.py:914 [entrypoints]  (expediente_id, period, modelo)

### TestNoWriteSurface

count=3  kind=class  class=name-collision

layers: application

- application\live\test_expedientes.py:189 [application]  []
- application\live\test_notifications.py:223 [application]  []
- application\live\test_verify.py:293 [application]  []

### _workflow_profile

count=3  kind=function  class=name-collision

layers: application

- application\modelo\test_file_flow.py:199 [application]  ()
- application\modelo\test_verificado_completo_regression.py:68 [application]  ()
- application\modelo\test_verification_substance.py:361 [application]  ()

### MODELO_130_FIXTURE

count=3  kind=constant  class=name-collision

layers: application, entrypoints

- application\modelo\test_reconcile.py:38 [application]  FIXTURES_DIR / 'justificantes' / 'modelo_130_2026Q1.pdf'
- entrypoints\cli\test_modelo_reconcile_from_justificante_verb.py:33 [entrypoints]  FIXTURES_DIR / 'justificantes' / 'modelo_130_2026Q1.pdf'
- entrypoints\cli\test_modelo_reconcile_verb.py:25 [entrypoints]  FIXTURES_DIR / 'justificantes' / 'modelo_130_2026Q1.pdf'

### _attribution_entity

count=3  kind=function  class=name-collision

layers: application

- application\overview\test_applicability.py:126 [application]  ()
- application\overview\test_calendar.py:744 [application]  ()
- application\overview\test_calendar_applicability_consistency.py:79 [application]  ()

### _seed_active_profile

count=3  kind=function  class=sig-collision

layers: application, entrypoints

- application\review\test_adapters.py:76 [application]  (bucket_id)
- application\test_config_parity.py:42 [application]  (tax_id, activity)
- entrypoints\cli\test_profile_census_verbs.py:50 [entrypoints]  ()

### _summary

count=3  kind=function  class=name-collision

layers: application

- application\review\test_adapters.py:87 [application]  (text)
- application\review\test_aggregator.py:52 [application]  (text)
- application\review\test_models.py:45 [application]  (text)

### _backend

count=3  kind=function  class=name-collision

layers: application

- application\setup\test_atomic_create_rollback.py:64 [application]  (tmp_path)
- application\user_profile\test_profile_repository.py:128 [application]  (tmp_path)
- application\wizard\test_create_pointer_atomicity.py:40 [application]  (tmp_path)

### _isolate

count=3  kind=function  class=sig-collision

layers: application, entrypoints

- application\test_config_parity.py:26 [application]  (tmp_path)
- entrypoints\cli\test_cli_surface.py:37 [entrypoints]  (monkeypatch, tmp_path)
- entrypoints\cli\test_profile_output_language.py:34 [entrypoints]  (tmp_path)

### _secure_objects_for_bucket

count=3  kind=function  class=name-collision

layers: application, domain

- application\user_profile\_repository.py:52 [application]  (bucket_id)
- domain\invoices\_repository.py:28 [domain]  (bucket_id)
- domain\transactions\_repository.py:31 [domain]  (bucket_id)

### _populated_record

count=3  kind=function  class=name-collision

layers: application

- application\user_profile\test_corporate_tax_facts_roundtrip.py:72 [application]  ()
- application\user_profile\test_repository_anti_tautology.py:58 [application]  ()
- application\user_profile\test_repository_roundtrip.py:70 [application]  ()

### _required_facts

count=3  kind=function  class=name-collision

layers: application

- application\user_profile\test_irpf_special_regime_persistence_roundtrip.py:66 [application]  (schema)
- application\user_profile\test_marriage_date_persistence_roundtrip.py:56 [application]  (schema)
- application\user_profile\test_taxpayer_axes_persistence_roundtrip.py:67 [application]  (schema)

### _emit

count=3  kind=function  class=sig-collision

layers: application, core, entrypoints

- application\wizard\_runner.py:84 [application]  (prompter, text)
- core\observability\test_sink_redaction.py:45 [core]  (sink, event)
- entrypoints\cli\_common.py:47 [entrypoints]  (ctx, payload, lines)

### _SUPPORTED_LOCALES

count=3  kind=annotated_assign  class=name-collision

layers: application, test_locale_coverage_inventory.py, test_w05_p23_locale_coverage.py

- application\wizard\test_flow_description_keys.py:21 [application]  :tuple[str, ...]=('en', 'es', 'ca', 'hu')
- test_locale_coverage_inventory.py:71 [test_locale_coverage_inventory.py]  :tuple[str, ...]=('en', 'es', 'ca', 'hu')
- test_w05_p23_locale_coverage.py:60 [test_w05_p23_locale_coverage.py]  :tuple[str, ...]=('en', 'es', 'ca', 'hu')

### _obligation

count=3  kind=function  class=sig-collision

layers: application, entrypoints

- application\workflow\test_engine.py:263 [application]  (modelo, period, closes_on)
- application\workflow\test_resume.py:38 [application]  (modelo, period)
- entrypoints\cli\test_work_resume.py:49 [entrypoints]  ()

### test_rejects_wrong_length

count=3  kind=function  class=name-collision

layers: domain

- domain\attachments\test_ids.py:29 [domain]  ()
- domain\invoices\test_ids.py:30 [domain]  ()
- domain\modelos\test_verification_report_id.py:29 [domain]  ()

### _casilla

count=3  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_cross_revision_drift.py:38 [domain]  (cid, label, section, data_type, semantic_role, legal_refs, continuidad_id)
- domain\calculations\registry\test_required_role_hardflip.py:28 [domain]  (cid, label, data_type, semantic_role)
- domain\calculations\registry\test_semantic_role.py:37 [domain]  (cid, data_type, semantic_role, semantic_role_cardinality, semantic_role_cardinality_reason, aliases, constraints)

### _evaluate

count=3  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_if_then_else_short_circuit.py:28 [domain]  (expression, values)
- domain\calculations\registry\test_lookup_bracket_by_ccaa.py:107 [domain]  (expression, parameters, enum_bindings)
- domain\calculations\registry\test_lookup_bracket_by_entity_type.py:111 [domain]  (expression, parameters, enum_bindings)

### _value_for

count=3  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_modelo_180_registry.py:172 [domain]  (data_type, period_index)
- domain\calculations\registry\test_modelo_190_registry.py:155 [domain]  (data_type, input_kind, period_index)
- domain\calculations\registry\test_modelo_193_registry.py:139 [domain]  (data_type, period_index)

### _citation

count=3  kind=function  class=name-collision

layers: domain

- domain\categories\test_profile.py:30 [domain]  ()
- domain\categories\test_proportionality.py:31 [domain]  ()
- domain\renta\test_ledger_expenses.py:69 [domain]  ()

### _finca

count=3  kind=function  class=sig-collision

layers: domain

- domain\fincas\test_amortization_ledger.py:28 [domain]  (coste_construccion, valor_catastral_construccion)
- domain\fincas\test_imputacion_regime.py:21 [domain]  (use_type)
- domain\fincas\test_tier_resolver.py:29 [domain]  (is_stressed_area)

### FILING_YEAR

count=3  kind=constant  class=name-collision

layers: domain

- domain\profile\test_custodia_compartida.py:30 [domain]  2024
- domain\profile\test_descendant_info.py:35 [domain]  2024
- domain\profile\test_marriage_facts.py:30 [domain]  2024

### _combined_output

count=3  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_audit_remediation.py:44 [entrypoints]  (result)
- entrypoints\cli\test_config_custody_profile_lifecycle.py:84 [entrypoints]  (result)
- entrypoints\cli\test_root_fallback_write_guard.py:168 [entrypoints]  (result)

### _create_303_work_unit

count=3  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_modelo_casilla_normalisation.py:86 [entrypoints]  ()
- entrypoints\cli\test_modelo_discovery_defects.py:71 [entrypoints]  ()
- entrypoints\cli\test_modelo_source_mesh_calculate.py:71 [entrypoints]  ()

### _is_excluded

count=3  kind=function  class=name-collision

layers: test_clock_enrollment_inventory.py, test_decimal_enrollment_inventory.py, test_parsing_enrollment_inventory.py

- test_clock_enrollment_inventory.py:166 [test_clock_enrollment_inventory.py]  (path)
- test_decimal_enrollment_inventory.py:72 [test_decimal_enrollment_inventory.py]  (path)
- test_parsing_enrollment_inventory.py:40 [test_parsing_enrollment_inventory.py]  (path)

### extract_pages_text

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\borrador\_parsers\_pdfplumber_backend.py:17 [adapters]  (pdf_path)
- adapters\inbound\declaracion\_parsers\_pdfplumber_backend.py:42 [adapters]  (pdf_path)

### _load_registry_snapshot

count=2  kind=function  class=sig-collision

layers: adapters, application

- adapters\inbound\declaracion\_parser.py:313 [adapters]  (template, period, registry_root, source_root)
- application\filing\__init__.py:251 [application]  (modelo, period)

### extract_pages_text_from_bytes

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\inbound\declaracion\_parsers\_pdfplumber_backend.py:106 [adapters]  (pdf_bytes, source_label)
- adapters\inbound\pdf\_pdfplumber.py:84 [adapters]  (pdf_bytes, error_class, pdf_label, source_label)

### _production_modules

count=2  kind=function  class=name-collision

layers: adapters, domain

- adapters\inbound\declaracion\test_exception_hygiene.py:16 [adapters]  ()
- domain\calculations\registry\test_exception_hygiene.py:16 [domain]  ()

### _location

count=2  kind=function  class=sig-collision

layers: adapters, core

- adapters\inbound\declaracion\test_exception_hygiene.py:95 [adapters]  (path, node)
- core\i18n\test_translatable_contract.py:17 [core]  (path, node, message)

### _is_broad_exception_type

count=2  kind=function  class=name-collision

layers: adapters, domain

- adapters\inbound\declaracion\test_exception_hygiene.py:111 [adapters]  (node)
- domain\calculations\registry\test_exception_hygiene.py:99 [domain]  (node)

### _is_logging_call

count=2  kind=function  class=name-collision

layers: adapters, domain

- adapters\inbound\declaracion\test_exception_hygiene.py:119 [adapters]  (node)
- domain\calculations\registry\test_exception_hygiene.py:107 [domain]  (node)

### _modelo_snapshot

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\declaracion\test_parser_boundary.py:1874 [adapters]  (modelo_id, filing_year, period)
- adapters\outbound\aeat\sede\test_declarations.py:138 [adapters]  (modelo_id, filing_year, period)

### _row_to_mapping

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\financial\providers\_csv.py:394 [adapters]  (headers, row)
- adapters\inbound\financial\providers\_xlsx.py:381 [adapters]  (headers, row)

### _load_expected

count=2  kind=function  class=sig-collision

layers: adapters, domain

- adapters\inbound\financial\providers\test_pdf_n26.py:43 [adapters]  (name)
- domain\calculations\registry\test_renta_web_open_replay_parity.py:76 [domain]  (payload_path)

### _parse_datetime

count=2  kind=function  class=sig-collision

layers: adapters, domain

- adapters\inbound\justificante\_extract.py:245 [adapters]  (raw)
- domain\transactions\_models.py:145 [domain]  (value)

### FIXTURES_DIR

count=2  kind=constant  class=sig-collision

layers: adapters, tests

- adapters\inbound\justificante\test_parser.py:31 [adapters]  _FIXTURES_ROOT / 'justificantes'
- tests\__init__.py:18 [tests]  :Path=Path(__file__).resolve().parent / 'fixtures'

### _committed_fixture_pairs

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\sanitizer\test_adversarial_absence.py:46 [adapters]  ()
- adapters\inbound\sanitizer\test_round_trip.py:41 [adapters]  ()

### test_fixture_root_is_skip_clean_when_empty

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\sanitizer\test_adversarial_absence.py:142 [adapters]  ()
- adapters\inbound\sanitizer\test_round_trip.py:120 [adapters]  ()

### _new_one_page_pdf

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\sanitizer\test_determinism.py:23 [adapters]  ()
- adapters\inbound\sanitizer\test_dynamic.py:31 [adapters]  ()

### _round_trip

count=2  kind=function  class=name-collision

layers: adapters

- adapters\inbound\sanitizer\test_dynamic.py:38 [adapters]  (pdf)
- adapters\inbound\sanitizer\test_metadata.py:53 [adapters]  (pdf)

### select_provider

count=2  kind=function  class=name-collision

layers: adapters, application

- adapters\outbound\aeat\auth\__init__.py:140 [adapters]  (kind, settings, browser_session_factory)
- application\auth\__init__.py:107 [application]  (kind, settings, browser_session_factory)

### _repository

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\_session_store.py:92 [adapters]  ()
- adapters\outbound\google\_session_store.py:169 [adapters]  ()

### SECRET_PASSPHRASE

count=2  kind=constant  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:60 [adapters]  'correct-horse-battery-staple'
- adapters\outbound\aeat\auth\test_certificate.py:41 [adapters]  'correct-horse-battery-staple'

### _default_pkcs12_bytes

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:104 [adapters]  ()
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:75 [adapters]  ()

### _build_bundle

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:117 [adapters]  (tmp_path, subject_attrs, not_valid_after)
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:103 [adapters]  (tmp_path)

### _load_cert

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:137 [adapters]  (tmp_path, subject_attrs, not_valid_after)
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:109 [adapters]  (tmp_path)

### _RecordingBrowserContext

count=2  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:267 [adapters]  []
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:150 [adapters]  []

### _successful_handshake

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:356 [adapters]  ()
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:139 [adapters]  ()

### _HandshakeVerifier

count=2  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:367 [adapters]  []
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:210 [adapters]  []

### _certificate_session

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:377 [adapters]  (authenticated_at, idle_deadline, thumbprint, subject, identity_nif, storage_state_path)
- adapters\outbound\aeat\auth\test_authenticator_translated_message.py:229 [adapters]  (authenticated_at, idle_deadline, thumbprint, subject, identity_nif, storage_state_path)

### test_close_is_idempotent

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\auth\test_authenticator.py:1156 [adapters]  (tmp_path, _settings_factory)
- adapters\persistence\storage\master_key\test_bucket_session.py:75 [adapters]  ()

### _URL_ADAPTER

count=2  kind=annotated_assign  class=sig-collision

layers: adapters, domain

- adapters\outbound\aeat\browser\_site_health.py:126 [adapters]  :TypeAdapter[AnyHttpUrl]=TypeAdapter(AnyHttpUrl)
- domain\portals\_entries\_common.py:22 [domain]  :TypeAdapter[HttpUrl]=TypeAdapter(HttpUrl)

### RecordingContext

count=2  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\browser\test_evasion.py:15 [adapters]  []
- adapters\outbound\aeat\browser\test_session.py:36 [adapters]  []

### ExportFormatError

count=2  kind=class  class=sig-collision

layers: adapters, application

- adapters\outbound\aeat\export\_errors.py:12 [adapters]  ['ExportError', 'ValueError']
- application\export\_errors.py:8 [application]  ['CoreError']

### _Draft

count=2  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\export\test_engine.py:45 [adapters]  ['BaseModel']
- adapters\outbound\aeat\export\test_preflight.py:26 [adapters]  ['BaseModel']

### _OkAuthProvider

count=2  kind=class  class=name-collision

layers: adapters

- adapters\outbound\aeat\export\test_engine.py:72 [adapters]  []
- adapters\outbound\aeat\export\test_preflight.py:55 [adapters]  []

### _assert_read_http

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\sede\_declarations.py:1760 [adapters]  (method, url, policy)
- adapters\outbound\aeat\sede\_iva_compensation_wallet.py:673 [adapters]  (method, url)

### _assert_read_browser_action

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\aeat\sede\_declarations.py:1772 [adapters]  (action, policy)
- adapters\outbound\aeat\sede\_iva_compensation_wallet.py:680 [adapters]  (action)

### _SELECTOR_PROBE_TIMEOUT_MS

count=2  kind=annotated_assign  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:78 [adapters]  :int=_TIMEOUT_DEFAULTS.aeat_browser_selector_probe_timeout_m
- adapters\outbound\aeat\sede\_nif_iva_check.py:129 [adapters]  :int=_TIMEOUT_DEFAULTS.aeat_browser_selector_probe_timeout_m

### _SUBMIT_SELECTORS

count=2  kind=annotated_assign  class=sig-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:91 [adapters]  :tuple[str, ...]=('input#enviar', 'input[name="enviar"]', 'i
- adapters\outbound\aeat\sede\_nif_iva_check.py:154 [adapters]  :tuple[str, ...]=('button:has-text("Consultar")', 'button:ha

### _assert_query_browser_action

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:109 [adapters]  (action)
- adapters\outbound\aeat\sede\_nif_iva_check.py:84 [adapters]  (action)

### _locate

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:128 [adapters]  (page, selectors, stage, description, timeout_ms)
- adapters\outbound\aeat\sede\_nif_iva_check.py:103 [adapters]  (page, selectors, stage, description, timeout_ms)

### _check_single_nif

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:394 [adapters]  (page, nif, timeout_ms)
- adapters\outbound\aeat\sede\_nif_iva_check.py:413 [adapters]  (page, nif, timeout_ms)

### extract_verdict_from_response_text

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_groi_check.py:446 [adapters]  (body_text)
- adapters\outbound\aeat\sede\_nif_iva_check.py:461 [adapters]  (body_text)

### _parse_spanish_decimal

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_iva_compensation_wallet.py:618 [adapters]  (value)
- adapters\outbound\aeat\sede\test_renta_web_open_capture_replay.py:210 [adapters]  (value)

### _fill_expected

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_nif_iva_check.py:548 [adapters]  (locator, value, stage, description, timeout_ms)
- adapters\outbound\aeat\sede\_renta_web_open.py:466 [adapters]  (locator, value, stage, description, timeout_ms)

### _click_expected

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\_nif_iva_check.py:558 [adapters]  (locator, stage, description, timeout_ms)
- adapters\outbound\aeat\sede\_renta_web_open.py:476 [adapters]  (locator, stage, description, timeout_ms)

### test_driver_mode_is_live

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:32 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:33 [adapters]  ()

### test_default_timeout_is_thirty_seconds

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:50 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:78 [adapters]  ()

### test_direct_driver_query_guard_rejects_unclassified_browser_action

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:84 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:71 [adapters]  ()

### test_observation_model_rejects_unknown_verdict

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:101 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:94 [adapters]  ()

### test_observation_model_rejects_empty_nif

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:106 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:99 [adapters]  ()

### test_observation_model_is_frozen

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:111 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:104 [adapters]  ()

### test_result_model_defaults_to_empty_observations

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\aeat\sede\test_groi_check.py:117 [adapters]  ()
- adapters\outbound\aeat\sede\test_nif_iva_check.py:110 [adapters]  ()

### _quarter_period

count=2  kind=function  class=name-collision

layers: adapters, application

- adapters\outbound\aeat\sede\test_iva_compensation_wallet_live.py:76 [adapters]  (month)
- application\live\test_iva_wallet_live.py:109 [application]  (month)

### _load_forbidden_verbs

count=2  kind=function  class=name-collision

layers: adapters, application

- adapters\outbound\aeat\sede\test_no_write_surface.py:22 [adapters]  ()
- application\filing\reconciliation\test_no_write_surface.py:27 [application]  ()

### TestNoCallContextWriteVerbs

count=2  kind=class  class=name-collision

layers: adapters, application

- adapters\outbound\aeat\sede\test_no_write_surface.py:33 [adapters]  []
- application\filing\reconciliation\test_no_write_surface.py:38 [application]  []

### TestNoWriteModeLiteral

count=2  kind=class  class=name-collision

layers: adapters, application

- adapters\outbound\aeat\sede\test_no_write_surface.py:62 [adapters]  []
- application\filing\reconciliation\test_no_write_surface.py:58 [application]  []

### _populated_observation

count=2  kind=function  class=sig-collision

layers: adapters, application

- adapters\outbound\aeat\sede\test_observation_store_roundtrip.py:42 [adapters]  (artefact)
- application\calculations\test_observations_repository_roundtrip.py:37 [application]  ()

### _OWNERSHIP_KEY

count=2  kind=annotated_assign  class=name-collision

layers: adapters

- adapters\outbound\google\_calc_sheets_apply.py:64 [adapters]  :Final[str]='aeat_vault_app'
- adapters\outbound\google\_calc_sheets_pull.py:71 [adapters]  :Final[str]='aeat_vault_app'

### _OWNERSHIP_VALUE

count=2  kind=annotated_assign  class=name-collision

layers: adapters

- adapters\outbound\google\_calc_sheets_apply.py:65 [adapters]  :Final[str]='aeat'
- adapters\outbound\google\_calc_sheets_pull.py:72 [adapters]  :Final[str]='aeat'

### _drive_service

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\google\_calc_sheets_apply.py:89 [adapters]  (credentials)
- adapters\outbound\google\_calc_sheets_pull.py:229 [adapters]  (credentials)

### _sheets_service

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\google\_calc_sheets_apply.py:101 [adapters]  (credentials)
- adapters\outbound\google\_calc_sheets_pull.py:241 [adapters]  (credentials)

### _column_index_to_letters

count=2  kind=function  class=name-collision

layers: adapters, application

- adapters\outbound\google\_calc_sheets_pull.py:741 [adapters]  (column)
- application\storage\calc_sheets\_records.py:79 [application]  (column)

### _live_profile

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\google\test_oauth_live.py:45 [adapters]  ()
- adapters\outbound\storage\test_google_drive_live.py:45 [adapters]  ()

### test_every_leaf_carries_a_registered_error_code

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\google\test_records.py:216 [adapters]  ()
- adapters\outbound\storage\test_foundation.py:129 [adapters]  ()

### _validate_namespace

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\storage\_google_drive.py:66 [adapters]  (namespace)
- adapters\outbound\storage\_local.py:45 [adapters]  (namespace)

### _validate_hmac

count=2  kind=function  class=name-collision

layers: adapters

- adapters\outbound\storage\_google_drive.py:78 [adapters]  (object_key_hmac)
- adapters\outbound\storage\_local.py:57 [adapters]  (object_key_hmac)

### _filename

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\storage\_google_drive.py:93 [adapters]  (object_key_hmac, label)
- adapters\outbound\storage\_local.py:77 [adapters]  (object_key_hmac, label, extension)

### provider

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\outbound\storage\test_local.py:37 [adapters]  (tmp_path)
- adapters\persistence\storage\envelope\test_envelope_ciphertext.py:54 [adapters]  ()

### _asset

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\persistence\profile\test_assets.py:31 [adapters]  (identifier, asset_class, cost_basis)
- adapters\persistence\storage\test_runtime_migrated_repositories.py:214 [adapters]  (identifier)

### USER_PROFILE_VALUE_NAMESPACE

count=2  kind=constant  class=sig-collision

layers: adapters, application

- adapters\persistence\storage\_namespace_registry.py:221 [adapters]  SecureObjectNamespaceDefinition(key='user_profile_value', na
- application\user_profile\_repository.py:44 [application]  USER_PROFILE_VALUE_STORAGE_NAMESPACE.namespace

### USER_PROFILE_SNAPSHOT_NAMESPACE

count=2  kind=constant  class=sig-collision

layers: adapters, application

- adapters\persistence\storage\_namespace_registry.py:230 [adapters]  SecureObjectNamespaceDefinition(key='user_profile_snapshot',
- application\user_profile\_repository.py:45 [application]  USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace

### store

count=2  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\blob_store\test_blob_store.py:32 [adapters]  (tmp_path, fixed_master_key)
- adapters\persistence\storage\secret_store\test_secret_store.py:43 [adapters]  (tmp_path, fixed_master_key)

### _expiry

count=2  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\blob_store\test_materialisation.py:26 [adapters]  ()
- adapters\persistence\storage\secret_store\test_secret_store.py:33 [adapters]  ()

### write_manifest

count=2  kind=function  class=sig-collision

layers: adapters, domain

- adapters\persistence\storage\bucket\_manifest_io.py:91 [adapters]  (paths, manifest)
- domain\manuals\_fetch.py:154 [domain]  (manifest_path, manifest)

### _now

count=2  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\bucket\test_manifest.py:29 [adapters]  ()
- core\time\_clock.py:18 [core]  ()

### _manifest

count=2  kind=function  class=sig-collision

layers: adapters, domain

- adapters\persistence\storage\bucket\test_manifest.py:33 [adapters]  (**overrides)
- domain\manuals\test_fetch.py:26 [domain]  (sha256, length)

### test_rejects_non_positive_schema_version

count=2  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\bucket\test_manifest.py:114 [adapters]  ()
- core\test_bucket_pointer.py:36 [core]  ()

### test_rejects_wrong_salt_length

count=2  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\bucket\test_manifest.py:119 [adapters]  ()
- adapters\persistence\storage\master_key\test_kdf_params.py:71 [adapters]  ()

### test_created_at_naive_raises_validation_error

count=2  kind=function  class=name-collision

layers: adapters

- adapters\persistence\storage\bucket\test_manifest.py:153 [adapters]  ()
- adapters\persistence\storage\master_key\test_recovery_record.py:133 [adapters]  ()

### test_read_rejects_unknown_key

count=2  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\bucket\test_manifest_io.py:105 [adapters]  (tmp_path)
- core\test_bucket_pointer_io.py:68 [core]  (tmp_path)

### _build_envelope

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\persistence\storage\envelope\test_envelope_ciphertext.py:64 [adapters]  (classification)
- adapters\persistence\storage\test_rotation.py:80 [adapters]  (nif)

### _DummyPayload

count=2  kind=class  class=sig-collision

layers: adapters

- adapters\persistence\storage\envelope\test_secure_bound_repository.py:37 [adapters]  ['BaseModel']
- adapters\persistence\storage\envelope\test_secure_bound_repository_contract.py:41 [adapters]  ['BaseModel']

### _EnvelopePayload

count=2  kind=class  class=name-collision

layers: adapters, entrypoints

- adapters\persistence\storage\master_key\_master_key.py:99 [adapters]  ['BaseModel']
- entrypoints\cli\test_common_output.py:15 [entrypoints]  ['OutputSchema']

### _open_session

count=2  kind=function  class=sig-collision

layers: adapters

- adapters\persistence\storage\master_key\test_bucket_session.py:25 [adapters]  (bucket_id, kek, dek, idle_minutes, opened_at)
- adapters\persistence\storage\master_key\test_idle_timeout.py:21 [adapters]  (idle_minutes)

### PortalRow

count=2  kind=class  class=name-collision

layers: adapters, application

- adapters\persistence\storage\sql\_orm.py:52 [adapters]  ['Base']
- application\portals\_service.py:24 [application]  ['BaseModel']

### _flush_or_wrap

count=2  kind=function  class=name-collision

layers: adapters, domain

- adapters\persistence\storage\sql\repository.py:28 [adapters]  (session, kind)
- domain\fincas\_repository.py:38 [domain]  (session, kind)

### _collect_environ_aliases

count=2  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\test_hardening_convention_guards.py:338 [adapters]  (tree)
- core\test_settings_single_surface_invariant.py:126 [core]  (tree)

### _iter_error_subclasses

count=2  kind=function  class=name-collision

layers: adapters, core

- adapters\persistence\storage\test_hardening_convention_guards.py:440 [adapters]  (root)
- core\errors\test_registry_enforcement.py:41 [core]  (root)

### TestErrorCodeBinding

count=2  kind=class  class=name-collision

layers: adapters, core

- adapters\persistence\storage\test_path_safety.py:112 [adapters]  []
- core\identity\test_documents.py:273 [core]  []

### _justificante

count=2  kind=function  class=sig-collision

layers: adapters, application

- adapters\persistence\storage\test_runtime_migrated_repositories.py:393 [adapters]  (tmp_path, label)
- application\filing\reconciliation\test_reconcile.py:121 [application]  (modelo, label)

### _make_filing

count=2  kind=function  class=name-collision

layers: adapters, domain

- adapters\persistence\storage\test_submission_repository.py:36 [adapters]  (draft_id, attempt_ordinal, status)
- domain\submission\test_repository.py:30 [domain]  (draft_id, attempt_ordinal, status)

### TestUnsafeSubmissionIds

count=2  kind=class  class=name-collision

layers: adapters, domain

- adapters\persistence\storage\test_submission_repository.py:173 [adapters]  []
- domain\submission\test_repository.py:171 [domain]  []

### TestPerSubmissionLockIsolation

count=2  kind=class  class=name-collision

layers: adapters, domain

- adapters\persistence\storage\test_submission_repository.py:184 [adapters]  []
- domain\submission\test_repository.py:182 [domain]  []

### _validate_source_kind

count=2  kind=function  class=name-collision

layers: application

- application\aggregation\_counterpart.py:37 [application]  (value)
- application\aggregation\_foreign_assets.py:32 [application]  (value)

### _validate_country

count=2  kind=function  class=sig-collision

layers: application

- application\aggregation\_counterpart.py:47 [application]  (value, field_name)
- application\aggregation\_foreign_assets.py:41 [application]  (value)

### _aggregate_for_modelo

count=2  kind=function  class=name-collision

layers: application

- application\aggregation\_counterpart.py:184 [application]  (observations, modelo, period)
- application\aggregation\_retenciones.py:179 [application]  (observations, modelo, period)

### ERROR_CODES

count=2  kind=constant  class=sig-collision

layers: application

- application\aggregation\_service.py:56 [application]  :tuple[str, ...]=('ERROR_FINANCIAL_AGGREGATION', 'REFUSED_FI
- application\operator_surface\_contract.py:332 [application]  :tuple[str, ...]=('REFUSED_OPERATOR_SURFACE_CONTRACT',)

### TestInvariants

count=2  kind=class  class=name-collision

layers: application

- application\aggregation\test_counterpart.py:155 [application]  []
- application\aggregation\test_foreign_assets.py:149 [application]  []

### _modelo_369_union_revision

count=2  kind=function  class=name-collision

layers: application, domain

- application\aggregation\test_oss_ioss.py:69 [application]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:38 [domain]  ()

### _counterpart_obs

count=2  kind=function  class=sig-collision

layers: application

- application\aggregation\test_per_modelo_registry_provider.py:26 [application]  (source_id, nif, country, operation_kind, base, name, source_kind, groi_verified, nif_iva_verified)
- application\aggregation\test_per_modelo_service.py:53 [application]  (nif, source_kind, operation_kind, country, invoice_total)

### _profile_with_ccaa

count=2  kind=function  class=name-collision

layers: application

- application\aggregation\test_source_mesh_profile_live.py:34 [application]  (ccaa)
- application\modelo\test_profile_binding.py:75 [application]  (ccaa)

### _append_bucket_event

count=2  kind=function  class=sig-collision

layers: application

- application\auth\_operator.py:1240 [application]  (state, action, object_id)
- application\ledger\_actions.py:3310 [application]  (repository, event)

### _append_bucket_events

count=2  kind=function  class=sig-collision

layers: application

- application\auth\_operator.py:1259 [application]  (state, events)
- application\ledger\_actions.py:3314 [application]  (repository, events)

### _LOCAL_FILING_PROVENANCE

count=2  kind=annotated_assign  class=name-collision

layers: application

- application\calculations\_binding_prefill.py:74 [application]  :Final='local_filing'
- application\calculations\_relation_prefill.py:52 [application]  :Final='local_filing'

### _calculate_303_from_observations

count=2  kind=function  class=name-collision

layers: application, domain

- application\calculations\test_binding_prefill.py:58 [application]  (filing_year, period, observations)
- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:86 [domain]  (filing_year, period, observations)

### _Cell

count=2  kind=class  class=name-collision

layers: application

- application\calculations\test_detail_record_round_trip.py:42 [application]  []
- application\calculations\test_row_set_assembly.py:34 [application]  []

### _modelo_115_observations

count=2  kind=function  class=name-collision

layers: application, domain

- application\calculations\test_relation_prefill_source_mesh.py:20 [application]  ()
- domain\calculations\registry\test_relation_closure.py:58 [domain]  ()

### _isolated_aeat_root

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\conftest.py:31 [application]  (request, monkeypatch, tmp_path)
- entrypoints\cli\conftest.py:19 [entrypoints]  (monkeypatch, tmp_path)

### TestVerify

count=2  kind=class  class=name-collision

layers: application, domain

- application\evidence\test_evidence.py:116 [application]  []
- domain\manuals\test_verify.py:94 [domain]  []

### _registry_period

count=2  kind=function  class=sig-collision

layers: application

- application\filing\__init__.py:266 [application]  (period)
- application\verification\_verify.py:215 [application]  (period, ejercicio)

### _filing_period_date

count=2  kind=function  class=sig-collision

layers: application

- application\filing\__init__.py:273 [application]  (period)
- application\verification\_verify.py:222 [application]  (period, ejercicio)

### _SEVERITY_RANK

count=2  kind=annotated_assign  class=sig-collision

layers: application

- application\filing\__init__.py:476 [application]  :dict[str, int]={_BaseSeverity.INFO: 0, _BaseSeverity.WARNIN
- application\review\_enums.py:44 [application]  :Mapping[ReviewSeverity, int]=MappingProxyType({ReviewSeveri

### _normalise_period

count=2  kind=function  class=sig-collision

layers: application

- application\filing\_import.py:143 [application]  (modelo, ejercicio, raw_period, schema_provider)
- application\filing\reconciliation\_reconcile.py:329 [application]  (period, ejercicio, supported_periods)

### _active_bucket_runtime

count=2  kind=function  class=name-collision

layers: application, domain

- application\filing\conftest.py:23 [application]  (tmp_path)
- domain\invoices\test_reconciliation.py:35 [domain]  (tmp_path)

### _canonical_tax_id

count=2  kind=function  class=sig-collision

layers: application

- application\filing\reconciliation\_reconcile.py:386 [application]  (value)
- application\user_profile\_profile_repository.py:81 [application]  (facts)

### _make_draft

count=2  kind=function  class=sig-collision

layers: application

- application\filing\test_calculate.py:35 [application]  (status, findings, modelo, period)
- application\filing\test_repository.py:30 [application]  (period, ingresos)

### _schema_provider

count=2  kind=function  class=sig-collision

layers: application

- application\filing\test_export.py:44 [application]  (filing_year, period, modelos)
- application\filing\test_filing.py:47 [application]  ()

### _make_svc

count=2  kind=function  class=sig-collision

layers: application

- application\inventory\test_inventory.py:34 [application]  (profile)
- application\ledger\test_evidence.py:43 [application]  (isolated_settings, objects)

### _event_repo

count=2  kind=function  class=sig-collision

layers: application

- application\inventory\test_inventory.py:41 [application]  (profile)
- application\ledger\test_evidence.py:50 [application]  (objects)

### _replace_transaction

count=2  kind=function  class=sig-collision

layers: application, domain

- application\ledger\_actions.py:3193 [application]  (catalogue, old_transaction_id, replacement)
- domain\transactions\_service.py:232 [domain]  (catalogue, transaction)

### _require_transaction

count=2  kind=function  class=name-collision

layers: application, domain

- application\ledger\_actions.py:3211 [application]  (catalogue, transaction_id)
- domain\transactions\_service.py:239 [domain]  (catalogue, transaction_id)

### _result

count=2  kind=function  class=sig-collision

layers: application

- application\ledger\_actions.py:3650 [application]  (bucket_id, transaction, bucket_event_ids)
- application\workflow\test_persistence.py:41 [application]  (run_id, started)

### _resolve_id

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\ledger\_business_operation_invoice.py:315 [application]  (records, id_or_prefix)
- entrypoints\cli\_ledger.py:253 [entrypoints]  (transaction_repository, prefix)

### _snapshot_from_record

count=2  kind=function  class=name-collision

layers: application

- application\live\_borrador_100.py:135 [application]  (record, requested_snapshot_id)
- application\live\_censo.py:170 [application]  (record, requested_snapshot_id)

### _derive_snapshot_id

count=2  kind=function  class=sig-collision

layers: application

- application\live\_expedientes.py:79 [application]  (capture)
- application\live\_notifications.py:81 [application]  (snapshot)

### TestCapture

count=2  kind=class  class=name-collision

layers: application

- application\live\test_expedientes.py:65 [application]  []
- application\live\test_notifications.py:69 [application]  []

### TestLatest

count=2  kind=class  class=name-collision

layers: application

- application\live\test_expedientes.py:122 [application]  []
- application\live\test_notifications.py:136 [application]  []

### _secure_object_namespace_count

count=2  kind=function  class=name-collision

layers: application

- application\live\test_iva_remote_state_acquisition.py:434 [application]  (database_path, namespace)
- application\live\test_iva_wallet_capture_backend.py:340 [application]  (database_path, namespace)

### _RevisionInputsProvider

count=2  kind=class  class=name-collision

layers: application

- application\modelo\_actions.py:388 [application]  []
- application\modelo\test_file_flow.py:221 [application]  []

### _RevisionDraftBuilder

count=2  kind=class  class=name-collision

layers: application

- application\modelo\_actions.py:421 [application]  []
- application\modelo\test_file_flow.py:243 [application]  []

### _decimal_value

count=2  kind=function  class=name-collision

layers: application

- application\modelo\_borrador_binding.py:294 [application]  (binding_id, value)
- application\modelo\_profile_binding.py:202 [application]  (binding_id, value)

### _resident_profile

count=2  kind=function  class=name-collision

layers: application

- application\modelo\test_actions.py:50 [application]  ()
- application\modelo\test_modelo_210_phase1.py:79 [application]  ()

### _zero_relation_values

count=2  kind=function  class=sig-collision

layers: application

- application\modelo\test_borrador_binding.py:128 [application]  ()
- application\modelo\test_profile_binding.py:230 [application]  (snapshot)

### _store_profile

count=2  kind=function  class=sig-collision

layers: application

- application\modelo\test_bucket_aggregation_flow.py:123 [application]  (objects)
- application\modelo\test_profile_binding.py:67 [application]  (record)

### _modelo_303_engine_inputs

count=2  kind=function  class=name-collision

layers: application

- application\modelo\test_declaration_period_binding.py:49 [application]  ()
- application\modelo\test_iva_wallet_engine_integration.py:150 [application]  ()

### _ACTIVE_STORAGE_STACK

count=2  kind=annotated_assign  class=name-collision

layers: application

- application\modelo\test_export.py:64 [application]  :ExitStack | None=None
- application\test_state_projection.py:53 [application]  :ExitStack | None=None

### _ensure_operator_storage_span

count=2  kind=function  class=name-collision

layers: application

- application\modelo\test_export.py:98 [application]  ()
- application\test_state_projection.py:83 [application]  ()

### _decision

count=2  kind=function  class=sig-collision

layers: application, domain

- application\modelo\test_iva_wallet_decision_binding.py:20 [application]  (blocked, amount)
- domain\calculations\registry\test_cross_reference_applicability.py:43 [domain]  (applicability_predicates, applicability_condition_mode)

### _aborted_result

count=2  kind=function  class=sig-collision

layers: application

- application\modelo\test_workflow_gate_error_boundary.py:36 [application]  (summary)
- application\workflow\test_resume.py:49 [application]  (run_id, reason, obligation)

### _landlord

count=2  kind=function  class=name-collision

layers: application

- application\overview\test_applicability.py:64 [application]  ()
- application\overview\test_calendar_applicability_consistency.py:70 [application]  ()

### _autonomo

count=2  kind=function  class=name-collision

layers: application

- application\overview\test_applicability.py:97 [application]  ()
- application\overview\test_calendar_applicability_consistency.py:51 [application]  ()

### _sociedad_limitada

count=2  kind=function  class=name-collision

layers: application

- application\overview\test_applicability.py:109 [application]  ()
- application\overview\test_calendar_applicability_consistency.py:61 [application]  ()

### _undeclared_profile

count=2  kind=function  class=name-collision

layers: application

- application\overview\test_calendar.py:412 [application]  ()
- application\overview\test_explain.py:41 [application]  ()

### test_explain_refuses_unknown_modelo

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\overview\test_explain.py:65 [application]  ()
- entrypoints\cli\test_overview_explain_verb.py:84 [entrypoints]  (cli_runner)

### _write_valid_normative

count=2  kind=function  class=name-collision

layers: application, entrypoints

- application\registry\test_corpus.py:43 [application]  (root)
- entrypoints\cli\test_registry_corpus.py:55 [entrypoints]  (root)

### _load_transactions

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\review\_adapters.py:133 [application]  (settings, bucket_id)
- entrypoints\cli\_common.py:248 [entrypoints]  (state)

### _load_invoices

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\review\_adapters.py:194 [application]  (settings)
- entrypoints\cli\_common.py:252 [entrypoints]  ()

### _load_drafts

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\review\_adapters.py:329 [application]  (settings)
- entrypoints\cli\_common.py:256 [entrypoints]  ()

### _coerce_decimal

count=2  kind=function  class=sig-collision

layers: application, domain

- application\review\_edit.py:127 [application]  (clause, scope)
- domain\calculations\registry\_schema.py:49 [domain]  (value)

### _ensure_unique_keys

count=2  kind=function  class=name-collision

layers: application

- application\review\_edit.py:212 [application]  (clauses, scope)
- application\review\_filter.py:215 [application]  (clauses, scope)

### _ensure_known_keys

count=2  kind=function  class=name-collision

layers: application

- application\review\_edit.py:228 [application]  (clauses, scope, allowed)
- application\review\_filter.py:236 [application]  (clauses, scope, allowed)

### _build_settings

count=2  kind=function  class=name-collision

layers: application

- application\review\test_adapters.py:64 [application]  (tmp_path)
- application\review\test_aggregator.py:60 [application]  (tmp_path)

### _schema_version

count=2  kind=function  class=name-collision

layers: application

- application\review\test_adapters.py:91 [application]  (modelo)
- application\review\test_aggregator.py:56 [application]  (modelo)

### _invoice_line

count=2  kind=function  class=name-collision

layers: application

- application\review\test_adapters.py:229 [application]  ()
- application\review\test_models.py:80 [application]  ()

### test_ledger_spec_rejects_unknown_key

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:141 [application]  ()
- application\review\test_filter.py:122 [application]  ()

### test_ledger_spec_rejects_duplicate_key

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:147 [application]  ()
- application\review\test_filter.py:140 [application]  ()

### test_ledger_spec_empty_returns_empty_spec

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:153 [application]  ()
- application\review\test_filter.py:113 [application]  ()

### test_invoice_spec_rejects_unknown_key

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:197 [application]  ()
- application\review\test_filter.py:165 [application]  ()

### test_invoice_spec_rejects_duplicate_key

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:209 [application]  ()
- application\review\test_filter.py:177 [application]  ()

### test_ledger_spec_is_frozen

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:302 [application]  ()
- application\review\test_filter.py:216 [application]  ()

### test_ledger_spec_rejects_inconsistent_construction

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:310 [application]  ()
- application\review\test_filter.py:224 [application]  ()

### test_invoice_spec_rejects_inconsistent_construction

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:315 [application]  ()
- application\review\test_filter.py:230 [application]  ()

### test_declaration_spec_rejects_inconsistent_construction

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit.py:320 [application]  ()
- application\review\test_filter.py:235 [application]  ()

### _clause

count=2  kind=function  class=sig-collision

layers: application

- application\review\test_edit_helpers.py:59 [application]  (key, raw_value)
- application\review\test_filter_helpers.py:47 [application]  (key, value)

### test_ensure_unique_keys_passes_when_all_keys_distinct

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit_helpers.py:225 [application]  ()
- application\review\test_filter_helpers.py:63 [application]  ()

### test_ensure_unique_keys_scope_tag_composes_into_reason

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit_helpers.py:244 [application]  ()
- application\review\test_filter_helpers.py:79 [application]  ()

### test_ensure_known_keys_passes_when_every_key_is_allowed

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit_helpers.py:258 [application]  ()
- application\review\test_filter_helpers.py:104 [application]  ()

### test_ensure_known_keys_scope_tag_composes_into_reason

count=2  kind=function  class=name-collision

layers: application

- application\review\test_edit_helpers.py:276 [application]  ()
- application\review\test_filter_helpers.py:127 [application]  ()

### _VALID_FACTS

count=2  kind=annotated_assign  class=sig-collision

layers: application

- application\setup\test_atomic_create_rollback.py:49 [application]  :Mapping[str, str]={'identity.tax_id': '00000000T', 'identit
- application\user_profile\test_profile_repository.py:52 [application]  :tuple[UserProfileFact, ...]=(UserProfileFact(path='identity

### _INCOMPLETE_FACTS

count=2  kind=annotated_assign  class=sig-collision

layers: application

- application\setup\test_atomic_create_rollback.py:60 [application]  :Mapping[str, str]={key: value for key, value in _VALID_FACT
- application\user_profile\test_profile_repository.py:74 [application]  :tuple[UserProfileFact, ...]=tuple((fact for fact in _SECOND

### _json

count=2  kind=function  class=name-collision

layers: application, entrypoints

- application\setup\test_atomic_create_roundtrip.py:67 [application]  (result)
- entrypoints\cli\test_apex_workflow_verification.py:51 [entrypoints]  (result)

### _create

count=2  kind=function  class=sig-collision

layers: application

- application\setup\test_atomic_create_roundtrip.py:71 [application]  (name, tax_id)
- application\user_profile\test_profile_repository.py:77 [application]  (repository, label, facts, enforce_unique_tax_id)

### _env

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\setup\test_cli.py:17 [application]  (tmp_path)
- entrypoints\cli\test_config_custody_profile_lifecycle.py:51 [entrypoints]  ()

### _translate

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\storage\calc_sheets\_translator.py:88 [application]  (expression, layout)
- entrypoints\cli\_common.py:156 [entrypoints]  (translatable)

### _isolated_default_secure_sql

count=2  kind=function  class=sig-collision

layers: application

- application\test_diagnostics.py:42 [application]  (tmp_path)
- application\test_repair_integrity.py:53 [application]  (tmp_path, request)

### _compare

count=2  kind=function  class=sig-collision

layers: application, domain

- application\user_profile\_censo_sync.py:435 [application]  (census_facts, profile_facts)
- domain\calculations\registry\_formula_runtime.py:1127 [domain]  (op, left, right)

### _clear_output_language_cache

count=2  kind=function  class=name-collision

layers: application

- application\user_profile\_repository.py:72 [application]  ()
- application\workflow\_persistence.py:64 [application]  ()

### test_show_refuses_when_no_snapshot_exists

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\user_profile\test_census_sync.py:89 [application]  (secure_store)
- entrypoints\cli\test_profile_census_verbs.py:112 [entrypoints]  (cli_runner)

### _all_required_facts

count=2  kind=function  class=name-collision

layers: application

- application\user_profile\test_lifecycle.py:57 [application]  (schema)
- application\user_profile\test_orchestration.py:49 [application]  (schema)

### test_boundary_catches_simulated_field_drop_via_corrupted_payload

count=2  kind=function  class=sig-collision

layers: application, domain

- application\user_profile\test_repository_anti_tautology.py:85 [application]  (runtime_profile)
- domain\filing\test_roundtrip_anti_tautology.py:103 [domain]  (tmp_path)

### _load_snapshot

count=2  kind=function  class=sig-collision

layers: application, entrypoints

- application\verification\_verify.py:186 [application]  (declaracion, registry_root)
- entrypoints\cli\_config\_google.py:771 [entrypoints]  (modelo, period, year)

### project_answers

count=2  kind=function  class=name-collision

layers: application, core

- application\wizard\_persistence.py:184 [application]  (flow, values)
- core\profile.py:112 [core]  (flow, values)

### _stringify

count=2  kind=function  class=sig-collision

layers: application, domain

- application\wizard\_prompter.py:303 [application]  (value)
- domain\deadlines\_profiles.py:242 [domain]  (raw)

### _flow

count=2  kind=function  class=sig-collision

layers: application

- application\wizard\test_commands_helpers.py:66 [application]  (*questions)
- application\wizard\test_compile.py:57 [application]  (questions)

### _section

count=2  kind=function  class=sig-collision

layers: application, domain

- application\wizard\test_models.py:55 [application]  ()
- domain\manuals\test_schema.py:83 [domain]  (section_id)

### _base_answers

count=2  kind=function  class=name-collision

layers: application

- application\wizard\test_monoparental_reduccion.py:36 [application]  (**overrides)
- application\wizard\test_situacion_familiar.py:67 [application]  (**overrides)

### _individual_answers

count=2  kind=function  class=name-collision

layers: application

- application\wizard\test_verifier.py:25 [application]  (**overrides)
- application\wizard\test_verifier_checks.py:40 [application]  (**overrides)

### _enum_value

count=2  kind=function  class=name-collision

layers: application, domain

- application\workflow\_engine.py:164 [application]  (value)
- domain\submission\_preflight.py:194 [domain]  (value)

### declaration_key

count=2  kind=function  class=name-collision

layers: application

- application\workflow\_engine.py:1290 [application]  (modelo, period)
- application\workflow\_models.py:163 [application]  (modelo, period)

### update_declaration_pointer

count=2  kind=function  class=sig-collision

layers: application

- application\workflow\_engine.py:1295 [application]  (state, modelo, period, draft_id, status, exported_path)
- application\workflow\_models.py:291 [application]  (state, modelo, period, draft_id, status, exported_path, verified)

### _validate_run_id

count=2  kind=function  class=name-collision

layers: application, core

- application\workflow\_persistence.py:393 [application]  (run_id)
- core\observability\_store.py:53 [core]  (run_id)

### _patch_secure_backend

count=2  kind=function  class=name-collision

layers: application

- application\workflow\test_persistence.py:32 [application]  (tmp_path)
- application\workflow\test_resume.py:30 [application]  (tmp_path)

### _output_language

count=2  kind=function  class=name-collision

layers: core, entrypoints

- core\errors\test_envelope.py:20 [core]  (language)
- entrypoints\cli\test_windows_encoding.py:33 [entrypoints]  (language)

### _module_name_for_path

count=2  kind=function  class=name-collision

layers: core

- core\errors\test_exception_base_hygiene.py:57 [core]  (path)
- core\errors\test_registry_enforcement.py:62 [core]  (path)

### _validate_nif

count=2  kind=function  class=sig-collision

layers: core

- core\identity\_documents.py:131 [core]  (candidate)
- core\identity\_tax_id.py:77 [core]  (value)

### _validate_nie

count=2  kind=function  class=sig-collision

layers: core

- core\identity\_documents.py:149 [core]  (candidate)
- core\identity\_tax_id.py:89 [core]  (value)

### _validate_cif

count=2  kind=function  class=sig-collision

layers: core

- core\identity\_documents.py:168 [core]  (candidate)
- core\identity\_tax_id.py:103 [core]  (value)

### _ReconfigurableStream

count=2  kind=class  class=name-collision

layers: core, entrypoints

- core\json_contract.py:112 [core]  ['Protocol']
- entrypoints\cli\test_stdio.py:95 [entrypoints]  ['io.StringIO']

### _json_default

count=2  kind=function  class=name-collision

layers: core, domain

- core\output_rendering.py:69 [core]  (value)
- domain\transactions\_models.py:140 [domain]  (value)

### _TRUTHY

count=2  kind=annotated_assign  class=sig-collision

layers: core, tests

- core\parsing\_utils.py:15 [core]  :frozenset[str]=frozenset({'true', '1', 'yes', 'y', 'si', 's
- tests\conftest.py:60 [tests]  :frozenset[str]=frozenset({'1', 'true', 'yes', 'on'})

### _is_production_module

count=2  kind=function  class=name-collision

layers: core

- core\resources\test_single_surface_invariant.py:34 [core]  (path)
- core\test_boundary_contract.py:51 [core]  (path)

### _resolve_relative_import

count=2  kind=function  class=sig-collision

layers: core, diagnostics

- core\test_boundary_contract.py:63 [core]  (path, level, module)
- diagnostics\_identity_placement.py:233 [diagnostics]  (consumer, module, level)

### catalogue

count=2  kind=function  class=name-collision

layers: domain

- domain\auth\apoderamientos\test_catalogue.py:19 [domain]  ()
- domain\transactions\_model_tier.py:167 [domain]  ()

### _canonical_payload

count=2  kind=function  class=name-collision

layers: domain

- domain\buckets\_event.py:183 [domain]  (payload)
- domain\user_profile\_values.py:341 [domain]  (payload)

### _build_event

count=2  kind=function  class=sig-collision

layers: domain

- domain\buckets\test_event_catalogue.py:37 [domain]  (bucket_id, event_type, occurred_at, object_type, object_id, actor, payload)
- domain\buckets\test_event_history_roundtrip.py:33 [domain]  (bucket_id, event_type, occurred_at, actor, object_type, object_id, payload)

### register_default

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\_aeat_nif_iva_oracle.py:207 [domain]  (catalogue, environment)
- domain\calculations\registry\_groi_oracle.py:225 [domain]  (catalogue, environment)

### _QUARTERLY_PERIOD_ORDINAL

count=2  kind=annotated_assign  class=name-collision

layers: domain

- domain\calculations\registry\_bindings.py:467 [domain]  :dict[str, int]={'1T': 1, '2T': 2, '3T': 3, '4T': 4}
- domain\calculations\registry\_relations.py:219 [domain]  :dict[str, int]={'1T': 1, '2T': 2, '3T': 3, '4T': 4}

### _ORDINAL_TO_QUARTERLY

count=2  kind=annotated_assign  class=name-collision

layers: domain

- domain\calculations\registry\_bindings.py:468 [domain]  :dict[int, str]={ordinal: code for code, ordinal in _QUARTER
- domain\calculations\registry\_relations.py:220 [domain]  :dict[int, str]={ordinal: code for code, ordinal in _QUARTER

### _PAGO_FRACCIONADO_PERIOD_ORDINAL

count=2  kind=annotated_assign  class=name-collision

layers: domain

- domain\calculations\registry\_bindings.py:469 [domain]  :dict[str, int]={'1P': 1, '2P': 2, '3P': 3}
- domain\calculations\registry\_relations.py:221 [domain]  :dict[str, int]={'1P': 1, '2P': 2, '3P': 3}

### _ORDINAL_TO_PAGO_FRACCIONADO

count=2  kind=annotated_assign  class=name-collision

layers: domain

- domain\calculations\registry\_bindings.py:470 [domain]  :dict[int, str]={ordinal: code for code, ordinal in _PAGO_FR
- domain\calculations\registry\_relations.py:222 [domain]  :dict[int, str]={ordinal: code for code, ordinal in _PAGO_FR

### _derive_offset_source_period

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\_bindings.py:475 [domain]  (offset, target_period)
- domain\calculations\registry\_relations.py:227 [domain]  (relation, target_period)

### _derive_offset_source_anchor

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\_bindings.py:480 [domain]  (offset, target_period)
- domain\calculations\registry\_relations.py:232 [domain]  (relation, target_period)

### _selector_int

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\_export.py:199 [domain]  (binding, key)
- domain\calculations\registry\test_record_design.py:899 [domain]  (value)

### _evaluate_expression

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\_formula_runtime.py:532 [domain]  (expression, values, binding_values, parameters, date_context, relation_values, operand_refs, operand_values, enum_binding_values, date_binding_values, filing_year, text_values)
- domain\calculations\registry\test_tautology_gate.py:56 [domain]  (expr, casilla_values)

### _binding_source_periods

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\_validate_previous_filing_sources.py:75 [domain]  (binding)
- domain\calculations\registry\test_relation_consistency.py:227 [domain]  (binding)

### _binding_source_outputs

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\_validate_previous_filing_sources.py:85 [domain]  (binding)
- domain\calculations\registry\test_relation_consistency.py:237 [domain]  (binding)

### _aeat_policy

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:32 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:42 [domain]  ()

### _wrong_host_policy

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:59 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:60 [domain]  ()

### test_verify_payload_without_driver_returns_unverifiable_after_guard_preflight

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:124 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:112 [domain]  ()

### test_verify_payload_reports_guard_block_when_aeat_host_not_in_policy

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:143 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:132 [domain]  ()

### test_register_default_under_production_environment

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:171 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:266 [domain]  ()

### test_register_default_test_environment_classification_supported

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_aeat_nif_iva_oracle.py:180 [domain]  ()
- domain\calculations\registry\test_groi_oracle.py:275 [domain]  ()

### _modelo_130

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_audit_oracle_bindings.py:29 [domain]  ()
- domain\calculations\registry\test_audit_oracle_surface_compatibility.py:51 [domain]  ()

### _modelo_100_bindings

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_borrador_prefilled_schema.py:14 [domain]  ()
- domain\calculations\registry\test_schema_hygiene.py:440 [domain]  (modelos)

### _modelos_by_id

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_census_modelo_registry_data.py:21 [domain]  ()
- domain\calculations\registry\test_detail_record_modelo_coverage.py:41 [domain]  ()

### _fixed_width_record

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_committed_registry.py:386 [domain]  (length, fields)
- domain\calculations\registry\test_modelo_349_registry.py:575 [domain]  (length, fields)

### _committed_130

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_corpus_round_trip_gate.py:33 [domain]  ()
- domain\calculations\registry\test_provisional_specimen_gate.py:31 [domain]  ()

### _committed_profile

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_corpus_round_trip_gate.py:38 [domain]  (provisional, round_trip_verified, verification_source)
- domain\calculations\registry\test_provisional_specimen_gate.py:36 [domain]  (provisional)

### test_corpus_root_derived_from_bundled_path

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_corpus_round_trip_gate.py:137 [domain]  ()
- domain\calculations\registry\test_provisional_specimen_gate.py:140 [domain]  ()

### _other_source_binding

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:43 [domain]  ()
- domain\calculations\registry\test_invoice_bindings.py:43 [domain]  ()

### test_row_binding_rejects_inconsistent_grouping_for_period_only_field

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:487 [domain]  ()
- domain\calculations\registry\test_invoice_bindings.py:436 [domain]  ()

### test_row_binding_requires_only_rectifications_for_period_field

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:500 [domain]  ()
- domain\calculations\registry\test_invoice_bindings.py:449 [domain]  ()

### test_row_binding_period_grouping_requires_rectification_scope

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_counterpart_bindings.py:512 [domain]  ()
- domain\calculations\registry\test_invoice_bindings.py:461 [domain]  ()

### _modelo_130_inputs

count=2  kind=function  class=name-collision

layers: domain, entrypoints

- domain\calculations\registry\test_cross_dependency_calculations.py:778 [domain]  ()
- entrypoints\cli\test_registry_cli.py:861 [entrypoints]  ()

### _run_python

count=2  kind=function  class=sig-collision

layers: domain, entrypoints

- domain\calculations\registry\test_cross_domain_snapshot_registration.py:36 [domain]  (*fragments)
- entrypoints\cli\test_lazy_command_tree.py:64 [entrypoints]  (code)

### _field

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_export.py:35 [domain]  (field_id, offset, length)
- domain\user_profile\test_census_schema_fields.py:34 [domain]  (schema, path)

### _revision_with_bindings

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:82 [domain]  (*bindings)
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:80 [domain]  (*bindings)

### test_validate_rejects_unknown_rate_kind

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:155 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:101 [domain]  ()

### test_validate_rejects_non_sum_aggregation

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:175 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:123 [domain]  ()

### test_validate_rejects_unknown_fact

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:180 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:128 [domain]  ()

### test_validate_rejects_wrong_source_kind

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:185 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:133 [domain]  ()

### test_resolve_supports_base_amount_sum_fact

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:275 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:210 [domain]  ()

### test_resolve_handles_multiple_bindings_independently

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_ledger_iva_aggregation_binding.py:305 [domain]  ()
- domain\calculations\registry\test_ledger_oss_aggregation_binding.py:220 [domain]  ()

### _dispatch_expression

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_lookup_bracket_by_ccaa.py:88 [domain]  (base)
- domain\calculations\registry\test_lookup_bracket_by_entity_type.py:93 [domain]  (base)

### m100_2025_snapshot

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_100_ahorro_base_chain.py:71 [domain]  (registry_authority)
- domain\calculations\registry\test_modelo_100_cripto_1812_propagation.py:47 [domain]  (registry_authority)

### _run_2024

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_modelo_100_ahorro_base_chain.py:77 [domain]  (snapshot, inputs)
- domain\calculations\registry\test_modelo_100_cripto_1812_propagation.py:64 [domain]  (snapshot, valor_1804)

### _committed_modelo_100

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_100_autonomic_chain.py:60 [domain]  ()
- domain\calculations\registry\test_temporal.py:29 [domain]  ()

### _modelo_100

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_100_drift_detection.py:64 [domain]  ()
- domain\calculations\registry\test_renta_cuota_chain_contract.py:87 [domain]  ()

### _base_binding_values

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_modelo_100_retenciones_binding_wiring.py:50 [domain]  (m111, m123)
- domain\calculations\registry\test_modelo_100_tarifa_real.py:300 [domain]  ()

### _snapshot_2024

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_modelo_123_registry.py:94 [domain]  (filing_year)
- domain\calculations\registry\test_modelo_200_temporal_coverage.py:74 [domain]  ()

### _layout_bindings_for

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_modelo_232_registry.py:402 [domain]  (revision, record_name)
- domain\calculations\registry\test_modelo_720_registry.py:192 [domain]  (revision, record_name)

### _scenario_2025

count=2  kind=function  class=sig-collision

layers: domain

- domain\calculations\registry\test_reduccion_art_84_conjunta.py:115 [domain]  (scenario_id, declaration_type, minor_children_in_unit, expected_0461)
- domain\calculations\registry\test_renta_chain_behaviour.py:93 [domain]  (scenario_id, overrides, expected)

### _with_revision

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_registry_schema.py:62 [domain]  (modelo, revision)
- domain\calculations\registry\test_relation_closure.py:42 [domain]  (modelo, revision)

### _ahorro_table

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:62 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:56 [domain]  (year)

### test_ahorro_escala_resolves_at_zero_base

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:85 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:72 [domain]  (year)

### test_ahorro_escala_aeat_manual_2800_worked_example

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:92 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:79 [domain]  (year)

### test_ahorro_escala_at_6000_breakpoint_matches_published_incremento

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:105 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:92 [domain]  (year)

### test_ahorro_escala_at_50000_breakpoint_matches_published_incremento

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:114 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:101 [domain]  (year)

### test_ahorro_escala_at_200000_breakpoint_matches_published_incremento

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:123 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:110 [domain]  (year)

### test_ahorro_escala_at_300000_breakpoint_matches_published_incremento

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:132 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:119 [domain]  (year)

### test_ahorro_escala_2020_top_bracket_is_open_11_5_percent

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:140 [domain]  ()
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:127 [domain]  ()

### test_ahorro_escala_2025_top_marginal_rate_is_15_percent

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:151 [domain]  ()
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:138 [domain]  ()

### test_ahorro_escala_2023_2024_top_marginal_rate_is_14_percent

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:161 [domain]  ()
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:148 [domain]  ()

### test_ahorro_escala_2021_2022_top_marginal_rate_is_13_percent

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:171 [domain]  ()
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:158 [domain]  ()

### test_ahorro_escala_rejects_date_outside_year_window

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_escala_autonomica_ahorro_bracket_resolution.py:251 [domain]  (year)
- domain\calculations\registry\test_renta_escala_estatal_ahorro_bracket_resolution.py:170 [domain]  (year)

### _open_simulator_policy

count=2  kind=function  class=name-collision

layers: domain

- domain\calculations\registry\test_renta_web_open_oracle.py:33 [domain]  ()
- domain\calculations\registry\test_renta_web_open_replay_parity.py:45 [domain]  ()

### _to_str_dict

count=2  kind=function  class=name-collision

layers: domain

- domain\categories\_registry.py:129 [domain]  (raw)
- domain\iva\_catalogue.py:113 [domain]  (raw)

### _parse_citation

count=2  kind=function  class=name-collision

layers: domain

- domain\categories\_registry.py:199 [domain]  (raw_citation)
- domain\iva\_catalogue.py:152 [domain]  (raw_citation)

### _rule

count=2  kind=function  class=sig-collision

layers: domain

- domain\categories\test_profile.py:40 [domain]  ()
- domain\manuals\test_schema.py:62 [domain]  (rule_id, kind)

### TestScheduleRoundTrip

count=2  kind=class  class=name-collision

layers: domain

- domain\deadlines\test_engine.py:447 [domain]  []
- domain\deadlines\test_models.py:163 [domain]  []

### _populated_draft

count=2  kind=function  class=name-collision

layers: domain

- domain\filing\test_roundtrip_anti_tautology.py:53 [domain]  ()
- domain\filing\test_secure_storage_roundtrip.py:42 [domain]  ()

### _parameter_value

count=2  kind=function  class=name-collision

layers: domain

- domain\fincas\_imputacion_parameters.py:109 [domain]  (parameters, parameter_id)
- domain\iva\_recargo_equivalencia.py:125 [domain]  (parameters, parameter_id)

### _IVA_RATE_TO_VAT_KIND

count=2  kind=annotated_assign  class=sig-collision

layers: domain

- domain\invoices\_enums.py:76 [domain]  :dict[IvaRate, IvaRateKind]={IvaRate.RATE_4: IvaRateKind.SUP
- domain\iva\_invoice_classification.py:63 [domain]  :dict[IvaRate, IvaRateKind]={IvaRate.RATE_0: IvaRateKind.ZER

### _valid_invoice

count=2  kind=function  class=sig-collision

layers: domain

- domain\invoices\test_catalogue.py:29 [domain]  (invoice_number, kind, counterparty_name, counterparty_tax_id, counterparty_country, linked_transaction_ids)
- domain\invoices\test_models.py:40 [domain]  (kind, invoice_number, issued_at, counterparty_name, counterparty_tax_id, counterparty_country, currency, lines, payment_status, linked_transaction_ids)

### test_persistence_round_trip_preserves_catalogue

count=2  kind=function  class=name-collision

layers: domain

- domain\invoices\test_catalogue.py:67 [domain]  (tmp_path)
- domain\transactions\test_catalogue.py:153 [domain]  (tmp_path)

### cite

count=2  kind=function  class=sig-collision

layers: domain

- domain\iva\_lookup.py:53 [domain]  (category, on, catalogue)
- domain\normatives\_cite.py:43 [domain]  (reference, articulo)

### verify_catalogue

count=2  kind=function  class=sig-collision

layers: domain

- domain\iva\_verify.py:32 [domain]  (catalogue)
- domain\normatives\_verify.py:25 [domain]  (catalogue, settings)

### _root_from_settings

count=2  kind=function  class=name-collision

layers: domain

- domain\manuals\_loader.py:53 [domain]  (settings)
- domain\normatives\_loader.py:23 [domain]  (settings)

### load_catalogue

count=2  kind=function  class=sig-collision

layers: domain

- domain\manuals\_loader.py:251 [domain]  (specs, settings)
- domain\normatives\_loader.py:33 [domain]  (settings)

### _require_spanish

count=2  kind=function  class=sig-collision

layers: domain

- domain\manuals\_schema.py:81 [domain]  (text, field_name)
- domain\normatives\_schema.py:121 [domain]  (translatable, field_name)

### raise_on_errors

count=2  kind=function  class=name-collision

layers: domain

- domain\manuals\_verify.py:251 [domain]  (report)
- domain\normatives\_verify.py:99 [domain]  (report)

### _write_json

count=2  kind=function  class=name-collision

layers: domain

- domain\manuals\test_loader.py:34 [domain]  (path, payload)
- domain\manuals\test_verify.py:25 [domain]  (path, payload)

### _settings_with_root

count=2  kind=function  class=name-collision

layers: domain

- domain\manuals\test_loader.py:39 [domain]  (root)
- domain\normatives\test_loader.py:22 [domain]  (root)

### _populated_catalogue

count=2  kind=function  class=name-collision

layers: domain

- domain\modelos\test_calculation_repository_roundtrip.py:59 [domain]  ()
- domain\modelos\test_filing_record_repository_roundtrip.py:50 [domain]  ()

### SCHEMA_VERSION

count=2  kind=constant  class=name-collision

layers: domain

- domain\profile\assets\__init__.py:20 [domain]  '1'
- domain\profile\inventory\__init__.py:34 [domain]  '1'

### _quantize

count=2  kind=function  class=name-collision

layers: domain

- domain\profile\assets\__init__.py:240 [domain]  (value)
- domain\profile\inventory\__init__.py:503 [domain]  (value)

### _hijo_no_menor_3

count=2  kind=function  class=sig-collision

layers: domain

- domain\profile\test_deduccion_maternidad_0611.py:47 [domain]  ()
- domain\profile\test_incremento_guarderia_0613.py:48 [domain]  (gastos)

### _sample_raw

count=2  kind=function  class=sig-collision

layers: domain

- domain\transactions\test_catalogue.py:29 [domain]  (provider_id, amount, description)
- domain\transactions\test_models.py:30 [domain]  (provider_id, value_date, amount, description, source_row_index, counterparty)

### iva_wallet_app

count=2  kind=module_assign  class=sig-collision

layers: entrypoints

- entrypoints\cli\_app_live.py:58 [entrypoints]  typer.Typer(name='iva-wallet', help=tr('cli.app.live.iva_wal
- entrypoints\cli\_modelo.py:5268 [entrypoints]  typer.Typer(name='iva-wallet', help=tr('cli.app.modelo.iva_w

### _metric_line

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\_app_live.py:73 [entrypoints]  (key, value)
- entrypoints\cli\registry.py:48 [entrypoints]  (key, value)

### _label_for

count=2  kind=function  class=sig-collision

layers: entrypoints

- entrypoints\cli\_common.py:152 [entrypoints]  (listing)
- entrypoints\cli\_config\_google.py:575 [entrypoints]  (namespace)

### _per_bucket_backend

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\_config\test_apoderado.py:22 [entrypoints]  (tmp_path)
- entrypoints\cli\test_profile_lifecycle_verbs.py:679 [entrypoints]  (tmp_path)

### _fresh_storage_root

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_cold_start_no_profile.py:49 [entrypoints]  (tmp_path)
- entrypoints\cli\test_repair_bootstrap_exempt.py:48 [entrypoints]  (tmp_path)

### _run_aeat

count=2  kind=function  class=sig-collision

layers: entrypoints

- entrypoints\cli\test_config_custody_profile_lifecycle.py:62 [entrypoints]  (storage_root, args, extra_env)
- entrypoints\cli\test_root_fallback_write_guard.py:140 [entrypoints]  (storage_root, args)

### _imported_transaction_id

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_ledger_allocate_classification.py:25 [entrypoints]  (tmp_path)
- entrypoints\cli\test_ledger_ux_defect_cluster.py:46 [entrypoints]  (tmp_path)

### _seed_natural_person_profile

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_modelo_calculation_through_real_cli.py:81 [entrypoints]  (runtime_profile)
- entrypoints\cli\test_modelo_compare.py:104 [entrypoints]  (runtime_profile)

### _create_202_work_unit

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_modelo_discovery_defects.py:414 [entrypoints]  (period)
- entrypoints\cli\test_modelo_period_consistency.py:60 [entrypoints]  (period)

### _profile_rows

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_profile_create_taxpayer_type_paths.py:34 [entrypoints]  (runner, name)
- entrypoints\cli\test_profile_incn_new_entity_paths.py:43 [entrypoints]  (runner, name)

### _json_output

count=2  kind=function  class=name-collision

layers: entrypoints

- entrypoints\cli\test_profile_output_language.py:29 [entrypoints]  (result)
- entrypoints\cli\test_workflow_surface.py:33 [entrypoints]  (result)

### _covered_by_namespace

count=2  kind=function  class=name-collision

layers: locales

- locales\cli.py:116 [locales]  (key, namespace_prefixes)
- locales\manager.py:410 [locales]  (key, namespace_prefixes)

### _collect_violations

count=2  kind=function  class=name-collision

layers: test_cast_rationale_inventory.py, test_clock_enrollment_inventory.py

- test_cast_rationale_inventory.py:90 [test_cast_rationale_inventory.py]  ()
- test_clock_enrollment_inventory.py:178 [test_clock_enrollment_inventory.py]  ()

### _Fixture

count=2  kind=class  class=name-collision

layers: tests

- tests\fixtures\financial\n26\_generate.py:20 [tests]  []
- tests\fixtures\justificantes\_generate.py:37 [tests]  []

### _FIXTURES

count=2  kind=annotated_assign  class=sig-collision

layers: tests

- tests\fixtures\financial\n26\_generate.py:32 [tests]  :tuple[_Fixture, ...]=(_Fixture(filename='n26-savings-2024-0
- tests\fixtures\justificantes\_generate.py:51 [tests]  :tuple[_Fixture, ...]=(_Fixture(filename='modelo_130_2026Q1.

### _BOXES

count=2  kind=annotated_assign  class=sig-collision

layers: tests

- tests\fixtures\pdf_corpus\l3_synthetic\_generators\modelo_100_generator.py:67 [tests]  :tuple[CasillaBox, ...]=tuple((CasillaBox(casilla_id=casilla
- tests\fixtures\pdf_corpus\l3_synthetic\_generators\modelo_303_generator.py:76 [tests]  :tuple[CasillaBox, ...]=tuple((CasillaBox(casilla_id=casilla

### SRC_AEAT

count=2  kind=constant  class=name-collision

layers: tests

- tests\test_cross_module_imports_resolve.py:36 [tests]  Path(__file__).resolve().parents[1]
- tests\test_layout_import_smoke.py:20 [tests]  Path(__file__).resolve().parents[1]
## Section 2 -- Semantic-Identical Clusters (collapse candidates)

251 names classified semantic-identical (same kind + matching signature across all sites).
Key actionable production-code clusters:

**_STRICT_FROZEN** (10 sites, adapters + application)
Value: ConfigDict(strict=True, frozen=True, extra=forbid). Declared independently in 10 modules.
Consolidate into a single export from core.types or core.pydantic_config.

**_log / _logger / logger / log** (59+51+11+10=131 sites total)
All are get_logger(__name__) assignments. Four different names for the same semantic role.
Normalise to _log (the majority name).

**_column_index_to_letters** -- identical in multiple Google Sheets adapter files; consolidate.
**_validate_namespace / _validate_hmac** -- identical across adapters; copy-pasted helpers.
**_RecordingBrowserContext** -- identical test double across auth adapter test files; merge.
**_OkAuthProvider / _Draft / _IsolatedSettings** -- identical test doubles; consolidate.
**_Holder** (5 sites, core + domain) -- identical BaseModel wrapper for ID typing tests.
**fixed_master_key / store** -- identical persistence test fixtures; consolidate in conftest.

Full list (251 names): Y:/tmp/dup_stats.json key semantic_identical.
## Section 3 -- Signature-Collision Groups (rename candidates)

170 names with same name but differing signatures or values. Production-code priority entries:

**ExportFormatError** (2 sites, critical cross-layer class collision)
- adapters/outbound/aeat/export/_errors.py:12  bases=[ExportError, ValueError]
- application/export/_errors.py:8  bases=[CoreError]
Consumer resolution: adapters/_formats/*.py import adapters copy; application/_tabular.py imports
application copy. Error registry lists both by fully-qualified path. No accidental cross-import
today but name duplication is ongoing maintenance risk. Rename adapters version to
AdapterExportFormatError or merge hierarchy so both inherit from a shared base in core.

**_parse_decimal** (4 sites, cross-layer)
- adapters/inbound/justificante/_extract.py:211  sig=(raw, field)
- domain/calculations/registry/_export_parse.py:402  sig=(field, raw)  [REVERSED arg order]
- domain/deadlines/_profiles.py:203  sig=(raw)
- entrypoints/cli/_ledger.py:101  sig=(raw, label)
Reversed arg order in _export_parse.py is a latent caller-confusion bug. Consolidate in core.parsing.

**_parse_date** (5 sites, cross-layer)
- adapters/outbound/aeat/sede/_censo.py:250  sig=(raw, field)
- core/parsing/_dates.py:116/125/133  sig=(raw, fmt, on_error)  [canonical; 3 overloads]
- domain/deadlines/_profiles.py:196  sig=(raw)
Adapters and domain carry independent copies; should import from core.parsing._dates.

**_parse_datetime** (2 sites) -- same pattern; consolidate via core.parsing.

**PROJECT_ROOT** (4 sites)
- core/config.py:60  Path(__file__).resolve().parent.parent.parent.parent
- core/paths.py:23  same expression
- entrypoints/cli/test_retired_cli_literals.py:9  .parents[4]
- tests/test_release_config.py:33  .parents[3]
Two production copies; test copies use different depth offsets. Remove core/config.py copy.

**_payload** (13 sites) -- application/auth/_diagnostics.py:215 sig=(raw) is a PRODUCTION function
obscured by 12 test helper functions in entrypoints/cli/ all named _payload sig=(output).

**_service** (7 sites) -- entrypoints/cli/_modelo.py:4212 is a PRODUCTION function among 6 test
fixtures in application/live/ and domain/. Rename test fixtures.

**_transaction** (17), **_invoice** (14), **_revision** (7), **_observation** (7) -- test fixture
functions with varying signatures (0 to 13 params), cross-layer, no shared implementation.
## Section 4 -- Name-Collision Groups (rename for clarity)

28 names with structurally unrelated semantics across sites.

**ExportFormatError** -- different base classes across layers. Detail in Section 3.

**_RecordingPage** (5), **_RecordingBrowserSession** (5) -- independent test double classes
in 5 auth/browser adapter test files. Merge into shared adapter test helper module.

**Repository contract test classes** (15 names, 2-8 sites each):
TestDelete (8), TestClassificationGate (8), TestEmptyState (6), TestSaveLoad (6),
TestListAndIter (2), TestObservationContract (2), TestInvariants (2), TestBucketIsolation (7),
TestShow (6), TestVerify (2), TestListIter (2), TestSecureStorage (4), TestCapture (2),
TestLatest (2), TestNoWriteSurface (2).
Each tests same contract interface for a different repository. Rename to include subject:
TestFilingRepositoryDelete, TestSubmissionRepositoryDelete, etc.

**_EmptyAnswersBase** (4, application/wizard/) -- identical BaseModel subclass. Consolidate in wizard conftest.
**_Holder** (5, core + domain) -- identical BaseModel wrapper. Consolidate in tests/ conftest.
**TestCasillaDefinitionDataType** (5, domain) -- per-data-type. Rename to include data type name.
**secure_objects** (22, application) -- SecureObjectRepository fixture. Move to application conftest.
**cli_runner** (21, entrypoints) -- CliRunner() fixture sig=(). Single entrypoints/cli/conftest.py.
**runtime_profile** (13, cross-layer) -- RuntimeProfile fixture. Consolidate into shared conftest.
**_load_modelo** (8, domain) -- loads modelo from registry, all sig=(modelo_id). Consolidate.
**_modelo_130_snapshot** (7, adapters+domain) -- snapshot fixture. Consolidate.
**schema** (8, application+domain) -- user profile schema sig=(). Consolidate.
**repos** (7, application/modelo/) -- repository bundle. Move to conftest.
**runner** (6, cross-layer) -- CliRunner() instance. Consolidate.
**_scrub_value** (7, core/logging.py:124-147) -- may be inner/conditional defs, not 7 separate
module-scope functions. Verify before action; possible false-positive from nested def in if-blocks.
**_call_name** (6) -- AST inspection helper sig=(node). Likely semantic-identical. Consolidate in tests/.
**_discover_test_modules** (5) -- consolidate into tests/ utility module.
## Section 5 -- Cross-Layer Distribution

152 of the 449 duplicate names span 2+ layer boundaries.

Key cross-layer collision pairs:

adapters + application: ExportFormatError (class collision), _STRICT_FROZEN (10x duplication),
  _payload (production + test confusion), _isolated_backend (28 fixture copies).

application + domain: _revision (7), _observation (7), _invoice (14), _transaction (17),
  _modelo (7), _database_bytes (8), runtime_profile (13), schema (8), _file_fingerprint (4).

adapters + domain: _modelo_130_snapshot (7), _parse_decimal (4), _parse_datetime (2).

adapters + core + domain: _parse_date (5 sites across 3 layers).

core + entrypoints + tests: PROJECT_ROOT (value drift risk between copies).

application + domain + entrypoints: _service (1 production + 6 test fixtures mixed).

adapters + application + domain + entrypoints: _filed_observation (4 sites).

## Consumer-Side Import Resolution

ExportFormatError: adapters consumers import from adapters/outbound/aeat/export/_errors.py
(ValueError-based). Application consumers from application/export/_errors.py (CoreError-based).
Error registry lists both by fully-qualified path. No accidental cross-import today.

_STRICT_FROZEN: no cross-module imports. 10x definition bloat; no runtime ambiguity.

PROJECT_ROOT: core/config.py and core/paths.py each define it from their own __file__.
Both resolve to the same path only if at the same directory depth from root.
Verify before removing the duplicate.

_parse_decimal reversed arg order at domain/calculations/registry/_export_parse.py:402
sig=(field, raw) vs all others sig=(raw, field). Positional callers would swap args silently.

## Module(s)

src/aeat/_data/, src/aeat/adapters/, src/aeat/application/, src/aeat/core/,
src/aeat/diagnostics/, src/aeat/domain/, src/aeat/entrypoints/, src/aeat/locales/, src/aeat/tests/

## File(s)

Key production-code duplication sites:
- src/aeat/adapters/outbound/aeat/export/_errors.py (ExportFormatError adapters version)
- src/aeat/application/export/_errors.py (ExportFormatError application version)
- src/aeat/core/parsing/_dates.py (_parse_date canonical; 3 overloads at :116/:125/:133)
- src/aeat/core/config.py (PROJECT_ROOT duplicate of core/paths.py)
- src/aeat/core/paths.py (PROJECT_ROOT canonical)
- src/aeat/adapters/outbound/aeat/sede/_declarations.py (_STRICT_FROZEN site 1)
- src/aeat/application/auth/_catalogue.py (_STRICT_FROZEN site 2 of 10)
- src/aeat/domain/calculations/registry/_export_parse.py (_parse_decimal reversed args at :402)
- src/aeat/adapters/inbound/justificante/_extract.py (_parse_decimal at :211)
- src/aeat/entrypoints/cli/_ledger.py (_parse_decimal at :101)
- src/aeat/entrypoints/cli/_modelo.py (_service production function at :4212)
- src/aeat/application/auth/_diagnostics.py (_payload production function at :215)
- src/aeat/core/logging.py (_scrub_value x7 same-file declarations at :124-147)

## Related

None.