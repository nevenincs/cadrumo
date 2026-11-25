"""Typed perceptor and annex row references for Modelo 296 filing projections."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from .models import STRICT_FROZEN_CONFIG


class M296PerceptorField(StrEnum):
    """Closed fields of one Modelo 296 perceptor row.

    Modelo 296 is the IRNR annual withholding summary, and AEAT repeats the whole
    PERCEPTOR RECORD once per payee rather than repeating fields inside one record. The
    snapshot carries operator-supplied typed perceptor rows, and these fields address a
    row through its render occurrence. They do not refer to declarant header facts or
    an enrolled withholding observation store.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    BASE_RETENCIONES_E_INGRESOS_A_CUENTA = "base_retenciones_e_ingresos_a_cuenta"
    CIUDAD = "ciudad"
    CLAVE = "clave"
    CLAVE_DE_MERCADO = "clave_de_mercado"
    CODIGO = "codigo"
    CODIGO_BIC_DEL_PERCEPTOR_MEDIADOR = "codigo_bic_del_perceptor_mediador"
    CODIGO_CUENTA_VALORES = "codigo_cuenta_valores"
    CODIGO_EMISOR = "codigo_emisor"
    CODIGO_LEI_DEL_PERCEPTOR = "codigo_lei_del_perceptor"
    CODIGO_PAIS = "codigo_pais"
    DECIMAL = "decimal"
    DECIMAL_NUMERICO_PARTE_DECIMAL = "decimal_numerico_parte_decimal"
    DECIMAL_NUMERICO_PARTE_DECIMAL_2 = "decimal_numerico_parte_decimal_2"
    DECIMAL_NUMERICO_PARTE_DECIMAL_3 = "decimal_numerico_parte_decimal_3"
    DECLARANTE = "declarante"
    DIRECCION_DEL_PERCEPTOR = "direccion_del_perceptor"
    EJERCICIO = "ejercicio"
    EJERCICIO_DEVENGO = "ejercicio_devengo"
    ENTERO = "entero"
    ENTERO_NUMERICO_PARTE_ENTERA = "entero_numerico_parte_entera"
    ENTERO_NUMERICO_PARTE_ENTERA_2 = "entero_numerico_parte_entera_2"
    ENTERO_NUMERICO_PARTE_ENTERA_3 = "entero_numerico_parte_entera_3"
    F_J = "f_j"
    FECHA_DE_DEVENGO = "fecha_de_devengo"
    FECHA_DE_INICIO_DEL_PRESTAMO = "fecha_de_inicio_del_prestamo"
    FECHA_DE_NACIMIENTO = "fecha_de_nacimiento"
    FECHA_DE_VENCIMIENTO_DEL_PRESTAMO = "fecha_de_vencimiento_del_prestamo"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    INGRESOS_A_CUENTA_REPERCUTIDOS = "ingresos_a_cuenta_repercutidos"
    NATURALEZA = "naturaleza"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PAGADOR_ANTERIOR = "nif_del_pagador_anterior"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL = "nif_en_el_pais_de_residencia_fiscal"
    PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "pais_o_territorio_de_residencia_fiscal"
    PARTE_DECIMAL_DEL_IMPORTE_DE_LAS_RETEN = "parte_decimal_del_importe_de_las_reten"
    PARTE_ENTERA_DEL_IMPORTE_DE_LAS_RETENC = "parte_entera_del_importe_de_las_retenc"
    PENDIENTE = "pendiente"
    PERCEPTOR_MEDIADOR = "perceptor_mediador"
    PROCEDIMIENTO_ESPECIAL_DE_RETENCIONES = "procedimiento_especial_de_retenciones"
    SUBCLAVE = "subclave"
    TIPO_CODIGO = "tipo_codigo"


class M296PerceptorProjectionRef(BaseModel):
    """One field of the Modelo 296 perceptor row.

    This reference carries NO slot, and the omission is the point. The m200 party
    references carry one because AEAT prints those rows a fixed number of times on the
    form, so the slot is part of the field's address. The number of perceptores is the
    number of payees and is not bounded by the design, so the perceptor RECORD repeats
    instead: it declares ``repeat = "projection_rows"``, the plan emits one render context
    per payee, and the projection address is completed by that context's occurrence. A
    slot here would be a second row axis that is always 1 -- meaningless at best, and at
    worst an invitation to cap the payees at the slots someone declared.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_perceptor"]
    field: M296PerceptorField


class M296PerceptorInteresesField(StrEnum):
    """Closed fields of one Modelo 296 perceptor-intereses row.

    AEAT's alternative Tipo 2 hoja (TIPO DE HOJA ``F``) for intereses y otras rentas,
    emitted once per perceptor of that type. Its single payload field is the aggregate
    of retenciones ingresadas across the Estado, the Diputaciones Forales del Pais
    Vasco and the Comunidad Foral de Navarra.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    EJERCICIO = "ejercicio"
    F_J = "f_j"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    RETENCIONES_E_INGRESOS_A_CUENTA_INGRES = "retenciones_e_ingresos_a_cuenta_ingres"


class M296PerceptorInteresesProjectionRef(BaseModel):
    """One field of a Modelo 296 perceptor-intereses row.

    No slot: the record repeats and the render occurrence identifies the perceptor.
    See :class:`M296PerceptorProjectionRef` for why that is the right axis here.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_perceptor_intereses"]
    field: M296PerceptorInteresesField


class M296AnexoPagoField(StrEnum):
    """Closed fields of one Modelo 296 anexo A row: a pago to one contribuyente.

    AEAT's "Anexo - Valores Negociables. Relacion de Pago a Contribuyentes" is a
    relacion -- a list -- and each row carries its own ISIN, fecha de devengo,
    contribuyente identity, importe, porcentaje and retenciones, beneath perceptor
    header fields that AEAT restates on every row.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "apellidos_y_nombre_razon_social_o_deno_2"
    CIUDAD = "ciudad"
    CLAVE_DE_PERSONALIDAD_DEL_CONTRIBUYENT = "clave_de_personalidad_del_contribuyent"
    CODIGO_ISIN = "codigo_isin"
    CODIGO_LEI_DEL_CONTRIBUYENTE = "codigo_lei_del_contribuyente"
    CODIGO_PAIS = "codigo_pais"
    DIRECCION_DEL_CONTRIBUYENTE = "direccion_del_contribuyente"
    EJERCICIO = "ejercicio"
    F_J = "f_j"
    FECHA_DE_DEVENGO = "fecha_de_devengo"
    FECHA_DE_NACIMIENTO_DEL_CONTRIBUYENTE = "fecha_de_nacimiento_del_contribuyente"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    IMPORTE_DEL_PAGO_AL_CONTRIBUYENTE = "importe_del_pago_al_contribuyente"
    NIF_DEL_CONTRIBUYENTE = "nif_del_contribuyente"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL_DE = "nif_en_el_pais_de_residencia_fiscal_de"
    NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "numero_de_justificante_del_modelo_210"
    PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "pais_o_territorio_de_residencia_fiscal"
    PORCENTAJE_DE_RETENCION = "porcentaje_de_retencion"
    RETENCIONES = "retenciones"


class M296AnexoPagoProjectionRef(BaseModel):
    """One field of a Modelo 296 anexo A pago row.

    No slot: the record repeats once per pago and the render occurrence identifies it.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_anexo_pago"]
    field: M296AnexoPagoField


class M296AnexoCertificadoField(StrEnum):
    """Closed fields of one Modelo 296 anexo B row: one certificado de pago.

    AEAT's "Anexo - Valores Negociables. Relacion de Certificados de Pago" is a
    relacion, one row per certificado, each carrying its ISIN, codigo cuenta de
    valores, titular registral, numero de titulos, fecha de pago, importe bruto and
    retencion.

    Several member names are opaque -- ``entero``, ``decimal``, ``entero_2`` and their
    siblings -- because AEAT's design splits a money field into entera and decimal
    sub-columns and the source slug took the sub-column heading rather than the parent
    field name. The parent each belongs to is recorded on the member.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "apellidos_y_nombre_razon_social_o_deno_2"
    CODIGO_CUENTA_VALORES_DEL_CERTIFICADO = "codigo_cuenta_valores_del_certificado"
    CODIGO_ISIN_DEL_CERTIFICADO = "codigo_isin_del_certificado"
    CODIGO_LEI_DEL_TITULAR_REGISTRAL = "codigo_lei_del_titular_registral"
    #: IMPORTE BRUTO DE LA RENTA DEL CERTIFICADO, decimal.
    DECIMAL = "decimal"
    #: RETENCION DEL CERTIFICADO, decimal.
    DECIMAL_2 = "decimal_2"
    #: PORCENTAJE DE RETENCION DEL CERTIFICADO, decimal.
    DECIMAL_3 = "decimal_3"
    EJERCICIO = "ejercicio"
    #: IMPORTE BRUTO DE LA RENTA DEL CERTIFICADO, entera.
    ENTERO = "entero"
    #: RETENCION DEL CERTIFICADO, entera.
    ENTERO_2 = "entero_2"
    #: PORCENTAJE DE RETENCION DEL CERTIFICADO, entera.
    ENTERO_3 = "entero_3"
    F_J = "f_j"
    FECHA_DE_PAGO = "fecha_de_pago"
    FECHA_DE_PRESENTACION_DEL_MODELO_210 = "fecha_de_presentacion_del_modelo_210"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "numero_de_justificante_del_modelo_210"
    #: NUMERO DE TITULOS EN LA CUENTA DE VALORES, decimal.
    PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS = "parte_decimal_del_numero_de_titulos"
    #: NUMERO DE TITULOS DEL CONTRIBUYENTE, decimal.
    PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS_2 = "parte_decimal_del_numero_de_titulos_2"
    #: NUMERO DE TITULOS EN LA CUENTA DE VALORES, entera.
    PARTE_ENTERA_DEL_NUMERO_DE_TITULOS = "parte_entera_del_numero_de_titulos"
    #: NUMERO DE TITULOS DEL CONTRIBUYENTE, entera.
    PARTE_ENTERA_DEL_NUMERO_DE_TITULOS_2 = "parte_entera_del_numero_de_titulos_2"
    TITULAR_REGISTRAL_DE_LA_CUENTA_DE_VALO = "titular_registral_de_la_cuenta_de_valo"


class M296AnexoCertificadoProjectionRef(BaseModel):
    """One field of a Modelo 296 anexo B certificado row.

    No slot: the record repeats once per certificado and the occurrence identifies it.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_anexo_certificado"]
    field: M296AnexoCertificadoField
