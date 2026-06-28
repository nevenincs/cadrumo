---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m200-role-assignment-audit]]"
---

# schema-hardening M200 regimenes-especiales role assignment

## Scope

Classification of all 130 casillas in the M200 **regimenes-especiales** cluster for the 2024-y-siguientes revision.  The cluster is a heterogeneous collection of per-regime correction/balance rows, each following the same structural pattern:

- **Correcciones del ejercicio – Temporarias** (two sub-types: current-year origin and prior-year origin)
- **Saldo pendiente a principio de ejercicio** (opening balance)
- **Saldo pendiente a fin de ejercicio** (closing balance)

plus regime-specific blocks for cooperative base imponible, naviera BIN compensation, RIC/RIIB materialisation, and flag identifiers.

Regimes covered (LIS chapter references where applicable):

| Regime key | LIS reference |
|---|---|
| Reserva para inversiones Illes Balears (RIIB) | DA 70ª Ley 31/2022 |
| Régimen especial buques/navieras Canarias (BIN) | Cap. XVI |
| Cooperativas – compensación cuotas | Ley 20/1990 |
| Cooperativas – base imponible | Ley 20/1990 |
| Reserva inversiones Canarias (RIC) | Ley 19/1994 |
| Entidad atribución rentas – asimetrías híbridas | art. 15 bis.12 LIS |
| Obra benéfico-social cajas ahorro/fundaciones bancarias | art. 24 LIS |
| Agrupación de interés económico (AIE) | Cap. II Tít. VII |
| Unión temporal de empresas – ajustes art. 45.1 | art. 45.1 LIS |
| Unión temporal de empresas – rentas exentas extranjero | art. 45.2 LIS |
| Unión temporal de empresas – rentas exentas fórmulas colaboración | art. 45.2 LIS (análogas) |
| Unión temporal de empresas – criterios imputación temporal | art. 46.2 LIS |
| Capital-riesgo / SDIR | Cap. IV Tít. VII |
| Minería e hidrocarburos – factor agotamiento | arts. 91 y 95 LIS |
| Hidrocarburos – amortización intangibles/investigación | art. 99 LIS |
| Transparencia fiscal internacional (TFI) | art. 100 LIS |
| Empresas de reducida dimensión – libertad amortización | art. 102 LIS |
| Empresas de reducida dimensión – amortización acelerada | art. 103 LIS |
| Empresas de reducida dimensión – pérdidas deterioro créditos | art. 104 LIS |
| Arrendamiento financiero – régimen especial | art. 106 LIS |
| Entidades de tenencia de valores extranjeros (ETV) | Cap. XIII Tít. VII |
| Entidades parcialmente exentas | Cap. XIV Tít. VII |
| Entidades navieras – tonelaje | Cap. XVI Tít. VII |
| Entidades sin fines lucrativos | Ley 49/2002 |
| Reserva para inversiones Canarias (correcc.) | Ley 19/1994 |
| Entidades atribución rentas extranjero | art. 38 TRLIRNR |
| RIC materialisation rows (RIC 2022–2025) | Ley 19/1994 |
| RIIB materialisation rows (RIIB 2023–2025) | DA 70ª Ley 31/2022 |

All casillas in this cluster have `data_type = money`; there are no data_type divergences.

## Role assignments

| id | role | label_snippet | data_type | notes |
|---|---|---|---|---|
| 00095 | `is_reserva_inversiones_illes_balears_importe` | RIIB DA 70ª – Aumento – Correcciones – Permanentes | money | Reused; correction-type sub-variant within RIIB aumento block |
| 00098 | `is_naviera_base_imponible_negativa` | Navieras Canarias – compensación BIN – resto actividades | money | Reused; resto-actividades BIN compensation row |
| 00695 | `is_cooperativa_compensacion_cuotas` | Cooperativas – compensación cuotas – Total pendiente aplicación futura | money | Reused |
| 00988 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN especial año 2023 – pendiente | money | Reused; year-2023 pendiente row |
| 00989 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN especial año 2023 – aplicado | money | Reused; year-2023 aplicado row |
| 01226 | `is_cooperativa_compensacion_cuotas` | Cooperativas – compensación cuotas 2024 – pendiente aplicación | money | Reused; year-specific pendiente row |
| 01746 | `is_reserva_inversiones_canarias_importe` | RIC 2022 – Aplicado/materializado – Inversiones previstas | money | Reused; RIC materialisation row for year 2022 |
| 01842 | `is_atribucion_rentas_hibridos_aumento` | Atribución rentas – asimetrías híbridas – Aumento – Correc. temporaria origen ejercicio | money | New; art. 15 bis.12 LIS hybrid-asymmetry increase correction current-year |
| 01843 | `is_atribucion_rentas_hibridos_aumento` | Atribución rentas – asimetrías híbridas – Aumento – Correc. temporaria origen previo | money | New; same role – prior-year origin sub-type |
| 01844 | `is_atribucion_rentas_hibridos_aumento` | Atribución rentas – asimetrías híbridas – Aumento – Saldo pendiente inicio | money | New; opening-balance row shares role with correction rows per regime-block convention |
| 01845 | `is_atribucion_rentas_hibridos_aumento` | Atribución rentas – asimetrías híbridas – Aumento – Saldo pendiente fin | money | New; closing-balance row |
| 01857 | `is_atribucion_rentas_hibridos_disminucion` | Atribución rentas – asimetrías híbridas – Disminución – Correc. temporaria origen ejercicio | money | New; decrease direction |
| 01858 | `is_atribucion_rentas_hibridos_disminucion` | Atribución rentas – asimetrías híbridas – Disminución – Correc. temporaria origen previo | money | New |
| 01859 | `is_atribucion_rentas_hibridos_disminucion` | Atribución rentas – asimetrías híbridas – Disminución – Saldo pendiente fin | money | New; closing balance decrease side |
| 02809 | `is_reserva_inversiones_canarias_importe` | RIC 2023 – Aplicado/materializado – Inversiones previstas | money | Reused; RIC materialisation year 2023 |
| 02828 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Ingresos computables – Resultados extracooperativos | money | Reused |
| 02829 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Gastos específicos – Resultados cooperativos | money | Reused |
| 02830 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Gastos específicos – Resultados extracooperativos | money | Reused |
| 02833 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Gastos generales imputados – Extracooperativos | money | Reused |
| 02834 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Fondo Educación y Promoción – Cooperativos | money | Reused |
| 02835 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Fondo Educación y Promoción – Extracooperativos | money | Reused |
| 02836 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Incrementos/disminuciones patrimoniales – Extracooperativos | money | Reused |
| 02837 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Resultado – Cooperativos | money | Reused |
| 02838 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Resultado – Extracooperativos | money | Reused |
| 02839 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Aumentos – Cooperativos | money | Reused |
| 02840 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Aumentos – Extracooperativos | money | Reused |
| 02841 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Disminuciones – Cooperativos | money | Reused |
| 02842 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Disminuciones – Extracooperativos | money | Reused |
| 02843 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – 50% Dotación obligatoria – Cooperativos | money | Reused |
| 02846 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Reserva inversiones Canarias – Cooperativos | money | Reused |
| 02847 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Reserva inversiones Canarias – Extracooperativos | money | Reused |
| 02848 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Factor de agotamiento – Cooperativos | money | Reused |
| 02849 | `is_cooperativa_base_imponible` | Cooperativas – base imponible – Factor de agotamiento – Extracooperativos | money | Reused |
| 02915 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2023 – Aplicado/materializado – Inversiones previstas | money | Reused; RIIB materialisation year 2023 |
| 02917 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2023 – Pendiente de materializar RIIB al final de período | money | Reused |
| 03042 | `is_obra_benefico_social_aumento` | Obra benéfico-social cajas ahorro – Aumento – Correc. ejercicio temporaria origen ejercicio | money | New; art. 24 LIS increase correction current-year |
| 03043 | `is_obra_benefico_social_aumento` | Obra benéfico-social cajas ahorro – Aumento – Correc. ejercicio temporaria origen previo | money | New |
| 03044 | `is_obra_benefico_social_aumento` | Obra benéfico-social cajas ahorro – Aumento – Saldo pendiente a principio | money | New |
| 03045 | `is_obra_benefico_social_aumento` | Obra benéfico-social cajas ahorro – Aumento – Saldo pendiente a fin | money | New |
| 03047 | `is_obra_benefico_social_disminucion` | Obra benéfico-social cajas ahorro – Disminución – Correc. ejercicio temporaria origen ejercicio | money | New |
| 03048 | `is_obra_benefico_social_disminucion` | Obra benéfico-social cajas ahorro – Disminución – Correc. ejercicio temporaria origen previo | money | New |
| 03049 | `is_obra_benefico_social_disminucion` | Obra benéfico-social cajas ahorro – Disminución – Saldo pendiente a principio | money | New |
| 03050 | `is_obra_benefico_social_disminucion` | Obra benéfico-social cajas ahorro – Disminución – Saldo pendiente a fin | money | New |
| 03072 | `is_aie_ajuste_aumento` | AIE Cap. II – Aumento – Correc. temporaria origen ejercicio | money | New; agrupación de interés económico increase correction |
| 03073 | `is_aie_ajuste_aumento` | AIE Cap. II – Aumento – Correc. temporaria origen previo | money | New |
| 03074 | `is_aie_ajuste_aumento` | AIE Cap. II – Aumento – Saldo pendiente a principio | money | New |
| 03075 | `is_aie_ajuste_aumento` | AIE Cap. II – Aumento – Saldo pendiente a fin | money | New |
| 03077 | `is_aie_ajuste_disminucion` | AIE Cap. II – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03078 | `is_aie_ajuste_disminucion` | AIE Cap. II – Disminución – Correc. temporaria origen previo | money | New |
| 03079 | `is_aie_ajuste_disminucion` | AIE Cap. II – Disminución – Saldo pendiente a principio | money | New |
| 03080 | `is_aie_ajuste_disminucion` | AIE Cap. II – Disminución – Saldo pendiente a fin | money | New |
| 03082 | `is_ute_ajuste_art451_aumento` | UTE art. 45.1 – Aumento – Correc. temporaria origen ejercicio | money | New; unión temporal de empresas art. 45.1 increase |
| 03083 | `is_ute_ajuste_art451_aumento` | UTE art. 45.1 – Aumento – Correc. temporaria origen previo | money | New |
| 03084 | `is_ute_ajuste_art451_aumento` | UTE art. 45.1 – Aumento – Saldo pendiente a principio | money | New |
| 03085 | `is_ute_ajuste_art451_aumento` | UTE art. 45.1 – Aumento – Saldo pendiente a fin | money | New |
| 03087 | `is_ute_ajuste_art451_disminucion` | UTE art. 45.1 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03088 | `is_ute_ajuste_art451_disminucion` | UTE art. 45.1 – Disminución – Correc. temporaria origen previo | money | New |
| 03089 | `is_ute_ajuste_art451_disminucion` | UTE art. 45.1 – Disminución – Saldo pendiente a principio | money | New |
| 03090 | `is_ute_ajuste_art451_disminucion` | UTE art. 45.1 – Disminución – Saldo pendiente a fin | money | New |
| 03092 | `is_ute_renta_exenta_extranjero_aumento` | UTE art. 45.2 rentas exentas extranjero – Aumento – Correc. temporaria origen ejercicio | money | New; UTE foreign exempt income increase |
| 03093 | `is_ute_renta_exenta_extranjero_aumento` | UTE art. 45.2 rentas exentas extranjero – Aumento – Correc. temporaria origen previo | money | New |
| 03094 | `is_ute_renta_exenta_extranjero_aumento` | UTE art. 45.2 rentas exentas extranjero – Aumento – Saldo pendiente a principio | money | New |
| 03095 | `is_ute_renta_exenta_extranjero_aumento` | UTE art. 45.2 rentas exentas extranjero – Aumento – Saldo pendiente a fin | money | New |
| 03097 | `is_ute_renta_exenta_extranjero_disminucion` | UTE art. 45.2 rentas exentas extranjero – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03098 | `is_ute_renta_exenta_extranjero_disminucion` | UTE art. 45.2 rentas exentas extranjero – Disminución – Correc. temporaria origen previo | money | New |
| 03099 | `is_ute_renta_exenta_extranjero_disminucion` | UTE art. 45.2 rentas exentas extranjero – Disminución – Saldo pendiente a principio | money | New |
| 03100 | `is_ute_renta_exenta_extranjero_disminucion` | UTE art. 45.2 rentas exentas extranjero – Disminución – Saldo pendiente a fin | money | New |
| 03102 | `is_ute_renta_exenta_colaboracion_aumento` | UTE rentas exentas fórmulas colaboración análogas extranjero – Aumento – Correc. temporaria origen ejercicio | money | New; analogous-collaboration exempt income increase |
| 03103 | `is_ute_renta_exenta_colaboracion_aumento` | UTE rentas exentas colaboración análogas – Aumento – Correc. temporaria origen previo | money | New |
| 03104 | `is_ute_renta_exenta_colaboracion_aumento` | UTE rentas exentas colaboración análogas – Aumento – Saldo pendiente a principio | money | New |
| 03105 | `is_ute_renta_exenta_colaboracion_aumento` | UTE rentas exentas colaboración análogas – Aumento – Saldo pendiente a fin | money | New |
| 03107 | `is_ute_renta_exenta_colaboracion_disminucion` | UTE rentas exentas colaboración análogas – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03108 | `is_ute_renta_exenta_colaboracion_disminucion` | UTE rentas exentas colaboración análogas – Disminución – Correc. temporaria origen previo | money | New |
| 03109 | `is_ute_renta_exenta_colaboracion_disminucion` | UTE rentas exentas colaboración análogas – Disminución – Saldo pendiente a principio | money | New |
| 03110 | `is_ute_renta_exenta_colaboracion_disminucion` | UTE rentas exentas colaboración análogas – Disminución – Saldo pendiente a fin | money | New |
| 03112 | `is_ute_imputacion_temporal_aumento` | UTE art. 46.2 criterios imputación temporal – Aumento – Correc. temporaria origen ejercicio | money | New; UTE temporal-imputation criteria increase |
| 03113 | `is_ute_imputacion_temporal_aumento` | UTE art. 46.2 imputación temporal – Aumento – Correc. temporaria origen previo | money | New |
| 03114 | `is_ute_imputacion_temporal_aumento` | UTE art. 46.2 imputación temporal – Aumento – Saldo pendiente a principio | money | New |
| 03115 | `is_ute_imputacion_temporal_aumento` | UTE art. 46.2 imputación temporal – Aumento – Saldo pendiente a fin | money | New |
| 03117 | `is_ute_imputacion_temporal_disminucion` | UTE art. 46.2 imputación temporal – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03118 | `is_ute_imputacion_temporal_disminucion` | UTE art. 46.2 imputación temporal – Disminución – Correc. temporaria origen previo | money | New |
| 03119 | `is_ute_imputacion_temporal_disminucion` | UTE art. 46.2 imputación temporal – Disminución – Saldo pendiente a principio | money | New |
| 03120 | `is_ute_imputacion_temporal_disminucion` | UTE art. 46.2 imputación temporal – Disminución – Saldo pendiente a fin | money | New |
| 03132 | `is_capital_riesgo_ajuste_aumento` | Capital-riesgo/SDIR Cap. IV – Aumento – Correc. temporaria origen ejercicio | money | New; sociedades y fondos capital-riesgo + SDIR increase |
| 03133 | `is_capital_riesgo_ajuste_aumento` | Capital-riesgo/SDIR Cap. IV – Aumento – Correc. temporaria origen previo | money | New |
| 03134 | `is_capital_riesgo_ajuste_aumento` | Capital-riesgo/SDIR Cap. IV – Aumento – Saldo pendiente a principio | money | New |
| 03135 | `is_capital_riesgo_ajuste_aumento` | Capital-riesgo/SDIR Cap. IV – Aumento – Saldo pendiente a fin | money | New |
| 03137 | `is_capital_riesgo_ajuste_disminucion` | Capital-riesgo/SDIR Cap. IV – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03138 | `is_capital_riesgo_ajuste_disminucion` | Capital-riesgo/SDIR Cap. IV – Disminución – Correc. temporaria origen previo | money | New |
| 03139 | `is_capital_riesgo_ajuste_disminucion` | Capital-riesgo/SDIR Cap. IV – Disminución – Saldo pendiente a principio | money | New |
| 03140 | `is_capital_riesgo_ajuste_disminucion` | Capital-riesgo/SDIR Cap. IV – Disminución – Saldo pendiente a fin | money | New |
| 03152 | `is_mineria_hidrocarburos_factor_agotamiento_aumento` | Minería/hidrocarburos factor agotamiento arts. 91/95 – Aumento – Correc. temporaria origen ejercicio | money | New |
| 03153 | `is_mineria_hidrocarburos_factor_agotamiento_aumento` | Minería/hidrocarburos factor agotamiento – Aumento – Correc. temporaria origen previo | money | New |
| 03154 | `is_mineria_hidrocarburos_factor_agotamiento_aumento` | Minería/hidrocarburos factor agotamiento – Aumento – Saldo pendiente a principio | money | New |
| 03155 | `is_mineria_hidrocarburos_factor_agotamiento_aumento` | Minería/hidrocarburos factor agotamiento – Aumento – Saldo pendiente a fin | money | New |
| 03157 | `is_mineria_hidrocarburos_factor_agotamiento_disminucion` | Minería/hidrocarburos factor agotamiento – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03158 | `is_mineria_hidrocarburos_factor_agotamiento_disminucion` | Minería/hidrocarburos factor agotamiento – Disminución – Correc. temporaria origen previo | money | New |
| 03159 | `is_mineria_hidrocarburos_factor_agotamiento_disminucion` | Minería/hidrocarburos factor agotamiento – Disminución – Saldo pendiente a principio | money | New |
| 03160 | `is_mineria_hidrocarburos_factor_agotamiento_disminucion` | Minería/hidrocarburos factor agotamiento – Disminución – Saldo pendiente a fin | money | New |
| 03162 | `is_hidrocarburos_amortizacion_intangibles_aumento` | Hidrocarburos amortización inversiones intangibles/invest. art. 99 – Aumento – Correc. temporaria origen ejercicio | money | New; art. 99 LIS hydrocarbon intangible amortisation increase |
| 03163 | `is_hidrocarburos_amortizacion_intangibles_aumento` | Hidrocarburos amortización intangibles – Aumento – Correc. temporaria origen previo | money | New |
| 03164 | `is_hidrocarburos_amortizacion_intangibles_aumento` | Hidrocarburos amortización intangibles – Aumento – Saldo pendiente a principio | money | New |
| 03165 | `is_hidrocarburos_amortizacion_intangibles_aumento` | Hidrocarburos amortización intangibles – Aumento – Saldo pendiente a fin | money | New |
| 03167 | `is_hidrocarburos_amortizacion_intangibles_disminucion` | Hidrocarburos amortización intangibles – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03168 | `is_hidrocarburos_amortizacion_intangibles_disminucion` | Hidrocarburos amortización intangibles – Disminución – Correc. temporaria origen previo | money | New |
| 03169 | `is_hidrocarburos_amortizacion_intangibles_disminucion` | Hidrocarburos amortización intangibles – Disminución – Saldo pendiente a principio | money | New |
| 03170 | `is_hidrocarburos_amortizacion_intangibles_disminucion` | Hidrocarburos amortización intangibles – Disminución – Saldo pendiente a fin | money | New |
| 03172 | `is_tfi_ajuste_aumento` | Transparencia fiscal internacional art. 100 – Aumento – Correc. temporaria origen ejercicio | money | New; TFI increase correction |
| 03173 | `is_tfi_ajuste_aumento` | TFI art. 100 – Aumento – Correc. temporaria origen previo | money | New |
| 03174 | `is_tfi_ajuste_aumento` | TFI art. 100 – Aumento – Saldo pendiente a principio | money | New |
| 03175 | `is_tfi_ajuste_aumento` | TFI art. 100 – Aumento – Saldo pendiente a fin | money | New |
| 03177 | `is_tfi_ajuste_disminucion` | TFI art. 100 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03178 | `is_tfi_ajuste_disminucion` | TFI art. 100 – Disminución – Correc. temporaria origen previo | money | New |
| 03179 | `is_tfi_ajuste_disminucion` | TFI art. 100 – Disminución – Saldo pendiente a principio | money | New |
| 03180 | `is_tfi_ajuste_disminucion` | TFI art. 100 – Disminución – Saldo pendiente a fin | money | New |
| 03182 | `is_erd_libertad_amortizacion_aumento` | ERD libertad amortización art. 102 – Aumento – Correc. temporaria origen ejercicio | money | New; empresa de reducida dimensión free-amortisation increase |
| 03183 | `is_erd_libertad_amortizacion_aumento` | ERD libertad amortización art. 102 – Aumento – Correc. temporaria origen previo | money | New |
| 03184 | `is_erd_libertad_amortizacion_aumento` | ERD libertad amortización art. 102 – Aumento – Saldo pendiente a principio | money | New |
| 03185 | `is_erd_libertad_amortizacion_aumento` | ERD libertad amortización art. 102 – Aumento – Saldo pendiente a fin | money | New |
| 03187 | `is_erd_libertad_amortizacion_disminucion` | ERD libertad amortización art. 102 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03188 | `is_erd_libertad_amortizacion_disminucion` | ERD libertad amortización art. 102 – Disminución – Correc. temporaria origen previo | money | New |
| 03189 | `is_erd_libertad_amortizacion_disminucion` | ERD libertad amortización art. 102 – Disminución – Saldo pendiente a principio | money | New |
| 03190 | `is_erd_libertad_amortizacion_disminucion` | ERD libertad amortización art. 102 – Disminución – Saldo pendiente a fin | money | New |
| 03192 | `is_erd_amortizacion_acelerada_aumento` | ERD amortización acelerada art. 103 – Aumento – Correc. temporaria origen ejercicio | money | New; accelerated amortisation increase |
| 03193 | `is_erd_amortizacion_acelerada_aumento` | ERD amortización acelerada art. 103 – Aumento – Correc. temporaria origen previo | money | New |
| 03194 | `is_erd_amortizacion_acelerada_aumento` | ERD amortización acelerada art. 103 – Aumento – Saldo pendiente a principio | money | New |
| 03195 | `is_erd_amortizacion_acelerada_aumento` | ERD amortización acelerada art. 103 – Aumento – Saldo pendiente a fin | money | New |
| 03197 | `is_erd_amortizacion_acelerada_disminucion` | ERD amortización acelerada art. 103 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03198 | `is_erd_amortizacion_acelerada_disminucion` | ERD amortización acelerada art. 103 – Disminución – Correc. temporaria origen previo | money | New |
| 03199 | `is_erd_amortizacion_acelerada_disminucion` | ERD amortización acelerada art. 103 – Disminución – Saldo pendiente a principio | money | New |
| 03200 | `is_erd_amortizacion_acelerada_disminucion` | ERD amortización acelerada art. 103 – Disminución – Saldo pendiente a fin | money | New |
| 03202 | `is_erd_deterioro_creditos_aumento` | ERD pérdidas deterioro créditos insolvencias art. 104 – Aumento – Correc. temporaria origen ejercicio | money | New |
| 03203 | `is_erd_deterioro_creditos_aumento` | ERD deterioro créditos – Aumento – Correc. temporaria origen previo | money | New |
| 03204 | `is_erd_deterioro_creditos_aumento` | ERD deterioro créditos – Aumento – Saldo pendiente a principio | money | New |
| 03205 | `is_erd_deterioro_creditos_aumento` | ERD deterioro créditos – Aumento – Saldo pendiente a fin | money | New |
| 03207 | `is_erd_deterioro_creditos_disminucion` | ERD deterioro créditos – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03208 | `is_erd_deterioro_creditos_disminucion` | ERD deterioro créditos – Disminución – Correc. temporaria origen previo | money | New |
| 03209 | `is_erd_deterioro_creditos_disminucion` | ERD deterioro créditos – Disminución – Saldo pendiente a principio | money | New |
| 03210 | `is_erd_deterioro_creditos_disminucion` | ERD deterioro créditos – Disminución – Saldo pendiente a fin | money | New |
| 03212 | `is_arrendamiento_financiero_ajuste_aumento` | Arrendamiento financiero régimen especial art. 106 – Aumento – Correc. temporaria origen ejercicio | money | New |
| 03213 | `is_arrendamiento_financiero_ajuste_aumento` | Arrendamiento financiero art. 106 – Aumento – Correc. temporaria origen previo | money | New |
| 03214 | `is_arrendamiento_financiero_ajuste_aumento` | Arrendamiento financiero art. 106 – Aumento – Saldo pendiente a principio | money | New |
| 03215 | `is_arrendamiento_financiero_ajuste_aumento` | Arrendamiento financiero art. 106 – Aumento – Saldo pendiente a fin | money | New |
| 03217 | `is_arrendamiento_financiero_ajuste_disminucion` | Arrendamiento financiero art. 106 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03218 | `is_arrendamiento_financiero_ajuste_disminucion` | Arrendamiento financiero art. 106 – Disminución – Correc. temporaria origen previo | money | New |
| 03219 | `is_arrendamiento_financiero_ajuste_disminucion` | Arrendamiento financiero art. 106 – Disminución – Saldo pendiente a principio | money | New |
| 03220 | `is_arrendamiento_financiero_ajuste_disminucion` | Arrendamiento financiero art. 106 – Disminución – Saldo pendiente a fin | money | New |
| 03222 | `is_etv_ajuste_aumento` | ETV Cap. XIII – Aumento – Correc. temporaria origen ejercicio | money | New; entidades de tenencia de valores extranjeros increase |
| 03223 | `is_etv_ajuste_aumento` | ETV Cap. XIII – Aumento – Correc. temporaria origen previo | money | New |
| 03224 | `is_etv_ajuste_aumento` | ETV Cap. XIII – Aumento – Saldo pendiente a principio | money | New |
| 03225 | `is_etv_ajuste_aumento` | ETV Cap. XIII – Aumento – Saldo pendiente a fin | money | New |
| 03227 | `is_etv_ajuste_disminucion` | ETV Cap. XIII – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03228 | `is_etv_ajuste_disminucion` | ETV Cap. XIII – Disminución – Correc. temporaria origen previo | money | New |
| 03229 | `is_etv_ajuste_disminucion` | ETV Cap. XIII – Disminución – Saldo pendiente a principio | money | New |
| 03230 | `is_etv_ajuste_disminucion` | ETV Cap. XIII – Disminución – Saldo pendiente a fin | money | New |
| 03232 | `is_entidad_parcialmente_exenta_aumento` | Entidades parcialmente exentas Cap. XIV – Aumento – Correc. temporaria origen ejercicio | money | New |
| 03233 | `is_entidad_parcialmente_exenta_aumento` | Entidades parcialmente exentas Cap. XIV – Aumento – Correc. temporaria origen previo | money | New |
| 03234 | `is_entidad_parcialmente_exenta_aumento` | Entidades parcialmente exentas Cap. XIV – Aumento – Saldo pendiente a principio | money | New |
| 03235 | `is_entidad_parcialmente_exenta_aumento` | Entidades parcialmente exentas Cap. XIV – Aumento – Saldo pendiente a fin | money | New |
| 03237 | `is_entidad_parcialmente_exenta_disminucion` | Entidades parcialmente exentas Cap. XIV – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03238 | `is_entidad_parcialmente_exenta_disminucion` | Entidades parcialmente exentas Cap. XIV – Disminución – Correc. temporaria origen previo | money | New |
| 03239 | `is_entidad_parcialmente_exenta_disminucion` | Entidades parcialmente exentas Cap. XIV – Disminución – Saldo pendiente a principio | money | New |
| 03240 | `is_entidad_parcialmente_exenta_disminucion` | Entidades parcialmente exentas Cap. XIV – Disminución – Saldo pendiente a fin | money | New |
| 03252 | `is_naviera_tonelaje_ajuste_aumento` | Navieras tonelaje Cap. XVI – Aumento – Correc. temporaria origen ejercicio | money | New; entidades navieras tonelaje adjustment increase |
| 03253 | `is_naviera_tonelaje_ajuste_aumento` | Navieras tonelaje Cap. XVI – Aumento – Correc. temporaria origen previo | money | New |
| 03254 | `is_naviera_tonelaje_ajuste_aumento` | Navieras tonelaje Cap. XVI – Aumento – Saldo pendiente a principio | money | New |
| 03255 | `is_naviera_tonelaje_ajuste_aumento` | Navieras tonelaje Cap. XVI – Aumento – Saldo pendiente a fin | money | New |
| 03257 | `is_naviera_tonelaje_ajuste_disminucion` | Navieras tonelaje Cap. XVI – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03258 | `is_naviera_tonelaje_ajuste_disminucion` | Navieras tonelaje Cap. XVI – Disminución – Correc. temporaria origen previo | money | New |
| 03259 | `is_naviera_tonelaje_ajuste_disminucion` | Navieras tonelaje Cap. XVI – Disminución – Saldo pendiente a principio | money | New |
| 03260 | `is_naviera_tonelaje_ajuste_disminucion` | Navieras tonelaje Cap. XVI – Disminución – Saldo pendiente a fin | money | New |
| 03272 | `is_entidad_sin_fines_lucrativos_aumento` | Entidades sin fines lucrativos Ley 49/2002 – Aumento – Correc. temporaria origen ejercicio | money | New |
| 03273 | `is_entidad_sin_fines_lucrativos_aumento` | Entidades sin fines lucrativos – Aumento – Correc. temporaria origen previo | money | New |
| 03274 | `is_entidad_sin_fines_lucrativos_aumento` | Entidades sin fines lucrativos – Aumento – Saldo pendiente a principio | money | New |
| 03275 | `is_entidad_sin_fines_lucrativos_aumento` | Entidades sin fines lucrativos – Aumento – Saldo pendiente a fin | money | New |
| 03277 | `is_entidad_sin_fines_lucrativos_disminucion` | Entidades sin fines lucrativos – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03278 | `is_entidad_sin_fines_lucrativos_disminucion` | Entidades sin fines lucrativos – Disminución – Correc. temporaria origen previo | money | New |
| 03279 | `is_entidad_sin_fines_lucrativos_disminucion` | Entidades sin fines lucrativos – Disminución – Saldo pendiente a principio | money | New |
| 03280 | `is_entidad_sin_fines_lucrativos_disminucion` | Entidades sin fines lucrativos – Disminución – Saldo pendiente a fin | money | New |
| 03292 | `is_reserva_inversiones_canarias_ajuste_aumento` | RIC Ley 19/1994 – Aumento – Correc. temporaria origen ejercicio | money | New; RIC correction-block row (distinct from RIC materialisation rows `is_reserva_inversiones_canarias_importe`) |
| 03293 | `is_reserva_inversiones_canarias_ajuste_aumento` | RIC Ley 19/1994 – Aumento – Correc. temporaria origen previo | money | New |
| 03294 | `is_reserva_inversiones_canarias_ajuste_aumento` | RIC Ley 19/1994 – Aumento – Saldo pendiente a principio | money | New |
| 03295 | `is_reserva_inversiones_canarias_ajuste_aumento` | RIC Ley 19/1994 – Aumento – Saldo pendiente a fin | money | New |
| 03297 | `is_reserva_inversiones_canarias_ajuste_disminucion` | RIC Ley 19/1994 – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03298 | `is_reserva_inversiones_canarias_ajuste_disminucion` | RIC Ley 19/1994 – Disminución – Correc. temporaria origen previo | money | New |
| 03299 | `is_reserva_inversiones_canarias_ajuste_disminucion` | RIC Ley 19/1994 – Disminución – Saldo pendiente a principio | money | New |
| 03300 | `is_reserva_inversiones_canarias_ajuste_disminucion` | RIC Ley 19/1994 – Disminución – Saldo pendiente a fin | money | New |
| 03362 | `is_atribucion_rentas_extranjero_aumento` | Atribución rentas entid. extranjeras art. 38 TRLIRNR – Aumento – Correc. temporaria origen ejercicio | money | New; foreign-constituted attribution-of-income entity increase |
| 03363 | `is_atribucion_rentas_extranjero_aumento` | Atribución rentas extranjero – Aumento – Correc. temporaria origen previo | money | New |
| 03364 | `is_atribucion_rentas_extranjero_aumento` | Atribución rentas extranjero – Aumento – Saldo pendiente a principio | money | New |
| 03365 | `is_atribucion_rentas_extranjero_aumento` | Atribución rentas extranjero – Aumento – Saldo pendiente a fin | money | New |
| 03367 | `is_atribucion_rentas_extranjero_disminucion` | Atribución rentas extranjero – Disminución – Correc. temporaria origen ejercicio | money | New |
| 03368 | `is_atribucion_rentas_extranjero_disminucion` | Atribución rentas extranjero – Disminución – Correc. temporaria origen previo | money | New |
| 03369 | `is_atribucion_rentas_extranjero_disminucion` | Atribución rentas extranjero – Disminución – Saldo pendiente a principio | money | New |
| 03370 | `is_atribucion_rentas_extranjero_disminucion` | Atribución rentas extranjero – Disminución – Saldo pendiente a fin | money | New |
| 03406 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN especial año 2025 – aplicado | money | Reused; year-2025 aplicado row |
| 03407 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN especial año 2025 – pendiente | money | Reused; year-2025 pendiente row |
| 03409 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN resto actividades año 2025 – aplicado | money | Reused |
| 03410 | `is_naviera_base_imponible_negativa` | Navieras Canarias – BIN resto actividades año 2025 – pendiente | money | Reused |
| 03624 | `is_reserva_inversiones_canarias_importe` | RIC 2024 – Aplicado/materializado – Inversiones previstas | money | Reused; RIC materialisation year 2024 |
| 03625 | `is_reserva_inversiones_canarias_importe` | RIC 2024 – Aplicado/materializado – Inversiones previstas (letra B/C/D) | money | Reused |
| 03626 | `is_reserva_inversiones_canarias_importe` | RIC 2024 – Integrado en BI por incumplimiento | money | Reused; clawback row assigned same role as materialisation rows |
| 03628 | `is_reserva_inversiones_canarias_importe` | RIC 2025 – Pendiente de materializar al final de período | money | Reused |
| 03631 | `is_reserva_inversiones_canarias_importe` | RIC inversiones anticipadas 2025 – Inversiones previstas letras B bis/C/D | money | Reused |
| 03632 | `is_reserva_inversiones_canarias_importe` | RIC inversiones anticipadas 2025 – Pendiente de dotar RIC al final del período | money | Reused |
| 03637 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2024 – Aplicado/materializado – Inversiones previstas | money | Reused; RIIB materialisation year 2024 |
| 03638 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2024 – Aplicado/materializado – Inversiones previstas (letra C) | money | Reused |
| 03639 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2024 – Integrado en BI por incumplimiento de requisitos | money | Reused; clawback row |
| 03641 | `is_reserva_inversiones_illes_balears_importe` | RIIB 2025 – Pendiente de materializar RIIB al final de período | money | Reused |
| 03644 | `is_reserva_inversiones_illes_balears_importe` | RIIB inversiones anticipadas 2025 – Inversiones previstas letra C DA 70.4 | money | Reused |
| 03645 | `is_reserva_inversiones_illes_balears_importe` | RIIB inversiones anticipadas 2025 – Pendiente de dotar RIIB al final del período | money | Reused |

## Data_type divergences

None. Every casilla in this cluster carries `data_type = money`. No divergences detected.

## Summary

- **Total casillas classified:** 130
- **Roles reused verbatim from existing-roles.txt:** 5 roles, covering 39 casillas
  - `is_cooperativa_base_imponible` (18 casillas — 02828–02849)
  - `is_cooperativa_compensacion_cuotas` (2 casillas — 00695, 01226)
  - `is_naviera_base_imponible_negativa` (8 casillas — 00098, 00988, 00989, 03406, 03407, 03409, 03410; plus existing casilla 00091 in TOMLs)
  - `is_reserva_inversiones_canarias_importe` (8 casillas — 01746, 02809, 03624–03632)
  - `is_reserva_inversiones_illes_balears_importe` (8 casillas — 00095, 02915, 02917, 03637–03645)
- **New roles introduced:** 44 new roles covering 91 casillas
  - 2 roles for atribución rentas híbridos (art. 15 bis.12): `is_atribucion_rentas_hibridos_aumento`, `is_atribucion_rentas_hibridos_disminucion`
  - 2 roles for obra benéfico-social: `is_obra_benefico_social_aumento`, `is_obra_benefico_social_disminucion`
  - 2 roles for AIE: `is_aie_ajuste_aumento`, `is_aie_ajuste_disminucion`
  - 2 roles for UTE art. 45.1: `is_ute_ajuste_art451_aumento`, `is_ute_ajuste_art451_disminucion`
  - 2 roles for UTE art. 45.2 extranjero: `is_ute_renta_exenta_extranjero_aumento`, `is_ute_renta_exenta_extranjero_disminucion`
  - 2 roles for UTE colaboración análoga: `is_ute_renta_exenta_colaboracion_aumento`, `is_ute_renta_exenta_colaboracion_disminucion`
  - 2 roles for UTE art. 46.2: `is_ute_imputacion_temporal_aumento`, `is_ute_imputacion_temporal_disminucion`
  - 2 roles for capital-riesgo/SDIR: `is_capital_riesgo_ajuste_aumento`, `is_capital_riesgo_ajuste_disminucion`
  - 2 roles for minería/hidrocarburos factor agotamiento: `is_mineria_hidrocarburos_factor_agotamiento_aumento`, `is_mineria_hidrocarburos_factor_agotamiento_disminucion`
  - 2 roles for hidrocarburos amortización intangibles: `is_hidrocarburos_amortizacion_intangibles_aumento`, `is_hidrocarburos_amortizacion_intangibles_disminucion`
  - 2 roles for TFI: `is_tfi_ajuste_aumento`, `is_tfi_ajuste_disminucion`
  - 2 roles for ERD libertad amortización: `is_erd_libertad_amortizacion_aumento`, `is_erd_libertad_amortizacion_disminucion`
  - 2 roles for ERD amortización acelerada: `is_erd_amortizacion_acelerada_aumento`, `is_erd_amortizacion_acelerada_disminucion`
  - 2 roles for ERD deterioro créditos: `is_erd_deterioro_creditos_aumento`, `is_erd_deterioro_creditos_disminucion`
  - 2 roles for arrendamiento financiero: `is_arrendamiento_financiero_ajuste_aumento`, `is_arrendamiento_financiero_ajuste_disminucion`
  - 2 roles for ETV: `is_etv_ajuste_aumento`, `is_etv_ajuste_disminucion`
  - 2 roles for entidades parcialmente exentas: `is_entidad_parcialmente_exenta_aumento`, `is_entidad_parcialmente_exenta_disminucion`
  - 2 roles for navieras tonelaje adjustment: `is_naviera_tonelaje_ajuste_aumento`, `is_naviera_tonelaje_ajuste_disminucion`
  - 2 roles for entidades sin fines lucrativos: `is_entidad_sin_fines_lucrativos_aumento`, `is_entidad_sin_fines_lucrativos_disminucion`
  - 2 roles for RIC correction block: `is_reserva_inversiones_canarias_ajuste_aumento`, `is_reserva_inversiones_canarias_ajuste_disminucion`
  - 2 roles for atribución rentas extranjero: `is_atribucion_rentas_extranjero_aumento`, `is_atribucion_rentas_extranjero_disminucion`
- **Data_type divergences:** 0
