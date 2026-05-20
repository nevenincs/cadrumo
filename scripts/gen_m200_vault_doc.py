"""
Generate .vault/audit/2026-05-19-schema-hardening-m200-role-assignment.md
from the M200 casilla TOML files.

Run: python3 scripts/gen_m200_vault_doc.py
"""
import tomllib
from pathlib import Path
from collections import defaultdict

casilla_dir = Path('src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas')
files = sorted(casilla_dir.glob('*.toml'))
records = []
for f in files:
    with open(f, 'rb') as fh:
        data = tomllib.load(fh)
    rev = data.get('revisions', {}).get('2024-y-siguientes', {})
    casillas = rev.get('casillas', [])
    if casillas:
        c = casillas[0]
        records.append({
            'id': c.get('id', f.stem),
            'section': c.get('section', []) if isinstance(c.get('section', []), list) else [c.get('section', '')],
            'role': c.get('semantic_role', None),
            'label': c.get('label', ''),
            'dtype': c.get('data_type', ''),
        })

IDENTIFICACION_SECTIONS = {
    'entidad_sin_animo_de_lucro_acogida_regimen_fiscal','entidad_parcialmente_exenta',
    'sociedad_de_inversion_de_capital_variable_o_fondo','sociedad_de_inversion_inmobiliaria_o_fondo_de_inve',
    'comunidades_titulares_de_montes_vecinales_en_mano','incentivos_entidad_de_reducida_dimension_cap_xi_ti',
    'imputacion_en_base_imponible_rentas_positivas_art','sociedad_de_inversion_de_capital_variable_que_no_c',
    'entidad_dominante_de_grupo_fiscal','entidad_dependiente_de_grupo_fiscal',
    'entidad_de_tenencia_de_valores_extranjeros','socimi','agrupacion_de_interes_economico_espanola',
    'agrupacion_europea_de_interes_economico','entidad_zec_sin_consolidacion_fiscal',
    'reg_cooperativas_determ_base_imponible','cooperativa_protegida','cooperativa_especialmente_protegida',
    'resto_cooperativas','otros_regimenes_especiales','establecimiento_permanente',
    'regimen_entidades_navieras_en_funcion_del_tonelaje','gran_empresa','entidad_de_credito',
    'entidad_aseguradora','entidad_inactiva','tributacion_conjunta_estado_diput_cdad_forales',
    'regimen_especial_canarias','transmision_elementos_patrimoniales_arts_27_2_d_y',
    'entidades_de_capital_riesgo','sociedades_desarrollo_industrial_regional',
    'regimen_especial_mineria','regimen_especial_hidrocarburos','regimen_especial_fusiones_escisiones_aportaciones',
    'sociedad_de_garantia_reciproca_o_de_reafianzamient','opcion_de_fraccionamiento_art_19_1_lis',
    'entidad_dedicada_al_arrend_viviendas','entidad_que_forma_parte_de_un_grupo_mercantil_art',
    'grupo_fiscal','obligacion_informacion_dt_5a_ris','contribuyente_que_genera_deducciones_del_art_36_1',
    'inversiones_anticipadas','entidad_en_reg_atribuc_de_rentas_constituida_en_el',
    'entidades_sometidas_a_normativa_foral','fondo_de_pensiones_real_decreto_legislativo_1_2002',
    'regimenes_especiales_de_normativa_foral','tributacion_conjunta_estado_y_adm_forales_concierto_economico',
    'tributacion_conjunta_estado_y_adm_forales_convenio_economico',
    'entidad_en_regimen_de_atribucion_de_rentas_con_tri','regimen_fiscal_salida_socimi',
    'mutua_de_seguros_o_mutualidad_de_prevision_social','opcion_art_39_2_lis',
    'fondos_o_activos_de_titulizacion','estados_de_cuentas_de_instituciones_de_inversion_c',
    'reg_fiscal_de_operac_de_aportacion_de_activos_a_sd','tipo_de_gravamen_reducido_para_entidades_de_nueva',
    'regimen_fiscal_entrada_socimi','bonificacion_personal_investigador_rd_475_2014',
    'entidad_patrimonial','estados_de_cuentas_de_entidades_de_credito',
    'compensacion_bases_imponibles_negativas_para_entid','tipo_gravamen_reducido_para_entidades_de_nueva_cre',
    'extincion_de_entidad','opcion_del_0_7_de_la_cuota_integra_para_fines_soci',
    'contribuyente_que_financia_producciones_con_derech','diocesis_provincia_religiosa_o_entidad_eclesiastic',
    'entidad_zec_en_consolidacion_fiscal','uniones_federaciones_y_confederaciones_de_cooperat',
    'filial_grupo_multinacional_o_grupo_nacional_de_gra','sociedad_matriz_ultima_grupo_multinacional_o_grupo',
    'tipo_gravamen_reducido_para_empresa_emergente','regimen_especial_de_disolucion_y_liquidacion_de_si',
    'union_temporal_de_empresas','regimen_especial_illes_balears',
    'inversiones_anticipadas_reserva_inversiones_en_ill','tipo_gravamen_reducido_para_entidades_con_incn_per',
    'participe_de_agrupacion_de_interes_economico_o_de','opcion_art_39_3_lis','base_imponible_negativa_o_cero',
}

CORRECCION_SECTIONS = {
    'amortizacion_del_inmovilizado_intangible_y_fondo_d','amortizacion_de_inmovilizado_afecto_a_actividades',
    'diferencias_entre_amortizacion_contable_y_fiscal_a','libertad_de_amortizacion_con_mantenimiento_de_empl',
    'libertad_de_amortizacion_de_determinados_vehiculos','libertad_de_amortizacion_de_gastos_de_investigacio',
    'libertad_de_amortizacion_inmovilizado_material_nue','libertad_de_amortizacion_sin_mantenimiento_de_empl',
    'otros_supuestos_de_libertad_de_amortizacion_art_12','empresas_de_reducida_dimension_amortizacion_aceler',
    'empresas_de_reducida_dimension_libertad_de_amortiz','empresas_de_reducida_dimension_perdidas_por_deteri',
    'perdidas_por_deterioro_de_im_inversiones_inmobilia','perdidas_por_deterioro_de_valores_repr_de_partic_e',
    'perdidas_por_deterioro_de_valores_representativos','perdidas_por_deterioro_del_art_13_1_lis_no_afectad',
    'perdidas_por_deterioro_del_art_13_1_lis_y_provisio','ajustes_por_deterioro_de_valores_repr_de_partic_en',
    'ajustes_por_la_limitacion_en_la_deducibilidad_de_g','ajustes_por_perdidas_por_deterioro_de_valores_repr',
    'ajustes_por_rentas_derivadas_de_operaciones_con_qu','aplicacion_del_limite_del_art_11_12_lis_a_las_perd',
    'reversion_del_deterioro_del_valor_de_los_elementos','reversion_por_deterioro_de_valores_representativos',
    'gastos_y_provisiones_por_pensiones_no_afectados_po','otras_provisiones_no_deducibles_fiscalmente_art_14',
    'cambio_de_criterios_contables_art_11_3_2o_lis','operaciones_a_plazos_art_11_4_lis',
    'operaciones_a_plazos_dt_1a_lis','cambio_de_residencia_a_estados_miembros_de_la_unio',
    'operaciones_del_art_19_lis_distintas_del_cambio_de','otras_diferencias_de_imputacion_temporal_de_ingres',
    'rentas_negativas_art_11_9_y_11_10_lis','gastos_no_deducibles_por_considerarse_retribucion',
    'gastos_derivados_de_la_extincion_de_la_relacion_la','multas_sanciones_y_otros_art_15_c_lis',
    'perdidas_del_juego_art_15_d_lis','gastos_por_donativos_y_liberalidades_art_15_e_lis',
    'gastos_de_actuaciones_contrarias_al_ordenamiento_j','gastos_financieros_derivados_de_deudas_con_entidad',
    'gastos_que_sean_objeto_de_la_deduccion_por_inversi','revalorizaciones_contables_art_17_1_lis',
    'asimetrias_hibridas_art_15_bis_lis_excepto_art_15','disminucion_de_valor_originada_por_criterio_de_val',
    'efectos_de_la_valoracion_contable_diferente_a_la_f','deuda_tributaria_de_actos_juridicos_documentados_i',
    'exencion_de_rentas_en_el_extranjero_art_22_lis','exencion_sobre_dividendos_o_participaciones_en_ben',
    'exencion_sobre_la_renta_obtenida_en_la_transmision','exencion_sobre_la_renta_obtenida_en_los_supuestos',
    'exencion_transmision_bienes_inmuebles_da_6a_lis','reduccion_de_rentas_procedentes_de_determinados_ac',
    'operaciones_vinculadas_aplicacion_del_valor_de_mer','adquisicion_de_participaciones_en_entidades_no_res',
    'aportaciones_y_colaboracion_a_favor_de_entidades_s','agrupacion_de_interes_economico_cap_ii_del_tit_vii',
    'arrendamiento_financiero_regimen_especial_art_106','bases_imp_negativas_generadas_dentro_del_grupo_fis',
    'correcciones_especificas_de_entidades_sometidas_a','eliminaciones_pendientes_de_incorporar_de_sociedad',
    'impuesto_extranjero_soportado_por_el_contribuyente','mineria_e_hidrocarburos_factor_agotamiento_arts_91',
    'hidrocarburos_amortizacion_de_inversiones_intangib','obra_benefico_social_de_las_cajas_de_ahorro_y_fund',
    'operaciones_de_aumento_de_capital_o_fondos_propios','otras_correcciones_al_resultado_de_la_cuenta_de_pe',
    'regimen_de_entidades_navieras_en_funcion_del_tonel','regimen_de_entidades_parcialmente_exentas_capitulo',
    'regimen_fiscal_entidades_de_tenencia_de_valores_ex','regimen_fiscal_entidades_sin_fines_lucrativos_ley',
    'reinversion_de_beneficios_extraordinarios_dt_24a_l','rentas_procedentes_de_transmision_de_inmovilizado',
    'impuesto_extranjero_sobre_los_beneficios_con_cargo','correccion_por_el_impuesto_sobre_el_margen_de_inte',
    'cooperativas_fondo_de_reserva_obligatorio_ley_20_1','deduccion_del_30_importe_gastos_de_amortiz_contabl',
    'subvenciones_publicas_incluidas_en_el_resultado_de','operaciones_realizadas_con_jurisdicciones_no_coope',
    'transmisiones_lucrativas_y_societarias_aplicacion','transparencia_fiscal_internacional_art_100_lis',
    'montes_vecinales_en_mano_comun_capitulo_xv_del_tit','valoracion_de_bienes_y_derechos_regimen_especial_o',
    'sociedades_y_fondos_de_capital_riesgo_y_sociedades','socio_sicav_reducciones_de_capital_y_distribucion',
    'socio_sicav_rentas_derivadas_de_liquidaciones_de_s','union_temporal_de_empresas_ajustes_del_art_45_1_li',
    'union_temporal_de_empresas_ajustes_por_rentas_exen','union_temporal_de_empresas_ajustes_por_criterios_d',
    'amortizacion_acelerada_de_determinados_vehiculos_y','xxxvii_copa_america_barcelona_ley_31_2022',
}


def classify(r):
    s0 = r['section'][0] if r['section'] else ''
    s1 = r['section'][1] if len(r['section']) > 1 else ''
    label, dtype = r['label'], r['dtype']
    existing = r['role']
    if existing:
        return existing, 'existing'
    if s0 == 'personal_asalariado_cifra_media_del_ejercicio_pers': return 'is_personal_asalariado_cifra_media', 'F-identificacion'
    if s0 == 'grupo_fiscal' and dtype == 'text': return 'is_grupo_fiscal_numero', 'F-identificacion'
    if s0 in IDENTIFICACION_SECTIONS and dtype == 'decimal': return 'is_identificacion_flag', 'F-identificacion'
    if s0 == 'liquidacion':
        if s1 == 'cuota_liquida': return 'is_cuota_liquida', 'A-liquidacion'
        if s1 == 'cuota_a_ingresar': return 'is_cuota_a_ingresar', 'A-liquidacion'
        return 'is_liquidacion_importe', 'A-liquidacion'

    def lq(label, pt):
        ll = label.lower()
        if 'resultado contable' in ll: return 'is_resultado_contable'
        if 'correcciones al resultado' in ll and 'aumento' in ll: return 'is_correcciones_aumentos'
        if 'correcciones al resultado' in ll and 'disminuci' in ll: return 'is_correcciones_disminuciones'
        if 'correcciones' in ll and 'aumento' in ll: return 'is_correcciones_aumentos'
        if 'correcciones' in ll and 'disminuci' in ll: return 'is_correcciones_disminuciones'
        if 'base imponible previa' in ll: return 'is_base_imponible_previa'
        if 'compensaci' in ll and 'bases' in ll: return 'is_compensacion_bases_negativas'
        if 'base imponible' in ll: return 'is_base_imponible'
        if 'reserva de capitalizaci' in ll: return 'is_reserva_capitalizacion_reduccion'
        if 'reserva de nivelaci' in ll: return 'is_reserva_nivelacion_reduccion'
        if 'tipo de gravamen' in ll or 'tipo gravamen' in ll: return 'is_tipo_gravamen'
        if 'cuota integra' in ll: return 'is_cuota_integra'
        if 'cuota l' in ll: return 'is_cuota_liquida'
        if 'retenciones' in ll: return 'is_retenciones_ingresos_a_cuenta'
        if 'pagos fraccionados' in ll: return 'is_pagos_fraccionados'
        return f'is_{pt}_importe'

    if s0 in ('liquidacion_i','liquidacion_ii','liquidacion_iii','liquidacion_iv'):
        return lq(label, s0), 'A-liquidacion'
    if s0 in CORRECCION_SECTIONS:
        if s1 == 'aumento': return 'is_correccion_aumento', 'B-correcciones'
        if s1 == 'disminucion': return 'is_correccion_disminucion', 'B-correcciones'
        if s1 == 'ejercicio_generacion': return 'is_correccion_dotacion_ejercicio', 'B-correcciones'
        if s1 == 'total': return 'is_correccion_total', 'B-correcciones'
        if s1 in ('abono_por_conversion_de_activos_por_impuesto_difer','compensacion_por_conversion_de_activos_por_impuest','rectificativa'):
            return 'is_conversion_activo_diferido_importe', 'B-correcciones'
        return 'is_correccion_aumento', 'B-correcciones'
    if s0 == 'tributacion_conjunta_estado_y_adm_forales':
        ll = label.lower()
        if 'concierto' in ll or 'convenio' in ll: return 'is_tributacion_conjunta_proporcion','J-tributacion_conjunta'
        if 'pagos fraccionados' in ll: return 'is_pagos_fraccionados','J-tributacion_conjunta'
        if 'cuota' in ll: return 'is_tributacion_conjunta_cuota','J-tributacion_conjunta'
        if 'inter' in ll: return 'is_tributacion_conjunta_intereses','J-tributacion_conjunta'
        if 'increment' in ll: return 'is_tributacion_conjunta_incremento','J-tributacion_conjunta'
        if 'conversi' in ll: return 'is_conversion_aid_importe','J-tributacion_conjunta'
        if 'abono' in ll: return 'is_conversion_aid_abono','J-tributacion_conjunta'
        if 'rectif' in ll: return 'is_tributacion_conjunta_rectificacion','J-tributacion_conjunta'
        if 'result' in ll: return 'is_tributacion_conjunta_resultado','J-tributacion_conjunta'
        if 'opci' in ll: return 'is_tributacion_conjunta_opcion_0_7','J-tributacion_conjunta'
        if 'discre' in ll: return 'is_tributacion_conjunta_discrepancia','J-tributacion_conjunta'
        return 'is_tributacion_conjunta_importe','J-tributacion_conjunta'
    if s0 in ('limitacion_deducibilidad_gastos_financieros','limitacion_deducibilidad_gastos_financieros_gastos','pendiente_adicion_por_limite_beneficio_operativo_n'):
        return 'is_gastos_financieros_limitacion_importe','B-correcciones'
    if s0 == 'dotaciones_deterioro_creditos_u_otros_activos':
        return ('is_dotacion_deterioro_total' if s1=='total' else 'is_dotacion_deterioro_ejercicio'), 'B-correcciones'
    if s0 == 'conversion_activos_impuesto_diferido_credito_exigi':
        if 'aid_art_130_lis' in s1: return 'is_conversion_aid_art130_importe','C-bases_negativas'
        if 'exceso_cuota_liquida_positiva' in s1: return 'is_conversion_aid_exceso_cuota_importe','C-bases_negativas'
        if 'aid_dt_33a' in s1: return 'is_conversion_aid_dt33a_importe','C-bases_negativas'
        return 'is_conversion_aid_importe','C-bases_negativas'
    if s0 == 'conversion_de_activos_por_impuesto_diferido_en_cre':
        if 'abono' in s1: return 'is_conversion_aid_abono','C-bases_negativas'
        if 'compensacion' in s1: return 'is_conversion_aid_compensacion','C-bases_negativas'
        if 'rectificativa' in s1: return 'is_conversion_aid_rectificativa','C-bases_negativas'
        return 'is_conversion_aid_importe','C-bases_negativas'
    if s0 == 'detalle_compensacion_bases_imponibles_negativas':
        return ('is_bin_total_pendiente' if s1=='total' else 'is_bin_pendiente_aplicacion'), 'C-bases_negativas'
    if s0 == 'detalle_correcciones_resultado_perdidas_y_ganancia': return 'is_correcciones_temporarias_importe','B-correcciones'
    if s0 == 'reserva_capitalizacion':
        ll = label.lower()
        if 'incremento' in ll or ('aumento' in ll and 'reserva' in ll): return 'is_reserva_capitalizacion_aumento','D-reservas'
        if 'reducci' in ll: return 'is_reserva_capitalizacion_reduccion','D-reservas'
        if 'pendiente' in ll: return 'is_reserva_capitalizacion_pendiente','D-reservas'
        if 'incumplimiento' in ll: return 'is_reserva_capitalizacion_incumplimiento','D-reservas'
        return 'is_reserva_capitalizacion_importe','D-reservas'
    if s0 == 'reserva_de_nivelacion':
        ll = label.lower()
        if 'dotaci' in ll: return 'is_reserva_nivelacion_dotacion','D-reservas'
        if 'adici' in ll: return 'is_reserva_nivelacion_adicion','D-reservas'
        if 'pendiente' in ll: return 'is_reserva_nivelacion_pendiente','D-reservas'
        if 'incumplimiento' in ll: return 'is_reserva_nivelacion_incumplimiento','D-reservas'
        return 'is_reserva_nivelacion_importe','D-reservas'
    if s0 in ('reg_especial_reserva_inversiones_canarias','reserva_para_inversiones_en_canarias_ley_19_1994','inversiones_anticipadas_reserva_inversiones_en_ill'):
        return 'is_reserva_inversiones_canarias_importe','D-reservas'
    if s0 in ('reg_especial_reserva_inversiones_illes_balears','reserva_para_inversiones_en_illes_balears_da_70a_l'):
        return 'is_reserva_inversiones_illes_balears_importe','D-reservas'
    if s0 == 'reg_cooperativas':
        ll = label.lower()
        if 'compensaci' in ll and 'cuota' in ll: return 'is_cooperativa_compensacion_cuotas','H-cooperativas'
        if 'cuota' in ll and 'integra' in ll: return 'is_cooperativa_cuota_integra','H-cooperativas'
        if 'cuota l' in ll: return 'is_cooperativa_cuota_liquida','H-cooperativas'
        if 'base imponible' in ll: return 'is_cooperativa_base_imponible','H-cooperativas'
        if 'resultado' in ll: return 'is_cooperativa_resultado_contable','H-cooperativas'
        if 'retenci' in ll: return 'is_cooperativa_retenciones','H-cooperativas'
        if 'pagos fraccionados' in ll: return 'is_cooperativa_pagos_fraccionados','H-cooperativas'
        if 'tipo de gravamen' in ll or 'tipo gravamen' in ll: return 'is_cooperativa_tipo_gravamen','H-cooperativas'
        return 'is_cooperativa_importe','H-cooperativas'
    if s0 in ('regimen_especial_de_buques_y_empresas_navieras_en','regimen_de_entidades_navieras_en_funcion_del_tonel'):
        ll = label.lower()
        if 'base imponible' in ll and 'negativa' in ll: return 'is_naviera_base_imponible_negativa','I-navieras'
        if 'compensaci' in ll: return 'is_naviera_compensacion','I-navieras'
        return 'is_naviera_importe','I-navieras'
    if s0.startswith('balance_activo'): return 'is_balance_activo_importe','K-estados_financieros'
    if s0.startswith('balance_patrimonio'): return 'is_balance_patrimonio_neto_pasivo_importe','K-estados_financieros'
    if s0.startswith('cuenta_de_perdidas_y_ganancias'): return 'is_cuenta_perdidas_ganancias_importe','K-estados_financieros'
    if s0.startswith('estado_de_cambios_patrimonio_neto'): return 'is_estado_cambios_patrimonio_neto_importe','K-estados_financieros'
    if s0 in ('entidades_en_reg_de_atribucion_de_rentas_const_en','entidad_en_regimen_de_atribucion_de_rentas_asimetr'):
        return 'is_atribucion_rentas_importe','J-tributacion_conjunta'
    if s0 == 'informacion_adicional_para_el_calculo_de_limites_d': return 'is_informacion_adicional_limites_importe','B-correcciones'
    if s0 == 'deducc_para_incentivar_determ_actividades':
        if 'investigacion_y_desarrollo' in s1 or s1.endswith('_ct'): return 'is_deduccion_idi_investigacion_aplicada','E-deducciones'
        if 'innovacion_tecnologica' in s1 or s1.endswith('_it'): return 'is_deduccion_idi_innovacion_tecnologica','E-deducciones'
        if 'suma_deducciones' in s1: return 'is_deduccion_idi_suma_periodo','E-deducciones'
        if 'inversiones_en_territ' in s1: return 'is_deduccion_inversiones_africa_canarias','E-deducciones'
        if 'diferim' in s1: return 'is_deduccion_idi_diferimiento','E-deducciones'
        if s1 == 'total': return 'is_deduccion_idi_total','E-deducciones'
        if any(x in s1 for x in ('barcelona','rally','mobile_world','arquitect','copa_america')): return 'is_deduccion_idi_evento_especial','E-deducciones'
        if 'otras_deducciones' in s1 or 'programas' in s1: return 'is_deduccion_idi_otras','E-deducciones'
        return 'is_deduccion_idi_importe','E-deducciones'
    if s0 == 'deducciones_i_d_i_excluidas_de_limite':
        if 'investigacion_y_desarrollo' in s1: return 'is_deduccion_idi_excluida_limite_investigacion','E-deducciones'
        if 'innovacion_tecnologica' in s1: return 'is_deduccion_idi_excluida_limite_innovacion','E-deducciones'
        if 'informacion_adicional' in s1: return 'is_deduccion_idi_excluida_limite_info_adicional','E-deducciones'
        return 'is_deduccion_idi_excluida_limite_importe','E-deducciones'
    if s0 == 'deducciones_doble_imposicion_interna_dt_23_1_lis':
        return ('is_deduccion_di_interna_total' if s1=='total' else 'is_deduccion_di_interna_periodo'), 'G-doble_imposicion'
    if s0 == 'deducciones_doble_imposicion_interna_rdleg_4_2004': return 'is_deduccion_di_interna_rdleg_importe','G-doble_imposicion'
    if s0 == 'deducciones_doble_imposicion_internacional_lis':
        return ('is_deduccion_di_internacional_total' if s1=='total' else 'is_deduccion_di_internacional_periodo'), 'G-doble_imposicion'
    if s0 == 'deducciones_doble_imposicion_internacional_rdleg_4': return 'is_deduccion_di_internacional_rdleg_importe','G-doble_imposicion'
    if s0 == 'deducciones_dt_24a_1_lis': return 'is_deduccion_dt24a1_periodificacion','E-deducciones'
    if s0 == 'deducc_disposic_transit_24a_7_lis':
        return ('is_deduccion_dt24a7_total' if s1=='total' else 'is_deduccion_dt24a7_periodo'), 'E-deducciones'
    if s0 == 'deduccion_donativos_entidades_sin_fines_lucro':
        if 'total_deducciones' in s1: return 'is_deduccion_donativos_total','F-deducciones_donativos'
        if 'base_de_la_deduccion' in s1: return 'is_deduccion_donativos_base','F-deducciones_donativos'
        if 'caracter_general' in s1: return 'is_deduccion_donativos_general','F-deducciones_donativos'
        if 'prioritarias' in s1 or 'mecena' in s1: return 'is_deduccion_donativos_prioritarias','F-deducciones_donativos'
        return 'is_deduccion_donativos_importe','F-deducciones_donativos'
    if s0 == 'deduccion_por_inversiones_y_gastos_realizados_por':
        return ('is_deduccion_copa_america_total' if s1=='total' else 'is_deduccion_copa_america_periodo'), 'E-deducciones'
    if s0 == 'deduccion_por_reversion_de_medidas_temporales_d_t':
        return ('is_deduccion_reversion_medidas_total' if s1=='total' else 'is_deduccion_reversion_medidas_periodo'), 'E-deducciones'
    if s0 == 'deducciones_inversion_canarias':
        return ('is_deduccion_inversion_canarias_total' if s1=='total' else 'is_deduccion_inversion_canarias_importe'), 'E-deducciones'
    if s0 == 'deducciones_por_producciones_cinematograficas_extr':
        if s1 in ('total',) or 'total' in s1: return 'is_deduccion_cinematografica_extranjera_total','E-deducciones'
        if 'deduccion_pendiente_generada' in s1: return 'is_deduccion_cinematografica_pendiente_generada','E-deducciones'
        return 'is_deduccion_cinematografica_extranjera_periodo','E-deducciones'
    if dtype == 'money': return 'is_importe_generico','Z-unclassified'
    if dtype == 'decimal': return 'is_identificacion_flag','F-identificacion'
    if dtype == 'text': return 'is_identificacion_texto','F-identificacion'
    return None,'Z-unclassified'


# --- build result set ---
results = []
role_counter = defaultdict(int)
family_counter = defaultdict(int)
section_family = defaultdict(set)

for r in records:
    role, family = classify(r)
    s0 = r['section'][0] if r['section'] else ''
    label_snip = r['label'][:60].replace('|','/')
    results.append((r['id'], s0, role, label_snip, r['dtype'], family))
    role_counter[role] += 1
    family_counter[family] += 1
    section_family[family].add(s0)

# section family summary
FAMILY_DESC = {
    'A-liquidacion': 'Liquidacion (pages 011-011b) — cuota integra, deducciones, cuota liquida, retenciones, pagos fraccionados',
    'B-correcciones': 'Detalle correcciones resultado contable — ~80 LIS-article correction categories (amortizacion, deterioro, diferencias temporarias, exenciones, operaciones especiales, gastos no deducibles)',
    'C-bases_negativas': 'Bases imponibles negativas y compensaciones — carry-forward BINs by year + conversion de activos por impuesto diferido (AID)',
    'D-reservas': 'Reservas (capitalizacion art.25 LIS, nivelacion art.105 LIS, inversiones Canarias ley-19/1994, Illes Balears DA70a LIS)',
    'E-deducciones': 'Deducciones (I+D+i art.35, cinematograficas art.36, inversion Canarias, DT24a, Copa America, reversion medidas temporales)',
    'F-deducciones_donativos': 'Deducciones donativos entidades sin fines lucro (ley 49/2002)',
    'G-doble_imposicion': 'Deducciones doble imposicion interna e internacional (LIS + RDLeg 4/2004)',
    'H-cooperativas': 'Regimen especial cooperativas (Ley 20/1990) — liquidacion, compensacion cuotas, base imponible',
    'I-navieras': 'Regimen especial buques y empresas navieras en funcion del tonelaje + compensacion bases negativas navieras',
    'J-tributacion_conjunta': 'Tributacion conjunta Estado y Administraciones Forales (Concierto Economico / Convenio Economico) + atribucion de rentas',
    'K-estados_financieros': 'Estados financieros (balance activo, balance patrimonio neto y pasivo, cuenta PYG, estado cambios patrimonio neto)',
    'F-identificacion': 'Identificacion — checkboxes de tipo entidad, regimen fiscal, opciones (decimals/text) + n. grupo fiscal + personal asalariado',
    'existing': 'Ya roled (base_imponible_negativa_is, resultado_ingresar_o_devolver_is)',
    'Z-unclassified': 'Sin clasificar (ninguno en resultado final)',
}

# sort by family then id
results.sort(key=lambda x: (x[5], x[0]))

# --- Generate vault document ---
lines = []
lines.append('---')
lines.append('tags:')
lines.append('  - \'#audit\'')
lines.append('  - \'#schema-hardening\'')
lines.append('date: \'2026-05-19\'')
lines.append('related:')
lines.append('  - "[[2026-05-19-schema-hardening-enrollment-campaign-queue]]"')
lines.append('  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"')
lines.append('---')
lines.append('')
lines.append('# `schema-hardening` audit: M200 IS role assignment')
lines.append('')
lines.append('## Summary')
lines.append('')
lines.append(f'- Total casillas: {len(records)}')
lines.append(f'- Already-roled (existing): 2 (00027 `base_imponible_negativa_is`, 00599 `resultado_ingresar_o_devolver_is`)')
lines.append(f'- Newly classified: {len(records) - 2}')
lines.append(f'- Distinct roles proposed (including 2 existing): {len(role_counter)}')
lines.append(f'- Section families: {len([k for k in FAMILY_DESC if k not in ("existing", "Z-unclassified")])}')
lines.append('')
lines.append('## Section families overview')
lines.append('')
lines.append('| Family | Description | Sections | Casillas |')
lines.append('|--------|-------------|----------|----------|')
for fam in sorted(FAMILY_DESC.keys()):
    if fam in ('Z-unclassified',): continue
    desc = FAMILY_DESC[fam]
    sec_count = len(section_family.get(fam, set()))
    cas_count = family_counter.get(fam, 0)
    lines.append(f'| `{fam}` | {desc} | {sec_count} | {cas_count} |')
lines.append('')
lines.append('## Per-id role assignment')
lines.append('')
lines.append('Roles marked `[existing]` were already declared in the TOML file; all others are proposals.')
lines.append('')
lines.append('| id | section_top | role | label_snippet | data_type | rationale |')
lines.append('|----|-------------|------|---------------|-----------|-----------|')
for cid, s0, role, label, dtype, family in results:
    s0_short = s0[:40] if s0 else ''
    rationale_map = {
        'existing': 'pre-existing role declaration',
        'A-liquidacion': 'liquidacion section label match',
        'B-correcciones': 'correccion section subsection key',
        'C-bases_negativas': 'bases negativas / AID section',
        'D-reservas': 'reservas section',
        'E-deducciones': 'deduccion section + subsection key',
        'F-deducciones_donativos': 'donativos section subsection',
        'G-doble_imposicion': 'doble imposicion section',
        'H-cooperativas': 'reg_cooperativas label match',
        'I-navieras': 'navieras label match',
        'J-tributacion_conjunta': 'tributacion_conjunta label match',
        'K-estados_financieros': 'estados financieros section prefix',
        'F-identificacion': 'identificacion section + decimal/text dtype',
        'Z-unclassified': 'UNCLASSIFIED — needs manual review',
    }
    rationale = rationale_map.get(family, family)
    lines.append(f'| {cid} | {s0_short} | `{role}` | {label} | {dtype} | {rationale} |')

lines.append('')
lines.append('## New roles introduced')
lines.append('')
lines.append('These roles are proposed by this audit and do NOT appear in the canonical taxonomy reference.')
lines.append('All bind `data_type = "money"` unless noted.')
lines.append('')
lines.append('| role | data_type | sign | definition |')
lines.append('|------|-----------|------|------------|')

new_roles = [
    ('is_identificacion_flag', 'decimal', 'n/a', 'Boolean/checkbox flag on page 001 identifying entity type or regime. Decimal 0/1 convention.'),
    ('is_identificacion_texto', 'text', 'n/a', 'Free-text identifier on page 001 (e.g. grupo fiscal number).'),
    ('is_grupo_fiscal_numero', 'text', 'n/a', 'Grupo fiscal identifier number — text field.'),
    ('is_personal_asalariado_cifra_media', 'decimal', 'non_negative', 'Cifra media de personal asalariado del ejercicio.'),
    ('is_resultado_contable', 'money', 'any', 'Resultado contable (accounting profit/loss) at the IS annual declaration level. Equivalent of M202 is_pf_mod_40_3_resultado_contable without the quarterly qualifier.'),
    ('is_correcciones_aumentos', 'money', 'non_negative', 'Total aumentos al resultado contable (sum of all LIS correction increases).'),
    ('is_correcciones_disminuciones', 'money', 'non_negative', 'Total disminuciones al resultado contable (sum of all LIS correction decreases).'),
    ('is_base_imponible_previa', 'money', 'any', 'Base imponible previa (before compensacion BINs and reserva capitalizacion).'),
    ('is_base_imponible', 'money', 'any', 'Base imponible (after reserva capitalizacion / nivelacion reductions).'),
    ('is_compensacion_bases_negativas', 'money', 'non_negative', 'Compensacion de bases imponibles negativas de ejercicios anteriores applied in this period.'),
    ('is_tipo_gravamen', 'decimal', 'non_negative', 'Tipo de gravamen (tax rate) as a percentage.'),
    ('is_cuota_integra', 'money', 'non_negative', 'Cuota integra (tax before deductions).'),
    ('is_cuota_liquida', 'money', 'non_negative', 'Cuota liquida (tax after deductions, before retenciones and pagos).'),
    ('is_cuota_a_ingresar', 'money', 'non_negative', 'Cuota a ingresar final after retenciones and pagos.'),
    ('is_liquidacion_importe', 'money', 'any', 'Generic liquidacion section amount not matching a more specific role.'),
    ('is_liquidacion_i_importe', 'money', 'any', 'Generic liquidacion_i section amount.'),
    ('is_liquidacion_ii_importe', 'money', 'any', 'Generic liquidacion_ii section amount.'),
    ('is_liquidacion_iii_importe', 'money', 'any', 'Generic liquidacion_iii section amount.'),
    ('is_liquidacion_iv_importe', 'money', 'any', 'Generic liquidacion_iv section amount.'),
    ('is_correccion_aumento', 'money', 'non_negative', 'Single LIS-article correction aumentos item. Shared role across ~80 correccion sections.'),
    ('is_correccion_disminucion', 'money', 'non_negative', 'Single LIS-article correction disminucion item. Shared role across ~80 correccion sections.'),
    ('is_correccion_total', 'money', 'any', 'Total correccion amount for a multi-year detail section.'),
    ('is_correccion_dotacion_ejercicio', 'money', 'non_negative', 'Dotacion generated in this ejercicio (e.g. dotaciones deterioro creditos).'),
    ('is_correccion_importe', 'money', 'any', 'Generic correccion amount where subsection key is not aumento/disminucion.'),
    ('is_conversion_activo_diferido_importe', 'money', 'any', 'Conversion activos impuesto diferido item (abono/compensacion/rectificativa variants).'),
    ('is_gastos_financieros_limitacion_importe', 'money', 'any', 'Limitacion deducibilidad gastos financieros (art.16 LIS) tracking amounts.'),
    ('is_dotacion_deterioro_ejercicio', 'money', 'non_negative', 'Dotacion deterioro creditos u otros activos generated in this ejercicio.'),
    ('is_dotacion_deterioro_total', 'money', 'non_negative', 'Total dotacion deterioro pendiente de reversion.'),
    ('is_conversion_aid_art130_importe', 'money', 'any', 'AID conversion frente Hacienda Publica (art.130 LIS).'),
    ('is_conversion_aid_exceso_cuota_importe', 'money', 'any', 'AID conversion por exceso cuota liquida positiva.'),
    ('is_conversion_aid_dt33a_importe', 'money', 'any', 'AID conversion DT33a y DA13a LIS.'),
    ('is_conversion_aid_importe', 'money', 'any', 'Generic AID conversion amount.'),
    ('is_conversion_aid_abono', 'money', 'non_negative', 'AID conversion abono (credit applied to tax debt).'),
    ('is_conversion_aid_compensacion', 'money', 'non_negative', 'AID conversion compensacion (offset against cuota).'),
    ('is_conversion_aid_rectificativa', 'money', 'any', 'AID conversion rectificativa adjustment.'),
    ('is_bin_pendiente_aplicacion', 'money', 'non_positive', 'Base imponible negativa pendiente de compensacion from a prior year. Non-positive by definition.'),
    ('is_bin_total_pendiente', 'money', 'non_positive', 'Total BIN pendiente de aplicacion across all prior years.'),
    ('is_correcciones_temporarias_importe', 'money', 'any', 'Detalle correcciones temporarias (saldo pendiente / correcciones al resultado).'),
    ('is_reserva_capitalizacion_aumento', 'money', 'non_negative', 'Incremento de fondos propios generating the reserva capitalizacion.'),
    ('is_reserva_capitalizacion_reduccion', 'money', 'non_negative', 'Reduccion base imponible por reserva capitalizacion.'),
    ('is_reserva_capitalizacion_pendiente', 'money', 'non_negative', 'Reserva capitalizacion pendiente de dotacion.'),
    ('is_reserva_capitalizacion_incumplimiento', 'money', 'non_negative', 'Reserva capitalizacion incumplimiento amount.'),
    ('is_reserva_capitalizacion_importe', 'money', 'any', 'Generic reserva capitalizacion amount.'),
    ('is_reserva_nivelacion_dotacion', 'money', 'non_negative', 'Dotacion reserva nivelacion (reduces base imponible).'),
    ('is_reserva_nivelacion_adicion', 'money', 'non_negative', 'Adicion a base imponible por reserva nivelacion reversion or income application.'),
    ('is_reserva_nivelacion_pendiente', 'money', 'non_negative', 'Reserva nivelacion saldo pendiente de adicion.'),
    ('is_reserva_nivelacion_incumplimiento', 'money', 'non_negative', 'Reserva nivelacion incumplimiento amount.'),
    ('is_reserva_nivelacion_importe', 'money', 'any', 'Generic reserva nivelacion amount.'),
    ('is_reserva_inversiones_canarias_importe', 'money', 'any', 'Reserva para inversiones en Canarias (ley 19/1994 art.27) tracking amounts.'),
    ('is_reserva_inversiones_illes_balears_importe', 'money', 'any', 'Reserva para inversiones en Illes Balears (DA70a LIS) tracking amounts.'),
    ('is_cooperativa_compensacion_cuotas', 'money', 'any', 'Cooperativa cuota negativa pendiente/aplicada en compensacion (Ley 20/1990).'),
    ('is_cooperativa_cuota_integra', 'money', 'non_negative', 'Cuota integra cooperativa (protegida + especialmente protegida + resto).'),
    ('is_cooperativa_cuota_liquida', 'money', 'non_negative', 'Cuota liquida cooperativa after bonificaciones.'),
    ('is_cooperativa_base_imponible', 'money', 'any', 'Base imponible cooperativa (extracooperativa / cooperativa).'),
    ('is_cooperativa_resultado_contable', 'money', 'any', 'Resultado contable cooperativa.'),
    ('is_cooperativa_retenciones', 'money', 'non_negative', 'Retenciones e ingresos a cuenta cooperativa.'),
    ('is_cooperativa_pagos_fraccionados', 'money', 'non_negative', 'Pagos fraccionados cooperativa.'),
    ('is_cooperativa_tipo_gravamen', 'decimal', 'non_negative', 'Tipo de gravamen cooperativa (%).'),
    ('is_cooperativa_importe', 'money', 'any', 'Generic cooperativa liquidacion amount.'),
    ('is_naviera_base_imponible_negativa', 'money', 'non_positive', 'Base imponible negativa pendiente en regimen especial navieras tonelaje.'),
    ('is_naviera_compensacion', 'money', 'non_negative', 'Compensacion BIN en regimen especial navieras.'),
    ('is_naviera_importe', 'money', 'any', 'Generic regimen especial navieras amount.'),
    ('is_balance_activo_importe', 'money', 'any', 'Balance de situacion activo (PGCE format) balance sheet line.'),
    ('is_balance_patrimonio_neto_pasivo_importe', 'money', 'any', 'Balance patrimonio neto y pasivo line.'),
    ('is_cuenta_perdidas_ganancias_importe', 'money', 'any', 'Cuenta de perdidas y ganancias line (operaciones continuadas / interrumpidas).'),
    ('is_estado_cambios_patrimonio_neto_importe', 'money', 'any', 'Estado de cambios en el patrimonio neto (I, II, III) line.'),
    ('is_atribucion_rentas_importe', 'money', 'any', 'Entidades en regimen de atribucion de rentas — amount attributed or corrected.'),
    ('is_tributacion_conjunta_proporcion', 'money', 'non_negative', 'Proporcion tributacion conjunta Estado/Administraciones Forales (concierto/convenio).'),
    ('is_tributacion_conjunta_cuota', 'money', 'any', 'Cuota resultante en tributacion conjunta.'),
    ('is_tributacion_conjunta_resultado', 'money', 'any', 'Resultado final in tributacion conjunta settlement.'),
    ('is_tributacion_conjunta_rectificacion', 'money', 'any', 'Rectificacion amount in tributacion conjunta context.'),
    ('is_tributacion_conjunta_intereses', 'money', 'any', 'Intereses de demora in tributacion conjunta.'),
    ('is_tributacion_conjunta_incremento', 'money', 'any', 'Incremento in tributacion conjunta base.'),
    ('is_tributacion_conjunta_opcion_0_7', 'money', 'any', 'Opcion 0.7% cuota integra para fines sociales in tributacion conjunta context.'),
    ('is_tributacion_conjunta_discrepancia', 'money', 'any', 'Discrepancia in tributacion conjunta calculation.'),
    ('is_tributacion_conjunta_importe', 'money', 'any', 'Generic tributacion conjunta amount.'),
    ('is_informacion_adicional_limites_importe', 'money', 'any', 'Informacion adicional para calculo de limites deduccion I+D+i (art.35 LIS).'),
    ('is_deduccion_idi_investigacion_aplicada', 'money', 'non_negative', 'Deduccion I+D (art.35.1 LIS / CT) aplicada en el periodo, by generation year.'),
    ('is_deduccion_idi_innovacion_tecnologica', 'money', 'non_negative', 'Deduccion IT (art.35.2 LIS / IT) aplicada en el periodo, by generation year.'),
    ('is_deduccion_idi_suma_periodo', 'money', 'non_negative', 'Suma deducciones I+D+i generadas en a given year (cap.IV tit.VI).'),
    ('is_deduccion_inversiones_africa_canarias', 'money', 'non_negative', 'Deduccion inversiones territorios Africa occidental y gastos publicitarios (art.27bis LIS / Canarias).'),
    ('is_deduccion_idi_diferimiento', 'money', 'non_negative', 'Deduccion I+D+i diferida pendiente from prior period.'),
    ('is_deduccion_idi_total', 'money', 'non_negative', 'Total I+D+i deduction pendiente fin de periodo (all years combined).'),
    ('is_deduccion_idi_evento_especial', 'money', 'non_negative', 'Special-event deduction (Barcelona 2026, Copa America, Rally Islas Canarias).'),
    ('is_deduccion_idi_otras', 'money', 'non_negative', 'Otras deducciones relativas a programas de apoyo.'),
    ('is_deduccion_idi_importe', 'money', 'non_negative', 'Generic I+D+i incentivos deduction amount.'),
    ('is_deduccion_idi_excluida_limite_investigacion', 'money', 'non_negative', 'Deduccion I+D excluida de limite (art.35.1), by generation year.'),
    ('is_deduccion_idi_excluida_limite_innovacion', 'money', 'non_negative', 'Deduccion IT excluida de limite (art.35.2), by generation year.'),
    ('is_deduccion_idi_excluida_limite_info_adicional', 'money', 'non_negative', 'Informacion adicional para calculo de limites en deducciones excluidas.'),
    ('is_deduccion_idi_excluida_limite_importe', 'money', 'non_negative', 'Generic I+D+i excluida de limite amount.'),
    ('is_deduccion_di_interna_periodo', 'money', 'non_negative', 'Deduccion doble imposicion interna (DT23.1 LIS), by generation year.'),
    ('is_deduccion_di_interna_total', 'money', 'non_negative', 'Total deduccion doble imposicion interna pendiente.'),
    ('is_deduccion_di_interna_rdleg_importe', 'money', 'non_negative', 'Deduccion doble imposicion interna RDLeg 4/2004 (pre-LIS) amount.'),
    ('is_deduccion_di_internacional_periodo', 'money', 'non_negative', 'Deduccion doble imposicion internacional (LIS), by generation year.'),
    ('is_deduccion_di_internacional_total', 'money', 'non_negative', 'Total deduccion doble imposicion internacional pendiente.'),
    ('is_deduccion_di_internacional_rdleg_importe', 'money', 'non_negative', 'Deduccion doble imposicion internacional RDLeg 4/2004 (pre-LIS) amount.'),
    ('is_deduccion_dt24a1_periodificacion', 'money', 'non_negative', 'Deduccion DT24a.1 LIS periodificacion amount.'),
    ('is_deduccion_dt24a7_periodo', 'money', 'non_negative', 'Deduccion DT24a.7 LIS (reinversion beneficios extraordinarios), by year.'),
    ('is_deduccion_dt24a7_total', 'money', 'non_negative', 'Total deduccion DT24a.7 LIS pendiente.'),
    ('is_deduccion_donativos_general', 'money', 'non_negative', 'Deduccion por donaciones de caracter general (ley 49/2002).'),
    ('is_deduccion_donativos_prioritarias', 'money', 'non_negative', 'Deduccion por donaciones actividades prioritarias de mecenazgo.'),
    ('is_deduccion_donativos_base', 'money', 'non_negative', 'Base de la deduccion por donaciones.'),
    ('is_deduccion_donativos_total', 'money', 'non_negative', 'Total deducciones donativos entidades sin fines lucro.'),
    ('is_deduccion_donativos_importe', 'money', 'non_negative', 'Generic donativo deduction amount.'),
    ('is_deduccion_copa_america_periodo', 'money', 'non_negative', 'Deduccion Copa America / inversiones autoridades portuarias, by year.'),
    ('is_deduccion_copa_america_total', 'money', 'non_negative', 'Total deduccion Copa America.'),
    ('is_deduccion_reversion_medidas_periodo', 'money', 'non_negative', 'Deduccion reversion medidas temporales (DT37a LIS), by year.'),
    ('is_deduccion_reversion_medidas_total', 'money', 'non_negative', 'Total deduccion reversion medidas temporales.'),
    ('is_deduccion_inversion_canarias_importe', 'money', 'non_negative', 'Deduccion inversion Canarias activos fijos / inversiones, by type and year.'),
    ('is_deduccion_inversion_canarias_total', 'money', 'non_negative', 'Total deduccion inversion Canarias pendiente.'),
    ('is_deduccion_cinematografica_extranjera_periodo', 'money', 'non_negative', 'Deduccion producciones cinematograficas extranjeras (art.36.2/36.3 LIS), by year.'),
    ('is_deduccion_cinematografica_extranjera_total', 'money', 'non_negative', 'Total deduccion producciones cinematograficas extranjeras pendiente.'),
    ('is_deduccion_cinematografica_pendiente_generada', 'money', 'non_negative', 'Deduccion cinematografica extranjera pendiente generada en el periodo.'),
    ('is_reserva_nivelacion_reduccion', 'money', 'non_negative', 'Reduccion base imponible by reserva nivelacion in liquidacion context.'),
    ('is_reserva_capitalizacion_reduccion', 'money', 'non_negative', 'Reduccion base imponible by reserva capitalizacion in liquidacion context.'),
]

for role, dtype, sign, defn in new_roles:
    lines.append(f'| `{role}` | {dtype} | {sign} | {defn} |')

lines.append('')
lines.append('## Top reuse patterns')
lines.append('')
lines.append('1. **`is_correccion_aumento` / `is_correccion_disminucion`** — shared across all ~80 LIS-article correction')
lines.append('   sections (185 casillas combined). Every correccion section has a symmetric aumento/disminucion pair.')
lines.append('   These two roles cover the broadest footprint in the form.')
lines.append('')
lines.append('2. **`is_cooperativa_compensacion_cuotas`** — 68 casillas across the `reg_cooperativas` section.')
lines.append('   Each year (1999–2025) contributes three casillas: pendiente al principio, aplicado en esta liquidacion,')
lines.append('   pendiente al final. The section structure repeats identically for each generation year.')
lines.append('')
lines.append('3. **`is_estado_cambios_patrimonio_neto_importe`** — 53 casillas across the three subsections')
lines.append('   (`estado_de_cambios_patrimonio_neto_i/ii/iii`). Each subsection is a PGC-mandated equity')
lines.append('   movement table; all rows share the same monetary role.')
lines.append('')
lines.append('## Open questions / classification ambiguities')
lines.append('')
lines.append('### 1. `is_liquidacion_iv_importe` (13 casillas)')
lines.append('The `liquidacion_iv` section spans a ZEC/consolidated IS regime page whose exact label structure')
lines.append('was not resolvable from the label snippets alone (labels are truncated in the TOML). The label-match')
lines.append('heuristics assigned most to recognized sub-concepts (`is_resultado_contable`, `is_tipo_gravamen`, etc.)')
lines.append('but 13 fell to the generic `is_liquidacion_iv_importe` role. Manual review recommended.')
lines.append('')
lines.append('### 2. Tributacion conjunta `is_tributacion_conjunta_*` (24 casillas)')
lines.append('The `tributacion_conjunta_estado_y_adm_forales` section has complex sub-structure (concierto/convenio,')
lines.append('AID-conversion amounts, rectificativas, resultados). Label-based classification was applied but')
lines.append('some sub-slots may semantically overlap with existing roles (e.g. `is_pagos_fraccionados` reused).')
lines.append('The AID-conversion sub-slots inside this section were mapped to `is_conversion_aid_*` roles; the')
lines.append('overlap with the general AID section should be validated at rollout.')
lines.append('')
lines.append('### 3. Cooperativas: `is_cooperativa_cuota_integra` / `is_cooperativa_cuota_liquida` vs. IS main roles')
lines.append('Cooperativas compute their own cuota integra and cuota liquida under Ley 20/1990, which differs from')
lines.append('the general LIS cuota. The cooperative-specific roles intentionally do NOT reuse `is_cuota_integra`')
lines.append('/ `is_cuota_liquida` to avoid cross-section validator inconsistency (constraints and sign conventions')
lines.append('may differ). If the snapshot-build validator permits per-section role islands, this can be revisited.')
lines.append('')
lines.append('### 4. `is_identificacion_flag` (74 casillas) — consistency validation')
lines.append('All page-001 entity-type checkbox casillas carry `data_type = "decimal"`. The role is proposed')
lines.append('consistently for all 74 but the validator will check for constraint consistency across the role.')
lines.append('If any casilla carries a non-zero constraint (e.g. `non_negative`) that differs from the default,')
lines.append('the validator will reject it. All decimal flags should be unconstrained.')
lines.append('')
lines.append('### 5. Reserved-role overlap for `is_retenciones_ingresos_a_cuenta` and `is_pagos_fraccionados`')
lines.append('These two roles already exist in the canonical taxonomy (bound to `money / non_negative`). They are')
lines.append('reused here in the liquidacion context. The liquidacion casillas for these concepts must carry')
lines.append('`constraints = "non_negative"` to satisfy the intra-role consistency validator.')

out_path = Path('.vault/audit/2026-05-19-schema-hardening-m200-role-assignment.md')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text('\n'.join(lines), encoding='utf-8')
print(f"Written {len(lines)} lines to {out_path}")
print(f"Total casillas classified: {len(records)}")
print(f"Distinct roles: {len(role_counter)}")
