---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-18'
modified: '2026-05-18'
related:
  - "[[2026-05-18-schema-hardening-plan]]"
---

# schema-hardening audit: NIF coverage classification for modelo 100

## Scope

Read-only classification of every casilla in the six M100 revision files (2020-2025) whose label contains "NIF", "N.I.F", or "NIE". Goal: produce a per-revision retrofit list for an automated edit that changes `data_type = "text"` to `data_type = "nif"` on casillas that genuinely hold a Spanish NIF/NIE/CIF. No TOML files were modified.

Validator bound: `NifString` accepts only Spanish-format NIF/NIE/CIF (no country prefix). Foreign/intracomunitario IDs are deferred.

---

## Counts per revision

| revision | total NIF-label hits | bucket 1 (retrofit) | bucket 2 (defer) | bucket 3 (skip) |
|----------|---------------------|---------------------|------------------|-----------------|
| 2020     | 95                  | 61                  | 3                | 31              |
| 2021     | 108                 | 74                  | 3                | 31              |
| 2022     | 118                 | 83                  | 3                | 32              |
| 2023     | 123                 | 86                  | 3                | 34              |
| 2024     | 145                 | 103                 | 3                | 39              |
| 2025     | 161                 | 115                 | 3                | 43              |
| **total**| **750**             | **522**             | **18**           | **210**         |

Bucket 3 counts include all `data_type = "boolean"` and empty-data_type casillas. No boolean or empty-data_type casilla is in bucket 1 or 2.

---

## Bucket 1: Spanish NIF retrofit list

All entries have `data_type = "text"` and hold a genuine Spanish NIF/NIE/CIF. The follow-up automation changes `data_type` to `"nif"`.

### 2020

| line  | id   | label                                                                                              | current_data_type | section                                                                                              |
|-------|------|----------------------------------------------------------------------------------------------------|-------------------|------------------------------------------------------------------------------------------------------|
| 4990  | 0077 | NIF del excónyuge                                                                                  | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 5108  | 0091 | Nif del arrendatario 1 (*)                                                                         | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 5135  | 0094 | Nif del arrendatario 2 (*)                                                                         | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 5153  | 0097 | Nif del arrendatario 3 (*)                                                                         | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 6136  | 0240 | NIF del cónyuge                                                                                    | text              | resultados > calculo_impuesto_res > deduc_conyuge_disc_res                                           |
| 6231  | 0257 | Nº de identificación fiscal (NIF) de la entidad                                                    | text              | toma_datos_ampliada > regimenes_especiales > re_agrup_interes_economico                              |
| 6685  | 0311 | NIF de la sociedad o fondo de inversión                                                            | text              | toma_datos_ampliada > gp_fondos > fondo                                                              |
| 7433  | 0403 | NIF de la sociedad emisora o fondo de inversión                                                    | text              | toma_datos_ampliada > g_cambio_residencia_ext > g4_re                                                |
| 7835  | 0456 | NIF/NIE del hijo 1(*)                                                                              | text              | toma_datos_ampliada > datos_adicionales                                                              |
| 7853  | 0458 | NIF/NIE del hijo 2(*)                                                                              | text              | toma_datos_ampliada > datos_adicionales                                                              |
| 7965  | 0471 | Nº de identificación fiscal (NIF) de la persona con discapacidad partícipe, mutualista o asegurada | text              | toma_datos_ampliada > red_base_imponible > red_discapacidad                                          |
| 8023  | 0478 | Número de identificación fiscal (NIF) de la persona con discapacidad titular del patrimonio protegido | text           | toma_datos_ampliada > red_base_imponible > red_patrimonio_protegido_discapacidad                     |
| 8065  | 0483 | Nº de identificación fiscal (NIF) de la persona que recibe cada pensión o anualidad                | text              | toma_datos_ampliada > red_base_imponible > red_pensiones_comensatorias_alimentos                     |
| 9058  | 0614 | NIF del descendiente                                                                               | text              | resultados > calculo_impuesto_res > deduc_descendiente_disc_res                                      |
| 9111  | 0620 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_descendiente_disc_res                                      |
| 9120  | 0622 | NIF del beneficiario                                                                               | text              | resultados > calculo_impuesto_res > deduc_descendiente_disc_res                                      |
| 9154  | 0625 | NIF del ascendiente                                                                                | text              | resultados > calculo_impuesto_res > deduc_ascendiente_disc_res                                       |
| 9207  | 0631 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_ascendiente_disc_res                                       |
| 9216  | 0632 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_ascendiente_disc_res                                       |
| 9225  | 0633 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_ascendiente_disc_res                                       |
| 9243  | 0635 | NIF del beneficiario                                                                               | text              | resultados > calculo_impuesto_res > deduc_ascendiente_disc_res                                       |
| 9268  | 0638 | NIF del arrendador 1                                                                               | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ctrd                                          |
| 9294  | 0641 | NIF del arrendador 2                                                                               | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ctrd                                          |
| 9406  | 0654 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_familia_numerosa_res                                       |
| 9415  | 0655 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_familia_numerosa_res                                       |
| 9424  | 0656 | NIF del cedente                                                                                    | text              | resultados > calculo_impuesto_res > deduc_familia_numerosa_res                                       |
| 9442  | 0658 | NIF del beneficiario                                                                               | text              | resultados > calculo_impuesto_res > deduc_familia_numerosa_res                                       |
| 9500  | 0665 | NIF del descendiente cuya deducción se regulariza                                                  | text              | resultados > calculo_impuesto_res > regularizacion_descendiente_res                                  |
| 9517  | 0667 | NIF del ascendiente cuya deducción se regulariza                                                   | text              | resultados > calculo_impuesto_res > regularizacion_ascendiente_res                                   |
| 9758  | 0707 | NIF del promotor o constructor                                                                     | text              | resultados > anexo_a_res > deduccion_vivienda_habitual_res                                           |
| 9793  | 0711 | NIF de la entidad 1 nueva o reciente creación                                                      | text              | resultados > anexo_a_res > deduccion_empresas_nueva_creacion_res                                     |
| 9810  | 0713 | NIF de la entidad 2 nueva o reciente creación                                                      | text              | resultados > anexo_a_res > deduccion_empresas_nueva_creacion_res                                     |
| 9827  | 0715 | NIF del arrendador 1                                                                               | text              | resultados > anexo_a_res > deduccion_alquiler_res                                                    |
| 9845  | 0717 | NIF del arrendador 2                                                                               | text              | resultados > anexo_a_res > deduccion_alquiler_res                                                    |
| 11307 | 0911 | NIF/NIE del arrendador 1                                                                           | text              | resultados > deduccion_autonomica_res > i_baleares_res                                               |
| 11610 | 0949 | NIF de la persona o entidad que realiza las obras                                                  | text              | resultados > deduccion_autonomica_res > cantabria_res                                                |
| 11916 | 0989 | NIF de la persona empleada del hogar, Escuela, Centro o Guardería Infantil                         | text              | resultados > deduccion_autonomica_res > castilla_y_leon_res                                          |
| 11949 | 0993 | NIF de la persona empleada                                                                         | text              | resultados > deduccion_autonomica_res > castilla_y_leon_res                                          |
| 12568 | 1076 | NIF de la Escuela, Centro o Guardería Infantil                                                     | text              | resultados > deduccion_autonomica_res > la_rioja_res                                                 |
| 12819 | 1107 | NIF de la persona o entidad que realiza las obras                                                  | text              | resultados > deduccion_autonomica_res > c_valenciana_res                                             |
| 12836 | 1109 | NIF de la persona o entidad que realiza las obras                                                  | text              | resultados > deduccion_autonomica_res > c_valenciana_res                                             |
| 12933 | 1122 | NIF/NIE del arrendador 1                                                                           | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_arr                                           |
| 12959 | 1125 | NIF/NIE del arrendador 2                                                                           | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_arr                                           |
| 13011 | 1131 | NIF de la entidad 1 de nueva o reciente creación                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enc                                           |
| 13028 | 1133 | NIF de la entidad 2 de nueva o reciente creación                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enc                                           |
| 13061 | 1137 | NIF de la entidad 1                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_mab                                           |
| 13078 | 1139 | NIF de la entidad 2                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_mab                                           |
| 13111 | 1143 | NIF de la entidad 1                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_rcf                                           |
| 13128 | 1145 | NIF de la entidad 2                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_rcf                                           |
| 13161 | 1149 | NIF de la entidad 1                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_agt                                           |
| 13178 | 1151 | NIF de la entidad 2                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_agt                                           |
| 13211 | 1155 | NIF/NIE del arrendador                                                                             | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_avh                                           |
| 13318 | 1168 | NIF de la persona empleada del hogar                                                               | text              | resultados > deduccion_autonomica_res > la_rioja_res                                                 |
| 13367 | 1174 | NIF de la entidad 1                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ides                                          |
| 13384 | 1176 | NIF de la entidad 2                                                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ides                                          |
| 13417 | 1187 | NIF/NIE del arrendatario 1                                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_eps                                           |
| 13461 | 1192 | NIF/NIE del arrendatario 2                                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_eps                                           |
| 13505 | 1197 | NIF/NIE del arrendatario 3                                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_eps                                           |
| 14578 | 1333 | Nº de identificación fiscal (NIF) de la persona con discapacidad                                  | text              | resultados > anexo_c_res > excesos_sistemas_prevision_social_personas_disc_parientes_res              |
| 14716 | 1350 | Nº de identificación fiscal (NIF) de la persona con discapacidad titular del patrimonio protegido  | text              | resultados > anexo_c_res > excesos_patrim_protegidos_res                                             |
| 15082 | 1395 | Gasto 1: NIF de quién realizó la obra o servicio                                                   | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 15099 | 1397 | Gasto 2: NIF de quién realizó la obra o servicio                                                   | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 15117 | 1399 | Gasto 3: NIF de quién realizó la obra o servicio                                                   | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 15135 | 1401 | Gasto 4: NIF de quién realizó la obra o servicio                                                   | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |
| 15153 | 1403 | Gasto 5: NIF de quién realizó la obra o servicio                                                   | text              | toma_datos_ampliada > inmuebles > inmueble                                                           |

### 2021

All 2020 entries carry forward at new line numbers, plus:

| line  | id   | label                                                                                              | current_data_type | section                                                                              |
|-------|------|----------------------------------------------------------------------------------------------------|-------------------|--------------------------------------------------------------------------------------|
| 5746  | 0158 | NIF del arrendatario                                                                               | text              | toma_datos_ampliada > inmuebles > inmueble                                           |
| 13815 | 1209 | NIF del otro progenitor 1                                                                          | text              | resultados > deduccion_autonomica_res > castilla_y_leon_res                          |
| 14095 | 1244 | NIF del otro progenitor 2                                                                          | text              | resultados > deduccion_autonomica_res > castilla_y_leon_res                          |
| 12705 | 1070 | NIF de la persona empleada del hogar, Escuela, Centro o Guardería Infantil                         | text              | resultados > deduccion_autonomica_res > la_rioja_res                                 |
| 18082 | 1724 | NIF del productor 1                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 18091 | 1725 | NIF del productor 2                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 18100 | 1726 | NIF del productor 3                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 18151 | 1732 | NIF del productor 1                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 18160 | 1733 | NIF del productor 2                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 18169 | 1734 | NIF del productor 3                                                                                | text              | resultados > anexo_a_res > deducciones_inversion_empresarial_res                     |
| 17537 | 1657 | NIF/NIE de la persona/entidad que ha realizado las obras (1)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |
| 17546 | 1658 | NIF/NIE de la persona/entidad que ha realizado las obras (2)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |
| 17606 | 1665 | NIF/NIE de la persona/entidad que ha realizado las obras (1)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |
| 17615 | 1666 | NIF/NIE de la persona/entidad que ha realizado las obras (2)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |
| 17684 | 1674 | NIF/NIE de la persona/entidad que ha realizado las obras (1)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |
| 17693 | 1675 | NIF/NIE de la persona/entidad que ha realizado las obras (2)                                       | text              | toma_datos_ampliada > anexo_a > mejoras_energeticas_viv                              |

### 2022

All 2021 entries carry forward at new line numbers, plus:

| line  | id   | label                                                                 | current_data_type | section                                                                  |
|-------|------|-----------------------------------------------------------------------|-------------------|--------------------------------------------------------------------------|
| 7862  | 0397 | NIF del plan de pensiones del sistema de empleo                       | text              | toma_datos_ampliada > red_base_imponible > red_prevision_social          |
| 8358  | 0456 | Hijo/Hija 1 (*): NIF/NIE                                              | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 8376  | 0458 | Hijo/Hija 2 (*): NIF/NIE                                              | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 11135 | 0804 | NIF de la persona empleada                                            | text              | resultados > deduccion_autonomica_res > c_valenciana_res                 |
| 13391 | 1096 | NIF del arrendador                                                    | text              | resultados > deduccion_autonomica_res > c_valenciana_res                 |
| 18778 | 1742 | Hijo/Hija 1 (*): NIF/NIE del otro progenitor                          | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18804 | 1745 | Hijo/Hija 2 (*): NIF/NIE del otro progenitor                          | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18822 | 1747 | Hijo/Hija 3 (*): NIF/NIE                                              | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18848 | 1750 | Hijo/Hija 3 (*): NIF/NIE del otro progenitor                          | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18866 | 1752 | Hijo/Hija 4 (*): NIF/NIE                                              | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18892 | 1755 | Hijo/Hija 4 (*): NIF/NIE del otro progenitor                          | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18910 | 1757 | Hijo/Hija 5 (*): NIF/NIE                                              | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |
| 18936 | 1760 | Hijo/Hija 5 (*): NIF/NIE del otro progenitor                          | text              | resultados > datos_adicionales_res > anualidades_alimentos_res           |

### 2023

All 2022 entries carry forward, plus:

| line  | id   | label                                                                       | current_data_type | section                                                              |
|-------|------|-----------------------------------------------------------------------------|-------------------|----------------------------------------------------------------------|
| 7936  | 0397 | NIF del empleador (label changed from 2022)                                 | text              | toma_datos_ampliada > red_base_imponible > red_prevision_social      |
| 20748 | 1974 | NIF                                                                         | text              | toma_datos_ampliada > regimen_especial > feac                        |
| 20784 | 1978 | NIF                                                                         | text              | toma_datos_ampliada > regimen_especial > feac                        |
| 20284 | 1918 | NIF/NIE de la persona/entidad vendedora                                     | text              | toma_datos_ampliada > anexo_a > vehiculos_elec_y_puntos_carga        |
| 20397 | 1931 | NIF/NIE de la persona/entidad que ha realizado la instalación (1)           | text              | toma_datos_ampliada > anexo_a > vehiculos_elec_y_puntos_carga        |

### 2024

All 2023 entries carry forward, plus:

| line  | id   | label                                                                       | current_data_type | section                                                                   |
|-------|------|-----------------------------------------------------------------------------|-------------------|---------------------------------------------------------------------------|
| 6461  | 0210 | NIF de la guarderia o centro de educación infantil autorizado               | text              | resultados > deduccion_autonomica_res > castilla_la_mancha_res            |
| 18523 | 1699 | NIF de la persona contratada o Centro de día 1                              | text              | resultados > deduccion_autonomica_res > i_baleares_res                    |
| 18532 | 1700 | NIF de la persona contratada o Centro de día 2                              | text              | resultados > deduccion_autonomica_res > i_baleares_res                    |
| 18654 | 1715 | NIF de la persona contratada o Centro de día                                | text              | resultados > deduccion_autonomica_res > i_baleares_res                    |
| 19056 | 1762 | Hijo/Hija 1 (*): NIF/NIE del pagador de las anualidades                     | text              | resultados > datos_adicionales_res > anualidades_alimentos_res            |
| 19257 | 1786 | Hijo/Hija 2 (*): NIF/NIE del pagador de las anualidades                     | text              | resultados > datos_adicionales_res > anualidades_alimentos_res            |
| 19266 | 1787 | Hijo/Hija 3 (*): NIF/NIE del pagador de las anualidades                     | text              | resultados > datos_adicionales_res > anualidades_alimentos_res            |
| 19275 | 1788 | Hijo/Hija 4 (*): NIF/NIE del pagador de las anualidades                     | text              | resultados > datos_adicionales_res > anualidades_alimentos_res            |
| 19284 | 1789 | Hijo/Hija 5 (*): NIF/NIE del pagador de las anualidades                     | text              | resultados > datos_adicionales_res > anualidades_alimentos_res            |
| 21241 | 2040 | NIF de la guardería autorizada 1                                            | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21258 | 2042 | NIF de la guardería autorizada 1                                            | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21275 | 2044 | NIF/NIE 1                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21284 | 2045 | NIF/NIE 3                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21293 | 2046 | NIF/NIE 3                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21302 | 2047 | NIF/NIE 4                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21335 | 2052 | NIF/NIE 1                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21344 | 2053 | NIF/NIE 3                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21353 | 2054 | NIF/NIE 3                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21362 | 2055 | NIF/NIE 4                                                                   | text              | resultados > deduccion_autonomica_res > canarias_res                      |
| 21371 | 2062 | NIF/NIE del arrendador 1                                                    | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ges                 |
| 21407 | 2066 | NIF del Colegio Mayor/Menor/Residencia de estudiantes 1                     | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ges                 |
| 21416 | 2067 | NIF/NIE del arrendador 2                                                    | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ges                 |
| 21452 | 2071 | NIF del Colegio Mayor/Menor/Residencia de estudiantes 2                     | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ges                 |
| 21515 | 2078 | NIF de la entidad 1                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ipse                |
| 21532 | 2080 | NIF de la entidad 2                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_ipse                |
| 21574 | 2085 | NIF prestador del servicio 1                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21591 | 2087 | NIF prestador del servicio 2                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21608 | 2089 | NIF prestador del servicio 3                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21625 | 2091 | NIF prestador del servicio 4                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21642 | 2093 | NIF prestador del servicio 5                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21659 | 2095 | NIF prestador del servicio 6                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21676 | 2097 | NIF prestador del servicio 7                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21693 | 2099 | NIF prestador del servicio 8                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_enf                 |
| 21743 | 2105 | NIF prestador del servicio 1                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21760 | 2107 | NIF prestador del servicio 2                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21777 | 2109 | NIF prestador del servicio 3                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21794 | 2111 | NIF prestador del servicio 4                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21811 | 2113 | NIF prestador del servicio 5                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21828 | 2115 | NIF prestador del servicio 6                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21845 | 2117 | NIF prestador del servicio 7                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21862 | 2119 | NIF prestador del servicio 8                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_dep                 |
| 21904 | 2124 | NIF prestador del servicio 1                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 21921 | 2126 | NIF prestador del servicio 2                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 21938 | 2128 | NIF prestador del servicio 3                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 21955 | 2130 | NIF prestador del servicio 4                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 21972 | 2132 | NIF prestador del servicio 5                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 21989 | 2134 | NIF prestador del servicio 6                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 22006 | 2136 | NIF prestador del servicio 7                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 22023 | 2138 | NIF prestador del servicio 8                                                | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aia                 |
| 22064 | 2143 | NIF de la entidad 1                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_afp                 |
| 22081 | 2145 | NIF de la entidad 2                                                         | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_afp                 |

### 2025

All 2024 entries carry forward at new line numbers, plus four new alpha-id bound casillas at file top, and new annexe groups:

| line  | id       | label                                                                          | current_data_type | section                                                                     |
|-------|----------|--------------------------------------------------------------------------------|-------------------|-----------------------------------------------------------------------------|
| 1438  | DPNIF_D  | Primer declarante NIF                                                          | text              | datos_identificativos > declarante                                          |
| 1522  | DPNIF_C  | Conyuge NIF                                                                    | text              | datos_identificativos > conyuge                                             |
| 1654  | NIFDLG   | Hijo o descendiente NIF                                                        | text              | datos_identificativos > hijos > hijo                                        |
| 1709  | DNIASDLG | Ascendiente NIF                                                                | text              | datos_identificativos > ascendientes > ascendiente                          |
| 24768 | 2167     | NIF de la entidad 1                                                            | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_scav                 |
| 24785 | 2169     | NIF de la entidad 2                                                            | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_scav                 |
| 24870 | 2179     | NIF de la entidad 1                                                            | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_rcince               |
| 24887 | 2181     | NIF de la entidad 2                                                            | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_rcince               |
| 24929 | 2186     | NIF prestador del servicio 1                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 24946 | 2188     | NIF prestador del servicio 2                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 24963 | 2190     | NIF prestador del servicio 3                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 24980 | 2192     | NIF prestador del servicio 4                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 24997 | 2194     | NIF prestador del servicio 5                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 25014 | 2196     | NIF prestador del servicio 6                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 25031 | 2198     | NIF prestador del servicio 7                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 25048 | 2200     | NIF prestador del servicio 8                                                   | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_aav                  |
| 25089 | 2205     | NIF/NIE del arrendador 1                                                       | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_arrvm               |
| 25115 | 2208     | NIF/NIE del arrendador 2                                                       | text              | resultados > datos_adicionales_anexo_b > an_b_inf_adc_arrvm               |
| 25264 | 2225     | NIF de la sociedad o fondo de inversión                                        | text              | toma_datos_ampliada > gp_fondos_coti > fondo                                |

---

## Bucket 2: NIF-IVA / foreign-ID deferrals

These three casillas appear in all six revisions with the same classification. They can hold a foreign fiscal identifier as explicitly stated in the label and must be deferred to a future `nif_iva` or `foreign_id` phase.

| id   | label                                                                                                                                          | reason for deferral                                                                                    | section                                                          |
|------|------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| 0272 | Persona o entidad primera cesionaria de los derechos de imagen: NIF (si es residente en territorio español) o denominación                    | Field holds name OR NIF conditioned on Spanish residency; non-residents provide a name, not a NIF       | toma_datos_ampliada > regimenes_especiales > re_derechos_imagen  |
| 0273 | Persona o entidad con la que el contribuyente mantiene la relación laboral: NIF (si es residente en territorio español) o denominación         | Same dual-mode field (name or NIF)                                                                     | toma_datos_ampliada > regimenes_especiales > re_derechos_imagen  |
| 1621 | NIF de la entidad en atribución de rentas, o Número de Identificación en el país de residencia en el caso de entidades no residentes           | Label explicitly names non-resident foreign fiscal ID as equally valid; cannot constrain to Spanish NIF | toma_datos_ampliada > regimenes_especiales > re_at_rentas        |

Line numbers vary by revision; identification is by `id` across all revisions.

---

## Bucket 3: Label-only mentions skipped

| id   | label (representative)                                                             | reason                                                                             |
|------|------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| 0028 | Intereses de activos financieros con derecho a la bonificación (…)                 | Missing data_type; content is a decimal; "NIF" appears in legal context in label   |
| 0078 | Marque una "X" si en la casilla [0077] ha consignado un NIF de otro país           | boolean; not a NIF field                                                           |
| 0092 | Marque una "X" si en la casilla [0091] ha consignado un NIF de otro país           | boolean                                                                            |
| 0095 | Marque una "X" si en la casilla [0094] ha consignado un NIF de otro país           | boolean                                                                            |
| 0098 | Marque una "X" si en la casilla [0097] ha consignado un NIF de otro país           | boolean                                                                            |
| 0382 | Si no tiene NIF, marque con una "X"                                                | boolean; absence indicator (2023+)                                                 |
| 0457 | Si no tiene NIF o NIE, marque con una "X"                                          | boolean                                                                            |
| 0459 | Si no tiene NIF o NIE, marque con una "X"                                          | boolean                                                                            |
| 0619 | Indique si le han cedido el derecho a la deducción y en su caso el NIF del cedente/s | boolean                                                                          |
| 0621 | Indique si cede el derecho a la deducción y en su caso el NIF del beneficiario     | boolean                                                                            |
| 0630 | Indique si le han cedido el derecho a la deducción y en su caso el NIF del cedente/s | boolean                                                                          |
| 0634 | Indique si cede el derecho a la deducción y en su caso el NIF del beneficiario     | boolean                                                                            |
| 0653 | Indique si le han cedido el derecho a la deducción y en su caso el NIF del cedente/s | boolean                                                                          |
| 0657 | Indique si cede el derecho a la deducción y en su caso el NIF del beneficiario     | boolean                                                                            |
| 0825 | Por obras de mejora de eficiencia energética (Galicia section)                     | Missing data_type; "NIF" not actually in this label — adjacent block context hit  |
| 0912 | Marque una "X" si en la casilla [0911] ha consignado un NIF de otro país           | boolean                                                                            |
| 1123 | Marque una "X" si en la casilla [1122] ha consignado un NIF de otro país           | boolean                                                                            |
| 1126 | Marque una "X" si en la casilla [1125] ha consignado un NIF de otro país           | boolean                                                                            |
| 1743 | Hijo/Hija 1 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean (2022+)                                                                    |
| 1746 | Hijo/Hija 2 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1748 | Hijo/Hija 3 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1751 | Hijo/Hija 3 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1753 | Hijo/Hija 4 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1756 | Hijo/Hija 4 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1758 | Hijo/Hija 5 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1761 | Hijo/Hija 5 (*): Si no tiene NIF o NIE, marque con una "X"                         | boolean                                                                            |
| 1975 | Si no tiene NIF, marque con una "X" (feac)                                         | boolean (2023+)                                                                    |
| 1979 | Si no tiene NIF, marque con una "X" (feac)                                         | boolean                                                                            |
| 2206 | Marque una "X" si en la casilla [2205] ha consignado un NIF de otro país           | boolean (2025 new)                                                                 |
| 2209 | Marque una "X" si en la casilla [2208] ha consignado un NIF de otro país           | boolean (2025 new)                                                                 |

---

## Cross-revision patterns

### Stable bucket-1 ids (all six revisions, identical classification)

`0077`, `0091`, `0094`, `0097`, `0240`, `0257`, `0311`, `0403`, `0456`, `0458`, `0471`, `0478`, `0483`, `0614`, `0620`, `0622`, `0625`, `0631`–`0633`, `0635`, `0638`, `0641`, `0654`–`0656`, `0658`, `0665`, `0667`, `0711`, `0713`, `0715`, `0717`, `0949`, `0989`, `0993`, `1076`, `1107`, `1109`, `1122`, `1125`, `1131`, `1133`, `1137`–`1139`, `1143`–`1145`, `1149`–`1151`, `1155`, `1168`, `1174`–`1176`, `1187`, `1192`, `1197`, `1333`, `1350`, `1395`–`1438` (gasto/mejora NIF block), `1562`.

### Casillas introduced in 2021

`0158` (NIF del arrendatario), `1209` and `1244` (NIF del otro progenitor), `1070` (NIF empleada del hogar La Rioja), `1657`–`1675` (mejoras energéticas), `1724`–`1734` (NIF del productor).

### Casilla `0397` — label changes between revisions

2022: "NIF del plan de pensiones del sistema de empleo". 2023–2025: "NIF del empleador". Same id, same bucket 1 in all years. Automation must key on id+revision, not label.

### Stable bucket-2 ids (all six revisions)

`0272`, `0273`, `1621` — consistently deferred in every revision.

### Large new cluster in 2024

An_b_inf_adc_enf, an_b_inf_adc_dep, an_b_inf_adc_aia (8 NIF-prestador slots each), an_b_inf_adc_afp, an_b_inf_adc_ges, an_b_inf_adc_ipse — all bucket 1, all carry forward into 2025.

### New semantic-id section in 2025

`DPNIF_D`, `DPNIF_C`, `NIFDLG`, `DNIASDLG` — first appearance of alpha ids in M100; all bound, all bucket 1.

---

## Open questions

### OQ-1: Casillas with foreign-NIF companion flags (0077, 0091, 0094, 0097, 0911, 1122, 1125, 2205, 2208)

Each of these has a sibling boolean "si ha consignado un NIF de otro país". The excónyuge (0077) and tenants (0091, 0094, 0097) can legally be non-Spanish residents who supply a foreign fiscal ID. If `NifString` is applied at input time it will reject valid foreign NIFs. If applied only at submission time (when the foreign-NIF flag is false), it is safe. Decision required: apply validator at input or submission gate? If at input, these nine casillas must move to bucket 2.

### OQ-2: FEAC casillas 1974 and 1978 (label bare "NIF")

FEAC operations (cross-border mergers under EU directive) can involve non-resident legal entities. The companion "Si no tiene NIF" booleans confirm that non-NIF paths are valid. Whether the NIF here is always a Spanish NIF depends on whether AEAT requires Spanish entity registration for FEAC declarants. Recommend verifying against the FEAC instructions in the Orden HFP or AEAT publication before retrofitting.

### OQ-3: Canarias NIF/NIE 2044–2055 (bare "NIF/NIE N" labels)

Labels are "NIF/NIE 1", "NIF/NIE 3", "NIF/NIE 4" with no further context. The surrounding section is `canarias_res` covering childcare and dependency deductions. These are assumed bucket 1 (domestic workers, guardería staff). Verify against the Canarias 2024 deduction instructions to confirm these are not foreigner-open slots.

### OQ-4: 0272 and 0273 (re_derechos_imagen name/NIF dual-mode)

These are in bucket 2 as deferred. However, for declarants with Spanish-resident counterparties only, the field would always hold a Spanish NIF. Consider whether a runtime check (if counterparty is resident, validate as NIF) is preferable to a bare `text` type for these casillas long-term.
