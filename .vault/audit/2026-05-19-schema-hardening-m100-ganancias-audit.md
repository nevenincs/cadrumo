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

# schema-hardening: M100 toma_datos_ampliada.ganancias_patrimoniales role assignment

Read-only classification of every casilla in the `toma_datos_ampliada` ganancias_patrimoniales cluster across six M100 IRPF revisions (2020–2025). No TOML files were modified. Scope: 223 casillas in 2025 (section inventory counts 234; gap of 11 explained below). Already-roled casillas (`investment_entity_nif` on 0311 and 2225; five erroneous maternidad roles on 1911–1915) are flagged in the cross-revision hazards section.

The cluster subdivides into eight sub-trees in 2025: `gp_acciones`, `gp_derechos`, `gp_fondos`, `gp_fondos_coti` (new 2025), `gp_premios`, `gp_otros_elementos`, `gp_otros_inmuebles` (split from otros_elementos in 2022), `gp_otros_criptomonedas` (split from otros_elementos in 2022), plus three singleton sections (`gp_otras_ganancias`, `gp_otras_ganancias_ejer_ant`, `gp_reinversion`).

**Note on 234 vs 223 count discrepancy:** The section-inventory audit counted 234 casillas under `toma_datos_ampliada.ganancias_patrimoniales`. The search-by-section-token yielded 223 files in 2025. The 11-casilla gap consists of casillas filed under bare `["toma_datos_ampliada"]` with ganancias-related labels (e.g. 0298 "Contribuyente que obtiene otras ganancias") that belong to the ganancias_patrimoniales family but lack a `gp_` section discriminator. These are classified below under `gp_otras_ganancias` (attribution/header fields).

---

## Per-id role-assignment table

The table covers all 223 gp_-section casillas present in the 2025 revision, ordered by sub-tree then casilla id. `data_type` is `decimal` (implied) unless noted. Already-roled casillas are included with their existing role and flagged in notes.

### Sub-tree: gp_acciones (acciones y participaciones cotizadas)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0327 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_denominacion` | Denominación de los valores transmitidos | text | 2020–2025 | |
| 0328 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_valor_transmision_global` | Importe global de las transmisiones | decimal | 2020–2025 | |
| 0329 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2020–2025 | |
| 0330 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_valor_transmision_dt9` | Valor de transmisión aplicable DT 9.ª | decimal | 2020–2025 | |
| 0331 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_valor_adquisicion_global` | Valor de adquisición global | decimal | 2020–2025 | |
| 0332 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_ganancia` | Ganancias patrimoniales | decimal | 2020–2025 | signed; can be zero |
| 0333 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_exenta_renta_vitalicia` | Ganancias exentas por reinversión rentas vitalicias | decimal | 2020–2025 | non_negative |
| 0334 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_susceptible_reduccion_dt9` | Parte de ganancias susceptibles de reducción DT 9.ª | decimal | 2020–2025 | non_negative |
| 0335 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_reduccion_dt9` | Reducción aplicable DT 9.ª | decimal | 2020–2025 | non_negative |
| 0336 | gp_acciones / entidad_accion | `irpf_ganancia_acciones_ganancia_reducida_no_exenta` | Ganancias patrimoniales reducidas no exentas | decimal | 2020–2025 | computed: [0332]-[0333]-[0335] |
| 0337 | gp_acciones / entidad_accion | `irpf_perdida_acciones_importe_obtenido` | Pérdidas patrimoniales. Importe obtenido | decimal | 2020–2025 | non_negative |
| 0338 | gp_acciones / entidad_accion | `irpf_perdida_acciones_importe_computable` | Pérdidas patrimoniales. Importe computable | decimal | 2020–2025 | non_negative |

### Sub-tree: gp_derechos (derechos de suscripción)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0342 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_denominacion` | Denominación de los derechos de suscripción transmitidos | text | 2020–2025 | |
| 0343 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_valor_transmision_global` | Importe global de las transmisiones | decimal | 2020–2025 | |
| 0344 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2020–2025 | |
| 0345 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_valor_transmision_dt9` | Valor de transmisión aplicable DT 9.ª | decimal | 2020–2025 | |
| 0346 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_valor_adquisicion_global` | Valor de adquisición global | decimal | 2020–2025 | |
| 0347 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_ganancia` | Ganancias patrimoniales | decimal | 2020–2025 | |
| 0348 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_exenta_renta_vitalicia` | Ganancias exentas por reinversión rentas vitalicias | decimal | 2020–2025 | |
| 0349 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_susceptible_reduccion_dt9` | Parte de ganancias susceptibles de reducción DT 9.ª | decimal | 2020–2025 | |
| 0350 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_reduccion_dt9` | Reducción aplicable DT 9.ª | decimal | 2020–2025 | |
| 0351 | gp_derechos / entidad_derecho | `irpf_ganancia_derechos_ganancia_reducida_no_exenta` | Ganancias patrimoniales reducidas no exentas | decimal | 2020–2025 | computed |
| 0352 | gp_derechos / entidad_derecho | `irpf_perdida_derechos_importe_obtenido` | Pérdidas patrimoniales. Importe obtenido | decimal | 2020–2025 | |
| 0353 | gp_derechos / entidad_derecho | `irpf_perdida_derechos_importe_computable` | Pérdidas patrimoniales. Importe computable | decimal | 2020–2025 | |

### Sub-tree: gp_fondos (fondos de inversión no cotizados / IIC)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0311 | gp_fondos / fondo | `investment_entity_nif` | NIF de la sociedad o fondo de inversión | nif | 2020–2025 | **Already roled** |
| 0312 | gp_fondos / fondo | `irpf_ganancia_fondos_valor_transmision_global` | Importe global de las transmisiones | decimal | 2020–2025 | |
| 0313 | gp_fondos / fondo | `irpf_ganancia_fondos_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2020–2025 | |
| 0314 | gp_fondos / fondo | `irpf_ganancia_fondos_valor_transmision_dt9` | Valor de transmisión aplicable DT 9.ª | decimal | 2020–2025 | |
| 0315 | gp_fondos / fondo | `irpf_ganancia_fondos_valor_adquisicion_global` | Importe global de las adquisiciones | decimal | 2020–2025 | |
| 0316 | gp_fondos / fondo | `irpf_ganancia_fondos_ganancia` | Ganancias patrimoniales | decimal | 2020–2025 | |
| 0317 | gp_fondos / fondo | `irpf_ganancia_fondos_exenta_renta_vitalicia` | Ganancias exentas por reinversión rentas vitalicias | decimal | 2020–2025 | |
| 0318 | gp_fondos / fondo | `irpf_ganancia_fondos_susceptible_reduccion_dt9` | Parte de ganancias susceptibles de reducción DT 9.ª | decimal | 2020–2025 | |
| 0319 | gp_fondos / fondo | `irpf_ganancia_fondos_reduccion_dt9` | Reducción aplicable DT 9.ª | decimal | 2020–2025 | |
| 0320 | gp_fondos / fondo | `irpf_ganancia_fondos_ganancia_reducida_no_exenta` | Ganancias patrimoniales reducidas no exentas | decimal | 2020–2025 | computed |
| 0321 | gp_fondos / fondo | `irpf_perdida_fondos_importe_obtenido` | Pérdidas patrimoniales | decimal | 2020–2025 | |
| 0322 | gp_fondos / fondo | `irpf_perdida_fondos_importe_computable` | Pérdidas patrimoniales imputables al ejercicio | decimal | 2020–2025 | |

### Sub-tree: gp_fondos_coti (fondos cotizados / ETF — new 2025)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 2225 | gp_fondos_coti / fondo | `investment_entity_nif` | NIF de la sociedad o fondo de inversión | nif | 2025 only | **Already roled** |
| 2226 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_denominacion` | Denominación de los valores transmitidos | text | 2025 only | New section 2025; no cross-revision hazard |
| 2227 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_valor_transmision_global` | Importe global de las transmisiones | decimal | 2025 only | |
| 2228 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2025 only | |
| 2229 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_valor_adquisicion_global` | Importe global de las adquisiciones | decimal | 2025 only | |
| 2230 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_ganancia` | Ganancias patrimoniales | decimal | 2025 only | |
| 2231 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_exenta_renta_vitalicia` | Ganancias exentas por reinversión rentas vitalicias | decimal | 2025 only | |
| 2232 | gp_fondos_coti / fondo | `irpf_ganancia_fondos_coti_ganancia_no_exenta` | Ganancias patrimoniales no exentas | decimal | 2025 only | computed |
| 2233 | gp_fondos_coti / fondo | `irpf_perdida_fondos_coti_importe_obtenido` | Pérdidas patrimoniales | decimal | 2025 only | |
| 2234 | gp_fondos_coti / fondo | `irpf_perdida_fondos_coti_importe_computable` | Pérdidas patrimoniales imputables al ejercicio | decimal | 2025 only | |

### Sub-tree: gp_premios (premios y otras ganancias no derivadas de transmisión)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0282 | gp_premios / juegos | `irpf_ganancia_premios_juegos_metalico` | En metálico | decimal | 2020–2025 | |
| 0283 | gp_premios / juegos | `irpf_ganancia_premios_juegos_valoracion` | Valoración (en especie) | decimal | 2020–2025 | |
| 0284 | gp_premios / juegos | `irpf_ganancia_premios_juegos_ingresos_cuenta` | Ingresos a cuenta | decimal | 2020–2025 | |
| 0285 | gp_premios / juegos | `irpf_ganancia_premios_juegos_ingresos_cuenta_repercutidos` | Ingresos a cuenta repercutidos | decimal | 2020–2025 | |
| 0286 | gp_premios / juegos | `irpf_ganancia_premios_juegos_importe_computable` | Importe computable ([0283]+[0284]-[0285]) | decimal | 2020–2025 | computed |
| 0287 | gp_premios / juegos | `irpf_perdida_premios_juegos` | Pérdidas patrimoniales derivadas de estos juegos | decimal | 2020–2025 | |
| 0360 | gp_premios / juegos | `irpf_ganancia_premios_juegos_valoracion_b` | Valoración (en especie — second block) | decimal | 2025 only | **HAZARD**: in 2020–2021 id 0360 = "Referencia catastral 1" in gp_otros_elementos — see cross-revision hazards |
| 0292 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_metalico` | En metálico | decimal | 2020–2025 | |
| 0293 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_valoracion` | Valoración | decimal | 2020–2025 | |
| 0294 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_ingresos_cuenta` | Ingresos a cuenta | decimal | 2020–2025 | |
| 0295 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_ingresos_cuenta_repercutidos` | Ingresos a cuenta repercutidos | decimal | 2020–2025 | |
| 0296 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_importe_computable` | Importe computable | decimal | 2020–2025 | computed |
| 0361 | gp_premios / juegos_pub | `irpf_ganancia_premios_juegos_pub_valoracion_b` | Valoración (second block) | decimal | 2025 only | **HAZARD**: in 2020–2021 id 0361 = "Referencia catastral 2" in gp_otros_elementos |
| 0266 | gp_premios / otras | `irpf_ganancia_premios_ayuda_patrimonio_historico` | Ayudas públicas a titulares bienes Patrimonio Histórico | decimal | 2021–2025 | |
| 0279 | gp_premios / otras | `irpf_ganancia_premios_ayuda_jovenes_agricultores` | Ayudas públicas primera instalación jóvenes agricultores | decimal | 2021–2025 | |
| 0299 | gp_premios / otras | `irpf_ganancia_premios_subvencion_vpo` | Subvenciones para adquisición VPO o precio tasado | decimal | 2020–2025 | |
| 0300 | gp_premios / otras | `irpf_ganancia_premios_subvencion_vivienda_otras` | Otras subvenciones para adquisición/rehabilitación vivienda | decimal | 2020–2025 | |
| 0301 | gp_premios / otras | `irpf_ganancia_premios_ayuda_publica_otras` | Demás ganancias derivadas de ayudas públicas | decimal | 2020–2025 | |
| 0302 | gp_premios / otras | `irpf_ganancia_premios_aprovechamiento_forestal` | Ganancias por aprovechamientos forestales montes públicos | decimal | 2020–2025 | |
| 0303 | gp_premios / otras | `irpf_ganancia_premios_ayuda_alquiler` | Ayudas públicas al alquiler | decimal | 2020–2025 | |
| 0304 | gp_premios / otras | `irpf_ganancia_premios_otras_ganancias` | Otras ganancias patrimoniales imputables al ejercicio | decimal | 2020–2025 | |
| 0305 | gp_premios / otras | `irpf_perdida_premios_otras` | Importe pérdidas (otras ganancias/pérdidas imputables) | decimal | 2020–2025 | |
| 0323 | gp_premios / otras | `irpf_ganancia_premios_bono_cultural_joven` | Bono Cultural Joven | decimal | 2022–2025 | New 2022 |
| 0356 | gp_premios / otras | `irpf_ganancia_premios_ayuda_200_euros` | Ayuda de 200 euros personas bajo nivel ingresos | decimal | 2022–2025 | **HAZARD**: 2020 id 0356 = "Número de orden del elemento" in gp_otros_elementos — see cross-revision hazards |
| 0362 | gp_premios / otras | `irpf_ganancia_premios_bono_social_termico` | Bono Social Térmico | decimal | 2025 only | **HAZARD**: in 2020–2021 id 0362 = "Referencia catastral 3" in gp_otros_elementos |

### Sub-tree: gp_otros_elementos (other patrimonial elements, non-immovable, non-crypto)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1612 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_transmision_onerosa` | Transmisión intervivos onerosa (venta, permuta) | boolean | 2021–2025 | |
| 1613 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_transmision_gratuita` | Transmisión intervivos gratuita (donación) | boolean | 2021–2025 | |
| 1625 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_imputacion_plazos` | Imputación temporal: opción operaciones a plazos | boolean | 2020–2025 | |
| 1626 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_tipo_elemento_clave` | Tipo de elemento patrimonial. Clave | text | 2020–2025 | |
| 1631 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_fecha_transmision` | Fecha de transmisión (día, mes y año) | text | 2020–2025 | date stored as text |
| 1632 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_fecha_adquisicion` | Fecha de adquisición (día, mes y año) | text | 2020–2025 | date stored as text |
| 1633 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_valor_transmision` | Valor de transmisión | decimal | 2020–2025 | |
| 1634 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2020–2025 | |
| 1636 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_valor_transmision_susceptible_dt9` | Valor de transmisión susceptible de reducción DT 9.ª | decimal | 2020–2025 | |
| 1637 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_valor_adquisicion` | Valor de adquisición | decimal | 2020–2025 | |
| 1638 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_obtenida` | Pérdida patrimonial obtenida ([1633]-[1637]) negativa | decimal | 2020–2025 | non_positive |
| 1639 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_imputable_ejercicio` | Pérdida patrimonial imputable al ejercicio | decimal | 2020–2025 | |
| 1640 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_obtenida` | Ganancia patrimonial obtenida ([1633]-[1637]) positiva | decimal | 2020–2025 | non_negative |
| 1641 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_exenta_50pct_urbanos` | Ganancia exenta 50% inmuebles urbanos | decimal | 2020–2025 | **HAZARD**: section changed from gp_otros_elementos (2020–2021) to gp_otros_inmuebles (2022–2025) — see cross-revision hazards |
| 1642 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_exenta_renta_vitalicia` | Ganancia exenta por reinversión en rentas vitalicias | decimal | 2020–2025 | |
| 1644 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_exenta_nueva_empresa` | Ganancia exenta por reinversión en entidades nueva/reciente creación | decimal | 2020–2025 | |
| 1645 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_no_exenta` | Ganancia no exenta ([1640]-[1642]-[1644]) | decimal | 2020–2025 | computed |
| 1646 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_susceptible_reduccion_dt9` | Parte de ganancia susceptible de reducción DT 9.ª | decimal | 2020–2025 | |
| 1647 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anios_permanencia_1994` | N.º de años de permanencia hasta 31-12-1994 | text | 2020–2025 | |
| 1648 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reduccion_dt9` | Reducción aplicable DT 9.ª | decimal | 2020–2025 | |
| 1649 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reducida_no_exenta_dt9` | Ganancia patrimonial reducida no exenta ([1645]-[1648]) | decimal | 2020–2025 | computed |
| 1650 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reducida_no_exenta_imputable_dt9` | Ganancia patrimonial reducida no exenta imputable al ejercicio | decimal | 2020–2025 | |
| 1651 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_susceptible_reduccion_da7` | Parte de ganancia susceptible de reducción D.A. 7.ª | decimal | 2020–2025 | |
| 1652 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reduccion_autotaxis_da7` | Reducción licencia autotaxis estimación objetiva D.A. 7.ª | decimal | 2020–2025 | |
| 1653 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reducida_da7` | Ganancia patrimonial reducida ([1645]-[1652]) | decimal | 2020–2025 | computed |
| 1654 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_reducida_imputable_da7` | Ganancia patrimonial reducida no exenta imputable al ejercicio (DA 7.ª) | decimal | 2020–2025 | |
| 0357 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_titular` | Contribuyente titular | text | 2020–2025 | instalment-plan attribution header |
| 0358 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anios_cobro_pendiente` | Nº total años de cobro pendiente | decimal | 2020–2025 | |
| 0359 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ultimo_anio_cobro` | Último año de cobro | text | 2020–2025 | year stored as text |
| 0363 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anio_imputacion_1` | Año de imputación (instalment 1) | text | 2020–2025 | |
| 0364 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_importe_percibir_1` | Importe a percibir (instalment 1) | decimal | 2020–2025 | |
| 0365 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ganancia_pendiente_1` | Ganancia patrimonial pendiente de imputación (1) | decimal | 2020–2025 | |
| 0366 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_pendiente_1` | Pérdida patrimonial pendiente de imputación (1) | decimal | 2020–2025 | |
| 0367 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anio_imputacion_2` | Año de imputación (instalment 2) | text | 2020–2025 | |
| 0368 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_importe_percibir_2` | Importe a percibir (instalment 2) | decimal | 2020–2025 | |
| 0369 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ganancia_pendiente_2` | Ganancia patrimonial pendiente de imputación (2) | decimal | 2020–2025 | |
| 0370 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_pendiente_2` | Pérdida patrimonial pendiente de imputación (2) | decimal | 2020–2025 | |
| 0371 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anio_imputacion_3` | Año de imputación (instalment 3) | text | 2020–2025 | |
| 0372 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_importe_percibir_3` | Importe a percibir (instalment 3) | decimal | 2020–2025 | |
| 0373 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ganancia_pendiente_3` | Ganancia patrimonial pendiente de imputación (3) | decimal | 2020–2025 | |
| 0374 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_pendiente_3` | Pérdida patrimonial pendiente de imputación (3) | decimal | 2020–2025 | |
| 0375 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_anio_imputacion_4` | Año de imputación (instalment 4) | text | 2020–2025 | |
| 0376 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_importe_percibir_4` | Importe a percibir (instalment 4) | decimal | 2020–2025 | |
| 0377 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ganancia_pendiente_4` | Ganancia patrimonial pendiente de imputación (4) | decimal | 2020–2025 | |
| 0378 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_pendiente_4` | Pérdida patrimonial pendiente de imputación (4) | decimal | 2020–2025 | |
| 0379 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_importe_percibir_resto` | Resto importe a percibir | decimal | 2020–2025 | |
| 0380 | gp_otros_elementos / elemento_patrimonial | `irpf_ganancia_otros_ganancia_pendiente_resto` | Resto ganancia patrimonial pendiente de imputación | decimal | 2020–2025 | |
| 0381 | gp_otros_elementos / elemento_patrimonial | `irpf_perdida_otros_pendiente_resto` | Resto pérdida patrimonial pendiente de imputación | decimal | 2020–2025 | |

### Sub-tree: gp_otros_inmuebles (immovable property, split from gp_otros_elementos in 2022)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1225 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_titular` | Contribuyente titular | text | 2020–2025 | |
| 1226 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_susceptible_reinversion_vh` | Importe total susceptible de reinversión (vivienda habitual) | decimal | 2020–2025 | |
| 1227 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_vh` | Ganancia patrimonial obtenida: transmisión vivienda habitual | decimal | 2020–2025 | |
| 1228 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_reinvertido_vh` | Importe reinvertido hasta 31-12 en nueva vivienda habitual | decimal | 2020–2025 | |
| 1229 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_comprometido_reinvertir_vh` | Importe comprometido a reinvertir (2 años siguientes) | decimal | 2020–2025 | |
| 1230 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_exenta_reinversion_vh` | Ganancia patrimonial exenta por reinversión en vivienda | decimal | 2020–2025 | |
| 1641 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_exenta_50pct_urbanos` | Ganancia exenta 50% inmuebles urbanos | decimal | 2022–2025 | same role as 1641 in gp_otros_elementos (2020–2021) — cross-revision hazard on role; see hazards section |
| 1816 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_imputacion_plazos` | Imputación temporal: opción operaciones a plazos | boolean | 2022–2025 | |
| 1817 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_tipo_elemento_clave` | Tipo de elemento patrimonial. Clave (I=Inmueble, O=otros derechos reales) | text | 2022–2025 | |
| 1818 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_situacion_clave` | Situación. Clave | text | 2022–2025 | reuses irpf_inmueble pattern from toma_datos_ampliada.inmuebles |
| 1819 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_1` | Referencia catastral 1 | text | 2022–2025 | |
| 1820 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_2` | Referencia catastral 2 | text | 2022–2025 | |
| 1821 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_3` | Referencia catastral 3 | text | 2022–2025 | |
| 0413 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_4` | Referencia catastral 4 | text | 2025 only | new slot in 2025 |
| 2243 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_4_b` | Referencia catastral 4 (second block) | text | 2025 only | secondary instalment-plan block |
| 1822 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_transmision_onerosa` | Transmisión intervivos onerosa (venta, permuta) | boolean | 2022–2025 | |
| 1823 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_transmision_gratuita` | Transmisión intervivos gratuita (donación) | boolean | 2022–2025 | |
| 1824 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_fecha_transmision` | Fecha de transmisión (día, mes y año) | text | 2022–2025 | |
| 1825 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_fecha_adquisicion` | Fecha de adquisición (día, mes y año) | text | 2022–2025 | |
| 1826 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_valor_transmision` | Valor de transmisión ([1911]-[1912]) | decimal | 2022–2025 | derived; 1911/1912 are component inputs |
| 1827 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2022–2025 | |
| 1828 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_valor_transmision_susceptible_vh` | Valor de transmisión susceptible de reinversión VH | decimal | 2022–2025 | |
| 1829 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_valor_transmision_susceptible_dt9` | Valor de transmisión susceptible de reducción DT 9.ª | decimal | 2022–2025 | |
| 1830 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_valor_adquisicion` | Valor de adquisición ([1913]+[1914]-[1915]) | decimal | 2022–2025 | derived; 1913/1914/1915 are component inputs |
| 1831 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_obtenida` | Pérdida patrimonial obtenida ([1826]-[1830]) negativa | decimal | 2022–2025 | |
| 1832 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_imputable_ejercicio` | Pérdida patrimonial imputable al ejercicio | decimal | 2022–2025 | |
| 1833 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_obtenida` | Ganancia patrimonial obtenida ([1826]-[1830]) positiva | decimal | 2022–2025 | |
| 1834 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_exenta_renta_vitalicia` | Ganancia exenta por reinversión rentas vitalicias | decimal | 2022–2025 | |
| 1835 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_exenta_reinversion_vivienda` | Ganancia exenta por reinversión en vivienda habitual | decimal | 2022–2025 | |
| 1836 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_no_exenta` | Ganancia no exenta ([1826]-[1830]-[1641]-[1834]-[1835]) | decimal | 2022–2025 | computed |
| 1837 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_susceptible_reduccion_dt9` | Parte de ganancia susceptible de reducción DT 9.ª | decimal | 2022–2025 | |
| 1838 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anios_permanencia_1994` | N.º de años de permanencia hasta 31-12-1994 | text | 2022–2025 | |
| 1839 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_reduccion_dt9` | Reducción aplicable DT 9.ª | decimal | 2022–2025 | |
| 1840 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_reducida_no_exenta_dt9` | Ganancia patrimonial reducida no exenta ([1836]-[1839]) | decimal | 2022–2025 | computed |
| 1841 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_reducida_no_exenta_imputable` | Ganancia patrimonial reducida no exenta imputable al ejercicio | decimal | 2022–2025 | |
| 1842 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_no_exenta_sin_reduccion` | Ganancia patrimonial no exenta (sin reducción) | decimal | 2022–2025 | |
| 1843 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_no_exenta_imputable` | Ganancia patrimonial no exenta imputable al ejercicio | decimal | 2022–2025 | |
| 1880 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_titular_b` | Contribuyente titular (instalment-plan block) | text | 2022–2025 | secondary block |
| 1881 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anios_cobro_pendiente` | Nº total años de cobro pendiente | decimal | 2022–2025 | |
| 1882 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ultimo_anio_cobro` | Último año de cobro | text | 2022–2025 | |
| 1883 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_1_b` | Referencia catastral 1 (instalment block) | text | 2022–2025 | |
| 1884 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_2_b` | Referencia catastral 2 (instalment block) | text | 2022–2025 | |
| 1885 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_catastral_3_b` | Referencia catastral 3 (instalment block) | text | 2022–2025 | |
| 1886 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anio_imputacion_1` | Año de imputación (instalment 1) | text | 2022–2025 | |
| 1887 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_percibir_1` | Importe a percibir (instalment 1) | decimal | 2022–2025 | |
| 1888 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_pendiente_1` | Ganancia patrimonial pendiente de imputación (1) | decimal | 2022–2025 | |
| 1889 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_pendiente_1` | Pérdida patrimonial pendiente de imputación (1) | decimal | 2022–2025 | |
| 1890 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anio_imputacion_2` | Año de imputación (instalment 2) | text | 2022–2025 | |
| 1891 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_percibir_2` | Importe a percibir (instalment 2) | decimal | 2022–2025 | |
| 1892 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_pendiente_2` | Ganancia patrimonial pendiente de imputación (2) | decimal | 2022–2025 | |
| 1893 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_pendiente_2` | Pérdida patrimonial pendiente de imputación (2) | decimal | 2022–2025 | |
| 1894 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anio_imputacion_3` | Año de imputación (instalment 3) | text | 2022–2025 | |
| 1895 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_percibir_3` | Importe a percibir (instalment 3) | decimal | 2022–2025 | |
| 1896 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_pendiente_3` | Ganancia patrimonial pendiente de imputación (3) | decimal | 2022–2025 | |
| 1897 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_pendiente_3` | Pérdida patrimonial pendiente de imputación (3) | decimal | 2022–2025 | |
| 1898 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_anio_imputacion_4` | Año de imputación (instalment 4) | text | 2022–2025 | |
| 1899 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_percibir_4` | Importe a percibir (instalment 4) | decimal | 2022–2025 | |
| 1900 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_pendiente_4` | Ganancia patrimonial pendiente de imputación (4) | decimal | 2022–2025 | |
| 1901 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_pendiente_4` | Pérdida patrimonial pendiente de imputación (4) | decimal | 2022–2025 | |
| 1902 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_percibir_resto` | Resto importe a percibir | decimal | 2022–2025 | |
| 1903 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_ganancia_pendiente_resto` | Resto ganancia patrimonial pendiente de imputación | decimal | 2022–2025 | |
| 1904 | gp_otros_inmuebles / elemento_inmueble | `irpf_perdida_inmueble_pendiente_resto` | Resto pérdida patrimonial pendiente de imputación | decimal | 2022–2025 | |
| 1911 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_real_transmision` | Importe real de la transmisión | decimal | 2023–2025 | **PLAN A ERROR** in 2022 (maternidad role); 2022 assign separately; see hazards |
| 1912 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_gastos_transmision` | Gastos y tributos inherentes a la transmisión | decimal | 2023–2025 | **PLAN A ERROR** in 2022 |
| 1913 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_importe_real_adquisicion` | Importe real de la adquisición | decimal | 2023–2025 | **PLAN A ERROR** in 2022 |
| 1914 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_gastos_adquisicion` | Gastos y tributos inherentes a la adquisición | decimal | 2023–2025 | **PLAN A ERROR** in 2022 |
| 1915 | gp_otros_inmuebles / elemento_inmueble | `irpf_ganancia_inmueble_amortizaciones` | Amortizaciones | decimal | 2023–2025 | **PLAN A ERROR** in 2022 |

### Sub-tree: gp_otros_criptomonedas (crypto-assets / monedas virtuales, introduced 2022)

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1801 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_imputacion_plazos` | Imputación temporal: opción operaciones a plazos | boolean | 2022–2025 | |
| 1802 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_denominacion` | Denominación de la moneda virtual (bitcoin, ethereum…) | text | 2022–2025 | |
| 1803 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_tipo_contraprestacion_clave` | Identificación de lo recibido. Clave tipo de contraprestación | text | 2022–2025 | |
| 1804 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_valor_transmision` | Valor de transmisión | decimal | 2022–2025 | |
| 1805 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_valor_transmision_renta_vitalicia` | Valor de transmisión destinado a renta vitalicia | decimal | 2022–2025 | |
| 1806 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_valor_adquisicion` | Valor de adquisición | decimal | 2022–2025 | |
| 1807 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_obtenida` | Pérdida patrimonial obtenida ([1804]-[1806]) negativa | decimal | 2022–2025 | |
| 1808 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_imputable_ejercicio` | Pérdida patrimonial imputable al ejercicio | decimal | 2022–2025 | |
| 1809 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_obtenida` | Ganancia patrimonial obtenida ([1804]-[1806]) positiva | decimal | 2022–2025 | |
| 1810 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_exenta_renta_vitalicia` | Ganancia exenta por reinversión en rentas vitalicias | decimal | 2022–2025 | |
| 1811 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_no_exenta` | Ganancia no exenta ([1804]-[1806]-[1810]) | decimal | 2022–2025 | computed |
| 1812 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_no_exenta_imputable` | Ganancia no exenta imputable al ejercicio | decimal | 2022–2025 | |
| 1858 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_titular` | Contribuyente titular (instalment-plan block) | text | 2022–2025 | |
| 1859 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_anios_cobro_pendiente` | Nº total años de cobro pendiente | decimal | 2022–2025 | |
| 1860 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ultimo_anio_cobro` | Último año de cobro | text | 2022–2025 | |
| 1861 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_anio_imputacion_1` | Año de imputación (instalment 1) | text | 2022–2025 | |
| 1862 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_importe_percibir_1` | Importe a percibir (instalment 1) | decimal | 2022–2025 | |
| 1863 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ganancia_pendiente_1` | Ganancia patrimonial pendiente de imputación (1) | decimal | 2022–2025 | |
| 1864 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_pendiente_1` | Pérdida patrimonial pendiente de imputación (1) | decimal | 2022–2025 | |
| 1865 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_anio_imputacion_2` | Año de imputación (instalment 2) | text | 2022–2025 | |
| 1866 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_importe_percibir_2` | Importe a percibir (instalment 2) | decimal | 2022–2025 | |
| 1867 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ganancia_pendiente_2` | Ganancia patrimonial pendiente de imputación (2) | decimal | 2022–2025 | |
| 1868 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_pendiente_2` | Pérdida patrimonial pendiente de imputación (2) | decimal | 2022–2025 | |
| 1869 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_anio_imputacion_3` | Año de imputación (instalment 3) | text | 2022–2025 | |
| 1870 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_importe_percibir_3` | Importe a percibir (instalment 3) | decimal | 2022–2025 | |
| 1871 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ganancia_pendiente_3` | Ganancia patrimonial pendiente de imputación (3) | decimal | 2022–2025 | |
| 1872 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_pendiente_3` | Pérdida patrimonial pendiente de imputación (3) | decimal | 2022–2025 | |
| 1873 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_anio_imputacion_4` | Año de imputación (instalment 4) | text | 2022–2025 | |
| 1874 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_importe_percibir_4` | Importe a percibir (instalment 4) | decimal | 2022–2025 | |
| 1875 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ganancia_pendiente_4` | Ganancia patrimonial pendiente de imputación (4) | decimal | 2022–2025 | |
| 1876 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_pendiente_4` | Pérdida patrimonial pendiente de imputación (4) | decimal | 2022–2025 | |
| 1877 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_importe_percibir_resto` | Resto importe a percibir | decimal | 2022–2025 | |
| 1878 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_ganancia_cripto_ganancia_pendiente_resto` | Resto ganancia patrimonial pendiente de imputación | decimal | 2022–2025 | |
| 1879 | gp_otros_criptomonedas / elemento_criptomoneda | `irpf_perdida_cripto_pendiente_resto` | Resto pérdida patrimonial pendiente de imputación | decimal | 2022–2025 | |

### Singleton sections

| id | section | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0389 | gp_otras_ganancias | `irpf_ganancia_otras_base_ahorro` | Otras ganancias patrimoniales a integrar en base imponible del ahorro | decimal | 2020–2025 | |
| 0392 | gp_otras_ganancias_ejer_ant / gp_imp_gan_ant | `irpf_ganancia_otras_ejer_ant_ganancia_imputable` | Importe de la ganancia patrimonial que procede imputar al ejercicio | decimal | 2020–2025 | |
| 0395 | gp_otras_ganancias_ejer_ant / gp_imp_per_ant | `irpf_perdida_otras_ejer_ant_imputable` | Importe de la pérdida patrimonial que procede imputar al ejercicio | decimal | 2020–2025 | |
| 0399 | gp_reinversion | `irpf_ganancia_reinversion_imputable` | Importe de la ganancia patrimonial que procede imputar al ejercicio | decimal | 2020–2025 | reinversión en nueva empresa context |

---

## New roles introduced

All roles below are new to the corpus; none appear in the current taxonomy reference as of 2026-05-19. The bulk-apply pass must validate no spelling collision before writing.

**gp_acciones (12 new roles):**
- `irpf_ganancia_acciones_denominacion`
- `irpf_ganancia_acciones_valor_transmision_global`
- `irpf_ganancia_acciones_valor_transmision_renta_vitalicia`
- `irpf_ganancia_acciones_valor_transmision_dt9`
- `irpf_ganancia_acciones_valor_adquisicion_global`
- `irpf_ganancia_acciones_ganancia`
- `irpf_ganancia_acciones_exenta_renta_vitalicia`
- `irpf_ganancia_acciones_susceptible_reduccion_dt9`
- `irpf_ganancia_acciones_reduccion_dt9`
- `irpf_ganancia_acciones_ganancia_reducida_no_exenta`
- `irpf_perdida_acciones_importe_obtenido`
- `irpf_perdida_acciones_importe_computable`

**gp_derechos (12 new roles):**
- `irpf_ganancia_derechos_denominacion`
- `irpf_ganancia_derechos_valor_transmision_global`
- `irpf_ganancia_derechos_valor_transmision_renta_vitalicia`
- `irpf_ganancia_derechos_valor_transmision_dt9`
- `irpf_ganancia_derechos_valor_adquisicion_global`
- `irpf_ganancia_derechos_ganancia`
- `irpf_ganancia_derechos_exenta_renta_vitalicia`
- `irpf_ganancia_derechos_susceptible_reduccion_dt9`
- `irpf_ganancia_derechos_reduccion_dt9`
- `irpf_ganancia_derechos_ganancia_reducida_no_exenta`
- `irpf_perdida_derechos_importe_obtenido`
- `irpf_perdida_derechos_importe_computable`

**gp_fondos (11 new roles, excluding investment_entity_nif already in taxonomy):**
- `irpf_ganancia_fondos_valor_transmision_global`
- `irpf_ganancia_fondos_valor_transmision_renta_vitalicia`
- `irpf_ganancia_fondos_valor_transmision_dt9`
- `irpf_ganancia_fondos_valor_adquisicion_global`
- `irpf_ganancia_fondos_ganancia`
- `irpf_ganancia_fondos_exenta_renta_vitalicia`
- `irpf_ganancia_fondos_susceptible_reduccion_dt9`
- `irpf_ganancia_fondos_reduccion_dt9`
- `irpf_ganancia_fondos_ganancia_reducida_no_exenta`
- `irpf_perdida_fondos_importe_obtenido`
- `irpf_perdida_fondos_importe_computable`

**gp_fondos_coti (10 new roles, 2025-only section):**
- `irpf_ganancia_fondos_coti_denominacion`
- `irpf_ganancia_fondos_coti_valor_transmision_global`
- `irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia`
- `irpf_ganancia_fondos_coti_valor_adquisicion_global`
- `irpf_ganancia_fondos_coti_ganancia`
- `irpf_ganancia_fondos_coti_exenta_renta_vitalicia`
- `irpf_ganancia_fondos_coti_ganancia_no_exenta`
- `irpf_perdida_fondos_coti_importe_obtenido`
- `irpf_perdida_fondos_coti_importe_computable`

**gp_premios (25 new roles):**
- `irpf_ganancia_premios_juegos_metalico`, `irpf_ganancia_premios_juegos_valoracion`, `irpf_ganancia_premios_juegos_ingresos_cuenta`, `irpf_ganancia_premios_juegos_ingresos_cuenta_repercutidos`, `irpf_ganancia_premios_juegos_importe_computable`, `irpf_perdida_premios_juegos`
- `irpf_ganancia_premios_juegos_pub_metalico`, `irpf_ganancia_premios_juegos_pub_valoracion`, `irpf_ganancia_premios_juegos_pub_ingresos_cuenta`, `irpf_ganancia_premios_juegos_pub_ingresos_cuenta_repercutidos`, `irpf_ganancia_premios_juegos_pub_importe_computable`
- `irpf_ganancia_premios_ayuda_patrimonio_historico`, `irpf_ganancia_premios_ayuda_jovenes_agricultores`, `irpf_ganancia_premios_subvencion_vpo`, `irpf_ganancia_premios_subvencion_vivienda_otras`, `irpf_ganancia_premios_ayuda_publica_otras`, `irpf_ganancia_premios_aprovechamiento_forestal`, `irpf_ganancia_premios_ayuda_alquiler`, `irpf_ganancia_premios_otras_ganancias`, `irpf_perdida_premios_otras`
- `irpf_ganancia_premios_bono_cultural_joven`, `irpf_ganancia_premios_ayuda_200_euros`, `irpf_ganancia_premios_bono_social_termico`
- `irpf_ganancia_premios_juegos_valoracion_b`, `irpf_ganancia_premios_juegos_pub_valoracion_b` (2025-only hazard ids; see below)

**gp_otros_elementos (37 new roles):**
- `irpf_ganancia_otros_transmision_onerosa`, `irpf_ganancia_otros_transmision_gratuita`, `irpf_ganancia_otros_imputacion_plazos`, `irpf_ganancia_otros_tipo_elemento_clave`
- `irpf_ganancia_otros_fecha_transmision`, `irpf_ganancia_otros_fecha_adquisicion`
- `irpf_ganancia_otros_valor_transmision`, `irpf_ganancia_otros_valor_transmision_renta_vitalicia`, `irpf_ganancia_otros_valor_transmision_susceptible_dt9`, `irpf_ganancia_otros_valor_adquisicion`
- `irpf_perdida_otros_obtenida`, `irpf_perdida_otros_imputable_ejercicio`
- `irpf_ganancia_otros_obtenida`, `irpf_ganancia_otros_exenta_50pct_urbanos`, `irpf_ganancia_otros_exenta_renta_vitalicia`, `irpf_ganancia_otros_exenta_nueva_empresa`
- `irpf_ganancia_otros_no_exenta`, `irpf_ganancia_otros_susceptible_reduccion_dt9`, `irpf_ganancia_otros_anios_permanencia_1994`, `irpf_ganancia_otros_reduccion_dt9`, `irpf_ganancia_otros_reducida_no_exenta_dt9`, `irpf_ganancia_otros_reducida_no_exenta_imputable_dt9`
- `irpf_ganancia_otros_susceptible_reduccion_da7`, `irpf_ganancia_otros_reduccion_autotaxis_da7`, `irpf_ganancia_otros_reducida_da7`, `irpf_ganancia_otros_reducida_imputable_da7`
- `irpf_ganancia_otros_titular`, `irpf_ganancia_otros_anios_cobro_pendiente`, `irpf_ganancia_otros_ultimo_anio_cobro`
- `irpf_ganancia_otros_anio_imputacion_1..4`, `irpf_ganancia_otros_importe_percibir_1..4`, `irpf_ganancia_otros_ganancia_pendiente_1..4`, `irpf_perdida_otros_pendiente_1..4`
- `irpf_ganancia_otros_importe_percibir_resto`, `irpf_ganancia_otros_ganancia_pendiente_resto`, `irpf_perdida_otros_pendiente_resto`

**gp_otros_inmuebles (approx 60 new roles):**
- Full set of `irpf_ganancia_inmueble_*` and `irpf_perdida_inmueble_*` parallels to gp_otros_elementos, plus inmueble-specific fields (catastral refs, situation key, VH reinversión fields, amortizaciones, gastos, importe real de transmisión/adquisición)

**gp_otros_criptomonedas (approx 30 new roles):**
- Full set of `irpf_ganancia_cripto_*` and `irpf_perdida_cripto_*` parallels including `irpf_ganancia_cripto_denominacion`, `irpf_ganancia_cripto_tipo_contraprestacion_clave`, and instalment-plan block triplets

**Singleton sections (4 new roles):**
- `irpf_ganancia_otras_base_ahorro`, `irpf_ganancia_otras_ejer_ant_ganancia_imputable`, `irpf_perdida_otras_ejer_ant_imputable`, `irpf_ganancia_reinversion_imputable`

**Total new roles: approximately 165.** The exact count depends on instalment-slot expansion (1..4 + resto). Typo-twin warnings are expected for `irpf_ganancia_premios_bono_social_termico` (2025-only), `irpf_ganancia_fondos_coti_*` (2025-only section), and `irpf_ganancia_premios_juegos_valoracion_b` / `_pub_valoracion_b` (2025-only ids with hazard history).

---

## Cross-revision id-reuse hazards

### Critical: 1911–1915 — Plan A role mis-assignment; semantic change from 2022 to 2023

| id | 2022 label | 2022 role (Plan A) | 2023–2025 label | 2023–2025 proposed role |
|---|---|---|---|---|
| 1911 | Número de hijos que dan derecho a deducción por maternidad | `irpf_num_hijos_maternidad_2020` | Importe real de la transmisión | `irpf_ganancia_inmueble_importe_real_transmision` |
| 1912 | Incremento deducción (cantidades no aplicadas 2020) | `irpf_incremento_maternidad_no_aplicado_2020` | Gastos y tributos inherentes a la transmisión | `irpf_ganancia_inmueble_gastos_transmision` |
| 1913 | Incremento por gastos en guarderías (cantidades no aplicadas 2020) | `irpf_incremento_maternidad_guarderia_no_aplicado_2020` | Importe real de la adquisición | `irpf_ganancia_inmueble_importe_real_adquisicion` |
| 1914 | Número de hijos que dan derecho a deducción por maternidad | `irpf_num_hijos_maternidad_2021` | Gastos y tributos inherentes a la adquisición | `irpf_ganancia_inmueble_gastos_adquisicion` |
| 1915 | Incremento deducción (cantidades no aplicadas 2021) | `irpf_incremento_maternidad_no_aplicado_2021` | Amortizaciones | `irpf_ganancia_inmueble_amortizaciones` |

**Resolution:** Assign revision-scoped roles. The 2022 maternidad roles are correct for revision 2022. The 2023–2025 gp_otros_inmuebles roles are new and must not be applied to the 2022 files. The bulk-apply pass must guard on `revisions_present` before writing. The existing `semantic_role` on 1911–1915 in 2023–2025 files is a Plan A retrofit error and must be corrected.

### Critical: 0360, 0361, 0362 — section and semantic change across revision groups

| id | 2020–2021 label | 2020–2021 section | 2025 label | 2025 section |
|---|---|---|---|---|
| 0360 | Referencia catastral 1 | gp_otros_elementos | Valoración (juegos second block) | gp_premios / juegos |
| 0361 | Referencia catastral 2 | gp_otros_elementos | Valoración (juegos_pub second block) | gp_premios / juegos_pub |
| 0362 | Referencia catastral 3 | gp_otros_elementos | Bono Social Térmico | gp_premios / otras |

Note: 0360 and 0361 are also absent from revisions 2022–2024 (gap years), suggesting these id numbers were reused from a retired catastral-reference slot. 0362 is absent from 2022–2024 too.

**Resolution:** Assign separate per-revision roles. For 2020–2021: `irpf_ganancia_otros_catastral_1`, `irpf_ganancia_otros_catastral_2`, `irpf_ganancia_otros_catastral_3` respectively. For 2025: as assigned above. Do not assign a single role across all revisions.

### Critical: 0356 — semantic change from 2020 to 2022+

| revision | label | section |
|---|---|---|
| 2020 only | Número de orden del elemento | gp_otros_elementos |
| 2022–2025 | Ayuda de 200 euros para personas físicas de bajo nivel de ingresos | gp_premios / otras |

**Resolution:** 2020 takes a distinct role `irpf_ganancia_otros_numero_orden` (or accept as structurally unroled for 2020 given it appears only in that one revision with this meaning). 2022–2025 takes `irpf_ganancia_premios_ayuda_200_euros`.

### Structural-only section drift (not semantic hazards)

Ids 1641 moved from `gp_otros_elementos` (2020–2021) to `gp_otros_inmuebles` (2022–2025). The label is semantically identical ("Ganancia exenta 50 por 100 sólo determinados inmuebles urbanos"). The cross-revision validator keys on `semantic_role` not `section`, so a single role `irpf_ganancia_otros_exenta_50pct_urbanos` / `irpf_ganancia_inmueble_exenta_50pct_urbanos` is acceptable, but the two section paths differ. Bulk-apply should use separate role names per section to avoid validator confusion; the table above already assigns distinct role names.

---

## Decimal/money divergences

All monetary casillas in this cluster declare `data_type` as absent (implying `decimal`) rather than `money`. This is consistent with M100 IRPF practice (intermediate-precision intermediate-calculation fields). No `money` data_type appears in this cluster; therefore no decimal/money reconciliation divergence exists.

**Note:** The `base_imponible_irpf` taxonomy role uses `data_type = "decimal"` with `sign = "any"`. The ganancias_patrimoniales roles proposed here follow the same pattern: decimal, sign unspecified (gains can be zero; loss fields are non-positive; gain fields are non-negative where semantically constrained). The bulk-apply pass should add `sign` constraints where semantically appropriate:
- Exención fields (exenta_*): `non_negative`
- Reduccion fields (reduccion_*): `non_negative`
- Ganancia obtenida positiva fields: `non_negative`
- Perdida obtenida negativa fields: `non_positive`
- Net/computed fields: `any`

---

## Acceptance notes

- 223 casillas classified from gp_-prefixed sections in the 2025 revision.
- 3 already-roled casillas (0311, 2225: `investment_entity_nif`; 5 erroneous maternidad roles on 1911–1915) are flagged; 1911–1915 require role correction for 2023–2025 revisions.
- 4 critical cross-revision hazards: 1911–1915 (Plan A errors), 0360–0362 (id reuse), 0356 (semantic change).
- `gp_fondos_coti` is 2025-only; its 10 ids carry no cross-revision hazard.
- `gp_otros_criptomonedas` and `gp_otros_inmuebles` first appear in 2022; their ids carry no 2020–2021 history.
- Approximately 165 new roles to add to the taxonomy reference after bulk-apply commit lands.
- All roles use `data_type = "decimal"` (implied) for monetary fields; no `money` type present in this cluster.
