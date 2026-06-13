---
tags:
  - '#reference'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-adr]]"
  - "[[2026-05-20-schema-hardening-plan]]"
  - "[[2026-05-19-schema-hardening-role-rollout-strategy-audit]]"
  - "[[2026-05-19-schema-hardening-m100-nif-role-assignment-audit]]"
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

This is a living document. The role tables below catalogue the
cross-modelo identity, monetary, address, and period roles in
detail. The full per-modelo role inventory is large enough that
its authoritative record is the set of per-cluster classification
audits under `.vault/audit/` rather than an exhaustive table here.

## Campaign completion status

The semantic_role enrollment campaign is complete. Every casilla
definition across all 26 modelos in the registry carries a
`semantic_role`:

- **14,971 casilla declarations, 100% role coverage** across the
  whole corpus.
- M100 (IRPF): 11,302 casillas across six revisions (2020-2025),
  zero cross-revision drift, all id-reuse handled via
  revision-scoped roles.
- M200 (Impuesto sobre Sociedades): 3,215 casillas in the single
  `2024-y-siguientes` revision.
- The remaining 24 modelos: fully enrolled in earlier rollout
  clusters.
- Zero intra-role `data_type`/`constraints` divergences; the
  registry cross-revision drift gate
  (`test_backend_registry_validation_accepts_committed_corpus_drift_gate`)
  passes on the committed corpus.

Per-modelo role assignments are recorded in the cluster
classification audits, e.g. `2026-05-19-schema-hardening-m100-*`
and `2026-05-20-schema-hardening-m200-*` under `.vault/audit/`.

## Semantic-correctness verification

Structural coverage is not semantic correctness. A post-enrollment
verification campaign (tracked in
`2026-05-20-schema-hardening-verification-ledger`) reviewed every
role against its casillas' true labels:

- A `tomllib`-based harness replaced the regex label-extraction that
  had truncated 561 casillas' labels at escaped quotes.
- 18 semantic-review agents read all ~2,100 roles in M100 and M200
  against full labels; ~24% (M100) / ~22% (M200) needed a correction.
- **3,405 role corrections applied** (M200 1,250 + M100 2,155):
  renames, splits of over-coarse roles, and outlier reassignments.
- Distinct roles after the sweep: **~2,426**.
- The M200 `correcciones` cluster fracture and the M100 AEIP
  event-deduction scatter were reconciled.

The taxonomy below remains the canonical cross-modelo identity,
monetary, address, and period role catalogue; the per-modelo detail
lives in the `r7-*` review and consolidation audits.

## Identity roles (data_type = "nif")

| role | count | example | notes |
|------|------:|---------|-------|
| `service_provider_nif` | 134 | M100 0949 | NIF de quien realizo obras / servicios / mejoras energeticas. Highest-footprint role. |
| `investment_entity_nif` | 115 | M100 0257 | NIF de sociedades, fondos, guarderias, entidades de inversion. |
| `assignor_nif` | 42 | M100 0620 | NIF del cedente in deduccion contexts. |
| `landlord_nif` | 38 | M100 0638 | NIF del arrendador across CCAA deduction annexes. |
| `descendant_nif` | 37 | M100 0456 | NIF del hijo / descendiente, including the dual-modelled NIFDLG bound casilla in 2025. |
| `producer_nif` | 30 | M100 1724 | NIF del productor in anexo_a inversiones empresariales. |
| `worker_nif` | 29 | M100 0989 | NIF de la persona empleada del hogar / centros / guarderias. |
| `parent_nif` | 27 | M100 1209 | NIF del otro progenitor across hijo/hija slots. |
| `disabled_person_nif` | 24 | M100 0471 | NIF de la persona con discapacidad partícipe / titular. |
| `tenant_nif` | 19 | M100 1187 | NIF del arrendatario with confirmed Spanish-NIF contract (excludes OQ-1 foreign-NIF-flag set). |
| `beneficiary_nif` | 18 | M100 0622 | NIF del beneficiario. |
| `canarias_nif_or_nie` | 16 | M100 2044 | Bare "NIF/NIE N" labels in Canarias section. |
| `ascendant_nif` | 13 | M100 0625 | NIF del ascendiente. |
| `beneficiary_annuity_payer_nif` | 13 | M100 1786 | NIF/NIE del pagador de las anualidades (hijo/hija 1-5). New role added by M100 NIF role-classification audit. |
| `spouse_nif` | 7 | M100 0240 | NIF del cónyuge / excónyuge. |
| `construction_entity_nif` | 7 | M100 0707 | NIF/NIE de la persona/entidad que ha realizado las obras (residential renovation context). |
| `pension_recipient_nif` | 6 | M100 0483 | NIF de la persona que recibe cada pensión o anualidad. |
| `feac_entity_nif` | 6 | M100 1974 | Bare "NIF" labels in FEAC section (EU cross-border mergers). |
| `college_entity_nif` | 4 | M100 2066 | NIF del Colegio Mayor/Menor/Residencia de estudiantes. New role from M100 audit. |
| `payee_nif` | 3 | M180 perc.nif, M184 tipo2.miembro-nif | Withholding-form payee identifier. |
| `employer_nif` | 3 | M100 0397 (2023+) | NIF del empleador. |
| `payee_representative_nif` | 2 | M180 perc.nif-representante-legal | Legal representative of the payee. |
| `pension_plan_employer_nif` | 1 | M100 0397 (2022 only) | Distinct legacy role for the casilla 0397 label in 2022; reclassified to `employer_nif` in 2023+. |
| `taxpayer_nif` | 1 | M100 DPNIF_D (2025) | Primary declarant NIF bound slot, new in 2025. Header-level NIFs in other modelos do not surface as casillas; deferred to a future ExportField extension. |

## Temporal roles

| role | data_type | count | example | notes |
|------|-----------|------:|---------|-------|
| `filing_year` | `year` | 16 | every modelo's `decl.ejercicio` casilla | Universal across modelos that declare ejercicio at the casilla layer. |
| `complementaria_year` | `year` | 1 | M349 rect.ejercicio-rectificado | Year of the prior period being rectified. |
| `devengo_year` | `year` | 2 | M180 perc.ejercicio-devengo | Year of devengo for the perceptor. |
| `filing_period` | `period_code` | 6 | M303, M322, M353, M369 (3 revisions) | Quarterly / monthly / OSS-quarter / IS-instalment / annual / ad-hoc period token. |
| `complementaria_period` | `period_code` | 1 | M349 rect.periodo-rectificado | Period of the prior filing being rectified. |

## Geographic roles

| role | data_type | count | example | notes |
|------|-----------|------:|---------|-------|
| `taxpayer_country` | `country_code` | 5 | M100 casilla 1799 across 2021-2025 | Country of residence for the taxpayer. |
| `payee_country` | `country_code` | 1 | M349 op.codigo-pais | Country of the intra-EU counterparty. |
| `payee_province` | `province_code` | 2 | M180 perc.provincia | Province of the perceptor's primary address. |
| `payee_immueble_province` | `province_code` | 2 | M180 perc.inmueble-provincia | Province of the property tied to the payee. |
| `payee_immueble_postal_code` | `postal_code` | 2 | M180 perc.inmueble-codigo-postal | Postal code of that property. |
| `payee_immueble_municipality_code` | `municipality_code` | 2 | M180 perc.inmueble-codigo-municipio | INE municipality code of that property. |

## Naming roles

| role | data_type | count | example | notes |
|------|-----------|------:|---------|-------|
| `payee_name` | `name` | 2 | M180 perc.nombre | Apellidos + nombre / razon social of the perceptor. |

## Banking roles

| role | data_type | count | example | notes |
|------|-----------|------:|---------|-------|
| `rectification_iban` | `iban` | 4 | M100 casillas 0687, 1780 | IBAN for refund of a prior-year rectification (dropped in 2024-2025). |
| `spouse_compensation_iban` | `iban` | 6 | M100 casillas 0696, 1790 | IBAN for compensacion-entre-conyuges refunds. |

## NIF-IVA roles

| role | data_type | count | example | notes |
|------|-----------|------:|---------|-------|
| `intracomunitario_nif_iva` | `nif_iva` | 1 | M349 op.nif-comunitario | Counterparty NIF-IVA for intra-EU operations. |

## Monetary roles

All monetary roles bind `data_type = "money"` (or `"decimal"` for
M100 IRPF intermediate-precision fields) and reconcile sign across
participating modelos at the validator boundary. Retrofits added
the `non_negative` constraint where modellers had left it unset,
turning the research artefact's nine-way divergence into a single
canonical shape per role.

| role | data_type | sign | count | example | notes |
|------|-----------|------|------:|---------|-------|
| `retenciones_ingresos_a_cuenta` | `money` | `non_negative` | 25 | M111 28 (total), M180 perc.retenciones | Cross-modelo withholding amount; canonical role bridging M111 / M115 / M123 / M130 / M131 / M180 / M190 / M193 / M202. |
| `base_retenciones_ingresos_a_cuenta` | `money` | `non_negative` | 7 | M115 02, M180 perc.base | Gross-base amount on which withholding is computed; pairs with retenciones_ingresos_a_cuenta. |
| `pago_fraccionado` | `money` | `non_negative` | 10 | M130 04, M202 22/25/63/66 | Current-period fractional payment amount. |
| `pago_fraccionado_previo` | `money` | `non_negative` | 8 | M130 05, M131 07, M202 30 | Prior-period fractional-payment totals carried into the current declaration. |
| `cuota_a_ingresar` | `money` | `non_negative` | 4 | M111 30, M115 05, M123 08/14 | Strict "Resultado a ingresar" total. Excludes the signed "o a devolver" form (M100/0700, M200/00599) which carry their own role. |
| `base_imponible_irpf` | `decimal` | `any` | 12 | M100 0259 (imputada), 0435 (general) | IRPF base imponible across M100's six revisions. Signed because IRPF base can be negative when losses dominate. |
| `base_intracomunitaria` | `money` | `non_negative` | 3 | M349 op.base-imponible, rect.base-rectificada, rect.base-anterior | Intracomunitario operation amount + rectification pair. |
| `base_imponible_negativa_is` | `decimal` | `non_positive` | 1 | M200 00027 | IS carry-forward of prior-year base imponible losses. Single-occurrence; legitimately M200-specific. |
| `resultado_ingresar_o_devolver_irpf` | `decimal` | `any` | 2 | M100 0700 (2024, 2025 only) | Signed cuota for IRPF — refund vs payment. M100 reuses casilla 0700 for an unrelated deduction concept in 2020-2023, so only 2024/2025 carry the role. |
| `resultado_ingresar_o_devolver_is` | `money` | `any` | 1 | M200 00599 | Signed cuota for IS. Single-modelo because IS has one current revision. |

## Validator behaviour

- **Intra-role consistency.** Any casilla declaring an active role
  is checked against the other casillas declaring the same role.
  The first casilla in document order sets the canonical
  `data_type` and `constraints` shape; divergent declarations fail
  registry load with `RegistryValidationError`.
- **Typo-twin warning.** A role appearing on exactly one casilla
  in the corpus emits a `warnings.warn` advisory at registry load.
  Legitimately rare roles (single-occurrence in the corpus today):
  `taxpayer_nif`, `pension_plan_employer_nif`, `payee_country`,
  `intracomunitario_nif_iva`, `complementaria_year`,
  `complementaria_period`. Each is documented above; the warning
  is expected output rather than a typo signal.
- **Aliases.** Where a single role covers casillas with divergent
  BOE-source label strings, the casilla declares the variant
  phrasings via `aliases: tuple[CasillaAlias, ...]`. Each alias
  carries its own `legal_refs` and `source_refs` to preserve
  provenance through the schema boundary.

## Reserved roles (not yet declared on any casilla)

These role names appear in the Plan C role-rollout-strategy audit
as planned canonical names; they will land as corpus rollouts
proceed:

- `representative_nif` — legal representative of the taxpayer (as
  distinct from `payee_representative_nif`).
- `taxpayer_ccaa` — autonomous-community code for the taxpayer's
  fiscal residence. Currently held via the
  `renta-2025-profile-tax-residence-ccaa` binding rather than a
  casilla; rollout deferred until the binding-vs-casilla
  decomposition decision lands.

## OQ-1 deferred casillas

Nine M100 casillas (0077, 0091, 0094, 0097, 0911, 1122, 1125,
2205, 2208) carry a companion boolean indicating "si ha consignado
un NIF de otro país", meaning the field may legally hold a foreign
fiscal ID under the boolean branch. These remain `data_type =
"text"` (not retrofitted to `"nif"`) pending a Plan C carve-out
role decision. Either a new `tenant_or_foreign_id_nif` role with
a permissive validator, or a polymorphic role tied to the boolean
discriminator, would close the open issue.

## Naming convention

Role identifiers use lowercase ASCII with underscores between
concept words (`taxpayer_nif`, `filing_year`). Avoid:

- Hyphens in role names (reserved for compound tokens like
  `EXT-1T` period codes).
- Modelo-specific role names (`m180_perc_nif`); the role is a
  semantic concept that can cross modelos.
- Section-path role names (`identificacion_nif`); prefer the
  subject relation (`taxpayer_nif`, `payee_nif`).

When introducing a new role, prefer a name that could legitimately
apply to a future sibling casilla in another modelo. If the role
is genuinely modelo-specific, acknowledge it explicitly in this
taxonomy and accept the typo-twin warning as expected output.

## Cross-references

- ADR: schema-hardening canonical semantic-atom layer.
- Plan C: per-role rollout phases W02 through W05.
- Audit: M100 NIF coverage (Bucket classification); M100 NIF role
  assignment (per-id role table); role rollout strategy (cadence).
