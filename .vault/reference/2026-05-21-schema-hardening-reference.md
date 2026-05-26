---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/reference/ location)
# Feature tag (replace schema-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#reference'
  - '#schema-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-21'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-21-schema-hardening-plan]]"
  - "[[2026-05-21-schema-hardening-semantic-role-sidecar-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

### Warning-sidecar behavior

The semantic-role typo-warning validator may treat the audited correction-table
suffixes as warning axes when two roles preserve the same base stem. This is
only a warning-suppression decision; it does not extract structured correction
metadata or certify the embedded suffix as legally correct.

The warning-sidecar suffix set includes:

- `permanente_aumento`
- `permanente_disminucion`
- `temporaria_ejercicio_aumento`
- `temporaria_ejercicio_disminucion`
- `temporaria_anteriores_aumento`
- `temporaria_anteriores_disminucion`
- `saldo_inicial`
- `saldo_final`

The mismatch bucket remains excluded from future metadata extraction unless a
later policy derives axes from official labels or corrects the registry role
under a source-backed decision.

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

The W04 manual lookup also promoted these source-grounded family-local
generated/pending warning-sidecar candidates:

- `irpf_deduccion_murcia_infraestructuras`
- `irpf_deduccion_madrid_nuevos_contribuyentes`

For warning-suppression only, these promoted families may treat family-local
`generado`, `pendiente`, `2025_generado`, `2025_pendiente`, and
`2024_pendiente` suffixes as generated-year and pending-state axes.

The following remain blocked until a registry role correction or separate
source-data policy creates a family-specific preserved base:

- `irpf_deduccion_la_rioja_generado_2025`
- `irpf_deduccion_la_rioja_generado_2025_pendiente`
- `irpf_deduccion_catalunya_generado_2025`
- `irpf_deduccion_catalunya_pendiente_ejercicio_anterior`

These La Rioja and Catalunya roles are source-identified but currently
CCAA-generic. They must not be normalized by a generated/pending suffix rule.

### Cross-CCAA warning boundary

Autonomous-community tokens are not warning-sidecar axes by themselves.
Roles such as `irpf_deduccion_murcia_vehiculo_importe` and
`irpf_deduccion_asturias_vehiculo_importe`, or
`irpf_deduccion_andalucia_nacimiento_adopcion` and
`irpf_deduccion_madrid_nacimiento_adopcion`, must not be treated as role
siblings merely because the non-region tokens are similar.

If a current registry role is a legitimate region-local singleton, the
registry must mark it with `semantic_role_cardinality = "intentional_singleton"`
and a source-backed reason. The warning validator must not hide it through a
global CCAA normalization rule.

### Legal-reference warning boundary

Legal-reference tokens are not warning-sidecar axes by themselves. Role
fragments such as `art11_4`, `dt1`, `rdleg`, and `lis` identify source-visible
legal regimes or provisions and must stay inside the preserved role stem unless
a later source-backed policy explicitly says otherwise.

The warning validator must therefore not treat these as typo-warning siblings:

- `is_correccion_operaciones_a_plazos_art11_4_permanente_aumento` and
  `is_correccion_operaciones_a_plazos_dt1_permanente_aumento`
- `is_deduccion_di_internacional_rdleg_pendiente` and
  `is_deduccion_di_internacional_pendiente`

If a current registry role is a legitimate legal-reference-specific singleton,
the registry must mark it with
`semantic_role_cardinality = "intentional_singleton"` and a source-backed
reason. The warning validator must not hide it through generic article,
transitional-provision, RDLeg, or LIS token stripping.

### Generic warning-suppressor control boundary

The remaining older warning suppressors are not all equally source-grounded.
Future work must distinguish exact source-backed helper families from generic
token stripping:

- The correction suffix guard is already tied to the Modelo 200 correction
  table contract and remains warning-only unless a later extractor policy is
  approved.
- The Anexo C carryforward, deferred-imputation slot, and family-local
  generated/pending helpers are exact allowlists from prior source-audit
  slices.
- The `axis_token_group` helper is a mixed legacy helper. Its current exposure
  includes relationship fields, birth/death fields, RIC Canarias type letters,
  internal/international DI, liquidacion roman numerals, and
  detail/other-correction roles. Each token group needs its own source-backed
  boundary before promotion or removal.
- The `optional_or_numeric_token_strip` helper is the highest-risk remaining
  broad suppressor because it strips optional words and all numeric tokens.
  Its current exposure includes year-specific C Valenciana and Cantabria rows,
  Murcia generated/pending rows, catastral slots, quoted-fund `coti` branches,
  and Modelo 200 `con/sin mantenimiento de empleo` rows. Do not replace it
  with another broad rule; burn it down by exact family-local policies.

## Modelo 100 audited warning-sidecar guards

The W08 source lookup adds two source-grounded warning-sidecar recognizers.
These recognizers only decide whether singleton `semantic_role` names are
axis siblings for typo-warning purposes. They do not rename registry roles,
rewrite role bases, or define legal concepts.

### Anexo C carryforward

The Anexo C carryforward guard is limited to the source-confirmed carryforward
baskets recorded in the sidecar audit. It may treat the following state
suffixes as axes within the same preserved basket:

- `pendiente_inicio`
- `aplicado`
- `pendiente_fin`
- `generado`

It must preserve the basket stem. For example,
`irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` and
`irpf_anexo_c_saldo_neg_gyp_general_aplicado` are warning-sidecar siblings,
but `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` and
`irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` are not.

Typo-adjacent stems remain blocked from automatic equivalence. In particular,
`irpf_anexo_c_exceso_eeficiencia_*` must not be equated to
`irpf_anexo_c_exceso_eficiencia_energetica_*` without a separate
semantic-role correction policy.

### Deferred imputation

The deferred-imputation guard is limited to the source-confirmed Anexo C.1
slot layout for:

- ordinary patrimonial elements,
- cryptocurrency elements,
- immovable-property elements.

It may treat slot numbers and `resto` as slot axes inside the same branch and
field. It may also treat `pendiente_imputacion` as the same pending field
label shape where the dictionary uses that spelling in a branch-local slot.

It must not merge:

- ordinary, cryptocurrency, and immovable-property branches,
- `ganancia` and `perdida` polarity,
- amount, year, pending-gain, and pending-loss fields.

### Cadastral references

The W08 audit blocks global cadastral-reference normalization. The validator
therefore must not treat text cadastral-reference roles and logical
no-reference marker roles as axis siblings merely because their labels share
`Referencia catastral`.

Future family-local cadastral slot extraction requires a separate exact-ID
policy decision that preserves field type and source family.

## Regression requirements

Future implementation must include real-behavior checks that prove:

- Preserve-listed base slugs remain distinct after extraction.
- The 23 mismatch records are not processed by blind suffix parsing.
- A repeated Modelo 100 label does not create a cross-region normalization.
- The `c_valenciana_autoconsumo` pilot preserves the `hasta_2022` and
  `desde_2023` legal windows while extracting only generated/pending axes.
- The Murcia infraestructuras and Madrid nuevos contribuyentes generated and
  pending roles suppress typo warnings only inside their exact family bases.
- The La Rioja and Catalunya generated/pending pairs remain non-siblings while
  their role bases are CCAA-generic.
- Cross-CCAA role names remain non-siblings unless a later source-backed
  policy adds an exact family rule; current region-local singleton rows must
  be marked explicitly as intentional singletons.
- Legal-reference role names remain non-siblings unless a later source-backed
  policy adds an exact family rule; current article, transitional-provision,
  RDLeg, and LIS singletons must be marked explicitly as intentional
  singletons.
- The legacy optional/numeric stripping helper must be reduced only through
  exact source-backed family policies; each exposed family must have a test
  proving adjacent legal/year/field concepts remain non-siblings.
- The first optional/numeric burn-down removes only `sin` from the broad
  optional-token list. Modelo 200 `con/sin mantenimiento de empleo` roles are
  legally distinct because the AEAT Sociedades manual separates the `RDL
  6/2010` employment-maintenance regime from the `RDL 13/2010` no-maintenance
  regime. Current correction rows must be explicit `intentional_singleton`
  entries rather than hidden by generic negation stripping.
- `coti`, generated/pending years, line numbers, cadastral slot numbers,
  `agr`, `aav`, `b`, `anio`, and `precio` remain broad optional/numeric debt.
  They must not be promoted without a family-local source map and tests proving
  adjacent legal, year, branch, and detail fields remain distinct.
- The second optional/numeric burn-down removes only `coti` from the broad
  optional-token list. Modelo 100 2025 `gp_fondos_coti` roles are a separate
  quoted-fund source family, grounded in the Modelo 100 2025 order and
  committed registry sectioning. Current warning-exposed rows are explicit
  `intentional_singleton` entries rather than hidden by generic token
  stripping.
- The legacy axis-token group helper must be reviewed token group by token
  group; `interna`/`internacional`, `i`/`ii`/`iii`/`iv`, and
  `detalle`/`otras` are not automatically safe outside their source context.
- The Anexo C warning-sidecar guard suppresses only same-basket state axes and
  keeps separate baskets distinct.
- The deferred-imputation warning-sidecar guard suppresses only same-branch
  slot axes and keeps branch and gain/loss polarity distinct.
- Cadastral reference text fields and no-reference logical marker fields remain
  non-siblings unless a later exact-ID policy explicitly authorizes a
  family-local extractor.

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
