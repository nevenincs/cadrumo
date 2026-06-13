---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# schema-hardening audit: M200 IS deducciones-b role assignment

## Scope

Cluster: **deducciones-b** — M200 2024-y-siguientes revision.
Total casillas classified: **279**.
Section families covered (8):

| Section family | Count |
|---|---|
| `deducc_para_incentivar_determ_actividades` | 88 |
| `deduccion_por_reversion_de_medidas_temporales_d_t` | 75 |
| `deducciones_inversion_canarias` | 64 |
| `deducciones_doble_imposicion_internacional_lis` | 29 |
| `deducc_disposic_transit_24a_7_lis` | 17 |
| `deducciones_doble_imposicion_internacional_rdleg_4` | 2 |
| `deducciones_doble_imposicion_interna_rdleg_4_2004` | 2 |
| `deduccion_del_30_importe_gastos_de_amortiz_contabl` | 2 |

Role sources: 11 roles reused verbatim from `_existing-roles.txt`; 23 new roles coined.

### Role naming conventions applied

Deduction lines follow a repeating three-axis structure: **generated/pending-opening** (`generado`), **applied this period** (`periodo`), **pending carry-forward** (`pendiente`). An additional **base** axis appears for DT37.2 lines. The roles encode `<concept>_<axis>`:

- `_generado` — importe generado / pendiente principio periodo (opening balance)
- `_periodo` — aplicado en esta liquidación
- `_pendiente` — pendiente de aplicación en periodos futuros
- `_base` — base de deducción (DT37.2 only)
- `_tipo_gravamen` — tipo gravamen período generación (decimal %)
- `_total` — aggregate / total row

New roles coined for this cluster use the existing M200 `is_` prefix convention. Vintage years embedded in labels are retained in role names when they form part of the canonical tax concept (e.g. `is_deduccion_idi_investigacion_desarrollo_ct_periodo` groups all CT-regime I+D applied entries regardless of year, since the year is the section dimension, not the role dimension). The `diferimiento` sub-concept within `incentivar` deductions keeps `_diferimiento` as its axis suffix.

---

## Role assignments

### Legend for notes column

- `reused` — exact role already in `_existing-roles.txt`
- `new` — new role coined for this cluster
- `only-applied` — cluster entry has no matching pending row (edge case)
- `only-pending` — cluster entry has no matching applied row (edge case)
- `single-decimal` — only the tipo-gravamen row present for this year (no amount rows in cluster)

---

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00182 | `is_deduccion_idi_suma_pendiente` | 2008 Suma deducciones - Pendiente de aplicación | money | new |
| 00829 | `is_deduccion_idi_diferimiento_periodo` | 2025 Diferim. deducciones Cap.IV Tít.VI - Ap | money | new; reuses existing `is_deduccion_idi_diferimiento` concept |
| 00830 | `is_deduccion_idi_diferimiento_pendiente` | 2025 Diferim. deducciones Cap.IV Tít.VI - Pe | money | new |
| 00832 | `is_deduccion_idi_suma_pendiente` | Total - Pendiente de aplicación en periodos futuros | money | new; total row |
| 00881 | `is_deduccion_inversiones_africa_canarias_periodo` | 2023 Inversiones territ. África Occ. - (axis truncated) | money | new; reuses existing `is_deduccion_inversiones_africa_canarias` concept |
| 00946 | `is_deduccion_idi_suma_periodo` | 2010 Suma deducciones - Aplicado en esta liquidación | money | reused (`is_deduccion_idi_suma_periodo`) |
| 00947 | `is_deduccion_idi_suma_pendiente` | 2010 Suma deducciones - Pendiente de aplicación | money | new |
| 00961 | `is_deduccion_idi_suma_periodo` | 2011 Suma deducciones - Aplicado en esta liquidación | money | reused |
| 00962 | `is_deduccion_idi_suma_pendiente` | 2011 Suma deducciones - Pendiente de aplicación | money | new |
| 00967 | `is_deduccion_idi_suma_periodo` | 2013 Suma deducciones - Aplicado en esta liquidación | money | reused |
| 00968 | `is_deduccion_idi_suma_pendiente` | 2013 Suma deducciones - Pendiente de aplicación | money | new |
| 01064 | `is_deduccion_idi_suma_periodo` | 2014 Suma deducciones - Aplicado en esta liquidación | money | reused |
| 01065 | `is_deduccion_idi_suma_pendiente` | 2014 Suma deducciones - Pendiente de aplicación | money | new |
| 01067 | `is_deduccion_idi_investigacion_aplicada` | 2014 Investigación y desarrollo - Aplicado | money | reused (`is_deduccion_idi_investigacion_aplicada`) |
| 01068 | `is_deduccion_idi_investigacion_pendiente` | 2014 Investigación y desarrollo - Pendiente | money | new |
| 01070 | `is_deduccion_idi_innovacion_tecnologica` | 2014 Innovación tecnológica - Aplicado | money | reused (`is_deduccion_idi_innovacion_tecnologica`) |
| 01071 | `is_deduccion_idi_innovacion_pendiente` | 2014 Innovación tecnológica - Pendiente | money | new |
| 01364 | `is_deduccion_idi_investigacion_aplicada` | 2025(*) Investigación y desarrollo (CT) - Aplicado | money | reused |
| 01365 | `is_deduccion_idi_investigacion_pendiente` | 2025(*) Investigación y desarrollo (CT) - Pendiente | money | new |
| 01367 | `is_deduccion_idi_innovacion_tecnologica` | 2025(*) Innovación tecnológica (IT) - Aplicado | money | reused |
| 01368 | `is_deduccion_idi_innovacion_pendiente` | 2025(*) Innovación tecnológica (IT) - Pendiente | money | new |
| 01618 | `is_deduccion_idi_investigacion_aplicada` | 2016 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 01619 | `is_deduccion_idi_investigacion_pendiente` | 2016 Investigación y desarrollo (CT) - Pendiente | money | new |
| 01621 | `is_deduccion_idi_innovacion_tecnologica` | 2016 Innovación tecnológica (IT) - Aplicado | money | reused |
| 01622 | `is_deduccion_idi_innovacion_pendiente` | 2016 Innovación tecnológica (IT) - Pendiente | money | new |
| 01684 | `is_deduccion_copa_america_periodo` | 2026(****) Otras deducciones programas apoyo acontec. - Ap | money | reused (`is_deduccion_copa_america_periodo`); generic event-support deduction |
| 01685 | `is_deduccion_copa_america_total` | 2026(****) Otras deducciones programas apoyo acontec. - Pe | money | reused (`is_deduccion_copa_america_total`); pending axis for event-support deductions |
| 01849 | `is_deduccion_idi_suma_periodo` | 2022 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 01851 | `is_deduccion_idi_investigacion_aplicada` | 2017 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 01852 | `is_deduccion_idi_investigacion_pendiente` | 2017 Investigación y desarrollo (CT) - Pendiente | money | new |
| 01854 | `is_deduccion_idi_innovacion_tecnologica` | 2017 Innovación tecnológica (IT) - Aplicado | money | reused |
| 01855 | `is_deduccion_idi_innovacion_pendiente` | 2017 Innovación tecnológica (IT) - Pendiente | money | new |
| 01875 | `is_deduccion_idi_investigacion_aplicada` | 2022 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 01876 | `is_deduccion_idi_investigacion_pendiente` | 2022 Investigación y desarrollo (CT) - Pendiente | money | new |
| 01895 | `is_deduccion_idi_innovacion_tecnologica` | 2022 Innovación tecnológica (IT) - Aplicado | money | reused |
| 01896 | `is_deduccion_idi_innovacion_pendiente` | 2022 Innovación tecnológica (IT) - Pendiente | money | new |
| 01898 | `is_deduccion_inversiones_africa_canarias_periodo` | 2022 Inversiones territ. África Occ. - Aplicado | money | new |
| 01899 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2022 Inversiones territ. África Occ. - Pendiente | money | new |
| 01917 | `is_deduccion_inversiones_africa_canarias_periodo` | 2018 Inversiones territ. África Occ. - Aplicado | money | new |
| 01918 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2018 Inversiones territ. África Occ. - Pendiente | money | new |
| 01920 | `is_deduccion_inversiones_africa_canarias_periodo` | 2019 Inversiones territ. África Occ. - Aplicado | money | new |
| 01921 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2019 Inversiones territ. África Occ. - Pendiente | money | new |
| 01923 | `is_deduccion_inversiones_africa_canarias_periodo` | 2020 Inversiones territ. África Occ. - Aplicado | money | new |
| 01924 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2020 Inversiones territ. África Occ. - Pendiente | money | new |
| 01926 | `is_deduccion_inversiones_africa_canarias_periodo` | 2021 Inversiones territ. África Occ. - Aplicado | money | new |
| 01927 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2021 Inversiones territ. África Occ. - Pendiente | money | new |
| 01929 | `is_deduccion_inversiones_africa_canarias_periodo` | 2025(*) Inversiones territ. África Occ. - Aplicado | money | new |
| 01930 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2025(*) Inversiones territ. África Occ. - Pendiente | money | new |
| 02082 | `is_deduccion_inversiones_africa_canarias_periodo` | 2015 Inversiones territ. África Occ. - Aplicado | money | new |
| 02083 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2015 Inversiones territ. África Occ. - Pendiente | money | new |
| 02085 | `is_deduccion_inversiones_africa_canarias_periodo` | 2016 Inversiones territ. África Occ. - Aplicado | money | new |
| 02086 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2016 Inversiones territ. África Occ. - Pendiente | money | new |
| 02089 | `is_deduccion_inversiones_africa_canarias_periodo` | 2017 Inversiones territ. África Occ. - Aplicado | money | new |
| 02090 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2017 Inversiones territ. África Occ. - Pendiente | money | new |
| 02092 | `is_deduccion_idi_suma_periodo` | 2018 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02093 | `is_deduccion_idi_suma_pendiente` | 2018 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 02095 | `is_deduccion_idi_suma_periodo` | 2019 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02096 | `is_deduccion_idi_suma_pendiente` | 2019 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 02098 | `is_deduccion_idi_suma_periodo` | 2020 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02099 | `is_deduccion_idi_suma_pendiente` | 2020 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 02146 | `is_deduccion_idi_suma_periodo` | 2021 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02222 | `is_deduccion_idi_investigacion_aplicada` | 2018 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 02223 | `is_deduccion_idi_investigacion_pendiente` | 2018 Investigación y desarrollo (CT) - Pendiente | money | new |
| 02225 | `is_deduccion_idi_innovacion_tecnologica` | 2018 Innovación tecnológica (IT) - Aplicado | money | reused |
| 02226 | `is_deduccion_idi_innovacion_pendiente` | 2018 Innovación tecnológica (IT) - Pendiente | money | new |
| 02295 | `is_deduccion_idi_suma_periodo` | 2015 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02296 | `is_deduccion_idi_suma_pendiente` | 2015 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 02298 | `is_deduccion_idi_suma_periodo` | 2016 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 02299 | `is_deduccion_idi_suma_pendiente` | 2016 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 02357 | `is_deduccion_idi_investigacion_aplicada` | 2019 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 02358 | `is_deduccion_idi_investigacion_pendiente` | 2019 Investigación y desarrollo (CT) - Pendiente | money | new |
| 02360 | `is_deduccion_idi_innovacion_tecnologica` | 2019 Innovación tecnológica (IT) - Aplicado | money | reused |
| 02361 | `is_deduccion_idi_innovacion_pendiente` | 2019 Innovación tecnológica (IT) - Pendiente | money | new |
| 02450 | `is_deduccion_idi_suma_periodo` | 2025(*) Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 03437 | `is_deduccion_idi_suma_periodo` | 2024 Suma deducciones Cap.IV Tit.VI - Aplicado | money | reused |
| 03438 | `is_deduccion_idi_suma_pendiente` | 2024 Suma deducciones Cap.IV Tit.VI - Pendiente | money | new |
| 03440 | `is_deduccion_idi_investigacion_aplicada` | 2024 Investigación y desarrollo (CT) - Aplicado | money | reused |
| 03441 | `is_deduccion_idi_investigacion_pendiente` | 2024 Investigación y desarrollo (CT) - Pendiente | money | new |
| 03443 | `is_deduccion_idi_innovacion_tecnologica` | 2024 Innovación tecnológica (IT) - Aplicado | money | reused |
| 03444 | `is_deduccion_idi_innovacion_pendiente` | 2024 Innovación tecnológica (IT) - Pendiente | money | new |
| 03446 | `is_deduccion_inversiones_africa_canarias_periodo` | 2024 Inversiones territ. África Occ. - Aplicado | money | new |
| 03447 | `is_deduccion_inversiones_africa_canarias_pendiente` | 2024 Inversiones territ. África Occ. - Pendiente | money | new |
| 03524 | `is_deduccion_copa_america_periodo` | 2025: Barcelona Mobile World Capital (MW) - Aplicado | money | reused; event-support applied axis |
| 03525 | `is_deduccion_copa_america_total` | 2025: Barcelona Mobile World Capital (MW) - Pendiente | money | reused; event-support pending axis |
| 03527 | `is_deduccion_copa_america_periodo` | 2025: Barcelona 2026 Capital Mundial Arquitectura - Ap | money | reused |
| 03528 | `is_deduccion_copa_america_total` | 2025: Barcelona 2026 Capital Mundial Arquitectura - Pe | money | reused |
| 03530 | `is_deduccion_copa_america_periodo` | 2025: Rally Islas Canarias (RCA) - Aplicado | money | reused |
| 03531 | `is_deduccion_copa_america_total` | 2025: Rally Islas Canarias (RCA) - Pendiente | money | reused |
| 00904 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2025(*) - Importe aplicado | money | new |
| 00905 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2025(*) - Importe pendiente | money | new; only-pending (no generado row here) |
| 01083 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2022 - Importe generado/pendiente principio | money | new |
| 01084 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2022 - Importe aplicado | money | new |
| 01085 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2022 - Importe pendiente | money | new |
| 01086 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2022 - Base deducción | money | new |
| 01167 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2015 - Importe generado/pendiente principio | money | new |
| 01171 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS Total - Importe generado/pendiente principio | money | new; total row |
| 01179 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2015 - Importe generado/pendiente principio | money | new |
| 01181 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2015 - Importe pendiente | money | new; only-pending (no applied row for 2015 DT2) |
| 01183 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS Total - Importe generado/pendiente principio | money | new; total row |
| 01378 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2023 - Importe generado/pendiente principio | money | new |
| 01379 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2023 - Importe aplicado | money | new |
| 01380 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2023 - Importe pendiente | money | new |
| 01381 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2023 - Base deducción | money | new |
| 01382 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2023 - Importe generado/pendiente principio | money | new |
| 01383 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2023 - Importe aplicado | money | new |
| 01384 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2023 - Importe pendiente | money | new |
| 01439 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2016 - Importe generado/pendiente principio | money | new |
| 01440 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2016 - Importe aplicado | money | new |
| 01441 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2016 - Importe pendiente | money | new |
| 01443 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2017 - Importe generado/pendiente principio | money | new |
| 01444 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2017 - Importe aplicado | money | new |
| 01445 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2017 - Importe pendiente | money | new |
| 01448 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2016 - Importe generado/pendiente principio | money | new |
| 01449 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2016 - Importe aplicado | money | new |
| 01450 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2016 - Importe pendiente | money | new |
| 01452 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2017 - Importe generado/pendiente principio | money | new |
| 01453 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2017 - Importe aplicado | money | new |
| 01454 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2017 - Importe pendiente | money | new |
| 01722 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2018 - Importe generado/pendiente principio | money | new |
| 01723 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2018 - Importe aplicado | money | new |
| 01724 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2018 - Importe pendiente | money | new |
| 01725 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2018 - Base deducción | money | new |
| 01726 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2018 - Importe generado/pendiente principio | money | new |
| 01727 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2018 - Importe aplicado | money | new |
| 01728 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2018 - Importe pendiente | money | new |
| 01954 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2019 - Importe generado/pendiente principio | money | new |
| 01955 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2019 - Importe aplicado | money | new |
| 01956 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2019 - Importe pendiente | money | new |
| 01957 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2019 - Base deducción | money | new |
| 01958 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2019 - Importe generado/pendiente principio | money | new |
| 01959 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2019 - Importe aplicado | money | new |
| 01960 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2019 - Importe pendiente | money | new |
| 02071 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2025(*) - Importe pendiente | money | new; only-pending |
| 2231 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2020 - Importe generado/pendiente principio | money | new; note: id is `2231` (non-zero-padded) |
| 02232 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2020 - Importe aplicado | money | new |
| 02233 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2020 - Importe pendiente | money | new |
| 02234 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2020 - Base deducción | money | new |
| 02235 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2020 - Importe generado/pendiente principio | money | new |
| 02236 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2020 - Importe aplicado | money | new |
| 02237 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2020 - Importe pendiente | money | new |
| 02384 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2021 - Importe generado/pendiente principio | money | new |
| 02385 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2021 - Importe aplicado | money | new |
| 02386 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2021 - Importe pendiente | money | new |
| 02387 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2021 - Base deducción | money | new |
| 02388 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2021 - Importe generado/pendiente principio | money | new |
| 02389 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2021 - Importe aplicado | money | new |
| 02390 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2021 - Importe pendiente | money | new |
| 02478 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2022 - Importe aplicado | money | new |
| 02479 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2022 - Importe pendiente | money | new |
| 02702 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2024 - Importe generado/pendiente principio | money | new |
| 02703 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2024 - Importe aplicado | money | new |
| 02704 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2024 - Importe pendiente | money | new |
| 02705 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2024 - Base deducción | money | new |
| 02706 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2024 - Importe generado/pendiente principio | money | new |
| 02707 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2024 - Importe aplicado | money | new |
| 02708 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2024 - Importe pendiente | money | new |
| 03568 | `is_deduccion_reversion_medidas_dt1_generado` | DT37.1 LIS 2025 - Importe generado/pendiente principio | money | new |
| 03569 | `is_deduccion_reversion_medidas_dt1_periodo` | DT37.1 LIS 2025 - Importe aplicado | money | new |
| 03570 | `is_deduccion_reversion_medidas_dt1_pendiente` | DT37.1 LIS 2025 - Importe pendiente | money | new |
| 03571 | `is_deduccion_reversion_medidas_dt2_base` | DT37.2 LIS 2025 - Base deducción | money | new |
| 03572 | `is_deduccion_reversion_medidas_dt2_generado` | DT37.2 LIS 2025 - Importe generado/pendiente principio | money | new |
| 03573 | `is_deduccion_reversion_medidas_dt2_periodo` | DT37.2 LIS 2025 - Importe aplicado | money | new |
| 03574 | `is_deduccion_reversion_medidas_dt2_pendiente` | DT37.2 LIS 2025 - Importe pendiente | money | new |
| 00853 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2018 - Aplicado en esta liquidación | money | reused (`is_deduccion_inversion_canarias_importe`); only-applied |
| 00855 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2010 - Aplicado en esta liquidación | money | reused; only-applied |
| 00858 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2011 - Aplicado en esta liquidación | money | reused |
| 00859 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2011 - Pendiente de aplicación | money | new |
| 00861 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2012 - Aplicado en esta liquidación | money | reused |
| 00862 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2012 - Pendiente de aplicación | money | new |
| 00864 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2013 - Aplicado en esta liquidación | money | reused |
| 00865 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2013 - Pendiente de aplicación | money | new |
| 00884 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2014 - Aplicado en esta liquidación | money | reused |
| 00885 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2014 - Pendiente de aplicación | money | new |
| 00887 | `is_deduccion_inversion_canarias_total` | Total - Pendiente de aplicación en periodos futuros | money | new |
| 01059 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2016 - Aplicado en esta liquidación | money | reused |
| 01060 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2016 - Pendiente de aplicación | money | new |
| 01358 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2016 - Aplicado en esta liquidación | money | reused |
| 01359 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2016 - Pendiente de aplicación | money | new |
| 01615 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2024 - Aplicado en esta liquidación | money | reused |
| 01616 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2024 - Pendiente de aplicación | money | new |
| 01779 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2017 - Aplicado en esta liquidación | money | reused |
| 01780 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2017 - Pendiente de aplicación | money | new |
| 01782 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2018 - Aplicado en esta liquidación | money | reused |
| 01783 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2018 - Pendiente de aplicación | money | new |
| 01801 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2024 - Pendiente | money | new; only-pending (partial row) |
| 01803 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2024 - Aplicado en esta liquidación | money | reused |
| 01804 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2024 - Pendiente de aplicación | money | new |
| 01806 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2024 - Aplicado | money | new; only-applied (partial row) |
| 02117 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2019 - Aplicado en esta liquidación | money | reused |
| 02118 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2019 - Pendiente de aplicación | money | new |
| 02120 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2018 - Aplicado | money | new |
| 02121 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Inversiones La Palma/Gomera/Hierro 2018 - Pendiente | money | new |
| 02123 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2019 - Aplicado en esta liquidación | money | reused |
| 02124 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2019 - Pendiente de aplicación | money | new |
| 02126 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2019 - Aplicado | money | new |
| 02127 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Inversiones La Palma/Gomera/Hierro 2019 - Pendiente | money | new |
| 02210 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2020 - Aplicado en esta liquidación | money | reused |
| 02211 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2020 - Pendiente de aplicación | money | new |
| 02213 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2020 - Aplicado en esta liquidación | money | reused |
| 02214 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2020 - Pendiente de aplicación | money | new |
| 02216 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2020 - Aplicado | money | new |
| 02217 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Inversiones La Palma/Gomera/Hierro 2020 - Pendiente | money | new |
| 02333 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2021 - Aplicado en esta liquidación | money | reused |
| 02334 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2021 - Pendiente de aplicación | money | new |
| 02336 | `is_deduccion_inversion_canarias_islas_menores_importe` | Activos fijos La Palma/Gomera/Hierro 2018 - Aplicado | money | new |
| 02337 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2018 - Pendiente | money | new |
| 02338 | `is_deduccion_inversion_canarias_islas_menores_generado` | Activos fijos La Palma/Gomera/Hierro 2019 - Pendiente/generada | money | new |
| 02339 | `is_deduccion_inversion_canarias_islas_menores_importe` | Activos fijos La Palma/Gomera/Hierro 2019 - Aplicado | money | new |
| 02340 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2019 - Pendiente | money | new |
| 02341 | `is_deduccion_inversion_canarias_islas_menores_generado` | Activos fijos La Palma/Gomera/Hierro 2020 - Pendiente/generada | money | new |
| 02342 | `is_deduccion_inversion_canarias_islas_menores_importe` | Activos fijos La Palma/Gomera/Hierro 2020 - Aplicado | money | new |
| 02343 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2020 - Pendiente | money | new |
| 02344 | `is_deduccion_inversion_canarias_islas_menores_generado` | Activos fijos La Palma/Gomera/Hierro 2021 - Pendiente/generada | money | new |
| 02345 | `is_deduccion_inversion_canarias_islas_menores_importe` | Activos fijos La Palma/Gomera/Hierro 2021 - Aplicado | money | new |
| 02346 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2021 - Pendiente | money | new |
| 02348 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2021 - Aplicado en esta liquidación | money | reused |
| 02349 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2021 - Pendiente de aplicación | money | new |
| 02351 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2021 - Aplicado | money | new |
| 02352 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Inversiones La Palma/Gomera/Hierro 2021 - Pendiente | money | new |
| 03425 | `is_deduccion_inversion_canarias_importe` | Activos fijos 2025 - Aplicado en esta liquidación | money | reused |
| 03426 | `is_deduccion_inversion_canarias_pendiente` | Activos fijos 2025 - Pendiente de aplicación | money | new |
| 03428 | `is_deduccion_inversion_canarias_islas_menores_importe` | Activos fijos La Palma/Gomera/Hierro 2025 - Aplicado | money | new |
| 03429 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Activos fijos La Palma/Gomera/Hierro 2025 - Pendiente | money | new |
| 03431 | `is_deduccion_inversion_canarias_importe` | Inversiones Canarias 2025 - Aplicado en esta liquidación | money | reused |
| 03432 | `is_deduccion_inversion_canarias_pendiente` | Inversiones Canarias 2025 - Pendiente de aplicación | money | new |
| 03434 | `is_deduccion_inversion_canarias_islas_menores_importe` | Inversiones La Palma/Gomera/Hierro 2025 - Aplicado | money | new |
| 03435 | `is_deduccion_inversion_canarias_islas_menores_pendiente` | Inversiones La Palma/Gomera/Hierro 2025 - Pendiente | money | new |
| 01051 | `is_deduccion_di_internacional_periodo` | DI internacional 2015 - 2025 Deducción pendiente (opening) | money | new; "2025 Deducción pendiente" = prior-year carry-forward brought forward to 2025 |
| 01052 | `is_deduccion_di_internacional_periodo` | DI internacional 2015 - Aplicado en esta liquidación | money | reused (`is_deduccion_di_internacional_periodo`) |
| 01053 | `is_deduccion_di_internacional_pendiente` | DI internacional 2015 - Pendiente aplic. en períodos futuros | money | new |
| 01054 | `is_deduccion_di_internacional_generado` | DI internacional 2015 - Deducción pendiente (original opening) | money | new; this older-format row (no "2025" prefix) is the original generation-year opening balance |
| 01349 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2016 - Tipo gravamen período generación | decimal | new |
| 01350 | `is_deduccion_di_internacional_periodo` | DI internacional 2016 - 2025 Deducción pendiente | money | new |
| 01351 | `is_deduccion_di_internacional_periodo` | DI internacional 2016 - Aplicado en esta liquidación | money | reused |
| 01352 | `is_deduccion_di_internacional_pendiente` | DI internacional 2016 - Pendiente aplic. en períodos futuros | money | new |
| 01362 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2023 - Tipo gravamen período generación | decimal | new; single-decimal (only row present for 2023 vintage) |
| 01771 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2017 - Tipo gravamen período generación | decimal | new |
| 01772 | `is_deduccion_di_internacional_periodo` | DI internacional 2017 - 2025 Deducción pendiente | money | new |
| 01773 | `is_deduccion_di_internacional_periodo` | DI internacional 2017 - Aplicado en esta liquidación | money | reused |
| 01774 | `is_deduccion_di_internacional_pendiente` | DI internacional 2017 - Pendiente aplic. en períodos futuros | money | new |
| 01834 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2018 - Tipo gravamen período generación | decimal | new |
| 01835 | `is_deduccion_di_internacional_periodo` | DI internacional 2018 - 2025 Deducción pendiente | money | new |
| 01836 | `is_deduccion_di_internacional_periodo` | DI internacional 2018 - Aplicado en esta liquidación | money | reused |
| 01837 | `is_deduccion_di_internacional_pendiente` | DI internacional 2018 - Pendiente aplic. en períodos futuros | money | new |
| 02202 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2019 - Tipo gravamen período generación | decimal | new |
| 02203 | `is_deduccion_di_internacional_periodo` | DI internacional 2019 - 2025 Deducción pendiente | money | new |
| 02204 | `is_deduccion_di_internacional_periodo` | DI internacional 2019 - Aplicado en esta liquidación | money | reused |
| 02205 | `is_deduccion_di_internacional_pendiente` | DI internacional 2019 - Pendiente aplic. en períodos futuros | money | new |
| 02325 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2020 - Tipo gravamen período generación | decimal | new |
| 02326 | `is_deduccion_di_internacional_periodo` | DI internacional 2020 - 2025 Deducción pendiente | money | new |
| 02327 | `is_deduccion_di_internacional_periodo` | DI internacional 2020 - Aplicado en esta liquidación | money | reused |
| 02328 | `is_deduccion_di_internacional_pendiente` | DI internacional 2020 - Pendiente aplic. en períodos futuros | money | new |
| 03417 | `is_deduccion_di_internacional_tipo_gravamen` | DI internacional 2025(*) - Tipo gravamen período generación | decimal | new |
| 03418 | `is_deduccion_di_internacional_periodo` | DI internacional 2025(*) - 2024 Deducción pendiente | money | new |
| 03419 | `is_deduccion_di_internacional_periodo` | DI internacional 2025(*) - Aplicado en esta liquidación | money | reused |
| 03420 | `is_deduccion_di_internacional_pendiente` | DI internacional 2025(*) - Pendiente aplic. en períodos futuros | money | new |
| 00697 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2023 - Aplicado en esta liquidación | money | reused (`is_deduccion_dt24a7_periodo`) |
| 00804 | `is_deduccion_dt24a7_periodo` | Art.42 RDLeg.4/2004 2014 - Aplicado en esta liquidación | money | reused; predecessor provision now filed under DT24ª.7 section |
| 00805 | `is_deduccion_dt24a7_pendiente` | Art.42 RDLeg.4/2004 2014 - Pendiente aplicación periodos futuros | money | new |
| 01056 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2015 - Aplicado en esta liquidación | money | reused |
| 01057 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2015 - Pendiente aplicación periodos futuros | money | new |
| 01354 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2017 - Aplicado en esta liquidación | money | reused |
| 01355 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2017 - Pendiente aplicación periodos futuros | money | new |
| 01776 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2018 - Aplicado en esta liquidación | money | reused |
| 01777 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2018 - Pendiente aplicación periodos futuros | money | new |
| 01839 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2019 - Aplicado en esta liquidación | money | reused |
| 01840 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2019 - Pendiente aplicación periodos futuros | money | new |
| 02207 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2020 - Aplicado en esta liquidación | money | reused |
| 02208 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2020 - Pendiente aplicación periodos futuros | money | new |
| 02330 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2021 - Aplicado en esta liquidación | money | reused |
| 02331 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2021 - Pendiente aplicación periodos futuros | money | new |
| 03422 | `is_deduccion_dt24a7_periodo` | DT24ª.7 LIS 2025 - Aplicado en esta liquidación | money | reused |
| 03423 | `is_deduccion_dt24a7_pendiente` | DT24ª.7 LIS 2025 - Pendiente aplicación periodos futuros | money | new |
| 00826 | `is_deduccion_di_internacional_rdleg_importe` | DI internacional RDLeg.4/2004 2008 - Aplicado | money | reused (`is_deduccion_di_interna_rdleg_importe` pattern → `is_deduccion_di_internacional_rdleg_importe`) |
| 00827 | `is_deduccion_di_internacional_rdleg_pendiente` | DI internacional RDLeg.4/2004 2008 - Pendiente aplic. | money | new |
| 00847 | `is_deduccion_di_interna_rdleg_importe` | DI interna RDLeg.4/2004 2008 - Aplicado | money | reused (`is_deduccion_di_interna_rdleg_importe`) |
| 00848 | `is_deduccion_di_interna_rdleg_pendiente` | DI interna RDLeg.4/2004 2008 - Pendiente aplic en períodos futuros | money | new |
| 02579 | `is_deduccion_amortizacion_libre_disminucion` | Deducción 30% amortiz. contable art.7 Ley 16/2012 - Disminución | money | new |
| 02580 | `is_deduccion_amortizacion_libre_disminucion` | Deducción 30% amortiz. contable art.7 Ley 16/2012 - Disminución | money | new; two rows under same disminucion subsection |

---

## Data_type divergences

One section contains a data_type mix:

| Section | IDs with `decimal` | IDs with `money` | Observation |
|---|---|---|---|
| `deducciones_doble_imposicion_internacional_lis` | 01349, 01362, 01771, 01834, 02202, 02325, 03417 (7 ids) | 22 ids | `Tipo gravamen período generación` is a tax rate (%), correctly typed `decimal`. All amount fields remain `money`. This is structurally correct — the role `is_deduccion_di_internacional_tipo_gravamen` is exclusively `decimal`. |

All other sections are uniformly `money`. No unexpected divergence.

### ID format anomaly

- `2231` (DT37.1 LIS 2020, importe generado/pendiente principio periodo) is stored without zero-padding (4 digits instead of 5). All other ids in the cluster are 5-digit zero-padded. This is a registry source artifact, not a classification error.

---

## Summary statistics

- Total ids classified: **279**
- Roles reused verbatim from existing 88-role list: **11 roles** (applied to 64 casilla entries)
- New roles coined: **23**
- New roles: `is_deduccion_idi_suma_pendiente`, `is_deduccion_idi_diferimiento_periodo`, `is_deduccion_idi_diferimiento_pendiente`, `is_deduccion_inversiones_africa_canarias_periodo`, `is_deduccion_inversiones_africa_canarias_pendiente`, `is_deduccion_idi_investigacion_pendiente`, `is_deduccion_idi_innovacion_pendiente`, `is_deduccion_reversion_medidas_dt1_generado`, `is_deduccion_reversion_medidas_dt1_periodo`, `is_deduccion_reversion_medidas_dt1_pendiente`, `is_deduccion_reversion_medidas_dt2_base`, `is_deduccion_reversion_medidas_dt2_generado`, `is_deduccion_reversion_medidas_dt2_periodo`, `is_deduccion_reversion_medidas_dt2_pendiente`, `is_deduccion_inversion_canarias_pendiente`, `is_deduccion_inversion_canarias_total`, `is_deduccion_inversion_canarias_islas_menores_importe`, `is_deduccion_inversion_canarias_islas_menores_pendiente`, `is_deduccion_inversion_canarias_islas_menores_generado`, `is_deduccion_di_internacional_tipo_gravamen`, `is_deduccion_di_internacional_generado`, `is_deduccion_di_internacional_pendiente`, `is_deduccion_dt24a7_pendiente`, `is_deduccion_di_internacional_rdleg_pendiente`, `is_deduccion_di_interna_rdleg_pendiente`, `is_deduccion_amortizacion_libre_disminucion`
- Data_type divergences: **1 section** (`deducciones_doble_imposicion_internacional_lis`), structurally correct — 7 `decimal` tipo-gravamen casillas within an otherwise `money` section.
