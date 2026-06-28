---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
---

# schema-hardening m100 rendimientos-economicos-resto role assignments

## Scope

Cluster: `rendimientos-economicos-resto`
Sections covered: `actividad_est_obj`, `rendimientos_actividades_economicas`, `re_at_rentas`, `regimen_especial`, `rdto_trabajo`, `rdto_capital_mobiliario_general`, `rdto_capital_mobiliario_dt4`
Total casilla ids classified: 15
Read-only audit — no TOML modifications.

Cross-revision TOML evidence gathered from revisions 2020–2025 under
`src/aeat/_data/registry/aeat/modelos/100/revisions/`.

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0002 | `irpf_rdto_trabajo_cesion_derechos_autor_anticipo_flag` | En el caso de los rendimientos derivados de la cesión de la explotación de los derechos de... | boolean | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Opt-in flag for deferring advance recognition of author-rights exploitation income. Section `rdto_trabajo`. |
| 0043 | `irpf_rendimiento_capital_mobiliario_ahorro_dt4_capital_diferido_acumulado` | Importe total acumulado del capital diferido percibido en 2015–2024 a cuyo rendimiento se aplicó la DT 4.ª | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Extends `irpf_rendimiento_capital_mobiliario_ahorro_*` family. DT 4ª transitional accumulated deferred capital. |
| 0044 | `irpf_rendimiento_capital_mobiliario_ahorro_dt4_seguros_vida_importe` | Importe total de los capitales diferidos correspondientes a seguros de vida percibidos en... | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | New role. DT 4ª life-insurance deferred capital total. |
| 0049 | `irpf_rendimiento_capital_mobiliario_general_cesion_derechos_autor_anticipo_flag` | En el caso de los rendimientos derivados de la cesión de la explotación de los derechos de... | boolean | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Same conceptual opt-in as 0002 but within `rdto_capital_mobiliario_general` section. |
| 0157 | `irpf_eo_reduccion_la_palma` | Reducción para actividades económicas desarrolladas en la isla de La Palma (Canarias) | money(default) | 2022, 2023, 2024 | New role. Extends `irpf_eo_*` family. Emergency reduction for La Palma (Canarias). |
| 0161a | `irpf_eo_reduccion_dana_municipios` | Reducción para actividades económicas por los daños producidos por la DANA | money(default) | 2024 | New role. Id-reuse row 1 of 2. Section `actividad_est_obj` rev 2024. DANA emergency reduction. |
| 0161b | `irpf_re_at_estimacion_directa_normal_flag` | Régimen estimación directa normal | boolean | 2025 | New role. Id-reuse row 2 of 2. Section `re_at_rentas` rev 2025. Flag indicating direct-normal estimation regime for atribución-de-rentas entity. |
| 0162 | `irpf_re_at_estimacion_directa_simplificada_flag` | Régimen estimación directa simplificada | boolean | 2025 | New role. Section `re_at_rentas`. Flag indicating direct-simplified estimation regime. |
| 0224 | `irpf_rendimiento_act_eco_estimacion_directa_rdto_neto` | Rendimiento neto de actividades economicas en estimacion directa | money(default) | 2021, 2022, 2023, 2024, 2025 | New role. Summary carry-forward of net yield from direct-estimation economic activities. |
| 0414a | `irpf_re_especial_tfi_declarante_num_operaciones` | DECLARANTE: Nº de operaciones | money(default) | 2020, 2021, 2022 | New role. Id-reuse row 1 of 2. Regimen especial TFI — number of operations (declarant). Revs 2020–2022 only. |
| 0416a | `irpf_re_especial_tfi_conyuge_num_operaciones` | CONYUGE: Nº de operaciones | money(default) | 2020, 2021, 2022 | New role. Id-reuse row 1 of 2. TFI — number of operations (spouse). Revs 2020–2022. |
| 0416b | `irpf_re_especial_tfi_fusiones_afectado_flag` | Si los contribuyentes, socios de entidades no residentes en España, se han visto afectados... fusión, escisión o canje | boolean | 2023, 2024, 2025 | New role. Id-reuse row 2 of 2. TFI — taxpayer affected by merger/split/share-exchange. Revs 2023–2025. |
| 0417 | `irpf_re_especial_tfi_no_regimen_similar_flag` | Si las entidades no residentes no han aplicado un régimen fiscal similar... | boolean | 2020, 2021, 2022, 2023, 2024, 2025 | New role. Labels vary slightly across years (affected wording) but concept is stable: TFI marker that non-resident entity did not apply equivalent fiscal regime. |
| 1476a | `irpf_eo_reduccion_lorca` | Reducción para actividades económicas desarrolladas en el término municipal de Lorca (Murcia) | money(default) | 2020, 2021, 2022, 2023, 2024 | New role. Id-reuse row 1 of 2. Section `actividad_est_obj`. Extends `irpf_eo_*` family. |
| 1479a | `irpf_eo_actividad_rdto_neto_actividad` | Rendimiento neto de la actividad | decimal | 2020 | New role. Id-reuse row 1 of 2. Detail-section `actividad_est_obj` rev 2020; decimal per-activity net yield field. |
| 1479b | `irpf_rendimiento_act_eco_eo_resto_rdto_neto` | Rendimiento neto de actividades economicas en estimacion objetiva excepto agricolas, ganaderas y forestales | money(default) | 2021, 2022, 2023, 2024, 2025 | New role. Id-reuse row 2 of 2. Section `rendimientos_actividades_economicas` 2021+. Summary EO non-agricultural net yield. |
| 1553 | `irpf_rendimiento_act_eco_eo_agr_rdto_neto` | Rendimiento neto de actividades agricolas ganaderas y forestales en estimacion objetiva | money(default) | 2021, 2022, 2023, 2024, 2025 | New role. Complements `irpf_eo_agr_rdto_neto_reducido` (detail section); this is the consolidated summary for `rendimientos_actividades_economicas`. |
| 1577a | `irpf_re_at_rdto_neto_estimacion_directa_objetiva` | Rendimiento neto (estimación directa normal y estimación objetiva) / Rendimiento neto previo (estimación directa simplificada) | decimal | 2020 | New role. Id-reuse row 1 of 2. Section `re_at_rentas` rev 2020; decimal per-entity yield entry in atribución-de-rentas detail screen. |
| 1577b | `irpf_rendimiento_act_eco_atribuido_rdto_neto` | Rendimiento neto de actividad economica atribuido por entidades en regimen de atribucion de rentas | money(default) | 2021, 2022, 2023, 2024, 2025 | New role. Id-reuse row 2 of 2. Section `rendimientos_actividades_economicas` 2021+; consolidated atribución-de-rentas economic-activity net yield. |

## Id-reuse hazards

Five casilla ids carry distinct concepts across revisions. Each is split into labelled rows (a, b) above.

**0161** — Concept switch between rev 2024 and rev 2025, plus section change:
- Rev 2024 (`actividad_est_obj`, `money(default)`): emergency DANA reduction for affected municipalities.
- Rev 2025 (`re_at_rentas`, `boolean`): flag for direct-normal estimation regime in atribución-de-rentas block.
  Action: two distinct roles `irpf_eo_reduccion_dana_municipios` (2024) and `irpf_re_at_estimacion_directa_normal_flag` (2025).

**0414** — Concept switch between revs 2020–2022 and revs 2023+:
- Revs 2020–2022 (`regimen_especial`, `money(default)`): "DECLARANTE: Nº de operaciones" in TFI block.
- Rev 2025 TOML shows id `0414` in `resultado_declaracion` as "Deduccion por obtencion de rendimientos del trabajo" — entirely different domain. The cluster JSON only covers 2020–2022 so the cluster scope stops there; the 2025 meaning falls outside this cluster. Row 0414a covers the in-scope concept only.

**0416** — Concept and data_type switch between revs 2020–2022 and revs 2023–2025:
- Revs 2020–2022 (`money(default)`): "CONYUGE: Nº de operaciones".
- Revs 2023–2025 (`boolean`): taxpayer affected by merger/spin-off/share-exchange of non-resident entity.
  Data_type divergence coincides with concept switch.

**1476** — Concept switch between revs 2020–2024 and rev 2025:
- Revs 2020–2024 (`actividad_est_obj`, `money(default)`): Lorca (Murcia) municipal activity reduction.
- Rev 2025 TOML shows id `1476` in `resultados/deduccion_autonomica_res/andalucia_res` as Andalucía celiac deduction (`irpf_deduccion_andalucia_enfermedad_celiaca`). This is outside the rendimientos-economicos-resto cluster; rev 2025 falls out of scope. Row 1476a covers 2020–2024 only.

**1479** — Section and data_type change between rev 2020 and revs 2021–2025:
- Rev 2020 (`actividad_est_obj`, `decimal`): individual-activity net yield in the EO detail tab.
- Revs 2021–2025 (`rendimientos_actividades_economicas`, `money(default)`): aggregate EO non-agricultural net yield in the summary section.

**1577** — Section and data_type change between rev 2020 and revs 2021–2025:
- Rev 2020 (`re_at_rentas`, `decimal`): per-entity net yield field in atribución-de-rentas detail.
- Revs 2021–2025 (`rendimientos_actividades_economicas`, `money(default)`): consolidated atribución-de-rentas economic-activity net yield in summary.

## Data_type divergences

| id | divergence | revisions |
|----|------------|-----------|
| 0416 | `money(default)` (2020–2022) vs `boolean` (2023–2025) | Coincides with concept switch; both rows carry a consistent type within their range. |
| 1479 | `decimal` (2020) vs `money(default)` (2021–2025) | Coincides with section/concept switch; consistent within each range. |
| 1577 | `decimal` (2020) vs `money(default)` (2021–2025) | Same pattern as 1479; consistent within each range. |

No same-concept data_type inconsistencies found. All divergences are revision-bounded and coincide with confirmed id-reuse concept switches documented above.
