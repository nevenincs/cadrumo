---
generated: true
tags:
  - '#index'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - '[[2026-07-01-import-centralization-W01-P02-S01]]'
  - '[[2026-07-01-import-centralization-W01-P03-S02]]'
  - '[[2026-07-01-import-centralization-W01-P04-S03]]'
  - '[[2026-07-01-import-centralization-W01-P05-S04]]'
  - '[[2026-07-01-import-centralization-W01-P08-S08]]'
  - '[[2026-07-01-import-centralization-W01-P10-S10]]'
  - '[[2026-07-01-import-centralization-W01-P10-S11]]'
  - '[[2026-07-01-import-centralization-W01-P12-S15]]'
  - '[[2026-07-01-import-centralization-W02-P36-S49]]'
  - '[[2026-07-01-import-centralization-W02-P37-S97]]'
  - '[[2026-07-01-import-centralization-W02-P38-S120]]'
  - '[[2026-07-01-import-centralization-W02-P40-S159]]'
  - '[[2026-07-01-import-centralization-W02-P41-S174]]'
  - '[[2026-07-01-import-centralization-W02-P43-S199]]'
  - '[[2026-07-01-import-centralization-W02-P45-S217]]'
  - '[[2026-07-01-import-centralization-W02-P49-S240]]'
  - '[[2026-07-01-import-centralization-W02-P54-S258]]'
  - '[[2026-07-01-import-centralization-W02-P61-S275]]'
  - '[[2026-07-01-import-centralization-W04-P89-S378]]'
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-07-01-import-centralization-plan]]'
  - '[[2026-07-01-import-centralization-research]]'
---

# `import-centralization` feature index

Auto-generated index of all documents tagged with `#import-centralization`.

## Documents

### adr

- `2026-07-01-import-centralization-adr` - `import-centralization` adr: `centralized top-level exports as the sole cross-package import surface` | (**status:** `accepted`)

### exec

- `2026-07-01-import-centralization-W01-P02-S01` - Promote `CalculationRevisionId`, `Dt12WindowEligibility`, `FilingRecordId`, `LedgerEvidenceRow`, `LedgerFilingEvidence`, `LedgerFilingSnapshot`, `LedgerFilingStalenessVerdict`, `LedgerRowFingerprint`, `ManualFactBasisEntry`, `Modelo184ShareSumError`, `Modelo347ThresholdError`, `ModeloError`, `ModeloExportError`, `ModeloValidationError`, `VerificationReportId`, `WorkUnitState`, `compute_dt12_reduccion_plan_pensiones`, `compute_sal_reserva_especial_dotacion`, `diff_ledger_fingerprints`, `dt12_regime_window_eligibility`, `m349_nif_number_for_export`, `snapshot_fingerprint`, `validate_m184_member_share_sum`, `validate_m347_threshold` to `aeat.domain.modelos.__all__` with eager re-exports so the 67 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P03-S02` - Promote `CalcSheetsApplyResult`, `DriveConfig`, `PullResult`, `RowSetEdit`, `apply_export_plan`, `compute_from_pull`, `delete_session`, `load_client`, `load_drive_config`, `load_metadata`, `load_token`, `pull_operator_edits`, `resolve_active_profile`, `run_login_flow`, `save_client`, `save_drive_config`, `save_metadata`, `save_token` to `aeat.adapters.outbound.google.__all__` with eager re-exports so the 26 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P04-S03` - Promote `Modelo`, `OUT_OF_SCOPE_OBLIGATIONS`, `Period`, `PeriodError`, `PostFilingEventKind`, `ResultDisposition`, `STRICT_FROZEN_CONFIG`, `TaxDomain`, `UNMODELED_OBLIGATIONS`, `classify_post_filing_event_kind`, `post_filing_event_is_actionable`, `resolve_active_bucket_id`, `result_disposition_is_refund` to `aeat.core.__all__` with eager re-exports so the 35 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P05-S04` - Promote `CensoSnapshot`, `CensoSnapshotService`, `PersistedExpedientesSnapshot`, `PersistedNotificationsSnapshot`, `VerifyObservation`, `censo_snapshot_object_key`, `expedientes_snapshot_object_key`, `notifications_snapshot_object_key`, `verify_observation_object_key` to `aeat.application.live.__all__` with eager re-exports so the 12 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P08-S08` - Promote `CarriedSecureObject`, `CoverageManifest`, `ProfileExportError`, `UserProfileError`, `UserProfileValidationError`, `utc_now` to `aeat.domain.user_profile.__all__` with eager re-exports so the 10 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P10-S10` - Promote `FiscalResidency`, `compute_deduccion_maternidad_0611`, `modelo100_ecivil_export_code`, `register_profile_keys` to `aeat.domain.contribuyente.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W01-P10-S11` - Decide and apply the public-surface disposition for `_profile_keys` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.contribuyente._keys` and consumed cross-package from `src/aeat/application/user_profile/_keys_validation.py`
- `2026-07-01-import-centralization-W01-P12-S15` - Promote `KNOWN_PROFILE_FLAG_ADVISORY_FIELDS`, `select_revision` to `aeat.domain.calculations.registry.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade
- `2026-07-01-import-centralization-W04-P89-S378` - Add a ratcheting production-Family-1 baseline JSON that fails the gate when the current cross-package private-import count exceeds the committed baseline, and shrink the baseline in the same commit as any fix that reduces the count
- `2026-07-01-import-centralization-W02-P36-S49` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`
- `2026-07-01-import-centralization-W02-P37-S97` - Rewire 7 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.fincas`
- `2026-07-01-import-centralization-W02-P38-S120` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.i18n`
- `2026-07-01-import-centralization-W02-P40-S159` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`
- `2026-07-01-import-centralization-W02-P41-S174` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`, `aeat.domain.user_profile`
- `2026-07-01-import-centralization-W02-P43-S199` - Rewire 2 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva_compensation`
- `2026-07-01-import-centralization-W02-P45-S217` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`
- `2026-07-01-import-centralization-W02-P49-S240` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`
- `2026-07-01-import-centralization-W02-P54-S258` - Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.errors`
- `2026-07-01-import-centralization-W02-P61-S275` - Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`

### plan

- `2026-07-01-import-centralization-plan` - `import-centralization` plan

### research

- `2026-07-01-import-centralization-research` - `import-centralization` research: `cross-package private-import inventory`
