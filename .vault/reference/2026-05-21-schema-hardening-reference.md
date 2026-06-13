---
tags:
  - '#reference'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-schema-hardening-plan]]"
  - "[[2026-05-21-schema-hardening-semantic-role-sidecar-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---



# `schema-hardening` reference: `semantic-role-normalization-guards`

This reference defines the guardrails for future semantic-role normalization
slices that follow the Modelo 100 / Modelo 200 singleton-warning sidecar
audit. It is intentionally a normalization contract, not a source rewrite.
Coding agents should use it before changing any registry `semantic_role`
surface touched by the sidecar.

Grounding sources consulted:

- Modelo 200 official manual at
  `src/aeat/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf`.
- Renta 2025 autonomous-deductions manual at
  `src/aeat/_data/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf`.
- Modelo 200 registry fragments under
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/`.
- Modelo 100 2025 registry fragments under
  `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/`.

## Modelo 200 correction-axis contract

The safe mechanical split is:

- `semantic_role`: the legal or concept base, preserving article,
  disposition, regime, event, entity, or table concept wording already
  encoded in the role stem.
- Structured sidecar metadata: correction-table axes currently embedded
  as suffixes.

Candidate sidecar axes:

- `correction_kind`: `permanente`, `temporaria`, or absent when the form
  line is a balance-only line.
- `exercise_origin`: `ejercicio`, `anteriores`, or absent.
- `movement`: `aumento`, `disminucion`, or absent.
- `balance_position`: `saldo_inicial`, `saldo_final`, or absent.

Examples that should become one preserved base plus sidecar axes, subject
to the mismatch bucket below:

- `is_correccion_cambio_criterios_contables_art11_3_temporaria_ejercicio_aumento`
- `is_correccion_deterioro_valores_representativos_permanente_disminucion`
- `is_correccion_operaciones_vinculadas_valor_mercado_temporaria_anteriores_aumento`
- `is_correccion_operaciones_art19_otras_saldo_inicial`

The sidecar audit counted 472 correction-axis assignments across 72 base
groups, including 253 singleton roles. That scale is enough to justify a
mechanical extraction, but only after the allowlist and mismatch bucket are
locked.

## Preserve-list policy

Extraction must not collapse or rename base slugs carrying legal or
conceptual identity. The following examples are preserve-list members until
a separate policy review says otherwise:

- Article stems such as `is_correccion_asimetrias_hibridas_art15bis`.
- Transitional-provision stems such as
  `is_correccion_deterioro_participaciones_dt16` and
  `is_correccion_reinversion_beneficios_extraordinarios_dt24`.
- Final-provision stems such as
  `is_correccion_impuesto_margen_intereses_comisiones_df9`.
- Special-event stems such as `is_correccion_copa_america_ley_31_2022`.
- Regime/entity stems such as `is_correccion_montes_vecinales_cap_xv`,
  `is_correccion_socio_sicav_liquidaciones`,
  `is_correccion_cooperativas_fondo_reserva_obligatorio`, and port-authority
  correction stems.

Any future change to a preserve-listed base must record the official source,
the old role, the proposed base, the exact axis split, and the reason the
legal/concept identity is unchanged.

## Mismatch bucket

The 23 Modelo 200 records where the official label indicates a temporary
correction but the role suffix says `permanente_*` are excluded from blind
suffix extraction. The affected base groups are:

- `is_correccion_amortizacion_intangible_fondo_comercio`
- `is_correccion_bases_negativas_grupo_fiscal`
- `is_correccion_deterioro_art13_1_provisiones`
- `is_correccion_deterioro_inmovilizado_inversiones_inmobiliarias`
- `is_correccion_deterioro_valores_participaciones_art13_2b`
- `is_correccion_impuesto_extranjero_deduccion_doble_imposicion`
- `is_correccion_libertad_amortizacion_vehiculos`
- `is_correccion_valoracion_bienes_derechos_regimen_especial`

Implementation must either derive the axis from the official label or keep
each record open for manual policy review. It must not infer correctness from
the current role suffix alone.

## Modelo 100 family-local pilot

Repeated labels in Modelo 100 are not a cross-region equivalence proof.
Labels such as `Importe generado en 2025`, `Importe generado en 2025
pendiente de aplicacion`, `Importe generado en 2024 pendiente de aplicacion`,
and `Codigo del municipio:` repeat across autonomous-community deduction
families with separate legal contexts.

The only approved pilot from the sidecar is the
`c_valenciana_autoconsumo` family:

- `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022`
- `irpf_deduccion_c_valenciana_autoconsumo_desde_2023`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_generado`
- `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente`
- `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente`

The `hasta_2022` and `desde_2023` distinctions remain part of the legal
concept family. The family-local sidecar axes are limited to generated year
and pending/application state for the generated/pending rows. No role may be
merged across autonomous communities or deduction families because its label
caption repeats.

## Regression requirements

Future implementation must include real-behavior checks that prove:

- Preserve-listed base slugs remain distinct after extraction.
- The 23 mismatch records are not processed by blind suffix parsing.
- A repeated Modelo 100 label does not create a cross-region normalization.
- The `c_valenciana_autoconsumo` pilot preserves the `hasta_2022` and
  `desde_2023` legal windows while extracting only generated/pending axes.

## Reviewer checklist

Every future normalization slice must answer these before code review:

- Which official manual, registry fragment, or previously approved vault
  record grounds the proposed base/axis split?
- Which role names are changed, and which legal/concept base is preserved?
- Which records are excluded from automation because they are year-specific,
  article-specific, regime-specific, event-specific, or label/role
  inconsistent?
- Which test or validator prevents cross-family normalization by repeated
  label alone?
- Which audit entry records the blast radius and the source references?
