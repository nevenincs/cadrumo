---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
  - '[[2026-05-20-schema-hardening-verification-ledger-audit]]'
  - '[[2026-05-20-schema-hardening-plan]]'
---

# `schema-hardening` semantic_role sidecar audit

## Purpose

This audit records the semantic-role taxonomy sidecar review requested for
the large singleton warning clusters in Modelo 100 and Modelo 200. The review
was explicitly concerned with avoiding blind or programmatic normalization of
legally binding tax semantics.

The sidecar did not modify registry source files. Its purpose was to identify
which warning clusters are mechanical taxonomy-axis noise and which clusters
carry region, year-window, regime, article, transitional-provision, or
event-specific legal meaning that must remain policy gated.

## Process correction

The initial sidecar work was reported as read-only because the original task
requested no file edits. The current instruction requires this work to be
tracked through the vault workflow. This document is the durable audit/review
record for the sidecar findings, and the continuation plan is recorded in
`2026-05-21-schema-hardening-plan`.

The first continuation plan was incorrectly authored by hand after checking
for a `vault` executable instead of the project command
`uv run vaultspec-core vault plan`. That hand-authored plan was removed and
recreated through `vaultspec-core` before execution continued.

## Grounding sources

- Modelo 200 official manual: `src/aeat/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf`.
- Renta 2025 autonomous deductions manual: `src/aeat/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf`.
- Modelo 200 registry fragments under `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`.
- Modelo 100 2025 registry fragments under `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/`.
- Existing semantic-role authority: `2026-05-18-schema-hardening-adr`, `2026-05-19-schema-hardening-role-taxonomy-reference`, and `2026-05-20-schema-hardening-verification-ledger`.

`pdftotext` emitted embedded-font warnings while extracting text from the
official PDFs, but the relevant labels, headings, and table-axis text were
recoverable and were cross-checked against registry labels.

## Slice 1 - Modelo 200 correction-axis surface

Fresh parsing of the Modelo 200 2024+ casilla fragments found 472
correction-axis role assignments across 72 base groups. 253 of those
assignments were singleton roles. The dominant pattern is a legal/concept
base slug with table axes embedded into the role name.

Examples:

- `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento`
- `is_correccion_deterioro_valores_representativos_permanente_disminucion`
- `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_aumento`
- `is_correccion_operaciones_art19_otras_saldo_inicial`

The Modelo 200 manual grounds these as form/table axes for correction detail:
permanent versus temporary corrections, current versus prior exercise origin,
increase versus decrease, and opening versus closing pending balances.

Finding: this is the strongest mechanical burn-down candidate. The role base
must remain the legal/concept identity; the suffixes are candidates for
structured metadata.

## Slice 2 - Modelo 200 legally meaningful bases

The same Modelo 200 surface contains base slugs whose legal markers must not
be normalized away. Labels and role stems include article, transitional
provision, additional provision, final provision, regime, SICAV, cooperative,
port-authority, and special-event markers.

Examples to keep policy gated:

- `is_correccion_copa_america_ley_31_2022`
- `is_correccion_deterioro_participaciones_dt16`
- `is_correccion_reinversion_beneficios_extraordinarios_dt24`
- `is_correccion_impuesto_margen_intereses_comisiones_df9`
- `is_correccion_montes_vecinales_cap_xv`
- `is_correccion_socio_sicav_liquidaciones`
- `is_correccion_cooperativas_fondo_reserva_obligatorio`
- `is_correccion_asimetrias_hibridas_art15bis`

Finding: mechanical extraction may remove table axes from the role identity,
but it must not collapse these legal/concept bases without a separate
policy-backed decision.

## Slice 3 - Modelo 200 label-vs-role axis mismatches

A label-versus-role comparison found 23 records across 8 base groups where
the official label text says a temporary correction axis while the current
role suffix says `permanente_*`.

Affected base groups:

- `is_correccion_amortizacion_intangible_fondo_comercio`
- `is_correccion_bases_negativas_grupo_fiscal`
- `is_correccion_deterioro_art13_1_provisiones`
- `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias`
- `is_correccion_deterioro_valores_participaciones_art13_2b`
- `is_correccion_impuesto_extranjero_deduccion_doble_imposicion`
- `is_correccion_libertad_amortizacion_vehiculos`
- `is_correccion_valoracion_bienes_derechos_regimen_especial`

Finding: these records must be carved out of any blind suffix-based
extraction. Either the axis must be derived from official labels or each
mismatch must be reviewed and corrected under policy.

## Slice 4 - Modelo 100 regional repeated-label surface

Modelo 100 2025 has repeated labels that are mostly singleton roles:

- `Importe generado en 2025`: 13 rows, 13 singleton roles.
- `Importe generado en 2025 pendiente de aplicación`: 15 rows, 14 singleton roles.
- `Importe generado en 2024 pendiente de aplicación`: 14 rows, 14 singleton roles.
- `Código del municipio:`: 6 rows, 6 singleton roles.

Examples:

- `irpf_deduccion_cantabria_generado_2025`
- `irpf_deduccion_galicia_generado_2025_pendiente`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`
- `irpf_deduccion_murcia_infraestructuras_2025_pendiente`
- `irpf_deduccion_la_rioja_generado_2025_pendiente`

The Renta 2025 autonomous deductions manual confirms that these labels sit
inside separate autonomous-community deduction families. The same caption does
not establish the same legal concept.

Finding: Modelo 100 should not be normalized across regions or deduction
families by repeated label alone. Only already-confirmed family-local axes
should be extracted.

## Slice 5 - Modelo 100 `c_valenciana_autoconsumo`

This is the best narrow Modelo 100 pilot because the official manual and
registry labels both expose the family boundaries.

Fields inspected:

- `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022`
- `irpf_deduccion_c_valenciana_autoconsumo_desde_2023`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_generado`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`
- `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente`

The manual explicitly distinguishes quantities invested up to 2022 from those
invested from 2023, and separately describes generated, applied, and pending
amounts with carryforward into the following three tax periods.

Finding: `hasta_2022` and `desde_2023` are legal/year-window concepts, not
cleanup noise. The generated/pending suffixes are candidate metadata inside
this already-confirmed family.

## Review conclusion

The next implementation work must proceed in two guarded tracks:

1. Modelo 200 correction-axis extraction, excluding the 23 mismatch records
   and preserving every legal/concept base slug.
2. Modelo 100 family-local carryforward-axis extraction, starting with
   `c_valenciana_autoconsumo`, with no cross-region merge by repeated label.

No source registry edit should proceed without a per-slice audit entry stating
the official source, the proposed role/base split, and the legal-policy
boundary for concepts that must not be normalized.
