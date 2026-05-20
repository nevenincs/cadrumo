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


def classify(r):
    cid = r['id']
    sec = r['section']
    s0 = sec[0] if len(sec) > 0 else ''
    s1 = sec[1] if len(sec) > 1 else ''
    label = r['label']
    dtype = r['dtype']
    existing = r['role']
    if existing:
        return existing, 'existing'

    # ---- IDENTIFICACION (checkbox flags, numeric identifiers) ----
    identificacion_sections = {
        'entidad_sin_animo_de_lucro_acogida_regimen_fiscal',
        'entidad_parcialmente_exenta',
        'sociedad_de_inversion_de_capital_variable_o_fondo',
        'sociedad_de_inversion_inmobiliaria_o_fondo_de_inve',
        'comunidades_titulares_de_montes_vecinales_en_mano',
        'incentivos_entidad_de_reducida_dimension_cap_xi_ti',
        'imputacion_en_base_imponible_rentas_positivas_art',
        'sociedad_de_inversion_de_capital_variable_que_no_c',
        'entidad_dominante_de_grupo_fiscal',
        'entidad_dependiente_de_grupo_fiscal',
        'entidad_de_tenencia_de_valores_extranjeros',
        'socimi',
        'agrupacion_de_interes_economico_espanola',
        'agrupacion_europea_de_interes_economico',
        'entidad_zec_sin_consolidacion_fiscal',
        'reg_cooperativas_determ_base_imponible',
        'cooperativa_protegida',
        'cooperativa_especialmente_protegida',
        'resto_cooperativas',
        'otros_regimenes_especiales',
        'establecimiento_permanente',
        'regimen_entidades_navieras_en_funcion_del_tonelaje',
        'gran_empresa',
        'entidad_de_credito',
        'entidad_aseguradora',
        'entidad_inactiva',
        'tributacion_conjunta_estado_diput_cdad_forales',
        'regimen_especial_canarias',
        'transmision_elementos_patrimoniales_arts_27_2_d_y',
        'entidades_de_capital_riesgo',
        'sociedades_desarrollo_industrial_regional',
        'regimen_especial_mineria',
        'regimen_especial_hidrocarburos',
        'regimen_especial_fusiones_escisiones_aportaciones',
        'sociedad_de_garantia_reciproca_o_de_reafianzamient',
        'opcion_de_fraccionamiento_art_19_1_lis',
        'entidad_dedicada_al_arrend_viviendas',
        'entidad_que_forma_parte_de_un_grupo_mercantil_art',
        'grupo_fiscal',
        'obligacion_informacion_dt_5a_ris',
        'contribuyente_que_genera_deducciones_del_art_36_1',
        'inversiones_anticipadas',
        'entidad_en_reg_atribuc_de_rentas_constituida_en_el',
        'entidades_sometidas_a_normativa_foral',
        'fondo_de_pensiones_real_decreto_legislativo_1_2002',
        'regimenes_especiales_de_normativa_foral',
        'tributacion_conjunta_estado_y_adm_forales_concierto_economico',
        'tributacion_conjunta_estado_y_adm_forales_convenio_economico',
        'entidad_en_regimen_de_atribucion_de_rentas_con_tri',
        'regimen_fiscal_salida_socimi',
        'mutua_de_seguros_o_mutualidad_de_prevision_social',
        'opcion_art_39_2_lis',
        'fondos_o_activos_de_titulizacion',
        'estados_de_cuentas_de_instituciones_de_inversion_c',
        'reg_fiscal_de_operac_de_aportacion_de_activos_a_sd',
        'tipo_de_gravamen_reducido_para_entidades_de_nueva',
        'regimen_fiscal_entrada_socimi',
        'bonificacion_personal_investigador_rd_475_2014',
        'entidad_patrimonial',
        'estados_de_cuentas_de_entidades_de_credito',
        'compensacion_bases_imponibles_negativas_para_entid',
        'tipo_gravamen_reducido_para_entidades_de_nueva_cre',
        'extincion_de_entidad',
        'opcion_del_0_7_de_la_cuota_integra_para_fines_soci',
        'contribuyente_que_financia_producciones_con_derech',
        'diocesis_provincia_religiosa_o_entidad_eclesiastic',
        'entidad_zec_en_consolidacion_fiscal',
        'uniones_federaciones_y_confederaciones_de_cooperat',
        'filial_grupo_multinacional_o_grupo_nacional_de_gra',
        'sociedad_matriz_ultima_grupo_multinacional_o_grupo',
        'tipo_gravamen_reducido_para_empresa_emergente',
        'regimen_especial_de_disolucion_y_liquidacion_de_si',
        'union_temporal_de_empresas',
        'regimen_especial_illes_balears',
        'inversiones_anticipadas_reserva_inversiones_en_ill',
        'tipo_gravamen_reducido_para_entidades_con_incn_per',
        'participe_de_agrupacion_de_interes_economico_o_de',
        'opcion_art_39_3_lis',
        'base_imponible_negativa_o_cero',
    }

    if s0 == 'personal_asalariado_cifra_media_del_ejercicio_pers':
        return 'is_personal_asalariado_cifra_media', 'identificacion_numeric'

    if s0 == 'grupo_fiscal' and dtype == 'text':
        return 'is_grupo_fiscal_numero', 'identificacion_text'

    if s0 in identificacion_sections and dtype == 'decimal':
        return 'is_identificacion_flag', 'identificacion_flag'

    # ---- LIQUIDACION ----
    if s0 == 'liquidacion':
        if s1 == 'cuota_liquida': return 'is_cuota_liquida', 'liquidacion'
        if s1 == 'cuota_a_ingresar': return 'is_cuota_a_ingresar', 'liquidacion'
        return 'is_liquidacion_importe', 'liquidacion'

    def liq_classify(label, page_tag):
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
        return f'is_{page_tag}_importe'

    if s0 == 'liquidacion_i': return liq_classify(label, 'liquidacion_i'), 'liquidacion_i'
    if s0 == 'liquidacion_ii': return liq_classify(label, 'liquidacion_ii'), 'liquidacion_ii'
    if s0 == 'liquidacion_iii': return liq_classify(label, 'liquidacion_iii'), 'liquidacion_iii'
    if s0 == 'liquidacion_iv': return liq_classify(label, 'liquidacion_iv'), 'liquidacion_iv'

    # ---- CORRECCIONES (aumento/disminucion/total/dotacion pairs) ----
    correccion_sections = {
        'amortizacion_del_inmovilizado_intangible_y_fondo_d',
        'amortizacion_de_inmovilizado_afecto_a_actividades',
        'diferencias_entre_amortizacion_contable_y_fiscal_a',
        'libertad_de_amortizacion_con_mantenimiento_de_empl',
        'libertad_de_amortizacion_de_determinados_vehiculos',
        'libertad_de_amortizacion_de_gastos_de_investigacio',
        'libertad_de_amortizacion_inmovilizado_material_nue',
        'libertad_de_amortizacion_sin_mantenimiento_de_empl',
        'otros_supuestos_de_libertad_de_amortizacion_art_12',
        'empresas_de_reducida_dimension_amortizacion_aceler',
        'empresas_de_reducida_dimension_libertad_de_amortiz',
        'empresas_de_reducida_dimension_perdidas_por_deteri',
        'perdidas_por_deterioro_de_im_inversiones_inmobilia',
        'perdidas_por_deterioro_de_valores_repr_de_partic_e',
        'perdidas_por_deterioro_de_valores_representativos',
        'perdidas_por_deterioro_del_art_13_1_lis_no_afectad',
        'perdidas_por_deterioro_del_art_13_1_lis_y_provisio',
        'ajustes_por_deterioro_de_valores_repr_de_partic_en',
        'ajustes_por_la_limitacion_en_la_deducibilidad_de_g',
        'ajustes_por_perdidas_por_deterioro_de_valores_repr',
        'ajustes_por_rentas_derivadas_de_operaciones_con_qu',
        'aplicacion_del_limite_del_art_11_12_lis_a_las_perd',
        'reversion_del_deterioro_del_valor_de_los_elementos',
        'reversion_por_deterioro_de_valores_representativos',
        'gastos_y_provisiones_por_pensiones_no_afectados_po',
        'otras_provisiones_no_deducibles_fiscalmente_art_14',
        'cambio_de_criterios_contables_art_11_3_2o_lis',
        'operaciones_a_plazos_art_11_4_lis',
        'operaciones_a_plazos_dt_1a_lis',
        'cambio_de_residencia_a_estados_miembros_de_la_unio',
        'operaciones_del_art_19_lis_distintas_del_cambio_de',
        'otras_diferencias_de_imputacion_temporal_de_ingres',
        'rentas_negativas_art_11_9_y_11_10_lis',
        'gastos_no_deducibles_por_considerarse_retribucion',
        'gastos_derivados_de_la_extincion_de_la_relacion_la',
        'multas_sanciones_y_otros_art_15_c_lis',
        'perdidas_del_juego_art_15_d_lis',
        'gastos_por_donativos_y_liberalidades_art_15_e_lis',
        'gastos_de_actuaciones_contrarias_al_ordenamiento_j',
        'gastos_financieros_derivados_de_deudas_con_entidad',
        'gastos_que_sean_objeto_de_la_deduccion_por_inversi',
        'revalorizaciones_contables_art_17_1_lis',
        'asimetrias_hibridas_art_15_bis_lis_excepto_art_15',
        'disminucion_de_valor_originada_por_criterio_de_val',
        'efectos_de_la_valoracion_contable_diferente_a_la_f',
        'deuda_tributaria_de_actos_juridicos_documentados_i',
        'exencion_de_rentas_en_el_extranjero_art_22_lis',
        'exencion_sobre_dividendos_o_participaciones_en_ben',
        'exencion_sobre_la_renta_obtenida_en_la_transmision',
        'exencion_sobre_la_renta_obtenida_en_los_supuestos',
        'exencion_transmision_bienes_inmuebles_da_6a_lis',
        'reduccion_de_rentas_procedentes_de_determinados_ac',
        'operaciones_vinculadas_aplicacion_del_valor_de_mer',
        'adquisicion_de_participaciones_en_entidades_no_res',
        'aportaciones_y_colaboracion_a_favor_de_entidades_s',
        'agrupacion_de_interes_economico_cap_ii_del_tit_vii',
        'arrendamiento_financiero_regimen_especial_art_106',
        'bases_imp_negativas_generadas_dentro_del_grupo_fis',
        'correcciones_especificas_de_entidades_sometidas_a',
        'eliminaciones_pendientes_de_incorporar_de_sociedad',
        'impuesto_extranjero_soportado_por_el_contribuyente',
        'mineria_e_hidrocarburos_factor_agotamiento_arts_91',
        'hidrocarburos_amortizacion_de_inversiones_intangib',
        'obra_benefico_social_de_las_cajas_de_ahorro_y_fund',
        'operaciones_de_aumento_de_capital_o_fondos_propios',
        'otras_correcciones_al_resultado_de_la_cuenta_de_pe',
        'regimen_de_entidades_navieras_en_funcion_del_tonel',
        'regimen_de_entidades_parcialmente_exentas_capitulo',
        'regimen_fiscal_entidades_de_tenencia_de_valores_ex',
        'regimen_fiscal_entidades_sin_fines_lucrativos_ley',
        'reinversion_de_beneficios_extraordinarios_dt_24a_l',
        'rentas_procedentes_de_transmision_de_inmovilizado',
        'impuesto_extranjero_sobre_los_beneficios_con_cargo',
        'correccion_por_el_impuesto_sobre_el_margen_de_inte',
        'cooperativas_fondo_de_reserva_obligatorio_ley_20_1',
        'deduccion_del_30_importe_gastos_de_amortiz_contabl',
        'subvenciones_publicas_incluidas_en_el_resultado_de',
        'operaciones_realizadas_con_jurisdicciones_no_coope',
        'transmisiones_lucrativas_y_societarias_aplicacion',
        'transparencia_fiscal_internacional_art_100_lis',
        'montes_vecinales_en_mano_comun_capitulo_xv_del_tit',
        'valoracion_de_bienes_y_derechos_regimen_especial_o',
        'sociedades_y_fondos_de_capital_riesgo_y_sociedades',
        'socio_sicav_reducciones_de_capital_y_distribucion',
        'socio_sicav_rentas_derivadas_de_liquidaciones_de_s',
        'union_temporal_de_empresas_ajustes_del_art_45_1_li',
        'union_temporal_de_empresas_ajustes_por_rentas_exen',
        'union_temporal_de_empresas_ajustes_por_criterios_d',
        'amortizacion_acelerada_de_determinados_vehiculos_y',
        'xxxvii_copa_america_barcelona_ley_31_2022',
    }

    if s0 in correccion_sections:
        if s1 == 'aumento': return 'is_correccion_aumento', 'correccion'
        if s1 == 'disminucion': return 'is_correccion_disminucion', 'correccion'
        if s1 == 'ejercicio_generacion': return 'is_correccion_dotacion_ejercicio', 'correccion_dotacion'
        if s1 == 'total': return 'is_correccion_total', 'correccion_total'
        if s1 in ('abono_por_conversion_de_activos_por_impuesto_difer',
                  'compensacion_por_conversion_de_activos_por_impuest',
                  'rectificativa'):
            return 'is_conversion_activo_diferido_importe', 'correccion_conversion'
        # no subsection: single-item correction
        return 'is_correccion_aumento', 'correccion'

    # ---- TRIBUTACION CONJUNTA FORALES ----
    if s0 == 'tributacion_conjunta_estado_y_adm_forales':
        ll = label.lower()
        if 'concierto' in ll or 'convenio' in ll: return 'is_tributacion_conjunta_proporcion', 'tributacion_conjunta'
        if 'pagos fraccionados' in ll: return 'is_pagos_fraccionados', 'tributacion_conjunta'
        if 'cuota' in ll: return 'is_tributacion_conjunta_cuota', 'tributacion_conjunta'
        if 'inter' in ll: return 'is_tributacion_conjunta_intereses', 'tributacion_conjunta'
        if 'increment' in ll: return 'is_tributacion_conjunta_incremento', 'tributacion_conjunta'
        if 'conversi' in ll: return 'is_conversion_aid_importe', 'tributacion_conjunta'
        if 'abono' in ll: return 'is_conversion_aid_abono', 'tributacion_conjunta'
        if 'rectif' in ll: return 'is_tributacion_conjunta_rectificacion', 'tributacion_conjunta'
        if 'result' in ll: return 'is_tributacion_conjunta_resultado', 'tributacion_conjunta'
        if 'opci' in ll: return 'is_tributacion_conjunta_opcion_0_7', 'tributacion_conjunta'
        if 'discre' in ll: return 'is_tributacion_conjunta_discrepancia', 'tributacion_conjunta'
        return 'is_tributacion_conjunta_importe', 'tributacion_conjunta'

    # ---- GASTOS FINANCIEROS LIMITACION ----
    if s0 in ('limitacion_deducibilidad_gastos_financieros',
              'limitacion_deducibilidad_gastos_financieros_gastos',
              'pendiente_adicion_por_limite_beneficio_operativo_n'):
        return 'is_gastos_financieros_limitacion_importe', 'gastos_financieros'

    # ---- DOTACIONES DETERIORO ----
    if s0 == 'dotaciones_deterioro_creditos_u_otros_activos':
        if s1 == 'total': return 'is_dotacion_deterioro_total', 'dotaciones_deterioro'
        return 'is_dotacion_deterioro_ejercicio', 'dotaciones_deterioro'

    # ---- CONVERSION ACTIVOS DIFERIDOS ----
    if s0 == 'conversion_activos_impuesto_diferido_credito_exigi':
        if 'aid_art_130_lis' in s1: return 'is_conversion_aid_art130_importe', 'conversion_aid'
        if 'exceso_cuota_liquida_positiva' in s1: return 'is_conversion_aid_exceso_cuota_importe', 'conversion_aid'
        if 'aid_dt_33a' in s1: return 'is_conversion_aid_dt33a_importe', 'conversion_aid'
        return 'is_conversion_aid_importe', 'conversion_aid'

    if s0 == 'conversion_de_activos_por_impuesto_diferido_en_cre':
        if 'abono' in s1: return 'is_conversion_aid_abono', 'conversion_aid'
        if 'compensacion' in s1: return 'is_conversion_aid_compensacion', 'conversion_aid'
        if 'rectificativa' in s1: return 'is_conversion_aid_rectificativa', 'conversion_aid'
        return 'is_conversion_aid_importe', 'conversion_aid'

    # ---- BASES IMPONIBLES NEGATIVAS ----
    if s0 == 'detalle_compensacion_bases_imponibles_negativas':
        if s1 == 'total': return 'is_bin_total_pendiente', 'bases_negativas'
        return 'is_bin_pendiente_aplicacion', 'bases_negativas'

    if s0 == 'detalle_correcciones_resultado_perdidas_y_ganancia':
        return 'is_correcciones_temporarias_importe', 'correcciones_temporarias'

    # ---- RESERVAS ----
    if s0 == 'reserva_capitalizacion':
        ll = label.lower()
        if 'incremento' in ll or ('aumento' in ll and 'reserva' in ll): return 'is_reserva_capitalizacion_aumento', 'reservas'
        if 'reducci' in ll: return 'is_reserva_capitalizacion_reduccion', 'reservas'
        if 'pendiente' in ll: return 'is_reserva_capitalizacion_pendiente', 'reservas'
        if 'incumplimiento' in ll: return 'is_reserva_capitalizacion_incumplimiento', 'reservas'
        return 'is_reserva_capitalizacion_importe', 'reservas'

    if s0 == 'reserva_de_nivelacion':
        ll = label.lower()
        if 'dotaci' in ll: return 'is_reserva_nivelacion_dotacion', 'reservas'
        if 'adici' in ll: return 'is_reserva_nivelacion_adicion', 'reservas'
        if 'pendiente' in ll: return 'is_reserva_nivelacion_pendiente', 'reservas'
        if 'incumplimiento' in ll: return 'is_reserva_nivelacion_incumplimiento', 'reservas'
        return 'is_reserva_nivelacion_importe', 'reservas'

    if s0 in ('reg_especial_reserva_inversiones_canarias',
              'reserva_para_inversiones_en_canarias_ley_19_1994',
              'inversiones_anticipadas_reserva_inversiones_en_ill'):
        return 'is_reserva_inversiones_canarias_importe', 'reservas'

    if s0 in ('reg_especial_reserva_inversiones_illes_balears',
              'reserva_para_inversiones_en_illes_balears_da_70a_l'):
        return 'is_reserva_inversiones_illes_balears_importe', 'reservas'

    # ---- REGIMENES ESPECIALES COOPERATIVAS ----
    if s0 == 'reg_cooperativas':
        ll = label.lower()
        # compensacion cuotas comes BEFORE cuota checks to avoid mismatch
        if 'compensaci' in ll and 'cuota' in ll: return 'is_cooperativa_compensacion_cuotas', 'cooperativas'
        if 'cuota' in ll and 'integra' in ll: return 'is_cooperativa_cuota_integra', 'cooperativas'
        if 'cuota l' in ll: return 'is_cooperativa_cuota_liquida', 'cooperativas'
        if 'base imponible' in ll: return 'is_cooperativa_base_imponible', 'cooperativas'
        if 'resultado' in ll: return 'is_cooperativa_resultado_contable', 'cooperativas'
        if 'retenci' in ll: return 'is_cooperativa_retenciones', 'cooperativas'
        if 'pagos fraccionados' in ll: return 'is_cooperativa_pagos_fraccionados', 'cooperativas'
        if 'tipo de gravamen' in ll or 'tipo gravamen' in ll: return 'is_cooperativa_tipo_gravamen', 'cooperativas'
        return 'is_cooperativa_importe', 'cooperativas'

    # ---- NAVIERAS ----
    if s0 in ('regimen_especial_de_buques_y_empresas_navieras_en',
              'regimen_de_entidades_navieras_en_funcion_del_tonel'):
        ll = label.lower()
        if 'base imponible' in ll and 'negativa' in ll: return 'is_naviera_base_imponible_negativa', 'navieras'
        if 'compensaci' in ll: return 'is_naviera_compensacion', 'navieras'
        return 'is_naviera_importe', 'navieras'

    # ---- ESTADOS FINANCIEROS ----
    if s0.startswith('balance_activo'): return 'is_balance_activo_importe', 'estados_financieros'
    if s0.startswith('balance_patrimonio'): return 'is_balance_patrimonio_neto_pasivo_importe', 'estados_financieros'
    if s0.startswith('cuenta_de_perdidas_y_ganancias'): return 'is_cuenta_perdidas_ganancias_importe', 'estados_financieros'
    if s0.startswith('estado_de_cambios_patrimonio_neto'): return 'is_estado_cambios_patrimonio_neto_importe', 'estados_financieros'

    # ---- TRIBUTACION CONJUNTA / ATRIBUCION ----
    if s0 in ('entidades_en_reg_de_atribucion_de_rentas_const_en',
              'entidad_en_regimen_de_atribucion_de_rentas_asimetr'):
        return 'is_atribucion_rentas_importe', 'tributacion_conjunta'

    # ---- INFORMACION ADICIONAL ----
    if s0 in ('informacion_adicional_para_el_calculo_de_limites_d',):
        return 'is_informacion_adicional_limites_importe', 'informacion_adicional'

    # ---- DEDUCCIONES ----
    if s0 == 'deducc_para_incentivar_determ_actividades':
        if 'investigacion_y_desarrollo' in s1 or s1.endswith('_ct'): return 'is_deduccion_idi_investigacion_aplicada', 'deducciones_idi'
        if 'innovacion_tecnologica' in s1 or s1.endswith('_it'): return 'is_deduccion_idi_innovacion_tecnologica', 'deducciones_idi'
        if 'suma_deducciones' in s1: return 'is_deduccion_idi_suma_periodo', 'deducciones_idi'
        if 'inversiones_en_territ' in s1: return 'is_deduccion_inversiones_africa_canarias', 'deducciones_idi'
        if 'diferim' in s1: return 'is_deduccion_idi_diferimiento', 'deducciones_idi'
        if s1 == 'total': return 'is_deduccion_idi_total', 'deducciones_idi'
        if any(x in s1 for x in ('barcelona', 'rally', 'mobile_world', 'arquitect', 'copa_america')): return 'is_deduccion_idi_evento_especial', 'deducciones_idi'
        if 'otras_deducciones' in s1 or 'programas' in s1: return 'is_deduccion_idi_otras', 'deducciones_idi'
        return 'is_deduccion_idi_importe', 'deducciones_idi'

    if s0 == 'deducciones_i_d_i_excluidas_de_limite':
        if 'investigacion_y_desarrollo' in s1: return 'is_deduccion_idi_excluida_limite_investigacion', 'deducciones_idi_excluida'
        if 'innovacion_tecnologica' in s1: return 'is_deduccion_idi_excluida_limite_innovacion', 'deducciones_idi_excluida'
        if 'informacion_adicional' in s1: return 'is_deduccion_idi_excluida_limite_info_adicional', 'deducciones_idi_excluida'
        return 'is_deduccion_idi_excluida_limite_importe', 'deducciones_idi_excluida'

    if s0 == 'deducciones_doble_imposicion_interna_dt_23_1_lis':
        if s1 == 'total': return 'is_deduccion_di_interna_total', 'deducciones_di'
        return 'is_deduccion_di_interna_periodo', 'deducciones_di'

    if s0 == 'deducciones_doble_imposicion_interna_rdleg_4_2004':
        return 'is_deduccion_di_interna_rdleg_importe', 'deducciones_di'

    if s0 == 'deducciones_doble_imposicion_internacional_lis':
        if s1 == 'total': return 'is_deduccion_di_internacional_total', 'deducciones_di'
        return 'is_deduccion_di_internacional_periodo', 'deducciones_di'

    if s0 == 'deducciones_doble_imposicion_internacional_rdleg_4':
        return 'is_deduccion_di_internacional_rdleg_importe', 'deducciones_di'

    if s0 == 'deducciones_dt_24a_1_lis':
        return 'is_deduccion_dt24a1_periodificacion', 'deducciones_transitorias'

    if s0 == 'deducc_disposic_transit_24a_7_lis':
        if s1 == 'total': return 'is_deduccion_dt24a7_total', 'deducciones_transitorias'
        return 'is_deduccion_dt24a7_periodo', 'deducciones_transitorias'

    if s0 == 'deduccion_donativos_entidades_sin_fines_lucro':
        if 'total_deducciones' in s1: return 'is_deduccion_donativos_total', 'deducciones_donativos'
        if 'base_de_la_deduccion' in s1: return 'is_deduccion_donativos_base', 'deducciones_donativos'
        if 'caracter_general' in s1: return 'is_deduccion_donativos_general', 'deducciones_donativos'
        if 'prioritarias' in s1 or 'mecena' in s1: return 'is_deduccion_donativos_prioritarias', 'deducciones_donativos'
        return 'is_deduccion_donativos_importe', 'deducciones_donativos'

    if s0 == 'deduccion_por_inversiones_y_gastos_realizados_por':
        if s1 == 'total': return 'is_deduccion_copa_america_total', 'deducciones_copa_america'
        return 'is_deduccion_copa_america_periodo', 'deducciones_copa_america'

    if s0 == 'deduccion_por_reversion_de_medidas_temporales_d_t':
        if s1 == 'total': return 'is_deduccion_reversion_medidas_total', 'deducciones_reversion'
        return 'is_deduccion_reversion_medidas_periodo', 'deducciones_reversion'

    if s0 == 'deducciones_inversion_canarias':
        if s1 == 'total': return 'is_deduccion_inversion_canarias_total', 'deducciones_canarias'
        return 'is_deduccion_inversion_canarias_importe', 'deducciones_canarias'

    if s0 == 'deducciones_por_producciones_cinematograficas_extr':
        if s1 in ('total',) or 'total' in s1: return 'is_deduccion_cinematografica_extranjera_total', 'deducciones_cine'
        if 'deduccion_pendiente_generada' in s1: return 'is_deduccion_cinematografica_pendiente_generada', 'deducciones_cine'
        return 'is_deduccion_cinematografica_extranjera_periodo', 'deducciones_cine'

    # catch-all
    if dtype == 'money':
        return 'is_importe_generico', 'unclassified'
    if dtype == 'decimal':
        return 'is_identificacion_flag', 'identificacion_flag'
    if dtype == 'text':
        return 'is_identificacion_texto', 'identificacion_text'
    return None, 'unclassified'


results = []
role_counter = defaultdict(int)
for r in records:
    role, family = classify(r)
    sec = r['section']
    s0 = sec[0] if len(sec) > 0 else ''
    label_snip = r['label'][:70]
    results.append((r['id'], s0, role, label_snip, r['dtype'], family))
    if role:
        role_counter[role] += 1

print(f"Total: {len(results)}")
print(f"Classified with a role: {sum(1 for _, _, role, _, _, _ in results if role)}")
print(f"is_importe_generico count: {sum(1 for _, _, role, _, _, _ in results if role == 'is_importe_generico')}")
print(f"None: {sum(1 for _, _, role, _, _, _ in results if not role)}")
print(f"Distinct roles: {len(role_counter)}")
print()
print("Roles by count:")
for role, cnt in sorted(role_counter.items(), key=lambda x: -x[1]):
    print(f"  {cnt:4d}  {role}")
print()
print("Remaining generics:")
for cid, s0, role, lbl, dtype, fam in results:
    if role == 'is_importe_generico':
        print(f"  {cid} | {s0} | {dtype} | {lbl[:60]}")
