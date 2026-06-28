---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-nif-role-assignment-audit]]"
---

# `schema-hardening` audit: M100 `resultados.anexo_c_res` role assignment

## Scope

`resultados.anexo_c_res` cluster across all six M100 revisions (2020–2025).
The 2025 revision contains 179 casillas in this cluster; 2 already carry
`disabled_person_nif` from the NIF role-assignment audit (IDs 1333, 1350).
177 casillas are unroled and classified here. Unique IDs across all revisions:
203 (the difference from 179 reflects IDs present only in 2021 legacy
sections and 2022–2025 `excesos_eficiencia_energetica_res` expansion).

Already-roled casillas skipped per dispatch mandate:
- `1333` — `disabled_person_nif` (NIF de la persona con discapacidad,
  `excesos_sistemas_prevision_social_personas_disc_parientes_res`)
- `1350` — `disabled_person_nif` (NIF de la persona con discapacidad titular
  del patrimonio protegido, `excesos_patrim_protegidos_res`)

---

## Sub-section taxonomy

Anexo C covers eight semantic groups:

| sub-section key | semantic group | year range present |
|---|---|---|
| `exencion_nuevas_empresas_res` | Reinvestment exemption — new companies (art. 68.1 LIRPF) | 2020–2025 |
| `exencion_rentas_vitalicias_res` | Reinvestment exemption — life annuities (art. 38 LIRPF) | 2020–2025 |
| `saldos_neg_gy_p_general_res` | Negative gains/losses carry-forward — base general | 2020–2025 |
| `saldos_neg_gy_p_ahorro_res` | Negative gains/losses carry-forward — base ahorro | 2020–2025 |
| `rdtos_cm_negativos_res` | Negative capital-mobiliario income carry-forward | 2020–2025 |
| `excesos_sistemas_prevision_social_res` / `_rt_res` | Excess pension-plan contributions (RT) carry-forward | 2020–2025 (section renamed in 2021) |
| `exceso_seguros_colectivos_dependencia_res` | Excess employer dependency-insurance contributions | 2020–2025 |
| `excesos_sistemas_prevision_social_personas_disc_propias_res` | Excess pension contributions — own disabled person | 2020–2025 |
| `excesos_sistemas_prevision_social_personas_disc_parientes_res` | Excess pension contributions — disabled relative | 2020–2025 |
| `excesos_patrim_protegidos_res` | Excess protected-patrimony contributions | 2020–2025 |
| `excesos_deportistas_res` | Excess sports-person pension contributions | 2020–2025 |
| `base_liq_neg_res` | Negative liquidable base carry-forward | 2020–2025 |
| `contribuciones_sist_prevision_social_rt_res` | Legacy employer-contribution carry-forward (pre-2022 years) | 2021 only |
| `aportaciones_sist_prevision_social_rg_res` | Personal pension contributions — current year | 2021 only |
| `contribuciones_sist_prevision_social_rg_res` | Employer pension contributions — current year | 2021 only |
| `gan_per_cuartas` | Public-subsidy gainpatrimonial deferred in quarters | 2021–2025 |
| `excesos_eficiencia_energetica_res` | Excess energy-efficiency deduction carry-forward | 2022–2025 |

---

## Structural patterns

The cluster uses three recurring structural patterns:

**Pattern A — Contributor/property triplet** (`text` header + NIF + amounts):
Present in subsections where a named contributor and their NIF precede the
rolling-slot amounts. The `text` header (`Contribuyente titular` or
`Contribuyente con derecho a reducción`) and the NIF slot are the
discriminating fields; NIF slots already carry `disabled_person_nif`.

**Pattern B — Carry-forward rolling slots** (no NIF, purely amounts):
`pendiente_inicio_periodo` → `aplicado_periodo` → `pendiente_fin`
across one to five prior-year rows plus a current-year generation slot.
All carry `data_type` absent (decimal implied, M100 convention).

**Pattern C — Exempt-amount calculation** (for exención subsections):
`titular` (text) → total obtained → gain computed → reinverted → committed →
exempt amount. These are calculation slots, not rolling carry-forward slots.

---

## Per-id role-assignment table

`data_type` is `(absent)` where the TOML field is not declared; M100
convention treats absent as `decimal`. Confirmed `text` and `nif` fields
are listed with their declared type.

### Group 1 — `exencion_nuevas_empresas_res`

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1231 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | Enum: `D`=declarante, `C`=conyuge; structural header |
| 1232 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_exencion_reinversion_importe_total_transmision` | Importe total obtenido como consecuencia de la transmisión de acciones o participaciones | (absent) | 2020–2025 | |
| 1233 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_exencion_reinversion_ganancia_patrimonial` | Ganancia patrimonial obtenida como consecuencia de la transmisión | (absent) | 2020–2025 | |
| 1234 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_exencion_reinversion_importe_reinvertido` | Importe reinvertido hasta el 31-12-ejercicio en adquisición | (absent) | 2020–2025 | Year suffix in label changes per revision; role is stable |
| 1235 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_exencion_reinversion_importe_comprometido` | Importe que el contribuyente se compromete a reinvertir en año siguiente | (absent) | 2020–2025 | |
| 1236 | resultados.anexo_c_res.exencion_nuevas_empresas_res | `irpf_anexo_c_exencion_reinversion_ganancia_exenta` | Ganancia patrimonial exenta por reinversión | (absent) | 2020–2025 | |

### Group 2 — `exencion_rentas_vitalicias_res`

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1237 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | Shared role with 1231; same D/C enum |
| 1238 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_importe_total_transmision` | Importe total obtenido por la transmisión del/los elemento/s patrimonial/es | (absent) | 2020–2025 | Distinct role from 1232 — source is real-estate/asset not shares |
| 1239 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_ganancia_patrimonial` | Ganancia patrimonial obtenida | (absent) | 2020–2025 | |
| 1240 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_importe_reinvertido` | Importe reinvertido hasta el 31-12-ejercicio en rentas vitalicias | (absent) | 2020–2025 | |
| 1241 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_importe_comprometido` | Importe que el contribuyente se compromete a reinvertir en 2026 | (absent) | 2020–2025 | |
| 1242 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_retencion_comprometida` | Importe de la retención que el contribuyente se compromete a reinvertir | (absent) | 2020–2025 | Distinct from committed amount: portion held as withheld |
| 1243 | resultados.anexo_c_res.exencion_rentas_vitalicias_res | `irpf_anexo_c_exencion_rv_ganancia_exenta` | Ganancia patrimonial exenta por reinversión | (absent) | 2020–2025 | |

### Group 3 — `saldos_neg_gy_p_general_res`

Rolling pattern: one row per prior year (2021–2024) with two or three slots each, plus a current-year generation slot. Role names use `_pendiente_inicio`, `_aplicado`, `_pendiente_fin` suffixes.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1245 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | |
| 1246 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | Year in label slides per revision; role stable |
| 1247 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1248 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | Same role as 1246 — sliding year label; shared role confirmed |
| 1249 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1250 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1251 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1252 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1253 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1254 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1255 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1256 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1257 | resultados.anexo_c_res.saldos_neg_gy_p_general_res | `irpf_anexo_c_saldo_neg_gyp_general_generado` | Saldo negativo de las ganancias y pérdidas imputables a N, a integrar en la base general | (absent) | 2020–2025 | Current-year generation slot |

### Group 4 — `saldos_neg_gy_p_ahorro_res`

Same rolling structure as Group 3, base ahorro variant.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1258 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | |
| 1259 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1260 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1261 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1262 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1263 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1264 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1265 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1266 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1267 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1268 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1269 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1270 | resultados.anexo_c_res.saldos_neg_gy_p_ahorro_res | `irpf_anexo_c_saldo_neg_gyp_ahorro_generado` | Saldo negativo de las ganancias y pérdidas imputables a N, a integrar en la base ahorro | (absent) | 2020–2025 | |

### Group 5 — `rdtos_cm_negativos_res`

Same rolling structure; capital-mobiliario negative income carry-forward.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1271 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | |
| 1272 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1273 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1274 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1275 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1276 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1277 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1278 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1279 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1280 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1281 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1282 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1283 | resultados.anexo_c_res.rdtos_cm_negativos_res | `irpf_anexo_c_rdto_cm_negativo_generado` | Saldo negativo de los rendimientos de capital mobiliario imputables a N | (absent) | 2020–2025 | |

### Group 6 — `excesos_sistemas_prevision_social_rt_res` (fka `_res` in 2020)

Rolling carry-forward for excess pension-plan contributions (RT — rendimientos trabajo). Section renamed `excesos_sistemas_prevision_social_res` → `excesos_sistemas_prevision_social_rt_res` between 2020 and 2021. Semantics identical; cross-revision role is shared.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1284 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | Section-rename hazard: section differs 2020 vs 2021+; semantics identical — see hazard table |
| 1285 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio N-5: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | Year label slides; role stable |
| 1286 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio N-5: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1287 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1288 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1289 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio N-4: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1290 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1291 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1292 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1293 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1294 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1295 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1296 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1297 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1298 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1299 | ...excesos_sistemas_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_generado` | Aportaciones y contribuciones de N no aplicadas (excepto contrib. empresariales a seguros dependencia) | (absent) | 2020, 2022–2025 | Absent in 2021 (moved to 1741–1755 in that year) |

### Group 7 — `exceso_seguros_colectivos_dependencia_res`

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1300 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | |
| 1301 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_inicio` | Ejercicio N-5: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1302 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_aplicado` | Ejercicio N-5: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1303 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1304 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1305 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_fin` | Ejercicio N-4: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1306 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1307 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1308 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1309 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1310 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1311 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1312 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1313 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1314 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1315 | ...exceso_seguros_colectivos_dependencia_res | `irpf_anexo_c_exceso_scd_generado` | Contribuciones de N a seguros colectivos de dependencia no aplicadas | (absent) | 2020–2025 | |

### Group 8 — `excesos_sistemas_prevision_social_personas_disc_propias_res`

Own-disabled-person pension carry-forward (no NIF field — contributor is the taxpayer themselves).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1316 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | |
| 1317 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | Ejercicio N-5: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1318 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | Ejercicio N-5: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1319 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1320 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1321 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | Ejercicio N-4: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1322 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1323 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1324 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1325 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1326 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1327 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1328 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1329 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1330 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1331 | ...excesos_sps_personas_disc_propias_res | `irpf_anexo_c_exceso_sps_disc_propias_generado` | Aportaciones y contribuciones de N no aplicadas cuyo importe se solicita poder reducir | (absent) | 2020–2025 | |

### Group 9 — `excesos_sistemas_prevision_social_personas_disc_parientes_res`

Disabled-relative pension carry-forward. Includes NIF field (1333, already roled).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1332 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | |
| **1333** | ...excesos_sps_personas_disc_parientes_res | **`disabled_person_nif`** (already roled) | NIF de la persona con discapacidad | nif | 2020–2025 | **SKIP — already roled** |
| 1334 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | Ejercicio N-5: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1335 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | Ejercicio N-5: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1336 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1337 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1338 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | Ejercicio N-4: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1339 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1340 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1341 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1342 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1343 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1344 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1345 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1346 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1347 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1348 | ...excesos_sps_personas_disc_parientes_res | `irpf_anexo_c_exceso_sps_disc_parientes_generado` | Aportaciones y contribuciones de N no aplicadas cuyo importe se solicita poder reducir | (absent) | 2020–2025 | |

### Group 10 — `excesos_patrim_protegidos_res`

Excess protected-patrimony contributions carry-forward. Includes NIF field (1350, already roled).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1349 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | |
| **1350** | ...excesos_patrim_protegidos_res | **`disabled_person_nif`** (already roled) | NIF de la persona con discapacidad titular del patrimonio protegido | nif | 2020–2025 | **SKIP** |
| 1351 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1352 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1353 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1354 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1355 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1356 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1357 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1358 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1359 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1360 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1361 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1362 | ...excesos_patrim_protegidos_res | `irpf_anexo_c_exceso_patrim_protegido_generado` | Aportaciones de N no aplicadas cuyo importe se solicita poder reducir en los 5 ejercicios siguientes | (absent) | 2020–2025 | |

### Group 11 — `excesos_deportistas_res`

Excess sports-person pension carry-forward (art. 51.8 LIRPF).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1363 | ...excesos_deportistas_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2020–2025 | |
| 1364 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | Ejercicio N-5: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1365 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_aplicado` | Ejercicio N-5: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1366 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1367 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1368 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_fin` | Ejercicio N-4: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1369 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1370 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1371 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1372 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1373 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1374 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1375 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1376 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1377 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1378 | ...excesos_deportistas_res | `irpf_anexo_c_exceso_deportistas_generado` | Aportaciones y contribuciones de N no aplicadas cuyo importe se solicita poder reducir | (absent) | 2020–2025 | |

### Group 12 — `base_liq_neg_res`

Negative liquidable base carry-forward (base general, 4-year window).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1379 | ...base_liq_neg_res | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2020–2025 | |
| 1380 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_inicio` | Ejercicio N-4: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1381 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_aplicado` | Ejercicio N-4: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1382 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1383 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1384 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_fin` | Ejercicio N-3: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1385 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1386 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1387 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1388 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2020–2025 | |
| 1389 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2020–2025 | |
| 1390 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2020–2025 | |
| 1391 | ...base_liq_neg_res | `irpf_anexo_c_base_liq_neg_generado` | Base liquidable general negativa de N pendiente de compensar en los 4 ejercicios siguientes | (absent) | 2020–2025 | |

### Group 13 — `gan_per_cuartas` (2021–2025)

Public-subsidy gain deferred in quarters rule (art. 14.2.g LIRPF — imputación temporal especial).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1735 | ...gan_per_cuartas | `irpf_anexo_c_contribuyente_titular` | Contribuyente titular | text | 2021–2025 | |
| 1736 | ...gan_per_cuartas | `irpf_anexo_c_gan_per_cuartas_tipo_ayuda` | Tipo de ayuda pública | text | 2021–2025 | Categorical description field |
| 1737 | ...gan_per_cuartas | `irpf_anexo_c_gan_per_cuartas_anio_obtencion` | Año en el que se ha obtenido la ayuda pública | text | 2021–2025 | Year as text (not `year` data_type — not a filing period) |
| 1738 | ...gan_per_cuartas | `irpf_anexo_c_gan_per_cuartas_importe_total` | Importe total de la ayuda pública percibida | (absent) | 2021–2025 | |
| 1739 | ...gan_per_cuartas | `irpf_anexo_c_gan_per_cuartas_aplicado` | Importe de la ayuda pública aplicada en el ejercicio | (absent) | 2021–2025 | |
| 1740 | ...gan_per_cuartas | `irpf_anexo_c_gan_per_cuartas_pendiente` | Importe pendiente de imputación | (absent) | 2021–2025 | |

### Group 14 — `contribuciones_sist_prevision_social_rt_res` (2021 only)

Legacy employer-contribution (RT) carry-forward for pre-2021 years. Present only in the 2021 revision; subsumed into the main `excesos_sps_rt_res` rolling table in 2022+.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1741 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2021 only | |
| 1742 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio 2016: Pendiente de aplicación al principio del periodo | (absent) | 2021 only | Shared role with Group 6 slots — same carry-forward concept |
| 1743 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio 2016: Aplicado en esta declaración | (absent) | 2021 only | |
| 1744 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio 2017: Pendiente de aplicación al principio del periodo | (absent) | 2021 only | |
| 1745 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio 2017: Aplicado en esta declaración | (absent) | 2021 only | |
| 1746 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio 2017: Pendiente de aplicación en ejercicios futuros | (absent) | 2021 only | |
| 1747 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio 2018: Pendiente de aplicación al principio del periodo | (absent) | 2021 only | |
| 1748 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio 2018: Aplicado en esta declaración | (absent) | 2021 only | |
| 1749 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio 2018: Pendiente de aplicación en ejercicios futuros | (absent) | 2021 only | |
| 1750 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio 2019: Pendiente de aplicación al principio del periodo | (absent) | 2021 only | |
| 1751 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio 2019: Aplicado en esta declaración | (absent) | 2021 only | |
| 1752 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio 2019: Pendiente de aplicación en ejercicios futuros | (absent) | 2021 only | |
| 1753 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | Ejercicio 2020: Pendiente de aplicación al principio del periodo | (absent) | 2021 only | |
| 1754 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_aplicado` | Ejercicio 2020: Aplicado en esta declaración | (absent) | 2021 only | |
| 1755 | ...contribuciones_sist_prevision_social_rt_res | `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | Ejercicio 2020: Pendiente de aplicación en ejercicios futuros | (absent) | 2021 only | |

### Group 15 — `aportaciones_sist_prevision_social_rg_res` (2021 only)

Personal pension contributions (RG) for current period. 2021 only; replaced by the main rolling table in subsequent revisions.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1756 | ...aportaciones_sist_prevision_social_rg_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2021 only | |
| 1757 | ...aportaciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_aportaciones_periodo` | Ejercicio 2021: Aportaciones personales del período | (absent) | 2021 only | Current-year generation (personal) |
| 1758 | ...aportaciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado` | Ejercicio 2021: Aportaciones personales aplicadas en esta declaración | (absent) | 2021 only | |
| 1759 | ...aportaciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_aportaciones_pendiente_fin` | Ejercicio 2021: Aportaciones personales pendientes de aplicación en ejercicios futuros | (absent) | 2021 only | |

### Group 16 — `contribuciones_sist_prevision_social_rg_res` (2021 only)

Employer pension contributions (RG) for current period. 2021 only.

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1760 | ...contribuciones_sist_prevision_social_rg_res | `irpf_anexo_c_contribuyente_con_derecho_reduccion` | Contribuyente con derecho a reducción | text | 2021 only | |
| 1761 | ...contribuciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_contribuciones_periodo` | Ejercicio 2021: Contribuciones empresariales del período | (absent) | 2021 only | |
| 1762 | ...contribuciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado` | Ejercicio 2021: Contribuciones empresariales aplicadas en esta declaración | (absent) | 2021 only | |
| 1763 | ...contribuciones_sist_prevision_social_rg_res | `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` | Ejercicio 2021: Contribuciones empresariales pendientes de aplicación | (absent) | 2021 only | |

### Group 17 — `excesos_eficiencia_energetica_res` (2022–2025)

Excess energy-efficiency deduction carry-forward (4-year window). Added in the 2022 revision; expanded with additional prior-year rows in subsequent revisions. ID 1694 (2024 only) is a transitional row that was dropped in 2025 (replaced by IDs 2024 and 2048).

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1853 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_contribuyente_con_derecho_deduccion` | Contribuyente con derecho a deducción | text | 2022–2025 | Note: "deducción" not "reducción" — different legal concept |
| 1692 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | Ejercicio N-3: Pendiente de aplicación al principio del periodo | (absent) | 2024–2025 | |
| 1693 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_aplicado` | Ejercicio N-3: Aplicado en esta declaración | (absent) | 2024–2025 | |
| 1694 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | Ejercicio 2021: Pendiente de aplicación en ejercicios futuros | (absent) | 2024 only | Transitional row; see hazard note |
| 2024 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | Ejercicio 2021: Pendiente de aplicación al principio del periodo | (absent) | 2025 only | New ID introduced 2025 for the 2021 row |
| 2025 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_aplicado` | Ejercicio 2021: Aplicado en esta declaración | (absent) | 2025 only | |
| 2048 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | Ejercicio 2022: Pendiente de aplicación en ejercicios futuros | (absent) | 2025 only | |
| 1695 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | Ejercicio N-2: Pendiente de aplicación al principio del periodo | (absent) | 2023–2025 | |
| 1696 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_aplicado` | Ejercicio N-2: Aplicado en esta declaración | (absent) | 2023–2025 | |
| 1697 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | Ejercicio N-2: Pendiente de aplicación en ejercicios futuros | (absent) | 2023–2025 | |
| 1854 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | Ejercicio N-1: Pendiente de aplicación al principio del periodo | (absent) | 2022–2025 | |
| 1855 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_aplicado` | Ejercicio N-1: Aplicado en esta declaración | (absent) | 2022–2025 | |
| 1856 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | Ejercicio N-1: Pendiente de aplicación en ejercicios futuros | (absent) | 2022–2025 | |
| 1857 | ...excesos_eficiencia_energetica_res | `irpf_anexo_c_exceso_eeficiencia_generado` | Cantidades satisfechas en el ejercicio N pendientes de deducir en los 4 ejercicios siguientes | (absent) | 2022–2025 | |

---

## New roles introduced

All roles below carry `data_type = (absent)` unless noted. M100 convention
treats absent as decimal; see decimal/money note below.

| role | data_type | definition |
|---|---|---|
| `irpf_anexo_c_contribuyente_titular` | text | Header enum field indicating which taxpayer (D=declarante, C=cónyuge) is the owner of this Anexo C item. Shared across all subsections using "Contribuyente titular" label. |
| `irpf_anexo_c_contribuyente_con_derecho_reduccion` | text | Header enum field for subsections where the eligible contributor is identified by reduction-right (D/C). Shared across all excess pension-contribution and carry-forward groups. |
| `irpf_anexo_c_contribuyente_con_derecho_deduccion` | text | Header enum field for the energy-efficiency deduction subsection (art. 68.1bis LIRPF). Distinct from `_reduccion` — deduction not reduction. |
| `irpf_anexo_c_exencion_reinversion_importe_total_transmision` | decimal | Total amount obtained from the transmission of shares/participations eligible for reinvestment exemption under art. 68.1 LIRPF (new/recent entities). |
| `irpf_anexo_c_exencion_reinversion_ganancia_patrimonial` | decimal | Capital gain from the transmission of shares for which the art. 68.1 deduction was previously obtained. |
| `irpf_anexo_c_exencion_reinversion_importe_reinvertido` | decimal | Amount reinvested by year-end in acquisition of new/recent-creation entity shares. |
| `irpf_anexo_c_exencion_reinversion_importe_comprometido` | decimal | Amount committed to reinvest in the year following transmission (future-year commitment slot). |
| `irpf_anexo_c_exencion_reinversion_ganancia_exenta` | decimal | Capital gain exempt by reinvestment under art. 38/68.1 LIRPF. Computed output. |
| `irpf_anexo_c_exencion_rv_importe_total_transmision` | decimal | Total amount obtained from the transmission of real-estate/asset eligible for annuity reinvestment exemption (art. 38 LIRPF). Distinct from `_reinversion_importe_total` — source asset is real property/tangible not shares. |
| `irpf_anexo_c_exencion_rv_ganancia_patrimonial` | decimal | Capital gain obtained from the asset transmission for the annuity exemption. |
| `irpf_anexo_c_exencion_rv_importe_reinvertido` | decimal | Amount reinvested in life annuities by year-end. |
| `irpf_anexo_c_exencion_rv_importe_comprometido` | decimal | Amount committed to reinvest in life annuities (within 6-month post-transmission window). |
| `irpf_anexo_c_exencion_rv_retencion_comprometida` | decimal | Portion withheld that the contributor commits to reinvest in life annuities. |
| `irpf_anexo_c_exencion_rv_ganancia_exenta` | decimal | Capital gain exempt by life-annuity reinvestment. |
| `irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio` | decimal | Carry-forward balance of negative gains/losses (base general) at start of application period. Multiple casillas per subsection share this role (one per prior-year row). |
| `irpf_anexo_c_saldo_neg_gyp_general_aplicado` | decimal | Amount applied in the current declaration from the negative GYP general balance. |
| `irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin` | decimal | Amount remaining after application — carry-forward to future periods. |
| `irpf_anexo_c_saldo_neg_gyp_general_generado` | decimal | Negative GYP general balance generated in the current year, to be compensated in future declarations. |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio` | decimal | Same pattern as `_general` variant — base ahorro (savings-base losses). |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_aplicado` | decimal | |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_fin` | decimal | |
| `irpf_anexo_c_saldo_neg_gyp_ahorro_generado` | decimal | |
| `irpf_anexo_c_rdto_cm_negativo_pendiente_inicio` | decimal | Carry-forward balance of negative capital-mobiliario income at start of period. |
| `irpf_anexo_c_rdto_cm_negativo_aplicado` | decimal | |
| `irpf_anexo_c_rdto_cm_negativo_pendiente_fin` | decimal | |
| `irpf_anexo_c_rdto_cm_negativo_generado` | decimal | |
| `irpf_anexo_c_exceso_sps_rt_pendiente_inicio` | decimal | Carry-forward of excess pension contributions (RT) at start of period. Shared across Groups 6 and 14. |
| `irpf_anexo_c_exceso_sps_rt_aplicado` | decimal | |
| `irpf_anexo_c_exceso_sps_rt_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_sps_rt_generado` | decimal | Excess pension contributions (RT) from the current year not applied, to be carried forward 5 years. |
| `irpf_anexo_c_exceso_scd_pendiente_inicio` | decimal | Carry-forward of excess employer dependency-insurance contributions. |
| `irpf_anexo_c_exceso_scd_aplicado` | decimal | |
| `irpf_anexo_c_exceso_scd_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_scd_generado` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_propias_pendiente_inicio` | decimal | Carry-forward of excess pension contributions for own disabled person. |
| `irpf_anexo_c_exceso_sps_disc_propias_aplicado` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_propias_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_propias_generado` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_inicio` | decimal | Carry-forward of excess pension contributions for disabled relative. |
| `irpf_anexo_c_exceso_sps_disc_parientes_aplicado` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_parientes_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_sps_disc_parientes_generado` | decimal | |
| `irpf_anexo_c_exceso_patrim_protegido_pendiente_inicio` | decimal | Carry-forward of excess protected-patrimony contributions. |
| `irpf_anexo_c_exceso_patrim_protegido_aplicado` | decimal | |
| `irpf_anexo_c_exceso_patrim_protegido_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_patrim_protegido_generado` | decimal | |
| `irpf_anexo_c_exceso_deportistas_pendiente_inicio` | decimal | Carry-forward of excess sports-person pension contributions. |
| `irpf_anexo_c_exceso_deportistas_aplicado` | decimal | |
| `irpf_anexo_c_exceso_deportistas_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_deportistas_generado` | decimal | |
| `irpf_anexo_c_base_liq_neg_pendiente_inicio` | decimal | Carry-forward of negative liquidable base at start of period (4-year window). |
| `irpf_anexo_c_base_liq_neg_aplicado` | decimal | |
| `irpf_anexo_c_base_liq_neg_pendiente_fin` | decimal | |
| `irpf_anexo_c_base_liq_neg_generado` | decimal | |
| `irpf_anexo_c_gan_per_cuartas_tipo_ayuda` | text | Description of the public subsidy type (categorical text — art. 14.2.g LIRPF deferred gain). |
| `irpf_anexo_c_gan_per_cuartas_anio_obtencion` | text | Year in which the public subsidy was obtained (text, not year data_type — not a filing period). |
| `irpf_anexo_c_gan_per_cuartas_importe_total` | decimal | Total amount of public subsidy received. |
| `irpf_anexo_c_gan_per_cuartas_aplicado` | decimal | Amount of public subsidy applied in the current period. |
| `irpf_anexo_c_gan_per_cuartas_pendiente` | decimal | Amount remaining for future imputación. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_periodo` | decimal | Personal pension contributions (RG) in the current period. 2021-only. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado` | decimal | Personal pension contributions (RG) applied in the declaration. 2021-only. |
| `irpf_anexo_c_exceso_sps_rg_aportaciones_pendiente_fin` | decimal | Personal pension contributions (RG) pending application in future years. 2021-only. |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_periodo` | decimal | Employer pension contributions (RG) in the current period. 2021-only. |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado` | decimal | Employer pension contributions (RG) applied in the declaration. 2021-only. |
| `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` | decimal | Employer pension contributions (RG) pending application. 2021-only. |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | decimal | Carry-forward of excess energy-efficiency deduction at start of period (4-year window, art. 68.1bis LIRPF). |
| `irpf_anexo_c_exceso_eeficiencia_aplicado` | decimal | |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | decimal | |
| `irpf_anexo_c_exceso_eeficiencia_generado` | decimal | Excess energy-efficiency deduction from current year, pending in future 4 years. |

**Total new roles: 67**

---

## Cross-revision id-reuse hazards

### Section-rename-only drift: IDs 1284–1299 (not a semantic hazard)

IDs 1284–1299 appear in `excesos_sistemas_prevision_social_res` (2020) and in
`excesos_sistemas_prevision_social_rt_res` (2021–2025). The section was simply
renamed to make the RT (rendimientos del trabajo) qualifier explicit. Label
content is substantively identical (minor year-number slide to track the
rolling window). The cross-revision validator keys on `semantic_role` not on
`section`; a shared role can be assigned safely across all 6 revisions.

Resolution: assign the `irpf_anexo_c_exceso_sps_rt_*` family to IDs 1284–1299
in all revisions. The section-path difference is structural metadata only.

### 2021-only section split: IDs 1741–1763

In the 2021 revision, AEAT split the pension-contribution carry-forward into
three sub-sections (`contribuciones_sist_prevision_social_rt_res`,
`aportaciones_sist_prevision_social_rg_res`,
`contribuciones_sist_prevision_social_rg_res`) using IDs 1741–1763 that do
not appear in any other revision. These IDs are genuinely revision-local.

Resolution: assign roles from the shared carry-forward families
(`irpf_anexo_c_exceso_sps_rt_*`, `irpf_anexo_c_exceso_sps_rg_*`) to match
the concept, accepting the single-revision range. No semantic hazard — the
concepts are consistent; the structural split was undone in 2022.

The `typo-twin` warning will fire for all `irpf_anexo_c_exceso_sps_rg_*`
roles (Groups 15–16) since they appear only in the 2021 revision.
These warnings are expected and should be documented in the taxonomy reference.

### ID 1694: transitional 2024-only row in `excesos_eficiencia_energetica_res`

| revision | id | label | notes |
|---|---|---|---|
| 2024 only | 1694 | Ejercicio 2021: Pendiente de aplicación en ejercicios futuros | Transitional row for 2021 pending-fin slot |
| 2025 | 2048 | Ejercicio 2022: Pendiente de aplicación en ejercicios futuros | Same slot concept, different year-label |

The concept (`irpf_anexo_c_exceso_eeficiencia_pendiente_fin`) is identical.
ID 1694 disappears in 2025 because the 2021 window expired. Role can be
assigned identically across both. No semantic hazard — calendar advancement
only.

---

## decimal/money divergences

All amount casillas in the `anexo_c_res` cluster declare `data_type` absent
(no explicit declaration). Per M100 convention, absent = decimal. No casilla
in this cluster declares explicit `data_type = "money"`.

**No decimal/money mixed-type roles in this cluster.** The bulk-apply pass
should confirm `data_type = (absent)` is treated consistently as `decimal`
for all amount roles defined here. The intra-role consistency validator
will catch any divergent explicit `money` declarations introduced later.

The three header roles (`irpf_anexo_c_contribuyente_titular`,
`irpf_anexo_c_contribuyente_con_derecho_reduccion`,
`irpf_anexo_c_contribuyente_con_derecho_deduccion`) declare `data_type = "text"`.
These must not be bulk-applied to amount slots.

The two already-roled NIF casillas (1333, 1350) declare `data_type = "nif"`.

---

## typo-twin expected warnings

Roles whose assigned casillas span only one or two revisions will emit the
typo-twin advisory. Expected single-revision roles (not errors):

- `irpf_anexo_c_exceso_sps_rg_aportaciones_periodo` — 2021 only
- `irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado` — 2021 only
- `irpf_anexo_c_exceso_sps_rg_aportaciones_pendiente_fin` — 2021 only
- `irpf_anexo_c_exceso_sps_rg_contribuciones_periodo` — 2021 only
- `irpf_anexo_c_exceso_sps_rg_contribuciones_aplicado` — 2021 only
- `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` — 2021 only
- `irpf_anexo_c_contribuyente_con_derecho_deduccion` — 2022–2025 only (4 revisions; not single-occurrence, but narrow range)

All six `_rg_*` roles are expected typo-twin artifacts of the 2021 section
split. Document in the taxonomy reference when appending these roles.

---

## Acceptance summary

| metric | value |
|---|---|
| Casillas classified (2025 revision) | 179 |
| Already roled (skipped) | 2 |
| Newly classified | 177 |
| Unique IDs across all 6 revisions (cluster total) | 203 |
| New roles introduced | 67 |
| Cross-revision semantic hazards | 0 (section-rename drifts resolved; calendar-slide IDs resolved) |
| decimal/money divergences | 0 |
| Expected typo-twin warnings | 6 (`_rg_*` 2021-only roles) |
