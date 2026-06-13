---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# M200 schema-hardening — base-imponible-ajustes role assignments

## Scope

120 casillas across 5 sub-domain clusters that reduce or limit the taxable base (base imponible) in Modelo 200 (Impuesto sobre Sociedades, revision `2024-y-siguientes`):

| Sub-domain | Section key | Casilla count |
|---|---|---|
| Detalle compensación BIN por año de generación | `detalle_compensacion_bases_imponibles_negativas/{year}` + `/total` | 27 |
| Limitación GF gastos pendientes deducir por año generación | `limitacion_deducibilidad_gastos_financieros_gastos/{year}` + `/total` | 37 |
| Limitación GF cálculo límite art. 16.5/83 y art. 16.1/16.2 LIS | `limitacion_deducibilidad_gastos_financieros/limite_art_*` | 20 |
| Reserva capitalización + reserva nivelación (dotación / reducción BI) | `reserva_capitalizacion/{year}` + `reserva_de_nivelacion/*` | 24 |
| Exenciones art. 21, 22 y DA 6ª LIS | `exencion_sobre_la_renta_*`, `exencion_de_rentas_*`, `exencion_transmision_bienes_*` | 32 |

All 120 casillas have `data_type = "money"`. No `data_type` divergences exist in this cluster.

### Role reuse decisions

- `is_compensacion_bases_negativas` — amount applied in the current settlement for a per-vintage BIN row.
- `is_bin_pendiente_aplicacion` — BIN carry-forward balance per vintage year (pending future periods).
- `is_bin_total_pendiente` — aggregate BIN carry-forward total row.
- `is_gastos_financieros_limitacion_importe` — all gastos financieros excess carry-forward detail amounts (per vintage and total) and all computation-line amounts in the límite art. 16 worksheets.
- `is_reserva_capitalizacion_importe` — reduction of BI actually applied in the current period.
- `is_reserva_capitalizacion_pendiente` — capitalisation-reserve reduction right pending future periods.
- `is_reserva_nivelacion_dotacion` — levelling-reserve amount already provisioned (dotada).
- `is_reserva_nivelacion_incumplimiento` — levelling-reserve amount reversed into BI due to requirement breach.
- `is_reserva_nivelacion_adicion` — levelling-reserve pending future addition to BI (importe pendiente adicionar en periodos futuros).
- `is_correccion_aumento` — temporarias and permanentes increase-corrections (reused from the general corrections taxonomy; confirmed assigned to neighbouring casillas in the same exención sections).
- `is_correccion_disminucion` — temporarias decrease-corrections (same reasoning).

### New roles introduced (7)

| Role | Concept |
|---|---|
| `is_reserva_nivelacion_dotacion_pendiente` | Levelling-reserve dotation amount still pending (pendiente dotación) |
| `is_reserva_nivelacion_dotacion_dispuesta` | Levelling-reserve amount drawn down / disposed (reserva dispuesta) |
| `is_reserva_nivelacion_adicion_realizada` | Levelling-reserve addition already realised into BI in a prior period |
| `is_reserva_nivelacion_minoracion` | Levelling-reserve BI reduction for the period / pending (minoración BI periodo) |
| `is_exencion_transmision_saldo_inicio` | Carry-forward balance of exemption correction at the start of the period (saldo pendiente a principio de ejercicio) |
| `is_exencion_transmision_saldo_fin` | Carry-forward balance of exemption correction at the end of the period (saldo pendiente a fin de ejercicio) |
| `is_reserva_capitalizacion_importe` | BI reduction actually applied in the current settlement (Reducción B.I. aplicada) — note: this role existed conceptually but was not listed in _existing-roles.txt; nearest neighbour `is_reserva_capitalizacion_pendiente` was listed |

## Role assignments

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00647 | `is_compensacion_bases_negativas` | BIN 1999 — Aplicado en esta liquidación | money | reuse |
| 00648 | `is_bin_pendiente_aplicacion` | BIN 1999 — Pendiente aplicación períodos futuros | money | reuse |
| 00650 | `is_compensacion_bases_negativas` | BIN 2000 — Aplicado en esta liquidación | money | reuse |
| 00651 | `is_bin_pendiente_aplicacion` | BIN 2000 — Pendiente aplicación períodos futuros | money | reuse |
| 00653 | `is_compensacion_bases_negativas` | BIN 2001 — Aplicado en esta liquidación | money | reuse |
| 00654 | `is_bin_pendiente_aplicacion` | BIN 2001 — Pendiente aplicación períodos futuros | money | reuse |
| 00656 | `is_compensacion_bases_negativas` | BIN 2002 — Aplicado en esta liquidación | money | reuse |
| 00657 | `is_bin_pendiente_aplicacion` | BIN 2002 — Pendiente aplicación períodos futuros | money | reuse |
| 00659 | `is_compensacion_bases_negativas` | BIN 2003 — Aplicado en esta liquidación | money | reuse |
| 00660 | `is_bin_pendiente_aplicacion` | BIN 2003 — Pendiente aplicación períodos futuros | money | reuse |
| 00662 | `is_compensacion_bases_negativas` | BIN 2004 — Aplicado en esta liquidación | money | reuse |
| 00663 | `is_bin_pendiente_aplicacion` | BIN 2004 — Pendiente aplicación períodos futuros | money | reuse |
| 00665 | `is_compensacion_bases_negativas` | BIN 2005 — Aplicado en esta liquidación | money | reuse |
| 00666 | `is_bin_pendiente_aplicacion` | BIN 2005 — Pendiente aplicación períodos futuros | money | reuse |
| 00668 | `is_compensacion_bases_negativas` | BIN 2006 — Aplicado en esta liquidación | money | reuse |
| 00669 | `is_bin_pendiente_aplicacion` | BIN 2006 — Pendiente aplicación períodos futuros | money | reuse |
| 00671 | `is_bin_total_pendiente` | BIN TOTAL — Pendiente de aplicación en períodos futuros | money | reuse; total row, no aplicado companion |
| 00748 | `is_bin_pendiente_aplicacion` | BIN 2007 — Pendiente aplicación períodos futuros | money | reuse; 2007 has no aplicado row in this cluster |
| 00897 | `is_compensacion_bases_negativas` | BIN 2022 — Aplicado en esta liquidación | money | reuse |
| 00898 | `is_bin_pendiente_aplicacion` | BIN 2022 — Pendiente aplicación períodos futuros | money | reuse |
| 01046 | `is_compensacion_bases_negativas` | BIN 2015 — Aplicado en esta liquidación | money | reuse |
| 01047 | `is_bin_pendiente_aplicacion` | BIN 2015 — Pendiente aplicación períodos futuros | money | reuse |
| 01049 | `is_bin_pendiente_aplicacion` | BIN 2025 — Pendiente aplicación períodos futuros | money | reuse; 2025 pending-only in this cluster |
| 01099 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2021 — Pendiente(s) | money | reuse; per-vintage carry-forward detail |
| 01101 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2022 — Pendiente | money | reuse |
| 01102 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2022 — Pendiente (2nd row) | money | reuse; two pending rows for 2022 |
| 01111 | `is_reserva_nivelacion_adicion` | Niv. reducción BI — gen. 2021 — Importe pendiente adicionar | money | reuse |
| 01113 | `is_reserva_nivelacion_dotacion` | Niv. dotación — gen. 2022 — Importe reserva dotada | money | reuse |
| 01114 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2022 — Importe reserva pendiente dotación | money | new |
| 01115 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2022 — Reserva dispuesta | money | new |
| 01139 | `is_reserva_capitalizacion_pendiente` | Cap. Total — Reducción B.I. pdte. aplicar períodos futuros | money | reuse |
| 01159 | `is_reserva_nivelacion_dotacion` | Niv. dotación — Total — Importe reserva dotada | money | reuse |
| 01160 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — Total — Importe reserva pendiente dotación | money | new |
| 01161 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — Total — Reserva dispuesta | money | new |
| 01189 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2012 — Aplicado en esta liquidación | money | reuse; confirmed in TOML neighbour 01188 |
| 01194 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2013 — Aplicado en esta liquidación | money | reuse |
| 01196 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2013 — Pendiente | money | reuse |
| 01199 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2014 — Aplicado en esta liquidación | money | reuse |
| 01203 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2015 — Pendiente (1st) | money | reuse |
| 01204 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2015 — Aplicado en esta liquidación | money | reuse |
| 01205 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2015 — Pendiente (2nd) | money | reuse |
| 01206 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2015 — Pendiente (3rd) | money | reuse |
| 01210 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2016 — Pendiente (1st) | money | reuse |
| 01211 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2016 — Pendiente (2nd) | money | reuse |
| 01213 | `is_gastos_financieros_limitacion_importe` | GF pendientes — Total — Pendiente aplicación a principio | money | reuse; total aggregate |
| 01214 | `is_gastos_financieros_limitacion_importe` | GF pendientes — Total — Aplicado en esta liquidación | money | reuse |
| 01215 | `is_gastos_financieros_limitacion_importe` | GF pendientes — Total — Pendiente aplicación períodos futuros (1st) | money | reuse |
| 01216 | `is_gastos_financieros_limitacion_importe` | GF pendientes — Total — Pendiente aplicación períodos futuros (2nd) | money | reuse |
| 01241 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.5/83 — b) límite adicional | money | reuse; límite computation line |
| 01242 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.5/83 — c1) GF deducibles tras límite | money | reuse |
| 01243 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.5/83 — c2) GF no deducibles | money | reuse |
| 01244 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.5/83 — d) GF ptes. períodos ant. | money | reuse |
| 01246 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — f) GF del período | money | reuse |
| 01247 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — g) Ingresos financieros | money | reuse |
| 01248 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — h) GF netos | money | reuse |
| 01249 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i) Límite deducción | money | reuse |
| 01250 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i1) Resultado explotación | money | reuse; EBITDA component |
| 01251 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i2) Amortización inmovilizado | money | reuse; EBITDA component |
| 01252 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i3) Imputación subvenciones | money | reuse; EBITDA component |
| 01253 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i4) Deterioro y enajenaciones | money | reuse; EBITDA component |
| 01254 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — i5) Ingresos financieros particip. | money | reuse; EBITDA component |
| 01255 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — j) Adición límite beneficio op. | money | reuse |
| 01256 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — l1) GF netos del período (≤30%) | money | reuse |
| 01257 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — l2) GF netos del período (resto) | money | reuse |
| 01258 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — m) GF ptes. deducir | money | reuse |
| 01259 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — n) GF ptes. deducir (períodos) | money | reuse |
| 01260 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — Total GF del período | money | reuse |
| 01394 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2022 — Pendiente (3rd row) | money | reuse |
| 01396 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2023 — Pendiente (1st) | money | reuse |
| 01397 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2023 — Pendiente (2nd) | money | reuse |
| 01402 | `is_reserva_capitalizacion_importe` | Cap. 2023 — Reducción B.I. aplicada | money | new role; applied-reduction distinct from pendiente |
| 01405 | `is_reserva_nivelacion_incumplimiento` | Niv. reducción BI — gen. 2022 — Importe integrado por incumplimiento | money | reuse |
| 01406 | `is_reserva_nivelacion_minoracion` | Niv. reducción BI — gen. 2022 — Importe minoración BI periodo/pendiente | money | new |
| 01407 | `is_reserva_nivelacion_adicion` | Niv. reducción BI — gen. 2022 — Importe pendiente adicionar | money | reuse |
| 01411 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2023 — Importe reserva pendiente dotación | money | new |
| 01412 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2023 — Reserva dispuesta | money | new |
| 01463 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2016 — Pendiente (3rd) | money | reuse |
| 01465 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2017 — Pendiente (1st) | money | reuse |
| 01466 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2017 — Pendiente (2nd) | money | reuse |
| 01520 | `is_compensacion_bases_negativas` | BIN 2016 — Aplicado en esta liquidación | money | reuse |
| 01521 | `is_bin_pendiente_aplicacion` | BIN 2016 — Pendiente aplicación períodos futuros | money | reuse |
| 01593 | `is_compensacion_bases_negativas` | BIN 2017 — Aplicado en esta liquidación | money | reuse |
| 01594 | `is_bin_pendiente_aplicacion` | BIN 2017 — Pendiente aplicación períodos futuros | money | reuse |
| 01605 | `is_reserva_nivelacion_incumplimiento` | Niv. reducción BI — gen. 2021 — Importe integrado por incumplimiento | money | reuse |
| 01606 | `is_reserva_nivelacion_incumplimiento` | Niv. reducción BI — Total — Importe integrado por incumplimiento | money | reuse; total row |
| 01731 | `is_reserva_nivelacion_adicion` | Niv. reducción BI — gen. 2025 — Importe pendiente adicionar | money | reuse |
| 01737 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2017 — Pendiente (3rd) | money | reuse |
| 01739 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2018 — Pendiente (1st) | money | reuse |
| 01740 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2018 — Pendiente (2nd) | money | reuse |
| 01826 | `is_compensacion_bases_negativas` | BIN 2018 — Aplicado en esta liquidación | money | reuse |
| 01827 | `is_bin_pendiente_aplicacion` | BIN 2018 — Pendiente aplicación períodos futuros | money | reuse |
| 01978 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2018 — Pendiente (3rd) | money | reuse |
| 01980 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2019 — Pendiente (1st) | money | reuse |
| 01981 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2019 — Pendiente (2nd) | money | reuse |
| 02194 | `is_compensacion_bases_negativas` | BIN 2019 — Aplicado en esta liquidación | money | reuse |
| 02195 | `is_bin_pendiente_aplicacion` | BIN 2019 — Pendiente aplicación períodos futuros | money | reuse |
| 02242 | `is_reserva_nivelacion_dotacion` | Niv. dotación — gen. 2020 — Importe reserva dotada | money | reuse |
| 02243 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2020 — Importe reserva pendiente dotación | money | new |
| 02244 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2020 — Reserva dispuesta | money | new |
| 02254 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2019 — Pendiente (3rd) | money | reuse |
| 02256 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2020 — Pendiente (1st) | money | reuse |
| 02257 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2020 — Pendiente (2nd) | money | reuse |
| 02317 | `is_compensacion_bases_negativas` | BIN 2025(*) — Aplicado en esta liquidación | money | reuse |
| 02318 | `is_bin_pendiente_aplicacion` | BIN 2025(*) — Pendiente aplicación períodos futuros | money | reuse |
| 02369 | `is_gastos_financieros_limitacion_importe` | Lim. GF art.16.1/16.2 — k) Límite total deducción | money | reuse |
| 02400 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2020 — Pendiente (3rd) | money | reuse |
| 02402 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2021 — Pendiente (1st) | money | reuse |
| 02403 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2021 — Pendiente (2nd) | money | reuse |
| 02411 | `is_reserva_nivelacion_adicion_realizada` | Niv. reducción BI — gen. 2020 — Importe adicionado BI en periodos | money | new |
| 02414 | `is_reserva_nivelacion_dotacion` | Niv. dotación — gen. 2021 — Importe reserva dotada | money | reuse |
| 02415 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2021 — Importe reserva pendiente dotación | money | new |
| 02416 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2021 — Reserva dispuesta | money | new |
| 02442 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2025(*) — Pendiente (1st) | money | reuse |
| 02765 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2023 — Pendiente (3rd) | money | reuse |
| 02767 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2024 — Pendiente (1st) | money | reuse |
| 02768 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2024 — Pendiente (2nd) | money | reuse |
| 02774 | `is_reserva_capitalizacion_importe` | Cap. 2024(*) — Reducción B.I. aplicada | money | new role |
| 02775 | `is_reserva_capitalizacion_pendiente` | Cap. 2024(*) — Reducción B.I. pdte. aplicar períodos futuros | money | reuse |
| 02777 | `is_reserva_nivelacion_adicion_realizada` | Niv. reducción BI — gen. 2023 — Importe adicionado BI en periodos | money | new |
| 02778 | `is_reserva_nivelacion_incumplimiento` | Niv. reducción BI — gen. 2023 — Importe integrado por incumplimiento | money | reuse |
| 02779 | `is_reserva_nivelacion_adicion` | Niv. reducción BI — gen. 2023 — Importe pendiente adicionar | money | reuse |
| 02783 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2024 — Importe reserva pendiente dotación | money | new |
| 02784 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2024 — Reserva dispuesta | money | new |
| 02982 | `is_correccion_aumento` | Exen. transmisión residentes — Aumento — Temporarias (ejercicio) | money | reuse; confirmed in neighbour 02981 |
| 02983 | `is_correccion_aumento` | Exen. transmisión residentes — Aumento — Temporarias (anteriores) | money | reuse |
| 02984 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión residentes — Aumento — Saldo pendiente principio | money | new |
| 02985 | `is_exencion_transmision_saldo_fin` | Exen. transmisión residentes — Aumento — Saldo pendiente fin | money | new |
| 02987 | `is_correccion_disminucion` | Exen. transmisión residentes — Disminución — Temporarias (ejercicio) | money | reuse |
| 02988 | `is_correccion_disminucion` | Exen. transmisión residentes — Disminución — Temporarias (anteriores) | money | reuse |
| 02989 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión residentes — Disminución — Saldo pendiente principio | money | new |
| 02990 | `is_exencion_transmision_saldo_fin` | Exen. transmisión residentes — Disminución — Saldo pendiente fin | money | new |
| 02992 | `is_correccion_aumento` | Exen. transmisión no residentes — Aumento — Temporarias (ejercicio) | money | reuse |
| 02993 | `is_correccion_aumento` | Exen. transmisión no residentes — Aumento — Temporarias (anteriores) | money | reuse |
| 02994 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión no residentes — Aumento — Saldo pendiente principio | money | new |
| 02995 | `is_exencion_transmision_saldo_fin` | Exen. transmisión no residentes — Aumento — Saldo pendiente fin | money | new |
| 02997 | `is_correccion_disminucion` | Exen. transmisión no residentes — Disminución — Temporarias (ejercicio) | money | reuse |
| 02998 | `is_correccion_disminucion` | Exen. transmisión no residentes — Disminución — Temporarias (anteriores) | money | reuse |
| 02999 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión no residentes — Disminución — Saldo pendiente principio | money | new |
| 03000 | `is_exencion_transmision_saldo_fin` | Exen. transmisión no residentes — Disminución — Saldo pendiente fin | money | new |
| 03002 | `is_correccion_aumento` | Exen. otros supuestos art.21 — Aumento — Temporarias (ejercicio) | money | reuse |
| 03003 | `is_correccion_aumento` | Exen. otros supuestos art.21 — Aumento — Temporarias (anteriores) | money | reuse |
| 03004 | `is_exencion_transmision_saldo_inicio` | Exen. otros supuestos art.21 — Aumento — Saldo pendiente principio | money | new |
| 03005 | `is_exencion_transmision_saldo_fin` | Exen. otros supuestos art.21 — Aumento — Saldo pendiente fin | money | new |
| 03007 | `is_correccion_disminucion` | Exen. otros supuestos art.21 — Disminución — Temporarias (ejercicio) | money | reuse |
| 03008 | `is_correccion_disminucion` | Exen. otros supuestos art.21 — Disminución — Temporarias (anteriores) | money | reuse |
| 03009 | `is_exencion_transmision_saldo_inicio` | Exen. otros supuestos art.21 — Disminución — Saldo pendiente principio | money | new |
| 03010 | `is_exencion_transmision_saldo_fin` | Exen. otros supuestos art.21 — Disminución — Saldo pendiente fin | money | new |
| 03012 | `is_correccion_aumento` | Exen. otros supuestos (art.21 + DT40ª) — Aumento — Temporarias (ejercicio) | money | reuse |
| 03013 | `is_correccion_aumento` | Exen. otros supuestos (art.21 + DT40ª) — Aumento — Temporarias (anteriores) | money | reuse |
| 03014 | `is_exencion_transmision_saldo_inicio` | Exen. otros supuestos (art.21 + DT40ª) — Aumento — Saldo pendiente principio | money | new |
| 03015 | `is_exencion_transmision_saldo_fin` | Exen. otros supuestos (art.21 + DT40ª) — Aumento — Saldo pendiente fin | money | new |
| 03017 | `is_correccion_disminucion` | Exen. otros supuestos (art.21 + DT40ª) — Disminución — Temporarias (ejercicio) | money | reuse |
| 03018 | `is_correccion_disminucion` | Exen. otros supuestos (art.21 + DT40ª) — Disminución — Temporarias (anteriores) | money | reuse |
| 03019 | `is_exencion_transmision_saldo_inicio` | Exen. otros supuestos (art.21 + DT40ª) — Disminución — Saldo pendiente principio | money | new |
| 03020 | `is_exencion_transmision_saldo_fin` | Exen. otros supuestos (art.21 + DT40ª) — Disminución — Saldo pendiente fin | money | new |
| 03022 | `is_correccion_aumento` | Exen. rentas extranjero art.22 — Aumento — Temporarias (ejercicio) | money | reuse; confirmed in TOML neighbour 03021 |
| 03023 | `is_correccion_aumento` | Exen. rentas extranjero art.22 — Aumento — Temporarias (anteriores) | money | reuse |
| 03024 | `is_exencion_transmision_saldo_inicio` | Exen. rentas extranjero art.22 — Aumento — Saldo pendiente principio | money | new |
| 03025 | `is_exencion_transmision_saldo_fin` | Exen. rentas extranjero art.22 — Aumento — Saldo pendiente fin | money | new |
| 03027 | `is_correccion_disminucion` | Exen. rentas extranjero art.22 — Disminución — Temporarias (ejercicio) | money | reuse |
| 03028 | `is_correccion_disminucion` | Exen. rentas extranjero art.22 — Disminución — Temporarias (anteriores) | money | reuse |
| 03029 | `is_exencion_transmision_saldo_inicio` | Exen. rentas extranjero art.22 — Disminución — Saldo pendiente principio | money | new |
| 03030 | `is_exencion_transmision_saldo_fin` | Exen. rentas extranjero art.22 — Disminución — Saldo pendiente fin | money | new |
| 03302 | `is_correccion_aumento` | Exen. transmisión bienes inmuebles DA6ª — Aumento — Temporarias (ejercicio) | money | reuse; confirmed in TOML neighbour 03301 |
| 03303 | `is_correccion_aumento` | Exen. transmisión bienes inmuebles DA6ª — Aumento — Temporarias (anteriores) | money | reuse |
| 03304 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión bienes inmuebles DA6ª — Aumento — Saldo pendiente principio | money | new |
| 03305 | `is_exencion_transmision_saldo_fin` | Exen. transmisión bienes inmuebles DA6ª — Aumento — Saldo pendiente fin | money | new |
| 03307 | `is_correccion_disminucion` | Exen. transmisión bienes inmuebles DA6ª — Disminución — Temporarias (ejercicio) | money | reuse |
| 03308 | `is_correccion_disminucion` | Exen. transmisión bienes inmuebles DA6ª — Disminución — Temporarias (anteriores) | money | reuse |
| 03309 | `is_exencion_transmision_saldo_inicio` | Exen. transmisión bienes inmuebles DA6ª — Disminución — Saldo pendiente principio | money | new |
| 03310 | `is_exencion_transmision_saldo_fin` | Exen. transmisión bienes inmuebles DA6ª — Disminución — Saldo pendiente fin | money | new |
| 03403 | `is_compensacion_bases_negativas` | BIN 2024 — Aplicado en esta liquidación | money | reuse |
| 03404 | `is_bin_pendiente_aplicacion` | BIN 2024 — Pendiente aplicación períodos futuros | money | reuse |
| 03584 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2025(*) — Pendiente (2nd) | money | reuse |
| 03585 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2025(**) — Aplicado en esta liquidación | money | reuse |
| 03586 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2025(**) — Pendiente (1st) | money | reuse |
| 03587 | `is_gastos_financieros_limitacion_importe` | GF pendientes — gen. 2025(**) — Pendiente (2nd) | money | reuse |
| 03592 | `is_reserva_capitalizacion_importe` | Cap. 2025 — Reducción B.I. aplicada | money | new role |
| 03593 | `is_reserva_capitalizacion_pendiente` | Cap. 2025 — Reducción B.I. pdte. aplicar períodos futuros | money | reuse |
| 03596 | `is_reserva_nivelacion_adicion_realizada` | Niv. reducción BI — gen. 2025(*) — Importe adicionado BI en periodos | money | new |
| 03597 | `is_reserva_nivelacion_incumplimiento` | Niv. reducción BI — gen. 2025(*) — Importe integrado por incumplimiento | money | reuse |
| 03598 | `is_reserva_nivelacion_adicion` | Niv. reducción BI — gen. 2025(*) — Importe pendiente adicionar | money | reuse |
| 03600 | `is_reserva_nivelacion_dotacion` | Niv. dotación — gen. 2025 — Importe reserva dotada | money | reuse |
| 03601 | `is_reserva_nivelacion_dotacion_pendiente` | Niv. dotación — gen. 2025 — Importe reserva pendiente dotación | money | new |
| 03602 | `is_reserva_nivelacion_dotacion_dispuesta` | Niv. dotación — gen. 2025 — Reserva dispuesta | money | new |

## Data_type divergences

None. All 120 casillas in this cluster carry `data_type = "money"`. No divergences detected within any role group.

---

**Summary:** 120 ids classified. 113 reused roles, 7 new roles introduced. 0 data_type divergences.

New roles: `is_reserva_capitalizacion_importe`, `is_reserva_nivelacion_dotacion_pendiente`, `is_reserva_nivelacion_dotacion_dispuesta`, `is_reserva_nivelacion_adicion_realizada`, `is_reserva_nivelacion_minoracion`, `is_exencion_transmision_saldo_inicio`, `is_exencion_transmision_saldo_fin`.
