"""Typed Modelo 200 producer facts and repeated export rows."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG


class Modelo200AdministradorRow(BaseModel):
    """One administrador row, projected into modelo 200's layout at slot 1..5."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    forma_juridica: str | None = None
    representante: str | None = None
    apellidos_nombre_razon_social: str | None = None
    domicilio_fiscal: str | None = None
    codigo_provincia: str | None = None


class Modelo200EntidadMenorDependienteRow(BaseModel):
    """One entidad menor dependiente row, projected into modelo 200's layout at slot 1..10."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    nombre_o_razon_social: str | None = None


class Modelo200EntidadParticipadaRow(BaseModel):
    """One entidad participada row, projected into modelo 200's layout at slot 1..3."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    nombre_o_razon_social: str | None = None
    codigo_provincia_pais: str | None = None
    tipo_agrupacion_interes_economico_espanola: str | None = None
    tipo_agrupacion_europea_interes_economico: str | None = None
    tipo_union_temporal_empresas: str | None = None
    tipo_colaboracion_extranjera_analoga: str | None = None
    criterio_imputacion_fin_periodo: str | None = None
    criterio_imputacion_siguiente_periodo: str | None = None
    valoracion_participacion_inicio: str | None = None
    valoracion_participacion_final: str | None = None
    ingresos_financieros_participacion: str | None = None
    resultado_contable_imputado: str | None = None
    gastos_financieros_netos_imputados: str | None = None
    reserva_capitalizacion_no_aplicada_imputada: str | None = None
    base_imponible_imputada: str | None = None
    deduccion_doble_imposicion_bases_imputadas: str | None = None
    bonificacion_bases_imputadas: str | None = None
    deduccion_activos_fijos_canarias: str | None = None
    deduccion_idi_canarias: str | None = None
    deduccion_produccion_espectaculos_canarias: str | None = None
    deduccion_resto_inversion_canarias: str | None = None
    deduccion_idi_bases_imputadas: str | None = None
    deduccion_produccion_espectaculos_bases_imputadas: str | None = None
    deduccion_resto_incentivar_actividades: str | None = None
    deduccion_resto_no_mencionadas: str | None = None
    retenciones_ingresos_a_cuenta_imputados: str | None = None
    dividendos_ejercicios_anteriores: str | None = None
    dividendos_ejercicios_posteriores: str | None = None


class Modelo200EstablecimientoPermanenteRow(BaseModel):
    """One establecimiento permanente row, projected into modelo 200's layout at slot 1..18."""

    model_config = STRICT_FROZEN_CONFIG

    identificacion: str | None = None
    pais_residencia_fiscal: str | None = None
    volumen_operaciones: str | None = None
    beneficio_o_perdida: str | None = None
    suma_ajustes_resultado_contable: str | None = None
    suma_deducciones_di_internacional_anteriores: str | None = None


class Modelo200IncnGrupoSociedadRow(BaseModel):
    """One incn grupo sociedad row, projected into modelo 200's layout at slot 1..12."""

    model_config = STRICT_FROZEN_CONFIG

    nif_entidad_grupo: str | None = None
    codigo_pais: str | None = None


class Modelo200OperacionReestructuracionRow(BaseModel):
    """One operacion reestructuracion row, projected into modelo 200's layout at slot 1..5."""

    model_config = STRICT_FROZEN_CONFIG

    tipo_operacion: str | None = None
    transmitente_nif: str | None = None
    transmitente_denominacion_social: str | None = None
    adquirente_nif: str | None = None
    adquirente_denominacion_social: str | None = None
    fecha_inscripcion_registro_mercantil: str | None = None
    fecha_comunicacion_operacion: str | None = None
    valor_acciones_entregadas: str | None = None
    valor_acciones_recibidas: str | None = None
    importe_rentas_no_integradas: str | None = None


class Modelo200ParticipacionDirectaRow(BaseModel):
    """One participacion directa row, projected into modelo 200's layout at slot 1..3."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    nombre_o_razon_social: str | None = None
    codigo_provincia_pais: str | None = None
    porcentaje_participacion: str | None = None
    valor_nominal_total: str | None = None
    valor_en_libros: str | None = None
    ingresos_por_dividendos: str | None = None
    correccion_valor_perdidas_ganancias: str | None = None
    reversion_perdidas_deterioro_valores: str | None = None
    eliminacion_deterioro_contable: str | None = None
    eliminacion_deterioro_valores_participacion: str | None = None
    ajuste_valor_razonable: str | None = None
    efecto_correccion_valorativa_base_imponible: str | None = None
    saldo_correcciones_fiscales_pendientes: str | None = None
    capital: str | None = None
    reservas_y_otras_partidas_fondos_propios: str | None = None
    otras_partidas_patrimonio_neto: str | None = None
    resultado_ultimo_ejercicio: str | None = None


class Modelo200ParticipacionSocioRow(BaseModel):
    """One participacion socio row, projected into modelo 200's layout at slot 1..6."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    representante: str | None = None
    forma_juridica: str | None = None
    apellidos_nombre_razon_social: str | None = None
    codigo_provincia_pais: str | None = None
    nominal: str | None = None
    porcentaje_participacion: str | None = None


class Modelo200ParticipeAieUteRow(BaseModel):
    """One participe aie ute row, projected into modelo 200's layout at slot 1..10."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str | None = None
    representante: str | None = None
    forma_juridica: str | None = None
    residencia: str | None = None
    apellidos_nombre_razon_social: str | None = None
    codigo_provincia_pais: str | None = None
    base_imponible: str | None = None
    porcentaje_participacion: str | None = None


class Modelo200RepresentanteLegalRow(BaseModel):
    """One representante legal row, projected into modelo 200's layout at slot 1..3."""

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre: str | None = None
    nif: str | None = None
    fecha_poder: str | None = None
    notaria_otros: str | None = None


class Modelo200SecretarioConsejoRow(BaseModel):
    """One secretario consejo row, projected into modelo 200's layout at slot 1..1."""

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre: str | None = None
    nif: str | None = None


class Modelo200SocioSicavDisolucionRow(BaseModel):
    """One socio sicav disolucion row, projected into modelo 200's layout at slot 1..5."""

    model_config = STRICT_FROZEN_CONFIG

    nif_sociedad_disuelta: str | None = None
    nif_iic_reinversion: str | None = None


class Modelo200TransparenciaFiscalInternacionalRow(BaseModel):
    """One transparencia fiscal internacional row, projected into modelo 200's layout at slot 1..6."""

    model_config = STRICT_FROZEN_CONFIG

    nombre_o_razon_social: str | None = None
    domicilio_social: str | None = None
    clave_pais_territorio: str | None = None
    importe_renta: str | None = None
    administradores_linea_1: str | None = None
    administradores_linea_2: str | None = None
    administradores_linea_3: str | None = None
    administradores_linea_4: str | None = None
    administradores_linea_5: str | None = None


class Modelo200ProjectionRows(BaseModel):
    """The repeated party, holding and establishment rows modelo 200's layout projects.

    Modelo 200's generated layout carries 578 projection-kind fields across fourteen
    kinds, and ``_projection_plan_for_layout`` built a plan for M303 alone -- so every one
    of them raised "requires a snapshot-owned render context" and the Impuesto sobre
    Sociedades return could not export at all. It failed CLOSED, so no wrong bytes were
    ever emitted, but it did not file.

    Unlike modelo 296's perceptores, whose data already exists as
    ``Withholding296Observation``, these rows are genuinely operator-supplied: the app
    holds no administrador, representante or participada register anywhere else. So they
    are declared here rather than projected from an existing substrate.

    Every family defaults to empty. An absent family emits no record occurrence, which is
    what AEAT expects of a page a filer has nothing to put on -- it is not the same as a
    filer who has rows and supplied none, and only the caller knows which it is.
    """

    model_config = STRICT_FROZEN_CONFIG

    administrador: tuple[Modelo200AdministradorRow, ...] = ()
    entidad_menor_dependiente: tuple[Modelo200EntidadMenorDependienteRow, ...] = ()
    entidad_participada: tuple[Modelo200EntidadParticipadaRow, ...] = ()
    establecimiento_permanente: tuple[Modelo200EstablecimientoPermanenteRow, ...] = ()
    incn_grupo_sociedad: tuple[Modelo200IncnGrupoSociedadRow, ...] = ()
    operacion_reestructuracion: tuple[Modelo200OperacionReestructuracionRow, ...] = ()
    participacion_directa: tuple[Modelo200ParticipacionDirectaRow, ...] = ()
    participacion_socio: tuple[Modelo200ParticipacionSocioRow, ...] = ()
    participe_aie_ute: tuple[Modelo200ParticipeAieUteRow, ...] = ()
    representante_legal: tuple[Modelo200RepresentanteLegalRow, ...] = ()
    secretario_consejo: tuple[Modelo200SecretarioConsejoRow, ...] = ()
    socio_sicav_disolucion: tuple[Modelo200SocioSicavDisolucionRow, ...] = ()
    transparencia_fiscal_internacional: tuple[Modelo200TransparenciaFiscalInternacionalRow, ...] = ()


class Modelo200ProfileFacts(BaseModel):
    """The header facts modelo 200's export layout cites as operator-supplied.

    All 132 ``m200.*`` producer keys resolved to nothing, so every one of these fields
    rendered blank on a filed Impuesto sobre Sociedades return.

    Two groups inside them are worth naming, because they are not operator facts at all
    and the categorisation belongs to the layout rather than to this type. SIX are
    ``identificador_de_fin_de_registro*`` at length 12 -- the record terminator, envelope
    mechanics. TWENTY-ONE are period and date components the snapshot's :class:`Period`
    and the draft's filing year already determine. Both are declared here because the
    layout cites them as header producers; correcting that belongs in the semantic map.

    Six field names carry an ``apartado_`` prefix because AEAT numbers those apartados and
    the key tail begins with a digit, which is not a legal Python identifier. The prefix
    is added rather than the name changed, so the field still reads as the key it resolves.

    Every field is optional and absent stays absent -- AEAT writes an empty alphanumeric
    header field to blancos.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_rows: Modelo200ProjectionRows = Modelo200ProjectionRows()
    apartado_6_deduc_evitar_doble_imposicion_participacio: str | None = None
    apartado_6_deduc_evitar_doble_imposicion_participacio_2: str | None = None
    apartado_6_deduc_evitar_doble_imposicion_participacio_3: str | None = None
    apartado_6_deduc_evitar_doble_imposicion_participacio_4: str | None = None
    apartado_6_deduc_evitar_doble_imposicion_participacio_5: str | None = None
    apartado_6_deduc_evitar_doble_imposicion_participacio_6: str | None = None
    abono_compensacion_abono_por_conversion_de_a: str | None = None
    abono_compensacion_compensacion_por_conversi: str | None = None
    apellidos_y_nombre: str | None = None
    b_2_suma_de_porcentajes_de_participacion_de: str | None = None
    b_2_suma_de_porcentajes_de_participaciones_e: str | None = None
    balance_0_no_consta_1_mod_normal_2_mod_abrev: str | None = None
    codigo_cnae_2025_actividad_principal: str | None = None
    codigo_pais_country_code: str | None = None
    como_consecuencia_de_la_presentacion_de_la_a: str | None = None
    cuenta_bancaria_banco_bank_name: str | None = None
    cuenta_bancaria_ciudad_city: str | None = None
    cuenta_bancaria_codigo_swift_bic: str | None = None
    cuenta_bancaria_marca_sepa: str | None = None
    cuenta_corriente_tributaria: str | None = None
    datos_de_la_sociedad_matriz_ultima_nif: str | None = None
    datos_de_la_sociedad_matriz_ultima_nombre_de: str | None = None
    datos_de_la_sociedad_matriz_ultima_razon_soc: str | None = None
    deduccion_resto_del_grupo: str | None = None
    deduccion_resto_del_grupo_10: str | None = None
    deduccion_resto_del_grupo_11: str | None = None
    deduccion_resto_del_grupo_12: str | None = None
    deduccion_resto_del_grupo_13: str | None = None
    deduccion_resto_del_grupo_14: str | None = None
    deduccion_resto_del_grupo_15: str | None = None
    deduccion_resto_del_grupo_16: str | None = None
    deduccion_resto_del_grupo_17: str | None = None
    deduccion_resto_del_grupo_18: str | None = None
    deduccion_resto_del_grupo_19: str | None = None
    deduccion_resto_del_grupo_2: str | None = None
    deduccion_resto_del_grupo_20: str | None = None
    deduccion_resto_del_grupo_21: str | None = None
    deduccion_resto_del_grupo_22: str | None = None
    deduccion_resto_del_grupo_23: str | None = None
    deduccion_resto_del_grupo_24: str | None = None
    deduccion_resto_del_grupo_25: str | None = None
    deduccion_resto_del_grupo_26: str | None = None
    deduccion_resto_del_grupo_3: str | None = None
    deduccion_resto_del_grupo_4: str | None = None
    deduccion_resto_del_grupo_5: str | None = None
    deduccion_resto_del_grupo_6: str | None = None
    deduccion_resto_del_grupo_7: str | None = None
    deduccion_resto_del_grupo_8: str | None = None
    deduccion_resto_del_grupo_9: str | None = None
    direccion_de_correo_electronico_para_inciden: str | None = None
    direccion_del_banco_bank_address: str | None = None
    ecpn_0_no_consta_1_mod_normal_2_mod_abreviad: str | None = None
    ejercicio: str | None = None
    entidad_cuyo_importe_neto_de_la_cifra_de_neg: str | None = None
    entidad_sin_obligacion_de_identificar_el_tit: str | None = None
    f_identificacion_del_titular_real_de_la_enti: str | None = None
    fecha_de_nacimiento: str | None = None
    identificacion_ejercicio: str | None = None
    identificacion_tipo_de_ejercicio: str | None = None
    identificador_de_fin_de_registro: str | None = None
    identificador_de_fin_de_registro_2: str | None = None
    identificador_de_fin_de_registro_3: str | None = None
    identificador_de_fin_de_registro_4: str | None = None
    identificador_de_fin_de_registro_5: str | None = None
    identificador_de_fin_de_registro_6: str | None = None
    importe_a_devolver: str | None = None
    importe_a_ingresar: str | None = None
    importe_neto_de_la_cifra_de_negocios_de_los: str | None = None
    importe_neto_de_la_cifra_de_negocios_de_los_2: str | None = None
    importe_neto_de_la_cifra_de_negocios_de_los_3: str | None = None
    informacion_adicional_producciones_cinematog: str | None = None
    informacion_adicional_producciones_cinematog_2: str | None = None
    informacion_adicional_producciones_cinematog_3: str | None = None
    informacion_adicional_producciones_cinematog_4: str | None = None
    informacion_adicional_producciones_cinematog_5: str | None = None
    informacion_adicional_producciones_cinematog_6: str | None = None
    inoperatividad_del_orden_de_cumplimentacion: str | None = None
    inversiones_en_producciones_cinematograficas: str | None = None
    inversiones_en_producciones_cinematograficas_2: str | None = None
    inversiones_en_producciones_cinematograficas_3: str | None = None
    inversiones_en_producciones_cinematograficas_4: str | None = None
    inversiones_en_producciones_cinematograficas_5: str | None = None
    inversiones_en_producciones_cinematograficas_6: str | None = None
    modalidad_de_ingreso_uno_de_los_siguientes_v: str | None = None
    modelo_de_estados_contables_que_se_va_a_cump: str | None = None
    n_i_f_de_la_sociedad_representante_dominante: str | None = None
    nif_codigo_de_identificacion_extranjero: str | None = None
    nif_en_el_pais_de_residencia_tin: str | None = None
    no_identificacion_de_la_sociedad_dominante_e: str | None = None
    no_residentes_mas_de_un_establecimiento_perm: str | None = None
    nombre_y_apellidos_de_la_persona_de_contacto: str | None = None
    numero_de_cuenta_iban: str | None = None
    numero_de_cuenta_iban_2: str | None = None
    numero_de_periodo_impositivo: str | None = None
    pais_de_expedicion_del_documento_de_identifi: str | None = None
    pais_de_residencia: str | None = None
    pais_de_residencia_2: str | None = None
    parte_de_la_base_imponible_del_periodo_impos: str | None = None
    parte_de_la_base_imponible_del_periodo_impos_2: str | None = None
    perdidas_y_ganancias_0_no_consta_1_mod_norma: str | None = None
    periodo: str | None = None
    periodo_impositivo: str | None = None
    periodo_impositivo_ano_final: str | None = None
    periodo_impositivo_ano_inicio: str | None = None
    periodo_impositivo_dia_final: str | None = None
    periodo_impositivo_dia_inicio: str | None = None
    periodo_impositivo_fin_ano: str | None = None
    periodo_impositivo_fin_dia: str | None = None
    periodo_impositivo_fin_mes: str | None = None
    periodo_impositivo_inicio_ano: str | None = None
    periodo_impositivo_inicio_dia: str | None = None
    periodo_impositivo_inicio_mes: str | None = None
    periodo_impositivo_mes_final: str | None = None
    periodo_impositivo_mes_inicio: str | None = None
    presentacion_de_documentacion_previa_en_la_s: str | None = None
    presentacion_de_documentacion_previa_en_la_s_2: str | None = None
    presentacion_de_documentacion_previa_en_la_s_3: str | None = None
    presentacion_de_documentacion_previa_en_la_s_4: str | None = None
    presentacion_de_documentacion_previa_en_la_s_5: str | None = None
    presentacion_de_documentacion_previa_en_la_s_6: str | None = None
    presentacion_de_documentacion_previa_en_la_s_7: str | None = None
    presentacion_de_documentacion_previa_en_la_s_8: str | None = None
    realiza_actividades_agricolas_y_o_ganaderas: str | None = None
    reg_entidades_navieras_en_funcion_del_tonela: str | None = None
    renuncia_o_por_transferencia: str | None = None
    resultado_a_ingresar_correspondiente_a_la_an: str | None = None
    resultado_a_ingresar_correspondiente_a_la_an_2: str | None = None
    resultado_cero: str | None = None
    socimis_regimen_fiscal_de_entrada_salida_ren: str | None = None
    tipo_de_declaracion_ver_nota: str | None = None
    tipo_de_ejercicio: str | None = None
    tipo_documento_identificativo: str | None = None


__all__ = [
    "Modelo200AdministradorRow",
    "Modelo200EntidadMenorDependienteRow",
    "Modelo200EntidadParticipadaRow",
    "Modelo200EstablecimientoPermanenteRow",
    "Modelo200IncnGrupoSociedadRow",
    "Modelo200OperacionReestructuracionRow",
    "Modelo200ParticipacionDirectaRow",
    "Modelo200ParticipacionSocioRow",
    "Modelo200ParticipeAieUteRow",
    "Modelo200ProfileFacts",
    "Modelo200ProjectionRows",
    "Modelo200RepresentanteLegalRow",
    "Modelo200SecretarioConsejoRow",
    "Modelo200SocioSicavDisolucionRow",
    "Modelo200TransparenciaFiscalInternacionalRow",
]
