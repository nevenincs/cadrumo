---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - "[[2026-05-22-schema-hardening-plan]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - "[[2026-05-22-schema-hardening-research]]"
---



# `schema-hardening` audit: `optional-numeric-suppressor-burn-down`

## Scope

This audit executes P01 of the optional/numeric suppressor burn-down plan. It
records the exact current Modelo 100 and Modelo 200 warning candidates hidden
only by `optional_or_numeric_token_strip`, classifies them into source-visible
families, and chooses the first implementation candidate for manual lookup.

The inventory was generated with the committed registry loader and the real
semantic-role typo-warning helper logic. The simulation disables only the
optional/numeric strip decision; all other existing warning suppressors remain
active.

## Findings

### P01.S01 inventory

Current optional/numeric-disabled exposure: 36 warning candidates.

| # | location | role | near role | source-visible family |
|---:|---|---|---|---|
| 1 | `100.2020.1171` | `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020` | `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat` | C Valenciana public aids, year/legal instrument split |
| 2 | `100.2025.0238` | `irpf_eo_reintegro_subvenciones` | `irpf_eo_agr_reintegro_subvenciones` | Estimacion objetiva ordinary vs agricultural branch |
| 3 | `100.2025.0239` | `irpf_eo_agr_reintegro_subvenciones` | `irpf_eo_reintegro_subvenciones` | Estimacion objetiva ordinary vs agricultural branch |
| 4 | `100.2025.0360` | `irpf_ganancia_premios_juegos_valoracion_b` | `irpf_ganancia_premios_juegos_valoracion` | Prizes/gambling valuation line split |
| 5 | `100.2025.0361` | `irpf_ganancia_premios_juegos_pub_valoracion_b` | `irpf_ganancia_premios_juegos_valoracion` | Prizes/gambling public-source line split |
| 6 | `100.2025.0413` | `irpf_ganancia_inmueble_catastral_4` | `irpf_ganancia_inmueble_catastral_1_b` | Immovable-gain cadastral numbered slot |
| 7 | `100.2025.0776` | `irpf_deduccion_cantabria_generado_pendiente` | `irpf_deduccion_cantabria_generado_2023_pendiente` | Cantabria generated/pending year family |
| 8 | `100.2025.1715` | `irpf_deduccion_cantabria_generado_2025_pendiente` | `irpf_deduccion_cantabria_generado_pendiente` | Cantabria generated/pending year family |
| 9 | `100.2025.1717` | `irpf_deduccion_cantabria_generado_2025_pendiente_2` | `irpf_deduccion_cantabria_generado_pendiente` | Cantabria generated/pending duplicate line |
| 10 | `100.2025.1958` | `irpf_deduccion_c_valenciana_generado_2023_pendiente_3` | `irpf_deduccion_c_valenciana_generado_pendiente` | C Valenciana generated/pending line family |
| 11 | `100.2025.2012` | `irpf_deduccion_c_valenciana_pendiente_2024_linea_4` | `irpf_deduccion_c_valenciana_pendiente_linea_5` | C Valenciana generated/pending line family |
| 12 | `100.2025.2013` | `irpf_deduccion_c_valenciana_pendiente_2023_linea_4` | `irpf_deduccion_c_valenciana_pendiente_linea_5` | C Valenciana generated/pending line family |
| 13 | `100.2025.2014` | `irpf_deduccion_c_valenciana_pendiente_linea_5` | `irpf_deduccion_c_valenciana_pendiente_2023_linea_4` | C Valenciana generated/pending line family |
| 14 | `100.2025.2027` | `irpf_deduccion_madrid_vivienda_municipio_riesgo` | `irpf_deduccion_madrid_vivienda_municipio_riesgo_anio` | Madrid vivienda despoblacion parent vs detail field |
| 15 | `100.2025.2165` | `irpf_deduccion_murcia_generado_2025_pendiente_2` | `irpf_deduccion_murcia_generado_2024_pendiente` | Murcia generated/pending generic role family |
| 16 | `100.2025.2166` | `irpf_deduccion_murcia_generado_2024_pendiente` | `irpf_deduccion_murcia_generado_2025_pendiente_2` | Murcia generated/pending generic role family |
| 17 | `100.2025.2202` | `irpf_anexo_b_aav_importe_satisfecho` | `irpf_anexo_b_importe_satisfecho` | Anexo B AAV branch |
| 18 | `100.2025.2227` | `irpf_ganancia_fondos_coti_valor_transmision_global` | `irpf_ganancia_fondos_valor_transmision_global` | Quoted-fund `coti` gain/loss branch |
| 19 | `100.2025.2228` | `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia` | `irpf_ganancia_fondos_valor_transmision_renta_vitalicia` | Quoted-fund `coti` gain/loss branch |
| 20 | `100.2025.2229` | `irpf_ganancia_fondos_coti_valor_adquisicion_global` | `irpf_ganancia_fondos_valor_adquisicion_global` | Quoted-fund `coti` gain/loss branch |
| 21 | `100.2025.2230` | `irpf_ganancia_fondos_coti_ganancia` | `irpf_ganancia_fondos_ganancia` | Quoted-fund `coti` gain/loss branch |
| 22 | `100.2025.2231` | `irpf_ganancia_fondos_coti_exenta_renta_vitalicia` | `irpf_ganancia_fondos_exenta_renta_vitalicia` | Quoted-fund `coti` gain/loss branch |
| 23 | `100.2025.2234` | `irpf_perdida_fondos_coti_importe_computable` | `irpf_perdida_fondos_importe_computable` | Quoted-fund `coti` gain/loss branch |
| 24 | `100.2025.2243` | `irpf_ganancia_inmueble_catastral_4_b` | `irpf_ganancia_inmueble_catastral_2` | Immovable-gain cadastral numbered slot |
| 25 | `200.2024-y-siguientes.02631` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 26 | `200.2024-y-siguientes.02632` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 27 | `200.2024-y-siguientes.02633` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 28 | `200.2024-y-siguientes.02636` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion` | Modelo 200 mantenimiento-empleo correction family |
| 29 | `200.2024-y-siguientes.02637` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion` | Modelo 200 mantenimiento-empleo correction family |
| 30 | `200.2024-y-siguientes.02638` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion` | Modelo 200 mantenimiento-empleo correction family |
| 31 | `200.2024-y-siguientes.02641` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 32 | `200.2024-y-siguientes.02642` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 33 | `200.2024-y-siguientes.02643` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento` | Modelo 200 mantenimiento-empleo correction family |
| 34 | `200.2024-y-siguientes.02646` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion` | Modelo 200 mantenimiento-empleo correction family |
| 35 | `200.2024-y-siguientes.02647` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion` | Modelo 200 mantenimiento-empleo correction family |
| 36 | `200.2024-y-siguientes.02648` | `is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion` | `is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion` | Modelo 200 mantenimiento-empleo correction family |

### P01.S02 classification

| family | count | initial risk | initial decision |
|---|---:|---|---|
| Modelo 200 mantenimiento-empleo correction family | 12 | High | First source lookup and implementation candidate. |
| Modelo 100 quoted-fund `coti` branch | 6 | High | Source lookup required before any helper. |
| C Valenciana generated/pending line family | 4 | High | Block generic line/year stripping; source lookup required. |
| Cantabria generated/pending year family | 3 | High | Block generic year stripping; source lookup required. |
| Estimacion objetiva ordinary vs agricultural branch | 2 | Medium | Source branch check required. |
| Prizes/gambling valuation line split | 2 | Medium | Source line and public-source check required. |
| Immovable-gain cadastral numbered slots | 2 | High | Continue global cadastral block; exact family review only. |
| Murcia generated/pending generic role family | 2 | High | Block until role base is family-specific. |
| C Valenciana public aids, year/legal instrument split | 1 | High | Treat as legal-instrument-specific pending source lookup. |
| Madrid vivienda despoblacion parent vs detail field | 1 | Medium | Likely parent/detail field boundary, not a warning sibling. |
| Anexo B AAV branch | 1 | Medium | Source branch check required. |

### P01.S03 candidate decision

The first implementation candidate is the Modelo 200 mantenimiento-empleo
correction family because:

- The exposed rows form a complete 12-row grid: con/sin mantenimiento,
  aumento/disminucion, and permanent/current-year/prior-year correction axes.
- The labels explicitly distinguish `RDL 6/2010` from `RDL 13/2010` while
  sharing `DT 13a.2 LIS`, so generic stripping of `sin` is too broad.
- This candidate is isolated to Modelo 200 correction roles and can be tested
  without touching Modelo 100 family-local generated/pending policy.

Initial implementation direction: remove or narrow the global `sin` optional
token behavior and handle the current legitimate maintenance-employment
singletons explicitly after source lookup. The implementation must not treat
`con`/`sin` as a harmless axis globally.

## Recommendations

Proceed to P02 manual source lookup for the selected first candidate, then
decide between exact warning sibling policy and explicit singleton markers.
Do not edit validator code or registry TOML before the P02 source decision is
recorded.

## P02 source lookup

### P02.S04 Modelo 200 mantenimiento-empleo corrections

Source basis:

- Local official AEAT Sociedades 2024 manual, extracted from
  `manual-sociedades-2024.pdf`, separately explains `Libertad de amortización
  con mantenimiento de empleo` and `Libertad de amortización sin mantenimiento
  de empleo`.
- The manual ties the first regime to `RDL 6/2010` and `DT 13a.2 LIS`, with
  an employment-maintenance requirement during the statutory period.
- The manual ties the second regime to `RDL 13/2010` and `DT 13a.2 LIS`, and
  states that the employment-maintenance requirements of the `RDL 6/2010`
  wording were not required for that regime, subject to the special long-term
  investment-project caveat described in the manual.
- The committed Modelo 200 registry mirrors that split in the labels for
  casillas `02631` through `02650`: `RDL 6/2010` rows use `con mantenimiento de
  empleo`; `RDL 13/2010` rows use `sin mantenimiento de empleo`.

Decision:

- `sin` must not remain a global optional semantic-role token.
- The 12 exposed correction rows, `02631` through `02633`, `02636` through
  `02638`, `02641` through `02643`, and `02646` through `02648`, are legally
  distinct singleton role names under the current naming scheme.
- The implementation slice should remove `sin` from broad optional-token
  stripping and mark these 12 rows as explicit `intentional_singleton` entries
  with a source-grounded reason.

### P02.S05 Modelo 100 quoted-fund `coti` family

Source basis:

- Local BOE corpus for `orden-hac-277-2026.html` states that, for Modelo 100
  2025, a new specific section is created to facilitate reporting buy/sell
  operations involving participations or shares of quoted funds and quoted
  index SICAVs under the Reglamento del IRPF reference named in the order.
- Local BOE corpus for `ley-35-2006.html` distinguishes transmissions or
  redemptions involving quoted investment funds and quoted index SICAVs in the
  capital-gains and collective-investment provisions.
- The committed 2025 registry places casillas `2225` through `2236` under
  `gp_fondos_coti`, while older/general fund rows remain under `gp_fondos`.
- Prior audit already records `gp_fondos_coti` as a 2025-only new section and
  treats its roles as coherent single-revision entries, not typo repairs.

Decision:

- `coti` must not be treated as a harmless globally optional token.
- No code normalization for `irpf_ganancia_fondos_coti_*` versus
  `irpf_ganancia_fondos_*` is approved in this slice.
- A later slice may remove `coti` from broad optional stripping and explicitly
  mark or source-map the six exposed 2025 quoted-fund rows.

### P02.S06 generated/pending year and line families

Source basis:

- The committed Modelo 100 registry labels for Cantabria, C. Valenciana,
  Murcia, Madrid, Catalunya, Galicia, and La Rioja pending rows explicitly
  encode generated year, pending application, and sometimes line position.
- Prior role-review audits repeatedly flagged hard-coded year and opaque line
  suffixes as rename candidates, not as evidence that years or line numbers are
  legally irrelevant.
- The local BOE Modelo 100 order explains that autonomic deductions are
  included as differentiated aspects of the unique IRPF model, which supports
  treating CCAA-local carry-forward rows as policy-specific source structure.

Decision:

- Numeric year tokens and line numbers remain blocked from global semantic-role
  normalization.
- Generated/pending families are not approved for helper suppression in this
  slice.
- Future work should use family-local source lookup and role-renaming plans,
  especially for Murcia infrastructure, Madrid new taxpayers, La Rioja, and
  Catalunya carry-forward rows.

### P02.S07 cadastral and miscellaneous optional-token families

Source basis:

- Cadastral rows are repeated numbered data-entry slots in the committed
  registry and prior gain/loss audit; slot numbers are data structure, not
  legal synonyms.
- Prize/gambling valuation rows are source-visible second-block and
  public-source fields introduced or reshaped in 2025; prior audit records
  cross-revision hazards on the same casilla ids.
- Objective-estimation ordinary/agricultural subsidy-reintegration rows live in
  distinct registry sections and the agricultural row label includes the amount
  declared by index application.
- The Madrid housing row `2027` is the deduction amount, while `2029` is the
  acquisition-year detail field. The `anio` token is not optional there.
- The Anexo B `aav` row is branch-specific and should not be collapsed with the
  generic Anexo B amount field without a dedicated source map.

Decision:

- `agr`, `aav`, `b`, `anio`, `precio`, and numeric-token normalization are not
  approved for global burn-down in this slice.
- These families remain blocked until family-local source lookup produces an
  exact helper or explicit singleton policy.

## P03 implementation and verification

### P03.S08 implementation

Implemented only the approved `sin` burn-down:

- Removed `sin` from the global optional semantic-role token set.
- Added explicit `intentional_singleton` markers and reasons to the 12 reviewed
  Modelo 200 maintenance-employment correction casillas:
  `02631`, `02632`, `02633`, `02636`, `02637`, `02638`, `02641`, `02642`,
  `02643`, `02646`, `02647`, and `02648`.
- Did not change `coti`, `agr`, `aav`, `b`, `anio`, `precio`, or numeric-token
  suppression in this implementation slice.

### P03.S09 regression coverage

Added/updated tests so:

- `con`/`sin` maintenance-employment roles are no longer axis siblings without
  explicit source policy.
- Unmarked synthetic `con`/`sin` maintenance-employment near roles emit a
  warning.
- The 12 committed source-reviewed Modelo 200 singleton rows are required to
  carry explicit singleton markers and reasons.
- The reviewed singleton set remains warning-clean after the committed registry
  loads.

### P03.S10 gates

Verification run:

- `uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
  passed, 43 tests.
- `uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`
  passed.
- `uv run pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_committed_registry.py -q`
  passed, 49 tests.
- Direct committed Modelo 100 and Modelo 200 warning probe returned 0 warnings.

One standalone warning-count probe initially failed because it imported a helper
from the wrong public module path. It was rerun through the committed-registry
loader path used by the tests and returned 0 warnings.
