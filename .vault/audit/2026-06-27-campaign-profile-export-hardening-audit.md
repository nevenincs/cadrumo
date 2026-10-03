---
tags:
  - '#audit'
  - '#campaign-profile-export-hardening'
date: '2026-06-27'
modified: '2026-10-03'
body_hash: 'sha256:c778535a1be6e8d5f2f6b8047c27225893ef284342ddd05d288411ed16c23393'
related: []
---

# `campaign-profile-export-hardening` audit: `profile gate and Modelo 303 export hardening`

## Scope

Campaign hardening changes from the persona-driven CLI run:
profile completeness gates before modelo work/export, M303 IVA first-period
wallet verification coverage, and Modelo 303 fichero-BOE export layout parity
against the official 2025 record-design workbook.

## Findings

### iva-first-period-zero-bypass | high | Missing local history is accepted as a legally certain first IVA period

The retired module called `reconcile_modelo_303_iva_compensation` with `treat_absent_recurrence_as_first_period=True` whenever no persisted wallet decision exists, no live wallet is supplied, and the bucket has a taxpayer NIF. That turns absence of local recurrence into a `first_period_zero` decision in the retired module, even though that function documents the flag as a caller assertion that the target is the taxpayer's first IVA period. The retired module then treats a local `first_period_zero` decision as enough authority to suppress the missing prior-303 cross-period dependency. The regression is locked in by the retired test, which seeds an activity-start date of `2020-01-01` and still verifies Modelo 303 `2025 1T` with a zero prior-compensation binding solely because there is no local `2024 4T` record. That is a legal-grounding bypass: LIVA art. 99.5 supports zero only when no prior compensation balance can exist, not whenever the local store lacks historical 303 evidence.

### readiness-gate-application-bypass | medium | Public modelo services still create and export without the readiness gate

The new readiness gate is invoked from the CLI wrappers, but the public application facade still exports `create_work_unit`, `calculate_modelo_revision`, `verify_modelo_revision`, `file_modelo_revision`, and `export_modelo_revision`, and those service entry points do not call `require_profile_ready_for_modelo_work` or `require_profile_ready_for_work_unit`. The retired module creates or reuses work units after only registry/period validation, while the retired module loads the revision and only later checks narrow export-name facts through `_operator_name_facts`. Programmatic callers and tests can therefore bypass the campaign's "before modelo work/export" readiness invariant and reach calculation, verification, filing, or export with profile facts that the CLI would refuse.

### readiness-locale-coverage-gap | low | New profile-readiness message keys are not in the locale coverage inventories

`ModeloProfileReadinessError` is registered with `REFUSED_MODELO_PROFILE_READINESS`, and the four locale catalogues define `application.modelo.errors.profile_readiness_missing` plus `application.modelo.errors.profile_readiness_profile_missing`. However, neither the retired test nor the retired test includes either new key. The current CLI smoke only exercises the default English incomplete-profile branch, so catalogue drift or a missing translation for the active-profile-missing branch would not be caught by the hardened locale coverage gates.

## Recommendations

### Resolution status

All three findings were repaired in this hardening pass.

- `iva-first-period-zero-bypass`: resolved. Lazy Modelo 303 IVA reconciliation now treats absent local recurrence as `first_period_zero` only when the lifecycle profile's `censo.activity_start_date` and the registry cross-period dependency graph prove every relevant prior-compensation dependency is pre-activity. Persisted or explicitly supplied `first_period_zero` decisions now run the same proof, and verification no longer lets `first_period_zero` cover an unclean in-scope dependency. Regression coverage: `test_existing_activity_m303_1t_missing_prior_filing_blocks_wallet_zero`, `test_first_iva_period_m303_1t_uses_wallet_first_period_zero`, `test_in_scope_period_rejects_supplied_first_period_zero_decision`, and `test_grounded_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate`.
- `readiness-gate-application-bypass`: resolved. Public application services now run profile readiness at `create_work_unit`, both calculation paths, `verify_modelo_revision`, `file_modelo_revision`, `export_modelo_revision`, and `mark_revision_verificado_completo`. Regression coverage: `test_create_work_unit_service_refuses_incomplete_profile`, `test_calculate_service_refuses_existing_work_unit_with_incomplete_profile`, and `test_mark_verified_service_refuses_existing_work_unit_with_incomplete_profile`.
- `readiness-locale-coverage-gap`: resolved. The readiness message keys are enrolled in both locale coverage inventories.

Verification passed:

- the historical check
- the historical check
- the historical check

Independent review: `Halley` found the persisted/supplied `first_period_zero` bypass and the missing `mark_revision_verificado_completo` readiness gate after the first patch. A follow-up review found and closed a revision-id injection issue in the first-period proof snapshot resolver. The final read-only recheck reported no remaining findings.
