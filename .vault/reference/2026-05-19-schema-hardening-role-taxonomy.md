---
tags:
  - '#reference'
  - '#schema-hardening'
date: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-adr]]"
  - "[[2026-05-20-schema-hardening-plan]]"
  - "[[2026-05-19-schema-hardening-role-rollout-strategy]]"
---

# `schema-hardening` reference: canonical semantic_role taxonomy

## Purpose

Catalogues every `semantic_role` value declared on `CasillaDefinition`
across the modelo corpus today, the `data_type` each role binds to,
and the rationale for declaring the role. Future modellers
introducing a new casilla in a role family should look here first
to find the canonical role name; the snapshot-build consistency
validator binds on exact-match role strings, so spelling consistency
matters.

This is a living document. Each row reflects a corpus reality as
of the most recent Plan C rollout commit. The role-rollout-strategy
audit documents the operational follow-up that adds new entries.

## Active roles

### Identity roles

| role | data_type | casilla count | example | notes |
|------|-----------|--------------:|---------|-------|
| `payee_nif` | `nif` | 3 | M180 perc.nif, M184 tipo2.miembro-nif | Withholding-form payee identifier; extends through binding-level surfaces in M190 / M193 (deferred). |
| `payee_representative_nif` | `nif` | 2 | M180 perc.nif-representante-legal | Legal representative acting on behalf of the payee. |
| `intracomunitario_nif_iva` | `nif_iva` | 1 | M349 op.nif-comunitario | Counterparty NIF-IVA for intra-EU operations. Single-occurrence by design (M349 is the only modelo with this surface). |

### Temporal roles

| role | data_type | casilla count | example | notes |
|------|-----------|--------------:|---------|-------|
| `filing_year` | `year` | 16 | every modelo's `decl.ejercicio` casilla | Universal across modelos that declare ejercicio at the casilla layer (header-only year fields in other modelos defer to a future ExportField extension). |
| `complementaria_year` | `year` | 1 | M349 rect.ejercicio-rectificado | Year of the prior period being rectified. Single-occurrence; other complementaria modelos encode this in opaque `previous_justificante` header strings. |
| `devengo_year` | `year` | 2 | M180 perc.ejercicio-devengo | Year of devengo for the perceptor; per-perceptor (not declaration-wide). |
| `filing_period` | `period_code` | 6 | M303, M322, M353, M369 (3 revisions) | Quarterly / monthly / OSS-quarter / IS-instalment / annual / ad-hoc period token. |
| `complementaria_period` | `period_code` | 1 | M349 rect.periodo-rectificado | Period of the prior filing being rectified. |

### Geographic roles

| role | data_type | casilla count | example | notes |
|------|-----------|--------------:|---------|-------|
| `taxpayer_country` | `country_code` | 5 | M100 casilla 1799 across revisions 2021-2025 | Country of residence for the taxpayer. |
| `payee_country` | `country_code` | 1 | M349 op.codigo-pais | Country of residence for the intra-EU counterparty. |
| `payee_province` | `province_code` | 2 | M180 perc.provincia | Province of the perceptor's primary address. |
| `payee_immueble_province` | `province_code` | 2 | M180 perc.inmueble-provincia | Province of the property tied to the payee. |
| `payee_immueble_postal_code` | `postal_code` | 2 | M180 perc.inmueble-codigo-postal | Postal code of that property. |
| `payee_immueble_municipality_code` | `municipality_code` | 2 | M180 perc.inmueble-codigo-municipio | INE municipality code of that property. |

### Naming roles

| role | data_type | casilla count | example | notes |
|------|-----------|--------------:|---------|-------|
| `payee_name` | `name` | 2 | M180 perc.nombre | Apellidos + nombre / razon social of the perceptor. |

### Banking roles

| role | data_type | casilla count | example | notes |
|------|-----------|--------------:|---------|-------|
| `rectification_iban` | `iban` | 4 | M100 casillas 0687, 1780 across the revisions that retain them | IBAN for refund of a prior-year rectification. Dropped in M100/2024-2025 (deprecation audit documents the open issue). |
| `spouse_compensation_iban` | `iban` | 6 | M100 casillas 0696, 1790 across all six revisions | IBAN for compensacion-entre-conyuges refunds. |

## Reserved roles (declared but pending corpus rollout)

The following role names appear in the Plan C role-rollout-strategy
audit as planned canonical names; they will land as corpus rollouts
proceed and may be referenced in future plan steps before any
casilla carries them:

- `taxpayer_nif` — primary declarant's NIF. Rolling out via the
  M100 NIF role-classification audit in flight.
- `representative_nif` — legal representative of the taxpayer.
- `spouse_nif`, `descendant_nif`, `ascendant_nif` — family-identity
  roles within M100 deduction sections.
- `disabled_person_nif`, `pension_recipient_nif`, `landlord_nif`,
  `tenant_nif`, `worker_nif`, `service_provider_nif`, `producer_nif`,
  `beneficiary_nif`, `assignor_nif`, `employer_nif`,
  `pension_plan_employer_nif`, `parent_nif`, `investment_entity_nif`,
  `feac_entity_nif`, `canarias_nif_or_nie`, `re_derechos_imagen_nif`
  — granular counterparty / family roles in M100 retrofits. Each
  binds to `data_type = "nif"`.
- `taxpayer_ccaa` — autonomous-community code for the taxpayer's
  fiscal residence. Currently held in M100 via the
  `renta-2025-profile-tax-residence-ccaa` binding rather than a
  casilla; rollout deferred until the binding-vs-casilla
  decomposition decision lands.
- `base_imponible`, `cuota_a_ingresar`,
  `retenciones_ingresos_a_cuenta`, `pago_fraccionado` — monetary
  roles. Cross-modelo constraint reconciliation pending (the
  research artefact flagged that nine modelos disagree on the
  `non_negative` sign for retenciones; reconciliation must land
  with the role declaration).

## Validator behaviour

- **Intra-role consistency.** Any casilla declaring an active role
  is checked against the other casillas declaring the same role.
  The first casilla in document order sets the canonical
  `data_type` and `constraints` shape; divergent declarations fail
  registry load with `RegistryValidationError`.
- **Typo-twin warning.** A role appearing on exactly one casilla
  in the corpus emits a `warnings.warn` advisory at registry load.
  This catches `taxpayer_nif` vs `taxpayer-nif` style typos. The
  role-rollout-strategy audit documents each legitimately
  single-occurrence role so the warnings can be filtered as
  expected output.
- **Aliases.** Where a single role covers casillas with divergent
  BOE-source label strings, the casilla declares the variant
  phrasings via `aliases: tuple[CasillaAlias, ...]`. Each alias
  carries its own `legal_refs` and `source_refs` to preserve
  provenance through the schema boundary.

## Naming convention

Role identifiers use kebab-friendly lowercase ASCII with
underscores between concept words (`taxpayer_nif`,
`filing_year`). Avoid:

- Hyphens in role names (reserved as a separator for compound
  concepts that DO use hyphens, e.g., `EXT-1T` period codes -
  hyphenated role names look like file or path tokens and read
  ambiguously).
- Modelo-specific role names (`m180_perc_nif`); the role is a
  semantic concept that can cross modelos, even if today only one
  modelo carries it.
- Section-path role names (`identificacion_nif`); prefer the
  subject relation (`taxpayer_nif`, `payee_nif`).

When introducing a new role, prefer a name that could legitimately
apply to a future sibling casilla in another modelo. If the role is
genuinely modelo-specific (e.g., the FEAC entity-NIF on M100),
acknowledge it explicitly in this taxonomy and accept the
typo-twin warning as expected output.

## Cross-references

- ADR: schema-hardening canonical semantic-atom layer.
- Plan C: per-role rollout phases W02 through W05.
- Audit: M100 NIF coverage (Bucket classification); role rollout
  strategy (operational follow-up cadence).
