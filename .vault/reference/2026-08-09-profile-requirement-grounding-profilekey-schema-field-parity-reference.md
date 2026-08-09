---
tags:
  - '#reference'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:641291f902aed2d673305f94658c64d63aa4b5bcce4c6484cca90ee608c78e2c'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
  - "[[2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit]]"
---

# `profile-requirement-grounding` reference: `ProfileKey vs schema.toml field-by-field parity audit`

## Summary

## Context

## Summary

P08.S24 deliverable: a complete, measured field-by-field parity comparison between the wizard-compiled `PROFILE_KEYS` registry (`domain/contribuyente/_keys.py`, sourced from `application/wizard/_catalogue.WIZARD_FLOWS`) and the schema-declared `ProfileFieldDefinition` set (`schema.toml`, loaded via `load_user_profile_schema()`). No code changes in this document; it is the evidence base P08.S26/S31's decomposition draws on.

The governing audit (`2026-08-09-...-audit.md`) already measured the headline gap in prose ("the schema declares 15 required fields while the wizard-compiled PROFILE_KEYS declares 1"). This document supplies the field-level breakdown that measurement did not include: exactly which fields disagree, and which required fields have no wizard representation at all.

## Method

```python
from cadrumo.application.wizard import ensure_profile_keys_registered
ensure_profile_keys_registered()
from cadrumo.domain.contribuyente import PROFILE_KEYS
from cadrumo.domain.user_profile import load_user_profile_schema

schema = load_user_profile_schema()
# schema_paths: {"section.field": required_bool, ...} over every section/field
# profile_keys: {pk.key: pk.requirement.value, ...} over every PROFILE_KEYS entry
```

Driven against the real registered wizard catalogue and the real loaded schema (uv run, 2026-08-09) - not read from source, not inferred.

## Scope

Every key in `PROFILE_KEYS` (75 total) and every `section.field` path declared in `schema.toml` (161 total).

## Findings

### Counts

| set | total | required |
|---|---|---|
| `PROFILE_KEYS` | 75 | 1 (`identity.tax_id`) |
| schema fields | 161 | 15 |

### Only in `PROFILE_KEYS`, absent from schema

**Zero.** Every `PROFILE_KEYS` entry has a matching schema field. The wizard catalogue is a strict subset of the schema by key coverage.

### Requirement-flag disagreements (present in both, `required` differs)

Exactly **two**, both schema-required but wizard-optional:

| path | `PROFILE_KEYS.required` | `schema.required` |
|---|---|---|
| `activities.description` | False | True |
| `iva.regime` | False | True |

A record satisfying `validate_profile_values` (the `PROFILE_KEYS`-driven surface) can leave both fields blank while `ProfileValidationService` (the schema-driven surface) refuses the same record - the opposite-verdict divergence the audit's fourth finding names.

### Schema-required fields with NO `PROFILE_KEYS` entry at all

**Twelve.** Not merely mismatched - absent. There is no wizard question that can populate these, so an operator using only the interactive setup flow cannot satisfy them; only a direct `config profile edit` (or bulk-value) surface can:

- `attribution_entity_socios.base_imponible_assigned`, `.name`, `.nif`, `.participe_clave`, `.share_pct` (5 - atribución de rentas socio rows)
- `attribution_received.base_imponible_attributed`, `.entity_name`, `.entity_nif`, `.filing_year`, `.share_pct` (5 - atribución de rentas received rows)
- `usage_ratios.business_ratio`, `.category_id` (2 - afectación parcial usage-ratio rows)

All twelve are repeatable-row constructs for edge-case regimes (atribución de rentas, afectación parcial) that the main wizard flow does not walk. This is architecturally plausible (not every schema field needs a wizard question), but it means these twelve are invisible to `validate_profile_values` categorically, not just under-flagged.

### Schema fields absent from `PROFILE_KEYS`, optional (74)

Grouped by section; none of these disagree on requiredness (schema says optional, `PROFILE_KEYS` has no opinion because it has no entry) - listed for completeness per this project's no-silent-under-declaration discipline, not because each is individually actionable:

- `activities`: `cnae`, `iae_epigraph` (2)
- `attribution_entity`: `legal_form` (1)
- `auth`: `dni_nie`, `fecha_validez`, `numero_soporte`, `provider` (4)
- `capabilities`: `cloud_evidence_upload` (1)
- `censo`: `activity_end_date`, `divergencia`, `elected_withholding_pct`, `establecimiento_type`, `status` (5)
- `contact`: `fiscal_address`, `fiscal_address_cadastral_reference`, `fiscal_address_is_habitual_vivienda` (3)
- `filing_export`: `aeat_seal`, `bank_address`, `bank_city`, `bank_country_code`, `bank_name`, `iban`, `period_end_date`, `period_start_date`, `presenter_tax_id`, `previous_receipt`, `program_version`, `rental_reduccion_art_23_2_tier_2024`, `sepa_marca`, `swift_bic` (14)
- `identity`: `email` (1)
- `irpf`: `activity_kind`, `objective_estimation_prior_year_agri_livestock_forest_gross_eur`, `objective_estimation_prior_year_gross_income_eur`, `objective_estimation_prior_year_invoice_gross_income_eur`, `objective_estimation_prior_year_purchases_eur`, `pagadores_count`, `pagadores_secondary_income`, `pagadores_total_work_income`, `professional_income_withholding_ge_70pct` (9)
- `iva`: `autoconsumo_promotor_base` (1)
- `maritime_worker`: `pending_eu_clearance`, `retmar_registered`, `tuna_fleet`, `vessel_flag`, `vessel_registry`, `waters_type`, `worker_class` (7)
- `properties`: `cadastral_reference`, `use_type` (2)
- `provenance`: `source`, `valid_from`, `valid_to` (3)
- `renta_family`: `anualidades_alimentos_euros`, `ascendants`, `cotizaciones_ss_madre_2024`, `descendants`, `descendiente`, `descendientes_count`, `madrid_nacimiento_adopcion_eligible_count`, `unidad_familiar_otros_miembros_base` (8)
- `renta_taxpayer`: `marriage_full_year`, `marriage_month_end`, `marriage_month_start` (3)
- `tax_residence`: `jurisdiction_scope`, `state_attribution_ratio` (2)
- `taxpayer_type`: `sal_capital_social`, `sal_reserva_especial_dotada`, `sal_socios_trabajadores_count`, `tributacion_estado_porcentaje` (4)
- `usage_ratios` (optional siblings): none beyond the 2 required ones already listed above
- `vivienda_office`: `office_m2`, `total_m2` (2)

### `legal_refs` is structurally asymmetric, not merely mismatched

`ProfileKey` (`_keys.py:43-52`) has no `legal_refs` field at all - only `key`, `requirement`, `description` (a locale-key `Translatable`, not literal prose), `required_when_key`, `required_when_value`. Every `PROFILE_KEYS`-driven surface therefore carries zero legal grounding by construction; this is not a per-field mismatch to enumerate; it is a structural gap on one side of the comparison. Any surface still reading `PROFILE_KEYS` for operator-facing grounding (rather than the enriched `ProfilePreflightRequirement` this campaign's P01-P06 work built) cannot show `legal_refs` regardless of the schema side's content.

`description` is likewise not directly comparable: `ProfileKey.description` is a locale-catalogue KEY (`profile.keys.*`, validated to start with that prefix), while `ProfileFieldDefinition.description` is literal schema-authored prose. A semantic diff would require dereferencing every `PROFILE_KEYS` locale key to its rendered text in all four catalogues and comparing prose meaning - out of this step's no-code-changes, field-identity-focused scope. Recorded as a scoping boundary, not investigated further here.

## Recommendations

1. The two requirement-flag disagreements (`activities.description`, `iva.regime`) are the highest-value P08.S26 fan-out candidates: fixing `PROFILE_KEYS`' requirement flag (or the wizard question's presence) for these two closes the concrete opposite-verdict divergence the audit's fourth finding names, with no schema change needed.
2. The twelve wizard-invisible required fields (`attribution_entity_socios.*`, `attribution_received.*`, `usage_ratios.*`) are a distinct, larger question - whether the wizard flow should grow new questions for atribución/afectación-parcial rows, or whether these rows are intentionally editor-only. This needs a product decision, not a mechanical sync, and should be scoped as its own P08.S26 fan-out row rather than assumed.
3. The 74 optional-only schema fields are NOT a to-do list by themselves; most are legitimately editor-only (bank/export metadata, provenance, maritime-worker niche facts). No action recommended on this set as a whole; a fan-out row should only target one if a SPECIFIC downstream surface is found reading `PROFILE_KEYS` and expecting it to be complete (none confirmed in this step's no-code-changes scope).
