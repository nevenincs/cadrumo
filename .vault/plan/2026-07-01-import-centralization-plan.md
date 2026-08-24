---
tags:
  - '#plan'
  - '#import-centralization'
date: '2026-07-01'
tier: L4
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-07-01-import-centralization-research]]'
modified: '2026-08-24'
body_hash: 'sha256:a7a4b809b416910772efda08e3a1ccc7c74a15c90f77dcc99a5047133261f790'
---

<!-- RETIRED: P01, S365, S366, S367, S370, S371, S372, S373, S374, S375, S376, S380, S381, S385, S386 -->

# `import-centralization` plan

## Steps

## Description

The on-disk import-hygiene scanner (`dev/import_hygiene_scan.py`) enumerates every
cross-package private import in `src/aeat`: 2465 total sites, split into 866
production and 1599 test-only, spanning 549 distinct (owning package, symbol) pairs
and 250 distinct production files. The accepted `import-centralization` ADR resolves
this onto one canonical top-level export per symbol: cross-package consumers import
only from the owning package's facade, never from a private submodule. This plan
serializes that ruling into six Waves. Wave W01 promotes every symbol a foreign
package reaches into its owning package's `__all__` (34 owning packages, 149
symbols; the 20 underscore-named candidates get an individual per-symbol
disposition Step rather than mechanical promotion, per the ADR's three-way rule).
Wave W02 rewrites the 250 production consumer files onto those facades, one Phase
per importer area and one Step per file so no two parallel workers ever touch the
same file. Wave W03 closes the findings the scanner cannot mechanically fix: the
undocumented Family-2 bridge, the `__main__.py` shim-classifier false positive, the
withholding-to-percepciones Spanish-stem rename, the dead `OutputLanguage`
re-export, the two `setup_answers` dynamic-import retargets, and the retirement of
7 duplicated app-layer re-exports in favour of their sole domain-layer source. Wave
W04 wires the scanner itself into CI as a ratcheting, then hard-zero, gate that
supersedes the two narrower pre-existing gates. Wave W05 repoints the 1599
test-only sites, batched one Step per owning package across 4 architecture-layer
Phases. Wave W06 verifies the campaign and runs the mandatory honesty review before
closeout. The accepted ADR and its grounding research (see the `related:`
frontmatter above) carry the rulings and the on-disk discovery every Step below
implements.

## Epic intent

Collapse the 549 cross-package private-import pairs (250 production files, 34 owning packages needing facade promotion, 1599 test-only sites) surfaced by the on-disk import-hygiene scanner onto one canonical top-level export per symbol, per the accepted 2026-07-01-import-centralization-adr. Tracked as a follow-on hardening campaign under milestone 0.1.5 (Codebase Restructure), continuing the per-module sanitization and structural-integrity lineage opened by the aeat-restructure execution pipeline (issue 476, EPIC 475); closes into the same milestone's structural-integrity charter (issue 120) rather than opening a new external artifact. Multi-week, multi-agent: parallel subagent dispatch per owning package (Wave W01) and per importer area (Wave W02), sequenced strictly before the Family-2/3 and umbrella-retirement cleanup (Wave W03), the CI gate wiring (Wave W04), the test-only sweep (Wave W05), and verification and closeout (Wave W06).

## Wave `W01` - facade promotions

Promote every symbol that a foreign package reaches across a private submodule into its owning package's public __all__ facade, batched one Phase per owning package, largest consumer-count first. This Wave is the hard precondition for Wave W02: no consumer import can be rewritten onto a facade that does not yet export the symbol. The 20 underscore-named candidates get individual per-symbol disposition Steps per the ADR three-way rule (rename-to-public and promote, expose a narrower public API, or remove the reach) rather than mechanical bulk promotion.

### Phase `W01.P02` - promote aeat.domain.modelos facade exports

Promote every symbol aeat.domain.modelos consumers reach cross-package into `aeat.domain.modelos.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P02.S01` - Promote `CalculationRevisionId`, `Dt12WindowEligibility`, `FilingRecordId`, `LedgerEvidenceRow`, `LedgerFilingEvidence`, `LedgerFilingSnapshot`, `LedgerFilingStalenessVerdict`, `LedgerRowFingerprint`, `ManualFactBasisEntry`, `Modelo184ShareSumError`, `Modelo347ThresholdError`, `ModeloError`, `ModeloExportError`, `ModeloValidationError`, `VerificationReportId`, `WorkUnitState`, `compute_dt12_reduccion_plan_pensiones`, `compute_sal_reserva_especial_dotacion`, `diff_ledger_fingerprints`, `dt12_regime_window_eligibility`, `m349_nif_number_for_export`, `snapshot_fingerprint`, `validate_m184_member_share_sum`, `validate_m347_threshold` to `aeat.domain.modelos.__all__` with eager re-exports so the 67 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/modelos/__init__.py`.

### Phase `W01.P03` - promote aeat.adapters.outbound.google facade exports

Promote every symbol aeat.adapters.outbound.google consumers reach cross-package into `aeat.adapters.outbound.google.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P03.S02` - Promote `CalcSheetsApplyResult`, `DriveConfig`, `PullResult`, `RowSetEdit`, `apply_export_plan`, `compute_from_pull`, `delete_session`, `load_client`, `load_drive_config`, `load_metadata`, `load_token`, `pull_operator_edits`, `resolve_active_profile`, `run_login_flow`, `save_client`, `save_drive_config`, `save_metadata`, `save_token` to `aeat.adapters.outbound.google.__all__` with eager re-exports so the 26 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/outbound/google/__init__.py`.

### Phase `W01.P04` - promote aeat.core facade exports

Promote every symbol aeat.core consumers reach cross-package into `aeat.core.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P04.S03` - Promote `Modelo`, `OUT_OF_SCOPE_OBLIGATIONS`, `Period`, `PeriodError`, `PostFilingEventKind`, `ResultDisposition`, `STRICT_FROZEN_CONFIG`, `TaxDomain`, `UNMODELED_OBLIGATIONS`, `classify_post_filing_event_kind`, `post_filing_event_is_actionable`, `resolve_active_bucket_id`, `result_disposition_is_refund` to `aeat.core.__all__` with eager re-exports so the 35 existing cross-package consumer site(s) can import from the facade; `src/aeat/core/__init__.py`.

### Phase `W01.P05` - promote aeat.application.live facade exports

Promote every symbol aeat.application.live consumers reach cross-package into `aeat.application.live.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P05.S04` - Promote `CensoSnapshot`, `CensoSnapshotService`, `PersistedExpedientesSnapshot`, `PersistedNotificationsSnapshot`, `VerifyObservation`, `censo_snapshot_object_key`, `expedientes_snapshot_object_key`, `notifications_snapshot_object_key`, `verify_observation_object_key` to `aeat.application.live.__all__` with eager re-exports so the 12 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/live/__init__.py`.

### Phase `W01.P06` - promote aeat.domain.iva_compensation facade exports

Promote every symbol aeat.domain.iva_compensation consumers reach cross-package into `aeat.domain.iva_compensation.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P06.S05` - Promote `DEFAULT_MAX_WALLET_AGE_DAYS`, `IvaCompensationAuthoritySource`, `IvaCompensationReconciliationDecision`, `IvaCompensationWalletObservationProtocol`, `local_recurrence_authority_source`, `reconcile_iva_compensation_wallet`, `validate_wallet_matches_snapshot` to `aeat.domain.iva_compensation.__all__` with eager re-exports so the 13 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/iva_compensation/__init__.py`.
- [x] `W01.P06.S06` - Decide and apply the public-surface disposition for `_period_sort_key` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.iva_compensation._carry_forward` and consumed cross-package from `src/aeat/application/calculations/_iva_compensation_history.py`; `src/aeat/domain/iva_compensation/__init__.py`.

### Phase `W01.P07` - promote aeat.adapters.inbound.pdf facade exports

Promote every symbol aeat.adapters.inbound.pdf consumers reach cross-package into `aeat.adapters.inbound.pdf.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P07.S07` - Promote `TEXT_VALUE_GROUP`, `extract_pages_text_concatenated`, `extract_pages_text_from_bytes`, `extract_pages_text_from_path`, `extract_pages_text_with_fast_path`, `sha256_file`, `source_pdf_reference_path` to `aeat.adapters.inbound.pdf.__all__` with eager re-exports so the 14 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/inbound/pdf/__init__.py`.

### Phase `W01.P08` - promote aeat.domain.user_profile facade exports

Promote every symbol aeat.domain.user_profile consumers reach cross-package into `aeat.domain.user_profile.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P08.S08` - Promote `CarriedSecureObject`, `CoverageManifest`, `ProfileExportError`, `UserProfileError`, `UserProfileValidationError`, `utc_now` to `aeat.domain.user_profile.__all__` with eager re-exports so the 10 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/user_profile/__init__.py`.

### Phase `W01.P09` - promote aeat.adapters.outbound.aeat.sede facade exports

Promote every symbol aeat.adapters.outbound.aeat.sede consumers reach cross-package into `aeat.adapters.outbound.aeat.sede.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P09.S09` - Promote `BrowserAdapterTypeError`, `GroiSedeDriver`, `NifIvaCheckSedeDriver`, `filed_declaracion_observation_object_key`, `iva_compensation_wallet_observation_object_key` to `aeat.adapters.outbound.aeat.sede.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/outbound/aeat/sede/__init__.py`.

### Phase `W01.P10` - promote aeat.domain.contribuyente facade exports

Promote every symbol aeat.domain.contribuyente consumers reach cross-package into `aeat.domain.contribuyente.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P10.S10` - Promote `FiscalResidency`, `compute_deduccion_maternidad_0611`, `modelo100_ecivil_export_code`, `register_profile_keys` to `aeat.domain.contribuyente.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/contribuyente/__init__.py`.
- [x] `W01.P10.S11` - Decide and apply the public-surface disposition for `_profile_keys` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.contribuyente._keys` and consumed cross-package from `src/aeat/application/user_profile/_keys_validation.py`; `src/aeat/domain/contribuyente/__init__.py`.

### Phase `W01.P11` - promote aeat.application.calculations facade exports

Promote every symbol aeat.application.calculations consumers reach cross-package into `aeat.application.calculations.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P11.S12` - Promote `M111_NO_RETENCIONES_PROFILE_PATH`, `MaritimeExemptionResult`, `m111_no_retenciones_periods_for_bucket` to `aeat.application.calculations.__all__` with eager re-exports so the 4 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/calculations/__init__.py`.
- [x] `W01.P11.S13` - Decide and apply the public-surface disposition for `_IvaWalletDecisionEnvelopePayload` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.calculations._observations_repository` and consumed cross-package from `src/aeat/application/user_profile/_custody_carry.py`; `src/aeat/application/calculations/__init__.py`.
- [x] `W01.P11.S14` - Decide and apply the public-surface disposition for `_MODELO_303_IVA_COMPENSATION_BINDING_ID` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.calculations._binding_prefill` and consumed cross-package from `src/aeat/application/modelo/_calculation_actions.py`; `src/aeat/application/calculations/__init__.py`.

### Phase `W01.P12` - promote aeat.domain.calculations.registry facade exports

Promote every symbol aeat.domain.calculations.registry consumers reach cross-package into `aeat.domain.calculations.registry.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P12.S15` - Promote `KNOWN_PROFILE_FLAG_ADVISORY_FIELDS`, `select_revision` to `aeat.domain.calculations.registry.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P12.S16` - Decide and apply the public-surface disposition for `_build_modelo_definition_from_data` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.calculations.registry._loader` and consumed cross-package from `src/aeat/locales/_modelo_manager.py`; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P12.S17` - Decide and apply the public-surface disposition for `_load_modelo_manifest` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.calculations.registry._loader` and consumed cross-package from `src/aeat/locales/_modelo_manager.py`; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P12.S18` - Decide and apply the public-surface disposition for `_load_modelo_revisions` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.calculations.registry._loader` and consumed cross-package from `src/aeat/locales/_modelo_manager.py`; `src/aeat/domain/calculations/registry/__init__.py`.

### Phase `W01.P13` - promote aeat.adapters.persistence.storage.master_key facade exports

Promote every symbol aeat.adapters.persistence.storage.master_key consumers reach cross-package into `aeat.adapters.persistence.storage.master_key.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P13.S19` - Promote `evaluate_idle`, `get_active_master_key`, `has_active_bucket_session` to `aeat.adapters.persistence.storage.master_key.__all__` with eager re-exports so the 8 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/persistence/storage/master_key/__init__.py`.
- [x] `W01.P13.S20` - Decide and apply the public-surface disposition for `_active_session` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.persistence.storage.master_key._active_session` and consumed cross-package from `src/aeat/adapters/persistence/storage/runtime.py, src/aeat/adapters/persistence/storage/sql/secure_objects.py`; `src/aeat/adapters/persistence/storage/master_key/__init__.py`.

### Phase `W01.P14` - promote aeat.adapters.persistence.storage.crypto facade exports

Promote every symbol aeat.adapters.persistence.storage.crypto consumers reach cross-package into `aeat.adapters.persistence.storage.crypto.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P14.S21` - Promote `decrypt_encrypted_bytes_column`, `decrypt_secure_object_payload`, `encrypt_secure_object_payload`, `secure_object_payload_aad` to `aeat.adapters.persistence.storage.crypto.__all__` with eager re-exports so the 9 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/persistence/storage/crypto/__init__.py`.

### Phase `W01.P15` - promote aeat.application.wizard facade exports

Promote every symbol aeat.application.wizard consumers reach cross-package into `aeat.application.wizard.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P15.S22` - Promote `WizardStatusError`, `WizardStatusReport`, `build_wizard_status`, `load_active_taxpayer_profile` to `aeat.application.wizard.__all__` with eager re-exports so the 4 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/wizard/__init__.py`.

### Phase `W01.P16` - promote aeat.application.user_profile facade exports

Promote every symbol aeat.application.user_profile consumers reach cross-package into `aeat.application.user_profile.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P16.S23` - Promote `list_profile_key_records`, `validate_profile_values` to `aeat.application.user_profile.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/user_profile/__init__.py`.
- [x] `W01.P16.S24` - Decide and apply the public-surface disposition for `_refuse_duplicate_label` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.user_profile._orchestration` and consumed cross-package from `src/aeat/application/wizard/_commands.py`; `src/aeat/application/user_profile/__init__.py`.
- [x] `W01.P16.S25` - Decide and apply the public-surface disposition for `_require_registered_label` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.user_profile._orchestration` and consumed cross-package from `src/aeat/application/wizard/_commands.py`; `src/aeat/application/user_profile/__init__.py`.

### Phase `W01.P17` - promote aeat.core.parsing facade exports

Promote every symbol aeat.core.parsing consumers reach cross-package into `aeat.core.parsing.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P17.S26` - Decide and apply the public-surface disposition for `_parse_bool` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.core.parsing._utils` and consumed cross-package from `src/aeat/domain/calculations/registry/_export_parse.py, src/aeat/domain/user_profile/_values.py`; `src/aeat/core/parsing/__init__.py`.
- [x] `W01.P17.S27` - Decide and apply the public-surface disposition for `_parse_date` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.core.parsing._dates` and consumed cross-package from `src/aeat/adapters/outbound/aeat/sede/_notifications.py`; `src/aeat/core/parsing/__init__.py`.
- [x] `W01.P17.S28` - Decide and apply the public-surface disposition for `_parse_iso8601_date` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.core.parsing._dates` and consumed cross-package from `src/aeat/application/calculations/_row_set_assembly.py, src/aeat/application/user_profile/_validation.py, src/aeat/domain/contribuyente/__init__.py, src/aeat/domain/contribuyente/_descendant_facts.py, src/aeat/domain/contribuyente/family.py, src/aeat/domain/invoices/_models.py, src/aeat/domain/user_profile/_values.py`; `src/aeat/core/parsing/__init__.py`.

### Phase `W01.P18` - promote aeat.application.aggregation facade exports

Promote every symbol aeat.application.aggregation consumers reach cross-package into `aeat.application.aggregation.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P18.S29` - Promote `MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND`, `compute_ledger_filing_evidence`, `compute_ledger_filing_snapshot` to `aeat.application.aggregation.__all__` with eager re-exports so the 3 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/aggregation/__init__.py`.

### Phase `W01.P19` - promote aeat.adapters.persistence.storage.envelope facade exports

Promote every symbol aeat.adapters.persistence.storage.envelope consumers reach cross-package into `aeat.adapters.persistence.storage.envelope.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P19.S30` - Decide and apply the public-surface disposition for `_build_aad` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.persistence.storage.envelope._envelope` and consumed cross-package from `src/aeat/adapters/persistence/storage/_rotation.py`; `src/aeat/adapters/persistence/storage/envelope/__init__.py`.
- [x] `W01.P19.S31` - Decide and apply the public-surface disposition for `_derive_envelope_key` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.persistence.storage.envelope._envelope` and consumed cross-package from `src/aeat/adapters/persistence/storage/_rotation.py`; `src/aeat/adapters/persistence/storage/envelope/__init__.py`.

### Phase `W01.P20` - promote aeat.adapters.persistence.storage.sql facade exports

Promote every symbol aeat.adapters.persistence.storage.sql consumers reach cross-package into `aeat.adapters.persistence.storage.sql.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P20.S32` - Promote `Base`, `SecureObjectRow` to `aeat.adapters.persistence.storage.sql.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade; `src/aeat/adapters/persistence/storage/sql/__init__.py`.

### Phase `W01.P21` - promote aeat.domain.invoices facade exports

Promote every symbol aeat.domain.invoices consumers reach cross-package into `aeat.domain.invoices.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P21.S33` - Promote `find_invoice`, `find_unmatched` to `aeat.domain.invoices.__all__` with eager re-exports so the 4 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/invoices/__init__.py`.

### Phase `W01.P22` - promote aeat.adapters.outbound.storage facade exports

Promote every symbol aeat.adapters.outbound.storage consumers reach cross-package into `aeat.adapters.outbound.storage.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P22.S34` - Decide and apply the public-surface disposition for `_build_google_credentials` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.outbound.storage._factory` and consumed cross-package from `src/aeat/entrypoints/cli/_config/_google_sync_calc.py, src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`; `src/aeat/adapters/outbound/storage/__init__.py`.
- [x] `W01.P22.S35` - Decide and apply the public-surface disposition for `_resolve_drive_root_folder_id` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.outbound.storage._factory` and consumed cross-package from `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`; `src/aeat/adapters/outbound/storage/__init__.py`.

### Phase `W01.P23` - promote aeat.application.storage.calc_sheets facade exports

Promote every symbol aeat.application.storage.calc_sheets consumers reach cross-package into `aeat.application.storage.calc_sheets.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P23.S36` - Promote `OperatorInputScenario`, `verify_modelo_parity` to `aeat.application.storage.calc_sheets.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/storage/calc_sheets/__init__.py`.

### Phase `W01.P24` - promote aeat.domain facade exports

Promote every symbol aeat.domain consumers reach cross-package into `aeat.domain.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P24.S37` - Promote `canonical_decimal_string` to `aeat.domain.__all__` with eager re-exports so the 6 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/__init__.py`.

### Phase `W01.P25` - promote aeat.domain.attachments facade exports

Promote every symbol aeat.domain.attachments consumers reach cross-package into `aeat.domain.attachments.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P25.S38` - Promote `is_link_only_mime_type` to `aeat.domain.attachments.__all__` with eager re-exports so the 1 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/attachments/__init__.py`.

### Phase `W01.P26` - promote aeat.adapters.outbound.aeat.auth facade exports

Promote every symbol aeat.adapters.outbound.aeat.auth consumers reach cross-package into `aeat.adapters.outbound.aeat.auth.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P26.S39` - Decide and apply the public-surface disposition for `_classify_identity` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.adapters.outbound.aeat.auth._clave_movil` and consumed cross-package from `src/aeat/application/auth/_operator_probes.py`; `src/aeat/adapters/outbound/aeat/auth/__init__.py`.

### Phase `W01.P27` - promote aeat.domain.buckets facade exports

Promote every symbol aeat.domain.buckets consumers reach cross-package into `aeat.domain.buckets.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P27.S40` - Promote `BucketEventHistoryRepositoryProtocol` to `aeat.domain.buckets.__all__` with eager re-exports so the 24 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/buckets/__init__.py`.

### Phase `W01.P28` - promote aeat.domain.renta facade exports

Promote every symbol aeat.domain.renta consumers reach cross-package into `aeat.domain.renta.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P28.S41` - Promote `RentaValidationError` to `aeat.domain.renta.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/renta/__init__.py`.

### Phase `W01.P29` - promote aeat.application.workflow facade exports

Promote every symbol aeat.application.workflow consumers reach cross-package into `aeat.application.workflow.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P29.S42` - Promote `AuthState` to `aeat.application.workflow.__all__` with eager re-exports so the 1 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/workflow/__init__.py`.

### Phase `W01.P30` - promote aeat.domain.calculations facade exports

Promote every symbol aeat.domain.calculations consumers reach cross-package into `aeat.domain.calculations.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P30.S43` - Promote `CasillaFieldKind` to `aeat.domain.calculations.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/calculations/__init__.py`.

### Phase `W01.P31` - promote aeat.application.ledger facade exports

Promote every symbol aeat.application.ledger consumers reach cross-package into `aeat.application.ledger.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P31.S44` - Promote `PurchaseInvoiceEvidenceRepository` to `aeat.application.ledger.__all__` with eager re-exports so the 1 existing cross-package consumer site(s) can import from the facade; `src/aeat/application/ledger/__init__.py`.

### Phase `W01.P32` - promote aeat.application.modelo facade exports

Promote every symbol aeat.application.modelo consumers reach cross-package into `aeat.application.modelo.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P32.S45` - Decide and apply the public-surface disposition for `_m036_declaration_object_key` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.application.modelo._m036_lifecycle` and consumed cross-package from `src/aeat/application/user_profile/_custody_carry.py`; `src/aeat/application/modelo/__init__.py`.

### Phase `W01.P33` - promote aeat.core.i18n facade exports

Promote every symbol aeat.core.i18n consumers reach cross-package into `aeat.core.i18n.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P33.S46` - Promote `clear_output_language_cache` to `aeat.core.i18n.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade; `src/aeat/core/i18n/__init__.py`.

### Phase `W01.P34` - promote aeat.domain.portals facade exports

Promote every symbol aeat.domain.portals consumers reach cross-package into `aeat.domain.portals.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P34.S47` - Promote `portal_host_name` to `aeat.domain.portals.__all__` with eager re-exports so the 1 existing cross-package consumer site(s) can import from the facade; `src/aeat/domain/portals/__init__.py`.

### Phase `W01.P35` - promote aeat.entrypoints.cli facade exports

Promote every symbol aeat.entrypoints.cli consumers reach cross-package into `aeat.entrypoints.cli.__all__` (or resolve its underscore-named reach individually) so Wave W02 consumer rewrites have a facade to land on.

- [x] `W01.P35.S48` - Decide and apply the public-surface disposition for `_command_schema_refs` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.entrypoints.cli._app_contract` and consumed cross-package from `src/aeat/entrypoints/mcp/_tools.py`; `src/aeat/entrypoints/cli/__init__.py`.

## Wave `W02` - consumer import rewrites

Rewrite every production cross-package private import onto the Wave W01 promoted facades, one Phase per importer area (largest file-count first), one Step per consumer file so no two parallel workers ever edit the same file. Behavior-preserving only: no symbol relocation, no signature change. Depends on Wave W01 completing for every owning package a given Phase's files reach into.

### Phase `W02.P36` - rewire aeat.application.modelo consumers

Repoint every production import in `aeat.application.modelo` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P36.S49` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/__init__.py`.
- [x] `W02.P36.S50` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_action_errors.py`.
- [x] `W02.P36.S51` - Rewire 17 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/modelo/_amendment_actions.py`.
- [x] `W02.P36.S52` - Rewire 12 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/modelo/_art109_activity_income.py`.
- [x] `W02.P36.S53` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_art20_advisory.py`.
- [x] `W02.P36.S54` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_binding_resolution.py`.
- [x] `W02.P36.S55` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `W02.P36.S56` - Rewire 32 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.core`, `aeat.domain.calculations.registry`, `aeat.domain.contribuyente`, `aeat.domain.modelos`; `src/aeat/application/modelo/_calculate_input.py`.
- [x] `W02.P36.S57` - Rewire 33 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.application.calculations`, `aeat.application.live`, `aeat.core`, `aeat.domain.buckets`, `aeat.domain.calculations.registry`, `aeat.domain.invoices`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W02.P36.S58` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_calculation_aggregation_context.py`.
- [x] `W02.P36.S59` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_calculation_helpers.py`.
- [x] `W02.P36.S60` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.application.user_profile`, `aeat.domain.modelos`; `src/aeat/application/modelo/_calculation_preparation.py`.
- [x] `W02.P36.S61` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`, `aeat.domain.modelos`; `src/aeat/application/modelo/_calculation_resolution.py`.
- [x] `W02.P36.S62` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`; `src/aeat/application/modelo/_calculation_source_policy.py`.
- [x] `W02.P36.S63` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_dt12_advisory.py`.
- [x] `W02.P36.S64` - Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.domain.buckets`, `aeat.domain.iva_compensation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_export.py`.
- [x] `W02.P36.S65` - Rewire 20 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/modelo/_external_import_actions.py`.
- [x] `W02.P36.S66` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_filed_revision_observation.py`.
- [x] `W02.P36.S67` - Rewire 17 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/modelo/_filing_actions.py`.
- [x] `W02.P36.S68` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/modelo/_history.py`.
- [x] `W02.P36.S69` - Rewire 13 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.application.user_profile`, `aeat.domain.iva_compensation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_iva_wallet_gate.py`.
- [x] `W02.P36.S70` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [x] `W02.P36.S71` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_ledger_evidence_gate.py`.
- [x] `W02.P36.S72` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/application/modelo/_m210_rate.py`.
- [x] `W02.P36.S73` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`; `src/aeat/application/modelo/_maritime_preview.py`.
- [x] `W02.P36.S74` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_objective_estimation_advisory.py`.
- [x] `W02.P36.S75` - Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_participation_index_rebuild.py`.
- [x] `W02.P36.S76` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.domain.modelos`; `src/aeat/application/modelo/_profile_binding.py`.
- [x] `W02.P36.S77` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.domain.modelos`; `src/aeat/application/modelo/_profile_readiness_gate.py`.
- [x] `W02.P36.S78` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_projection.py`.
- [x] `W02.P36.S79` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.domain.modelos`; `src/aeat/application/modelo/_reconcile.py`.
- [x] `W02.P36.S80` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.calculations.registry`; `src/aeat/application/modelo/_registry_discovery.py`.
- [x] `W02.P36.S81` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_registry_helpers.py`.
- [x] `W02.P36.S82` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_registry_resources.py`.
- [x] `W02.P36.S83` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_required_binding_gate.py`.
- [x] `W02.P36.S84` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_result_disposition_resolution.py`.
- [x] `W02.P36.S85` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_result_summary.py`.
- [x] `W02.P36.S86` - Rewire 19 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `W02.P36.S87` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`, `aeat.domain.modelos`; `src/aeat/application/modelo/_revision_replay_inputs.py`.
- [x] `W02.P36.S88` - Rewire 13 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_selectors.py`.
- [x] `W02.P36.S89` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_semantic_role_resolution.py`.
- [x] `W02.P36.S90` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_taxation_comparison.py`.
- [x] `W02.P36.S91` - Rewire 58 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.application.calculations`, `aeat.application.workflow`, `aeat.core`, `aeat.domain.buckets`, `aeat.domain.calculations.registry`, `aeat.domain.iva_compensation`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `W02.P36.S92` - Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`, `aeat.domain.modelos`; `src/aeat/application/modelo/_verification_cross_period.py`.
- [x] `W02.P36.S93` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`, `aeat.domain.modelos`; `src/aeat/application/modelo/_work_addressing.py`.
- [x] `W02.P36.S94` - Rewire 10 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.contribuyente`, `aeat.domain.modelos`; `src/aeat/application/modelo/_work_lifecycle.py`.
- [x] `W02.P36.S95` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.deadlines`, `aeat.domain.modelos`; `src/aeat/application/modelo/_work_plazo.py`.
- [x] `W02.P36.S96` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/modelo/_workflow_gate.py`.

### Phase `W02.P37` - rewire aeat.adapters.persistence consumers

Repoint every production import in `aeat.adapters.persistence` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P37.S97` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.fincas`; `src/aeat/adapters/persistence/profile/fincas.py`.
- [x] `W02.P37.S98` - Rewire 61 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.blob_store`, `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.envelope`, `aeat.adapters.persistence.storage.master_key`, `aeat.adapters.persistence.storage.secret_store`; `src/aeat/adapters/persistence/storage/__init__.py`.
- [x] `W02.P37.S99` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.blob_store`, `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.envelope`, `aeat.adapters.persistence.storage.master_key`; `src/aeat/adapters/persistence/storage/_rotation.py`.
- [x] `W02.P37.S100` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.attachments`; `src/aeat/adapters/persistence/storage/attachment.py`.
- [x] `W02.P37.S101` - Rewire 10 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.envelope`, `aeat.adapters.persistence.storage.master_key`; `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`.
- [x] `W02.P37.S102` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.secret_store`; `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py`.
- [x] `W02.P37.S103` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `W02.P37.S104` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/persistence/storage/bucket/_manifest.py`.
- [x] `W02.P37.S105` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.master_key`; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [x] `W02.P37.S106` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.master_key`, `aeat.core.time`; `src/aeat/adapters/persistence/storage/envelope/_envelope.py`.
- [x] `W02.P37.S107` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.sql`; `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py`.
- [x] `W02.P37.S108` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W02.P37.S109` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`.
- [x] `W02.P37.S110` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_master_key_derivation.py`.
- [x] `W02.P37.S111` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_master_key_ephemeral.py`.
- [x] `W02.P37.S112` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W02.P37.S113` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W02.P37.S114` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py`.
- [x] `W02.P37.S115` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.master_key`; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `W02.P37.S116` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.blob_store`, `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.envelope`, `aeat.adapters.persistence.storage.master_key`, `aeat.core.time`; `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`.
- [x] `W02.P37.S117` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W02.P37.S118` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`; `src/aeat/adapters/persistence/storage/sql/_secure_object_integrity.py`.
- [x] `W02.P37.S119` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.master_key`; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.

### Phase `W02.P38` - rewire aeat.entrypoints.cli consumers

Repoint every production import in `aeat.entrypoints.cli` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P38.S120` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W02.P38.S121` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.portals`; `src/aeat/entrypoints/cli/_app_live_portals_cli.py`.
- [x] `W02.P38.S122` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`; `src/aeat/entrypoints/cli/_app_live_verify_cli.py`.
- [x] `W02.P38.S123` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W02.P38.S124` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`; `src/aeat/entrypoints/cli/_config/_capabilities_cli.py`.
- [x] `W02.P38.S125` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W02.P38.S126` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`; `src/aeat/entrypoints/cli/_config/_google_folder.py`.
- [x] `W02.P38.S127` - Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`, `aeat.adapters.outbound.storage`, `aeat.application.storage.calc_sheets`; `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`.
- [x] `W02.P38.S128` - Rewire 22 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.master_key`, `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.core`, `aeat.domain.buckets`, `aeat.domain.user_profile`; `src/aeat/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `W02.P38.S129` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.invoices`, `aeat.domain.iva`; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P38.S130` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`, `aeat.adapters.outbound.storage`; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P38.S131` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`, `aeat.domain.transactions`; `src/aeat/entrypoints/cli/_ledger_llm_cli.py`.
- [x] `W02.P38.S132` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [x] `W02.P38.S133` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`, `aeat.domain.deadlines`; `src/aeat/entrypoints/cli/_ledger_support.py`.
- [x] `W02.P38.S134` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`.
- [x] `W02.P38.S135` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.renta`; `src/aeat/entrypoints/cli/_modelo_maritime_cli.py`.
- [x] `W02.P38.S136` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W02.P38.S137` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/entrypoints/cli/_modelo_records_cli.py`.
- [x] `W02.P38.S138` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/entrypoints/cli/_modelo_work_revision_payloads.py`.
- [x] `W02.P38.S139` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.calculations`; `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `W02.P38.S140` - Rewire 30 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`, `aeat.application.calculations`, `aeat.application.live`, `aeat.application.modelo`, `aeat.application.overview`, `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.core`, `aeat.domain.justificante`, `aeat.domain.modelos`; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W02.P38.S141` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.overview`, `aeat.core`; `src/aeat/entrypoints/cli/_overview_rendering.py`.

### Phase `W02.P39` - rewire aeat.adapters.outbound consumers

Repoint every production import in `aeat.adapters.outbound` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P39.S142` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/outbound/aeat/auth/_authenticator_types.py`.
- [x] `W02.P39.S143` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.user_profile`; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W02.P39.S144` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/outbound/aeat/auth/certificate.py`.
- [x] `W02.P39.S145` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/adapters/outbound/aeat/browser/_site_health_parsers.py`.
- [x] `W02.P39.S146` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`; `src/aeat/adapters/outbound/aeat/sede/_auth_state.py`.
- [x] `W02.P39.S147` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [x] `W02.P39.S148` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P39.S149` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py`.
- [x] `W02.P39.S150` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W02.P39.S151` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`, `aeat.core.parsing`; `src/aeat/adapters/outbound/aeat/sede/_notifications.py`.
- [x] `W02.P39.S152` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`; `src/aeat/adapters/outbound/aeat/sede/_walker.py`.
- [x] `W02.P39.S153` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`, `aeat.domain.justificante`; `src/aeat/adapters/outbound/aeat/verify/__init__.py`.
- [x] `W02.P39.S154` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.storage`; `src/aeat/adapters/outbound/google/_api.py`.
- [x] `W02.P39.S155` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.storage`; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [x] `W02.P39.S156` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.storage`, `aeat.application.storage.calc_sheets`, `aeat.core.time`; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [x] `W02.P39.S157` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.storage`; `src/aeat/adapters/outbound/google/_document_link_resolver.py`.
- [x] `W02.P39.S158` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`; `src/aeat/adapters/outbound/storage/_factory.py`.

### Phase `W02.P40` - rewire aeat.application.ledger consumers

Repoint every production import in `aeat.application.ledger` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P40.S159` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_classification.py`.
- [x] `W02.P40.S160` - Rewire 10 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.attachments`, `aeat.domain.buckets`, `aeat.domain.invoices`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_common.py`.
- [x] `W02.P40.S161` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_export.py`.
- [x] `W02.P40.S162` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_import.py`.
- [x] `W02.P40.S163` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.invoices`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_lifecycle.py`.
- [x] `W02.P40.S164` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.attachments`, `aeat.domain.buckets`, `aeat.domain.invoices`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_manual.py`.
- [x] `W02.P40.S165` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_actions_split_merge.py`.
- [x] `W02.P40.S166` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`, `aeat.domain.buckets`; `src/aeat/application/ledger/_business_operation_invoice.py`.
- [x] `W02.P40.S167` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`, `aeat.domain.buckets`; `src/aeat/application/ledger/_evidence.py`.
- [x] `W02.P40.S168` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/application/ledger/_evidence_textlayer.py`.
- [x] `W02.P40.S169` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.buckets`, `aeat.domain.transactions`; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W02.P40.S170` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`, `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/application/ledger/_models.py`.
- [x] `W02.P40.S171` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/ledger/_participation_read.py`.
- [x] `W02.P40.S172` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`; `src/aeat/application/ledger/_review_projection.py`.
- [x] `W02.P40.S173` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.transactions`; `src/aeat/application/ledger/_rule_repository.py`.

### Phase `W02.P41` - rewire aeat.application.user_profile consumers

Repoint every production import in `aeat.application.user_profile` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P41.S174` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_aggregate.py`.
- [x] `W02.P41.S175` - Rewire 14 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`, `aeat.domain.modelos`, `aeat.domain.transactions`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_bundle.py`.
- [x] `W02.P41.S176` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`; `src/aeat/application/user_profile/_capabilities.py`.
- [x] `W02.P41.S177` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`, `aeat.application.live`, `aeat.domain.buckets`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_censo_sync.py`.
- [x] `W02.P41.S178` - Rewire 39 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`, `aeat.adapters.persistence.storage.envelope`, `aeat.adapters.persistence.storage.sql`, `aeat.application.aggregation`, `aeat.application.calculations`, `aeat.application.evidence`, `aeat.application.filing`, `aeat.application.ledger`, `aeat.application.live`, `aeat.application.modelo`, `aeat.domain.filing`, `aeat.domain.justificante`, `aeat.domain.submission`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_custody_carry.py`.
- [x] `W02.P41.S179` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`; `src/aeat/application/user_profile/_keys_validation.py`.
- [x] `W02.P41.S180` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`; `src/aeat/application/user_profile/_language_resolver.py`.
- [x] `W02.P41.S181` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_lifecycle.py`.
- [x] `W02.P41.S182` - Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage`, `aeat.adapters.persistence.storage.bucket`, `aeat.adapters.persistence.storage.master_key`, `aeat.application.workflow`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `W02.P41.S183` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`, `aeat.domain.user_profile`; `src/aeat/application/user_profile/_profile_repository.py`.
- [x] `W02.P41.S184` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.deadlines`; `src/aeat/application/user_profile/_projections.py`.
- [x] `W02.P41.S185` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`; `src/aeat/application/user_profile/_repository.py`.
- [x] `W02.P41.S186` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`, `aeat.domain.deadlines`; `src/aeat/application/user_profile/_testing.py`.
- [x] `W02.P41.S187` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/application/user_profile/_validation.py`.

### Phase `W02.P42` - rewire aeat.adapters.inbound consumers

Repoint every production import in `aeat.adapters.inbound` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P42.S188` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`.
- [x] `W02.P42.S189` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`.
- [x] `W02.P42.S190` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/borrador/_schema.py`.
- [x] `W02.P42.S191` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P42.S192` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`.
- [x] `W02.P42.S193` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`; `src/aeat/adapters/inbound/declaracion/_schema.py`.
- [x] `W02.P42.S194` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`; `src/aeat/adapters/inbound/financial/__init__.py`.
- [x] `W02.P42.S195` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`, `aeat.domain.justificante`; `src/aeat/adapters/inbound/justificante/_extract.py`.
- [x] `W02.P42.S196` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.justificante`; `src/aeat/adapters/inbound/justificante/_parser.py`.
- [x] `W02.P42.S197` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`, `aeat.domain.justificante`; `src/aeat/adapters/inbound/justificante/_parsers/__init__.py`.
- [x] `W02.P42.S198` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.inbound.pdf`, `aeat.domain.justificante`; `src/aeat/adapters/inbound/justificante/_parsers/_pdfplumber_backend.py`.

### Phase `W02.P43` - rewire aeat.application.calculations consumers

Repoint every production import in `aeat.application.calculations` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P43.S199` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W02.P43.S200` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`; `src/aeat/application/calculations/_iva_compensation_annual_partition.py`.
- [x] `W02.P43.S201` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `W02.P43.S202` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/application/calculations/_iva_wallet_balance.py`.
- [x] `W02.P43.S203` - Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.domain.iva_compensation`; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W02.P43.S204` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`; `src/aeat/application/calculations/_m111_no_retenciones.py`.
- [x] `W02.P43.S205` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.renta`; `src/aeat/application/calculations/_maritime_exemption_service.py`.
- [x] `W02.P43.S206` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`; `src/aeat/application/calculations/_multi_year.py`.
- [x] `W02.P43.S207` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W02.P43.S208` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.application.storage.calc_sheets`, `aeat.application.user_profile`; `src/aeat/application/calculations/_relation_prefill.py`.
- [x] `W02.P43.S209` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/application/calculations/_row_set_assembly.py`.

### Phase `W02.P44` - rewire aeat.domain.calculations consumers

Repoint every production import in `aeat.domain.calculations` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P44.S210` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/domain/calculations/_export_field_kind.py`.
- [x] `W02.P44.S211` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/calculations/registry/_export_parse.py`.
- [x] `W02.P44.S212` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/domain/calculations/registry/_invoice_bindings.py`.
- [x] `W02.P44.S213` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`; `src/aeat/domain/calculations/registry/_ledger_bindings.py`.
- [x] `W02.P44.S214` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`; `src/aeat/domain/calculations/registry/_queries.py`.
- [x] `W02.P44.S215` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P44.S216` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.user_profile`; `src/aeat/domain/calculations/registry/_validate.py`.

### Phase `W02.P45` - rewire aeat.application.auth consumers

Repoint every production import in `aeat.application.auth` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P45.S217` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/application/auth/_acquisition_lock.py`.
- [x] `W02.P45.S218` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`; `src/aeat/application/auth/_actions.py`.
- [x] `W02.P45.S219` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`; `src/aeat/application/auth/_operator.py`.
- [x] `W02.P45.S220` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.auth`, `aeat.application.user_profile`, `aeat.application.workflow`; `src/aeat/application/auth/_operator_probes.py`.
- [x] `W02.P45.S221` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`; `src/aeat/application/auth/_operator_scope.py`.
- [x] `W02.P45.S222` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.core.time`; `src/aeat/application/auth/_sessions.py`.

### Phase `W02.P46` - rewire aeat.application.filing consumers

Repoint every production import in `aeat.application.filing` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P46.S223` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.submission`; `src/aeat/application/filing/_calculate.py`.
- [x] `W02.P46.S224` - Rewire 17 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.calculations`, `aeat.domain.calculations.registry`, `aeat.domain.contribuyente`, `aeat.domain.submission`; `src/aeat/application/filing/_export.py`.
- [x] `W02.P46.S225` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`; `src/aeat/application/filing/_history_models.py`.
- [x] `W02.P46.S226` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain`, `aeat.domain.submission`; `src/aeat/application/filing/_review.py`.
- [x] `W02.P46.S227` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.filing`; `src/aeat/application/filing/_testing_registry.py`.
- [x] `W02.P46.S228` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.wizard`, `aeat.application.workflow`; `src/aeat/application/filing/runtime.py`.

### Phase `W02.P47` - rewire aeat.application.overview consumers

Repoint every production import in `aeat.application.overview` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P47.S229` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.deadlines`; `src/aeat/application/overview/_agenda.py`.
- [x] `W02.P47.S230` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.deadlines`, `aeat.domain.modelos`; `src/aeat/application/overview/_backlog.py`.
- [x] `W02.P47.S231` - Rewire 22 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.sede`, `aeat.application.live`, `aeat.core`, `aeat.domain.calculations.registry`, `aeat.domain.deadlines`, `aeat.domain.justificante`, `aeat.domain.modelos`; `src/aeat/application/overview/_calendar.py`.
- [x] `W02.P47.S232` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.domain.deadlines`; `src/aeat/application/overview/_calendar_models.py`.
- [x] `W02.P47.S233` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`, `aeat.core`, `aeat.domain.deadlines`; `src/aeat/application/overview/_coverage.py`.
- [x] `W02.P47.S234` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core`, `aeat.core.resources`, `aeat.domain.calculations.registry`, `aeat.domain.deadlines`; `src/aeat/application/overview/_explain.py`.

### Phase `W02.P48` - rewire aeat.application.wizard consumers

Repoint every production import in `aeat.application.wizard` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P48.S235` - Rewire 8 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`, `aeat.domain.deadlines`; `src/aeat/application/wizard/_catalogue.py`.
- [x] `W02.P48.S236` - Rewire 12 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.domain.contribuyente`, `aeat.domain.deadlines`; `src/aeat/application/wizard/_commands.py`.
- [x] `W02.P48.S237` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`; `src/aeat/application/wizard/_compiler.py`.
- [x] `W02.P48.S238` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`; `src/aeat/application/wizard/_persistence.py`.
- [x] `W02.P48.S239` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.domain.deadlines`; `src/aeat/application/wizard/_status.py`.

### Phase `W02.P49` - rewire aeat.application.aggregation consumers

Repoint every production import in `aeat.application.aggregation` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P49.S240` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W02.P49.S241` - Rewire 11 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/aggregation/_ledger_filing_snapshot.py`.
- [x] `W02.P49.S242` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W02.P49.S243` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`; `src/aeat/application/aggregation/_source_profile.py`.

### Phase `W02.P50` - rewire aeat.application.invoices consumers

Repoint every production import in `aeat.application.invoices` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P50.S244` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.invoices`; `src/aeat/application/invoices/__init__.py`.
- [x] `W02.P50.S245` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.invoices`; `src/aeat/application/invoices/_queries.py`.
- [x] `W02.P50.S246` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.invoices`, `aeat.domain.transactions`; `src/aeat/application/invoices/_reconciliation.py`.
- [x] `W02.P50.S247` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.aggregation`, `aeat.domain.invoices`; `src/aeat/application/invoices/_source_resolver.py`.

### Phase `W02.P51` - rewire aeat.application.workflow consumers

Repoint every production import in `aeat.application.workflow` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P51.S248` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.browser`, `aeat.application.auth`, `aeat.application.review`, `aeat.application.user_profile`; `src/aeat/application/workflow/_models.py`.
- [x] `W02.P51.S249` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`; `src/aeat/application/workflow/_persistence.py`.
- [x] `W02.P51.S250` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`; `src/aeat/application/workflow/_profile_health.py`.
- [x] `W02.P51.S251` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.submission`; `src/aeat/application/workflow/_protocols.py`.

### Phase `W02.P52` - rewire aeat.application.review consumers

Repoint every production import in `aeat.application.review` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P52.S252` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`; `src/aeat/application/review/_actions.py`.
- [x] `W02.P52.S253` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`; `src/aeat/application/review/_adapters.py`.
- [x] `W02.P52.S254` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`, `aeat.core.time`; `src/aeat/application/review/_models.py`.

### Phase `W02.P53` - rewire aeat.application.storage consumers

Repoint every production import in `aeat.application.storage` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P53.S255` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`; `src/aeat/application/storage/calc_sheets/_evidence.py`.
- [x] `W02.P53.S256` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.google`; `src/aeat/application/storage/calc_sheets/_parity_harness.py`.
- [x] `W02.P53.S257` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/application/storage/calc_sheets/_records.py`.

### Phase `W02.P54` - rewire aeat.core.resources consumers

Repoint every production import in `aeat.core.resources` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P54.S258` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.errors`; `src/aeat/core/resources/_errors.py`.
- [x] `W02.P54.S259` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`; `src/aeat/core/resources/_repos/iva_catalogues.py`.
- [x] `W02.P54.S260` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`; `src/aeat/core/resources/_repos/iva_rate_tables.py`.

### Phase `W02.P55` - rewire aeat.domain.contribuyente consumers

Repoint every production import in `aeat.domain.contribuyente` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P55.S261` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/contribuyente/__init__.py`.
- [x] `W02.P55.S262` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/contribuyente/_descendant_facts.py`.
- [x] `W02.P55.S263` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/contribuyente/family.py`.

### Phase `W02.P56` - rewire aeat.domain.user_profile consumers

Repoint every production import in `aeat.domain.user_profile` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P56.S264` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`, `aeat.domain.transactions`; `src/aeat/domain/user_profile/_portable_export.py`.
- [x] `W02.P56.S265` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations`; `src/aeat/domain/user_profile/_registry_contract.py`.
- [x] `W02.P56.S266` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/user_profile/_values.py`.

### Phase `W02.P57` - rewire aeat.application.evidence consumers

Repoint every production import in `aeat.application.evidence` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P57.S267` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`; `src/aeat/application/evidence/_models.py`.
- [x] `W02.P57.S268` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`; `src/aeat/application/evidence/_service.py`.

### Phase `W02.P58` - rewire aeat.application.live consumers

Repoint every production import in `aeat.application.live` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P58.S269` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`, `aeat.domain.modelos`; `src/aeat/application/live/_filed_observation_persistence.py`.
- [x] `W02.P58.S270` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.domain.iva_compensation`; `src/aeat/application/live/_iva_remote_state.py`.

### Phase `W02.P59` - rewire aeat.core.observability consumers

Repoint every production import in `aeat.core.observability` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P59.S271` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/core/observability/_context.py`.
- [x] `W02.P59.S272` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/core/observability/_models.py`.

### Phase `W02.P60` - rewire aeat.domain.invoices consumers

Repoint every production import in `aeat.domain.invoices` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P60.S273` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`; `src/aeat/domain/invoices/_enums.py`.
- [x] `W02.P60.S274` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.parsing`; `src/aeat/domain/invoices/_models.py`.

### Phase `W02.P61` - rewire aeat.domain.modelos consumers

Repoint every production import in `aeat.domain.modelos` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P61.S275` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/domain/modelos/_calculation_revision.py`.
- [x] `W02.P61.S276` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`; `src/aeat/domain/modelos/_work_unit.py`.

### Phase `W02.P62` - rewire aeat.domain.transactions consumers

Repoint every production import in `aeat.domain.transactions` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P62.S277` - Rewire 4 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.iva`; `src/aeat/domain/transactions/_models.py`.
- [x] `W02.P62.S278` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/domain/transactions/_raw_transaction.py`.

### Phase `W02.P63` - rewire aeat.application.bucket_maintenance consumers

Repoint every production import in `aeat.application.bucket_maintenance` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P63.S279` - Rewire 40 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage`, `aeat.adapters.persistence.storage.bucket`, `aeat.adapters.persistence.storage.crypto`, `aeat.adapters.persistence.storage.master_key`, `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.core`, `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.user_profile`; `src/aeat/application/bucket_maintenance/_service.py`.

### Phase `W02.P64` - rewire aeat.application.config_reset consumers

Repoint every production import in `aeat.application.config_reset` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P64.S280` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`; `src/aeat/application/config_reset.py`.

### Phase `W02.P65` - rewire aeat.application.diagnostics consumers

Repoint every production import in `aeat.application.diagnostics` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P65.S281` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.wizard`, `aeat.application.workflow`; `src/aeat/application/diagnostics.py`.

### Phase `W02.P66` - rewire aeat.application.inventory consumers

Repoint every production import in `aeat.application.inventory` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P66.S282` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`; `src/aeat/application/inventory/_service.py`.

### Phase `W02.P67` - rewire aeat.application.registry consumers

Repoint every production import in `aeat.application.registry` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P67.S283` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.manuals`; `src/aeat/application/registry/_corpus.py`.

### Phase `W02.P68` - rewire aeat.application.setup consumers

Repoint every production import in `aeat.application.setup` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P68.S284` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`; `src/aeat/application/setup/_service.py`.

### Phase `W02.P69` - rewire aeat.application.state_projection consumers

Repoint every production import in `aeat.application.state_projection` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P69.S285` - Rewire 9 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.user_profile`, `aeat.application.workflow`, `aeat.domain.modelos`; `src/aeat/application/state_projection.py`.

### Phase `W02.P70` - rewire aeat.application.storage_write_policy consumers

Repoint every production import in `aeat.application.storage_write_policy` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P70.S286` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.modelo`; `src/aeat/application/storage_write_policy.py`.

### Phase `W02.P71` - rewire aeat.application.transactions consumers

Repoint every production import in `aeat.application.transactions` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P71.S287` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.transactions`; `src/aeat/application/transactions/_import.py`.

### Phase `W02.P72` - rewire aeat.core.config consumers

Repoint every production import in `aeat.core.config` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P72.S288` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`; `src/aeat/core/config.py`.

### Phase `W02.P73` - rewire aeat.core.corpus_manifest consumers

Repoint every production import in `aeat.core.corpus_manifest` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P73.S289` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/core/corpus_manifest/__init__.py`.

### Phase `W02.P74` - rewire aeat.core.json_contract consumers

Repoint every production import in `aeat.core.json_contract` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P74.S290` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.observability`; `src/aeat/core/json_contract.py`.

### Phase `W02.P75` - rewire aeat.core.logging consumers

Repoint every production import in `aeat.core.logging` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P75.S291` - Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.observability`; `src/aeat/core/logging.py`.

### Phase `W02.P76` - rewire aeat.domain.attachments consumers

Repoint every production import in `aeat.domain.attachments` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P76.S292` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`; `src/aeat/domain/attachments/_models.py`.

### Phase `W02.P77` - rewire aeat.domain.deadlines consumers

Repoint every production import in `aeat.domain.deadlines` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P77.S293` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`; `src/aeat/domain/deadlines/_models.py`.

### Phase `W02.P78` - rewire aeat.domain.fincas consumers

Repoint every production import in `aeat.domain.fincas` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P78.S294` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/domain/fincas/_imputacion_parameters.py`.

### Phase `W02.P79` - rewire aeat.domain.iva consumers

Repoint every production import in `aeat.domain.iva` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P79.S295` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/domain/iva/_recargo_equivalencia.py`.

### Phase `W02.P80` - rewire aeat.entrypoints.mcp consumers

Repoint every production import in `aeat.entrypoints.mcp` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P80.S296` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.entrypoints.cli`; `src/aeat/entrypoints/mcp/_tools.py`.

### Phase `W02.P81` - rewire aeat.locales._fstring_registry consumers

Repoint every production import in `aeat.locales._fstring_registry` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P81.S297` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.contribuyente`, `aeat.domain.deadlines`; `src/aeat/locales/_fstring_registry.py`.

### Phase `W02.P82` - rewire aeat.locales._modelo_manager consumers

Repoint every production import in `aeat.locales._modelo_manager` that reaches into a foreign package private module onto that package promoted top-level facade, behavior-preserving only.

- [x] `W02.P82.S298` - Rewire 6 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`; `src/aeat/locales/_modelo_manager.py`.

## Wave `W03` - shim retirement, dynamic-import retargeting, and umbrella facade retirement

Close the Family 2 and Family 3 findings the scanner cannot mechanically promote or rewrite: document the 6 kept bridges, exclude __main__.py from the shim classifier, rename the withholding-labelled percepciones repository module in one atomic relocation commit, drop the dead OutputLanguage re-export, retarget the two setup_answers dynamic imports at their public facades, and retire the 7 duplicated app-layer re-exports (CalculationRevision, CalculationRevisionAmendmentKind, ExternalEvidenceKind, WorkUnit from application.modelo; link_transaction, suggest_reconciliations, verify_link_consistency from application.invoices) in favour of their sole domain-layer source, repointing every consumer. save_envelope and DEFAULT_IVA_GENERAL_RATE_PCT were investigated and need no action. Depends on Waves W01 and W02 completing for the packages this Wave touches.

### Phase `W03.P87` - family 2 bridge hygiene and dynamic-import retargeting

Close the shim-classifier findings the scanner can resolve without a symbol move: document the one undocumented bridge, exempt the standard __main__ entrypoint pattern from the shim classifier, and retarget the two setup_answers lazy dynamic imports at their public facades.

- [x] `W03.P87.S364` - Add a bridge-justification docstring to _utils.py matching the five other documented Family-2 bridges (applicability.py, taxpayer_model.py, _ids.py, _schemas.py, _playwright.py), explaining why normalise_key and utc_now are re-exported through this shared workflow-application surface rather than imported directly from aeat.domain.contribuyente and aeat.core.time at each call site; `src/aeat/application/workflow/_utils.py`.
- [x] `W03.P87.S368` - Retarget setup_answers._m() to lazily import the public aeat.domain.deadlines.taxpayer_model bridge instead of the private aeat.domain.deadlines._models submodule; `src/aeat/core/setup_answers.py`.
- [x] `W03.P87.S369` - Retarget setup_answers._ccaa() to resolve CCAA from the public aeat.domain.contribuyente facade instead of the private aeat.domain.contribuyente._ccaa submodule; `src/aeat/core/setup_answers.py`.
- [x] `W03.P87.S388` - Exclude __main__.py modules from the shim/pure-reexport classifier in the import-hygiene scanner, since a module whose only statement is from .cli import app plus an if __name__ == "__main__": app() guard is the standard entrypoint pattern, not a Family-2 shim; `dev/import_hygiene_scan.py`.
- [x] `W03.P87.S389` - Rename _withholding_observations_repository.py to _percepciones_observations_repository.py, using Spanish-stem naming since retencion is already taken by a sibling module, rename its test module, and repoint every consumer import in one atomic explicit-path relocation commit, running pytest --collect-only -q clean before committing; `src/aeat/application/aggregation/_withholding_observations_repository.py`.
- [x] `W03.P87.S390` - Drop the dead OutputLanguage re-export from entrypoints.cli._config.__all__, confirming no live consumer imports it from that facade before removing it (the canonical source is aeat.core.i18n); `src/aeat/entrypoints/cli/_config/__init__.py`.

### Phase `W03.P88` - umbrella facade retirement

Retire the 7 duplicated app-layer re-exports that violate strict single-source per the operator-decided ruling: CalculationRevision, CalculationRevisionAmendmentKind, ExternalEvidenceKind, and WorkUnit from application.modelo (sole source domain.modelos), and link_transaction, suggest_reconciliations, and verify_link_consistency from application.invoices (sole source domain.invoices). One Step per retired symbol, repointing every one of the roughly 180 extra consumer sites onto the sole canonical source in that symbol's atomic commit. save_envelope and DEFAULT_IVA_GENERAL_RATE_PCT were investigated and require no action.

- [x] `W03.P88.S391` - Retire CalculationRevision from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos; `src/aeat/application/modelo/__init__.py`.
- [x] `W03.P88.S392` - Retire CalculationRevisionAmendmentKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos; `src/aeat/application/modelo/__init__.py`.
- [x] `W03.P88.S393` - Retire ExternalEvidenceKind from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos; `src/aeat/application/modelo/__init__.py`.
- [x] `W03.P88.S394` - Retire WorkUnit from application.modelo.__all__ and repoint every consumer onto its sole canonical source aeat.domain.modelos; `src/aeat/application/modelo/__init__.py`.
- [x] `W03.P88.S395` - Retire link_transaction from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices; `src/aeat/application/invoices/__init__.py`.
- [x] `W03.P88.S396` - Retire suggest_reconciliations from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices; `src/aeat/application/invoices/__init__.py`.
- [x] `W03.P88.S397` - Retire verify_link_consistency from application.invoices.__all__ and repoint every consumer onto its sole canonical source aeat.domain.invoices; `src/aeat/application/invoices/__init__.py`.

## Wave `W04` - import-hygiene gate wiring and supersession

Make dev/import_hygiene_scan.py the authoritative CI gate for cross-package private imports: seed its exception allowlist from the two narrower existing gates, add a ratcheting production-Family-1 baseline JSON that fails the build if the current count exceeds the committed baseline and shrinks in the same commit as any fix, wire it into the pytest/CI surface, and supersede test_public_api_boundaries.py and test_architecture_boundaries.py. Depends on Waves W01 through W03 landing enough of the reduction that the ratchet baseline is meaningful.

### Phase `W04.P89` - import-hygiene gate wiring and supersession

Make dev/import_hygiene_scan.py the authoritative CI gate for cross-package private imports, ratcheting the production-Family-1 baseline down to zero across the campaign, and retire the two narrower gates it now supersedes.

- [x] `W04.P89.S377` - Seed dev/import_hygiene_scan.py exception allowlist from the pre-existing exceptions in test_public_api_boundaries.py and test_architecture_boundaries.py so the new gate starts from the same tolerated baseline; `dev/import_hygiene_scan.py`.
- [x] `W04.P89.S378` - Add a ratcheting production-Family-1 baseline JSON that fails the gate when the current cross-package private-import count exceeds the committed baseline, and shrink the baseline in the same commit as any fix that reduces the count; `dev/import_hygiene_scan.py`.
- [x] `W04.P89.S379` - Wire dev/import_hygiene_scan.py into the pytest/CI surface as the authoritative import-hygiene gate; `src/aeat/tests/test_import_hygiene_gate.py`.
- [x] `W04.P89.S398` - Supersede test_public_api_boundaries.py and test_architecture_boundaries.py now that the ratcheting scanner gate covers their checks, retiring the narrower assertions while keeping any check the scanner does not yet cover; `src/aeat/tests/test_public_api_boundaries.py`.

## Wave `W05` - test-only import sweep

Repoint the 1599 test-only cross-package private import sites (65 owning packages, 484 test files) onto the Wave W01 facades, batched one Step per owning package and grouped into 4 architecture-layer Phases (domain, application, adapters, core-entrypoints-locales-tests). Runs last because test fixtures and support modules are the least production-risk surface and the most numerous, so they should not block the production reduction. Depends on Wave W01 for every owning package a test file reaches into.

### Phase `W05.P83` - domain test-only import sweep

Repoint every test-only cross-package private import reaching a domain owning package onto that package promoted facade, one Step per owning package.

- [x] `W05.P83.S299` - Rewire the 427 test-only cross-package private import site(s) across 138 test file(s) reaching into `aeat.domain.modelos` onto its promoted top-level facade; `src/aeat/domain/modelos (test consumers)`.
- [x] `W05.P83.S300` - Rewire the 69 test-only cross-package private import site(s) across 43 test file(s) reaching into `aeat.domain.calculations.registry` onto its promoted top-level facade; `src/aeat/domain/calculations/registry (test consumers)`.
- [x] `W05.P83.S301` - Rewire the 37 test-only cross-package private import site(s) across 31 test file(s) reaching into `aeat.domain.deadlines` onto its promoted top-level facade; `src/aeat/domain/deadlines (test consumers)`.
- [x] `W05.P83.S302` - Rewire the 44 test-only cross-package private import site(s) across 29 test file(s) reaching into `aeat.domain.iva_compensation` onto its promoted top-level facade; `src/aeat/domain/iva_compensation (test consumers)`.
- [x] `W05.P83.S303` - Rewire the 26 test-only cross-package private import site(s) across 20 test file(s) reaching into `aeat.domain.transactions` onto its promoted top-level facade; `src/aeat/domain/transactions (test consumers)`.
- [x] `W05.P83.S304` - Rewire the 21 test-only cross-package private import site(s) across 12 test file(s) reaching into `aeat.domain.user_profile` onto its promoted top-level facade; `src/aeat/domain/user_profile (test consumers)`.
- [x] `W05.P83.S305` - Rewire the 15 test-only cross-package private import site(s) across 10 test file(s) reaching into `aeat.domain.contribuyente` onto its promoted top-level facade; `src/aeat/domain/contribuyente (test consumers)`.
- [x] `W05.P83.S306` - Rewire the 21 test-only cross-package private import site(s) across 10 test file(s) reaching into `aeat.domain.filing` onto its promoted top-level facade; `src/aeat/domain/filing (test consumers)`.
- [x] `W05.P83.S307` - Rewire the 11 test-only cross-package private import site(s) across 8 test file(s) reaching into `aeat.domain.buckets` onto its promoted top-level facade; `src/aeat/domain/buckets (test consumers)`.
- [x] `W05.P83.S308` - Rewire the 12 test-only cross-package private import site(s) across 7 test file(s) reaching into `aeat.domain.submission` onto its promoted top-level facade; `src/aeat/domain/submission (test consumers)`.
- [x] `W05.P83.S309` - Rewire the 6 test-only cross-package private import site(s) across 6 test file(s) reaching into `aeat.domain` onto its promoted top-level facade; `src/aeat/domain (test consumers)`.
- [x] `W05.P83.S310` - Rewire the 6 test-only cross-package private import site(s) across 6 test file(s) reaching into `aeat.domain.iva` onto its promoted top-level facade; `src/aeat/domain/iva (test consumers)`.
- [x] `W05.P83.S311` - Rewire the 7 test-only cross-package private import site(s) across 4 test file(s) reaching into `aeat.domain.invoices` onto its promoted top-level facade; `src/aeat/domain/invoices (test consumers)`.
- [x] `W05.P83.S312` - Rewire the 6 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.domain.attachments` onto its promoted top-level facade; `src/aeat/domain/attachments (test consumers)`.
- [x] `W05.P83.S313` - Rewire the 7 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.domain.portals` onto its promoted top-level facade; `src/aeat/domain/portals (test consumers)`.
- [x] `W05.P83.S314` - Rewire the 4 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.domain.usage_ratios` onto its promoted top-level facade; `src/aeat/domain/usage_ratios (test consumers)`.
- [x] `W05.P83.S315` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.justificante` onto its promoted top-level facade; `src/aeat/domain/justificante (test consumers)`.
- [x] `W05.P83.S316` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.retention` onto its promoted top-level facade; `src/aeat/domain/retention (test consumers)`.
- [x] `W05.P83.S317` - Rewire the 2 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.renta` onto its promoted top-level facade; `src/aeat/domain/renta (test consumers)`.
- [x] `W05.P83.S318` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.calculations` onto its promoted top-level facade; `src/aeat/domain/calculations (test consumers)`.
- [x] `W05.P83.S319` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.calculations.registry.tests` onto its promoted top-level facade; `src/aeat/domain/calculations/registry/tests (test consumers)`.
- [x] `W05.P83.S320` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.manuals` onto its promoted top-level facade; `src/aeat/domain/manuals (test consumers)`.
- [x] `W05.P83.S321` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.auth.apoderamientos` onto its promoted top-level facade; `src/aeat/domain/auth/apoderamientos (test consumers)`.
- [x] `W05.P83.S322` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.fincas` onto its promoted top-level facade; `src/aeat/domain/fincas (test consumers)`.

### Phase `W05.P84` - application test-only import sweep

Repoint every test-only cross-package private import reaching a application owning package onto that package promoted facade, one Step per owning package.

- [x] `W05.P84.S323` - Rewire the 232 test-only cross-package private import site(s) across 113 test file(s) reaching into `aeat.application.user_profile` onto its promoted top-level facade; `src/aeat/application/user_profile (test consumers)`.
- [x] `W05.P84.S324` - Rewire the 140 test-only cross-package private import site(s) across 106 test file(s) reaching into `aeat.application.workflow` onto its promoted top-level facade; `src/aeat/application/workflow (test consumers)`.
- [x] `W05.P84.S325` - Rewire the 41 test-only cross-package private import site(s) across 30 test file(s) reaching into `aeat.application.calculations` onto its promoted top-level facade; `src/aeat/application/calculations (test consumers)`.
- [x] `W05.P84.S326` - Rewire the 39 test-only cross-package private import site(s) across 19 test file(s) reaching into `aeat.application.aggregation` onto its promoted top-level facade; `src/aeat/application/aggregation (test consumers)`.
- [x] `W05.P84.S327` - Rewire the 39 test-only cross-package private import site(s) across 14 test file(s) reaching into `aeat.application.live` onto its promoted top-level facade; `src/aeat/application/live (test consumers)`.
- [x] `W05.P84.S328` - Rewire the 18 test-only cross-package private import site(s) across 14 test file(s) reaching into `aeat.application.modelo` onto its promoted top-level facade; `src/aeat/application/modelo (test consumers)`.
- [x] `W05.P84.S329` - Rewire the 18 test-only cross-package private import site(s) across 7 test file(s) reaching into `aeat.application.auth` onto its promoted top-level facade; `src/aeat/application/auth (test consumers)`.
- [x] `W05.P84.S330` - Rewire the 5 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.application.storage.calc_sheets` onto its promoted top-level facade; `src/aeat/application/storage/calc_sheets (test consumers)`.
- [x] `W05.P84.S331` - Rewire the 10 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.application.ledger` onto its promoted top-level facade; `src/aeat/application/ledger (test consumers)`.
- [x] `W05.P84.S332` - Rewire the 7 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.application.wizard` onto its promoted top-level facade; `src/aeat/application/wizard (test consumers)`.
- [x] `W05.P84.S333` - Rewire the 5 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.application.filing` onto its promoted top-level facade; `src/aeat/application/filing (test consumers)`.
- [x] `W05.P84.S334` - Rewire the 3 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.application.review` onto its promoted top-level facade; `src/aeat/application/review (test consumers)`.
- [x] `W05.P84.S335` - Rewire the 2 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.application.bucket_maintenance` onto its promoted top-level facade; `src/aeat/application/bucket_maintenance (test consumers)`.
- [x] `W05.P84.S336` - Rewire the 3 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.application.evidence` onto its promoted top-level facade; `src/aeat/application/evidence (test consumers)`.
- [x] `W05.P84.S337` - Rewire the 2 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.application.overview` onto its promoted top-level facade; `src/aeat/application/overview (test consumers)`.
- [x] `W05.P84.S338` - Rewire the 3 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.application.invoices` onto its promoted top-level facade; `src/aeat/application/invoices (test consumers)`.

### Phase `W05.P85` - adapters test-only import sweep

Repoint every test-only cross-package private import reaching a adapters owning package onto that package promoted facade, one Step per owning package.

- [x] `W05.P85.S339` - Rewire the 42 test-only cross-package private import site(s) across 23 test file(s) reaching into `aeat.adapters.persistence.storage.bucket` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage/bucket (test consumers)`.
- [x] `W05.P85.S340` - Rewire the 24 test-only cross-package private import site(s) across 21 test file(s) reaching into `aeat.adapters.persistence.storage.crypto` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage/crypto (test consumers)`.
- [x] `W05.P85.S341` - Rewire the 24 test-only cross-package private import site(s) across 21 test file(s) reaching into `aeat.adapters.persistence.storage.sql` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage/sql (test consumers)`.
- [x] `W05.P85.S342` - Rewire the 24 test-only cross-package private import site(s) across 15 test file(s) reaching into `aeat.adapters.persistence.storage.master_key` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage/master_key (test consumers)`.
- [x] `W05.P85.S343` - Rewire the 20 test-only cross-package private import site(s) across 12 test file(s) reaching into `aeat.adapters.outbound.aeat.sede` onto its promoted top-level facade; `src/aeat/adapters/outbound/aeat/sede (test consumers)`.
- [x] `W05.P85.S344` - Rewire the 7 test-only cross-package private import site(s) across 7 test file(s) reaching into `aeat.adapters.inbound.pdf` onto its promoted top-level facade; `src/aeat/adapters/inbound/pdf (test consumers)`.
- [x] `W05.P85.S345` - Rewire the 7 test-only cross-package private import site(s) across 7 test file(s) reaching into `aeat.adapters.outbound.storage` onto its promoted top-level facade; `src/aeat/adapters/outbound/storage (test consumers)`.
- [x] `W05.P85.S346` - Rewire the 10 test-only cross-package private import site(s) across 6 test file(s) reaching into `aeat.adapters.outbound.google` onto its promoted top-level facade; `src/aeat/adapters/outbound/google (test consumers)`.
- [x] `W05.P85.S347` - Rewire the 8 test-only cross-package private import site(s) across 6 test file(s) reaching into `aeat.adapters.inbound.financial.providers` onto its promoted top-level facade; `src/aeat/adapters/inbound/financial/providers (test consumers)`.
- [x] `W05.P85.S348` - Rewire the 8 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.adapters.outbound.aeat.browser` onto its promoted top-level facade; `src/aeat/adapters/outbound/aeat/browser (test consumers)`.
- [x] `W05.P85.S349` - Rewire the 7 test-only cross-package private import site(s) across 4 test file(s) reaching into `aeat.adapters.persistence.storage` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage (test consumers)`.
- [x] `W05.P85.S350` - Rewire the 12 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.adapters.outbound.aeat.auth` onto its promoted top-level facade; `src/aeat/adapters/outbound/aeat/auth (test consumers)`.
- [x] `W05.P85.S351` - Rewire the 6 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.adapters.outbound.llm` onto its promoted top-level facade; `src/aeat/adapters/outbound/llm (test consumers)`.
- [x] `W05.P85.S352` - Rewire the 2 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.adapters.inbound.declaracion` onto its promoted top-level facade; `src/aeat/adapters/inbound/declaracion (test consumers)`.
- [x] `W05.P85.S353` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.adapters.persistence.storage.blob_store` onto its promoted top-level facade; `src/aeat/adapters/persistence/storage/blob_store (test consumers)`.
- [x] `W05.P85.S354` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.adapters.inbound.borrador` onto its promoted top-level facade; `src/aeat/adapters/inbound/borrador (test consumers)`.

### Phase `W05.P86` - core-entrypoints-locales-tests test-only import sweep

Repoint every test-only cross-package private import reaching a core-entrypoints-locales-tests owning package onto that package promoted facade, one Step per owning package.

- [x] `W05.P86.S355` - Rewire the 14 test-only cross-package private import site(s) across 14 test file(s) reaching into `aeat.tests` onto its promoted top-level facade; `src/aeat/tests (test consumers)`.
- [x] `W05.P86.S356` - Rewire the 13 test-only cross-package private import site(s) across 13 test file(s) reaching into `aeat.core.errors` onto its promoted top-level facade; `src/aeat/core/errors (test consumers)`.
- [x] `W05.P86.S357` - Rewire the 37 test-only cross-package private import site(s) across 13 test file(s) reaching into `aeat.core` onto its promoted top-level facade; `src/aeat/core (test consumers)`.
- [x] `W05.P86.S358` - Rewire the 12 test-only cross-package private import site(s) across 11 test file(s) reaching into `aeat.core.i18n` onto its promoted top-level facade; `src/aeat/core/i18n (test consumers)`.
- [x] `W05.P86.S359` - Rewire the 9 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.entrypoints.cli` onto its promoted top-level facade; `src/aeat/entrypoints/cli (test consumers)`.
- [x] `W05.P86.S360` - Rewire the 5 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.core.observability` onto its promoted top-level facade; `src/aeat/core/observability (test consumers)`.
- [x] `W05.P86.S361` - Rewire the 8 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.locales` onto its promoted top-level facade; `src/aeat/locales (test consumers)`.
- [x] `W05.P86.S362` - Rewire the 2 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.entrypoints.mcp` onto its promoted top-level facade; `src/aeat/entrypoints/mcp (test consumers)`.
- [x] `W05.P86.S363` - Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.core.decimal` onto its promoted top-level facade; `src/aeat/core/decimal (test consumers)`.

## Wave `W06` - verification and closeout

Confirm the scanner reports zero production Family-1 violations and flip the Wave W04 gate to hard-zero mode, run the full collection and test suites green, dispatch a structural code review and a fresh-context honesty review before declaring the campaign structurally complete, and codify the durable lessons into the rule layer. Depends on every prior Wave.

### Phase `W06.P90` - verification and closeout

Confirm the scanner reports zero production Family-1 violations, flip the Wave W04 gate to hard-zero, run the full suite green, and run an independent structural and honesty review before declaring the campaign structurally complete.

- [x] `W06.P90.S382` - Run pytest --collect-only -q across src/aeat and confirm clean collection with no import errors; `src/aeat`.
- [x] `W06.P90.S383` - Run the full src/aeat test suite and confirm green, sequentially re-running any registry-suite failure before triaging it as a regression; `src/aeat`.
- [x] `W06.P90.S384` - Dispatch a vaultspec-code-review structural audit over the full campaign diff, confirming every promoted facade, every rewritten consumer, and the retired umbrella re-exports are behavior-preserving; `.vault/audit/2026-07-01-import-centralization-audit.md`.
- [x] `W06.P90.S387` - Codify the durable lessons: refine service-imports-via-top-level-reexports with the mechanical-vs-disposition promotion split, and author a new rule dynamic-import-targets-the-public-facade capturing the setup_answers lazy-import retargeting lesson; `.vaultspec/rules/rules/`.
- [x] `W06.P90.S399` - Re-run dev/import_hygiene_scan.py and confirm zero production Family-1 cross-package private-import violations, then flip the Wave W04 ratchet gate to hard-zero mode; `dev/import_hygiene_scan.py`.
- [x] `W06.P90.S400` - Run a fresh-context honesty review against the campaign closure summary per the campaign-close-honesty-review discipline before declaring the campaign structurally complete, tracking every surfaced item as a new Step or a formally deferred follow-up; `.vault/audit/2026-07-01-import-centralization-audit.md`.
- [x] `W06.P90.S401` - Persist Step Records for every closed Step and rebuild the feature index, then confirm vaultspec-core vault plan status reports the plan fully closed; `.vault/exec/2026-07-01-import-centralization`.
- [x] `W06.P90.S402` - Extend the import-hygiene scanner to detect underscore-named __all__ entries and dispose the 8 pre-existing hits surfaced by honesty-review finding #7; `dev/import_hygiene_scan.py`.
- [x] `W06.P90.S403` - Reconcile the post-close import-integrity drift measured by the machine-secret S18 honesty review: return the test-only private-import debt ratchet to exact named equality, dispose every new Family-2 forwarding wrapper, correct the excluded-test-tree dev-tooling detector, remove every dangling first-party import target, and prove the complete import-hygiene and import-edge lane has zero failures without enlarging a baseline or exemption; `dev/quality/import_hygiene_test_debt.json; dev/quality/import_hygiene_scan.py; dev/tests/test_import_hygiene_gate.py; dev/tests/test_import_edge_integrity_gate.py; current named producer and consumer sites`.

## Parallelization

Waves are sequenced strictly: W01 before W02 (a consumer cannot import a symbol its
owning package has not yet exported), W02 before W03 (the umbrella retirement in W03
repoints roughly 180 additional consumer sites and must not race the W02 rewrite of
the same files), W01 through W03 before W04 (the ratchet baseline is only meaningful
once most of the reduction has landed), W01 before W05 (test files reach the same
facades production files do), and every prior Wave before W06.

Within Wave W01, every Phase is independent (each promotes a different owning
package's facade) and may run fully in parallel across subagents; a single Phase's
Steps touch only that package's `__init__.py` and may need to land as one
sequential commit per Phase to avoid two workers editing the same file, but
different Phases never share a file.

Within Wave W02, every Phase (one per importer area) is independent once Wave W01
has landed for every owning package that area's files reach into. Within a Phase,
every Step names exactly one consumer file, so every Step in the Phase may be
dispatched to a different parallel worker with zero risk of two workers editing the
same file; the constraint is per-file exclusivity, not per-Phase sequencing.

Within Wave W03, Phase `W03.P87` (bridge hygiene and dynamic-import retargeting)
and Phase `W03.P88` (umbrella retirement) may run in parallel with each other, but
each of the 7 umbrella-retirement Steps in `W03.P88` touches the same
`application/modelo/__init__.py` or `application/invoices/__init__.py` facade file
its sibling Steps touch, so those Steps land as sequential commits within their
Phase, not parallel dispatch.

Wave W04's 4 Steps are sequential (seed allowlist, add ratchet, wire CI, supersede
narrower gates each depend on the previous landing).

Within Wave W05, the 4 Phases (domain, application, adapters,
core-entrypoints-locales-tests) are independent and may run in parallel; within a
Phase, every Step names a distinct owning package's test files and may be
dispatched in parallel.

Wave W06's 7 Steps are strictly sequential: the scanner re-run and gate flip must
precede the collection and suite gates, which must precede the structural and
honesty reviews, which must precede the Step Record rollup and codification.

## Verification

The plan is complete when every Step in the plan is closed (`- [x]`) and every
closed Step carries a matching Step Record, per the plan-closure-requires-exec-
records discipline. Concretely:

- `dev/import_hygiene_scan.py --top 40` reports zero non-test Family-1
  cross-package private-import violations (Wave W01 through W03 and W06.S399).
- `pytest --collect-only -q` against `src/aeat` collects cleanly with no import
  errors, run immediately before every relocation-style commit per the
  aeat-architecture-boundaries discipline and again as the Wave W06 gate.
- The full `src/aeat` test suite passes; any registry-suite failure is re-run
  sequentially before being triaged as a regression, per the aeat-local-execution
  discipline.
- The ratcheting import-hygiene gate wired in Wave W04 is live in the pytest/CI
  surface, its baseline has reached zero, and it has been flipped to hard-zero
  mode; `test_public_api_boundaries.py` and `test_architecture_boundaries.py` are
  superseded.
- A `vaultspec-code-review` structural audit and a fresh-context honesty review
  (per the aeat-campaign-close-honesty-review discipline) have both run against the
  closure summary, and every item either surfaced is closed with verification or
  formally deferred to a named follow-up.
- The durable lessons are codified: `service-imports-via-top-level-reexports` is
  refined with the mechanical-vs-disposition promotion split, and a new rule
  `dynamic-import-targets-the-public-facade` is authored from the `setup_answers`
  retargeting Steps.

For the tier-specific verification cadence and the full rulings this plan
implements, see the ADR and research documents named in the `related:`
frontmatter.
