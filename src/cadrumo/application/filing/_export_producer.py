"""Producer-value projection for the declaration export renderer."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.filing_producer_key import FilingProducerKey
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.prorrata_register import ProrrataEspecialTransitionKind
from ...domain.deadlines.models import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ...domain.filing.errors import FilingExportValidationError
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ._producer_ownership import filing_producer_ownership as _filing_producer_ownership
from ._producer_snapshot import (
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    M303FilingFacts,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    Modelo200ProfileFacts,
    Modelo202ProducerProfile,
    Modelo210ProfileFacts,
    Modelo222ProfileFacts,
    Modelo296ProfileFacts,
    Modelo353ProfileFacts,
    RefundAccountSelection,
)


@dataclass(frozen=True)
class SelectedAccountLexicals:
    iban: str | None = None
    swift_bic: str | None = None
    bank_name: str | None = None
    bank_address: str | None = None
    bank_city: str | None = None
    bank_country_code: str | None = None


@dataclass(frozen=True)
class M303ProfileLexicals:
    redeme_enrolled: str | None = None
    exclusively_foral: str | None = None
    regime_composition_code: str | None = None
    cash_accounting_regime_enrolled: str | None = None
    voluntary_sii_enrolled: str | None = None
    hydrocarbon_deposit_advance_payment_deduction_entitled: str | None = None
    is_foral: bool = False


@dataclass(frozen=True)
class M303FilingLexicals:
    joint_return_elected: str | None = None
    annual_volume_nonzero: str | None = None
    recipient_of_cash_accounting_operations: str | None = None
    prorrata_special_option: str | None = None
    prorrata_special_revocation: str | None = None
    insolvency_declared: str | None = None
    insolvency_judicial_order_date: str | None = None
    insolvency_filing_subtype: str | None = None
    exonerado_390_applicable: str | None = None
    prorrata_transition_applicable: bool = False


@dataclass(frozen=True)
class M303ForalLexicals:
    prorrata_special_option: str | None
    prorrata_special_revocation: str | None


_M296_DECLARANTE_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M296_DEC_EJERCICIO: "ejercicio",
    FilingProducerKey.M296_DEC_NIF_DEL_DECLARANTE: "nif_del_declarante",
    FilingProducerKey.M296_DEC_APELLIDOS_Y_NOMBRE_O_RAZON_SOCIAL_DEL: "apellidos_y_nombre_o_razon_social_del",
    FilingProducerKey.M296_DEC_TIPO_DE_SOPORTE: "tipo_de_soporte",
    FilingProducerKey.M296_DEC_TELEFONO: "telefono",
    FilingProducerKey.M296_DEC_APELLIDOS_Y_NOMBRE: "apellidos_y_nombre",
    FilingProducerKey.M296_DEC_NUMERO_IDENTIFICATIVO_DE_LA_DECLARACIO: "numero_identificativo_de_la_declaracio",
    FilingProducerKey.M296_DEC_DECLARACION_COMPLEMENTARIA_O_SUSTITUTI: "declaracion_complementaria_o_sustituti",
    FilingProducerKey.M296_DEC_NUMERO_IDENTIFICATIVO_DE_LA_DECLARACIO_2: "numero_identificativo_de_la_declaracio_2",
    FilingProducerKey.M296_DEC_NUMERO_TOTAL_DE_PERCEPTORES: "numero_total_de_perceptores",
    FilingProducerKey.M296_DEC_N: "n",
    FilingProducerKey.M296_DEC_SELLO_ELECTRONICO: "sello_electronico",
}


_SHARED_SNAPSHOT_PRODUCER_KEYS = frozenset(
    {
        FilingProducerKey.PRESENTER_TAX_ID,
        FilingProducerKey.FILING_RESULT_DISPOSITION,
        FilingProducerKey.TAXPAYER_TAX_ID,
        FilingProducerKey.TAXPAYER_LEGAL_NAME,
        FilingProducerKey.TAXPAYER_GIVEN_NAME,
        FilingProducerKey.TAXPAYER_SURNAMES,
        FilingProducerKey.TAXPAYER_FULL_NAME,
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME,
        FilingProducerKey.CONTACT_PERSON_PHONE,
        FilingProducerKey.CONTACT_PERSON_NAME,
        FilingProducerKey.CONTACT_PERSON_SECONDARY_PHONE,
        FilingProducerKey.CONTACT_PERSON_EMAIL,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_2,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_3,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_4,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_5,
        FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_6,
        FilingProducerKey.M200_ABONO_COMPENSACION_ABONO_POR_CONVERSION_DE_A,
        FilingProducerKey.M200_ABONO_COMPENSACION_COMPENSACION_POR_CONVERSI,
        FilingProducerKey.M200_APELLIDOS_Y_NOMBRE,
        FilingProducerKey.M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACION_DE,
        FilingProducerKey.M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACIONES_E,
        FilingProducerKey.M200_BALANCE_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREV,
        FilingProducerKey.M200_CODIGO_CNAE_2025_ACTIVIDAD_PRINCIPAL,
        FilingProducerKey.M200_CODIGO_PAIS_COUNTRY_CODE,
        FilingProducerKey.M200_COMO_CONSECUENCIA_DE_LA_PRESENTACION_DE_LA_A,
        FilingProducerKey.M200_CUENTA_BANCARIA_BANCO_BANK_NAME,
        FilingProducerKey.M200_CUENTA_BANCARIA_CIUDAD_CITY,
        FilingProducerKey.M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC,
        FilingProducerKey.M200_CUENTA_BANCARIA_MARCA_SEPA,
        FilingProducerKey.M200_CUENTA_CORRIENTE_TRIBUTARIA,
        FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NIF,
        FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NOMBRE_DE,
        FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_RAZON_SOC,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_10,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_11,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_12,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_13,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_14,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_15,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_16,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_17,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_18,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_19,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_2,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_20,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_21,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_22,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_23,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_24,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_25,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_26,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_3,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_4,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_5,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_6,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_7,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_8,
        FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_9,
        FilingProducerKey.M200_DIRECCION_DE_CORREO_ELECTRONICO_PARA_INCIDEN,
        FilingProducerKey.M200_DIRECCION_DEL_BANCO_BANK_ADDRESS,
        FilingProducerKey.M200_ECPN_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREVIAD,
        FilingProducerKey.M200_EJERCICIO,
        FilingProducerKey.M200_ENTIDAD_CUYO_IMPORTE_NETO_DE_LA_CIFRA_DE_NEG,
        FilingProducerKey.M200_ENTIDAD_SIN_OBLIGACION_DE_IDENTIFICAR_EL_TIT,
        FilingProducerKey.M200_F_IDENTIFICACION_DEL_TITULAR_REAL_DE_LA_ENTI,
        FilingProducerKey.M200_FECHA_DE_NACIMIENTO,
        FilingProducerKey.M200_IDENTIFICACION_EJERCICIO,
        FilingProducerKey.M200_IDENTIFICACION_TIPO_DE_EJERCICIO,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_2,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_3,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_4,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_5,
        FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_6,
        FilingProducerKey.M200_IMPORTE_A_DEVOLVER,
        FilingProducerKey.M200_IMPORTE_A_INGRESAR,
        FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS,
        FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_2,
        FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_3,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_2,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_3,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_4,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_5,
        FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_6,
        FilingProducerKey.M200_INOPERATIVIDAD_DEL_ORDEN_DE_CUMPLIMENTACION,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_2,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_3,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_4,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_5,
        FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_6,
        FilingProducerKey.M200_MODALIDAD_DE_INGRESO_UNO_DE_LOS_SIGUIENTES_V,
        FilingProducerKey.M200_MODELO_DE_ESTADOS_CONTABLES_QUE_SE_VA_A_CUMP,
        FilingProducerKey.M200_N_I_F_DE_LA_SOCIEDAD_REPRESENTANTE_DOMINANTE,
        FilingProducerKey.M200_NIF_CODIGO_DE_IDENTIFICACION_EXTRANJERO,
        FilingProducerKey.M200_NIF_EN_EL_PAIS_DE_RESIDENCIA_TIN,
        FilingProducerKey.M200_NO_IDENTIFICACION_DE_LA_SOCIEDAD_DOMINANTE_E,
        FilingProducerKey.M200_NO_RESIDENTES_MAS_DE_UN_ESTABLECIMIENTO_PERM,
        FilingProducerKey.M200_NOMBRE_Y_APELLIDOS_DE_LA_PERSONA_DE_CONTACTO,
        FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN,
        FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN_2,
        FilingProducerKey.M200_NUMERO_DE_PERIODO_IMPOSITIVO,
        FilingProducerKey.M200_PAIS_DE_EXPEDICION_DEL_DOCUMENTO_DE_IDENTIFI,
        FilingProducerKey.M200_PAIS_DE_RESIDENCIA,
        FilingProducerKey.M200_PAIS_DE_RESIDENCIA_2,
        FilingProducerKey.M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS,
        FilingProducerKey.M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS_2,
        FilingProducerKey.M200_PERDIDAS_Y_GANANCIAS_0_NO_CONSTA_1_MOD_NORMA,
        FilingProducerKey.M200_PERIODO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_ANO_FINAL,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_ANO_INICIO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_DIA_FINAL,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_DIA_INICIO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_ANO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_DIA,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_MES,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_ANO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_DIA,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_MES,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_MES_FINAL,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_MES_INICIO,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_2,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_3,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_4,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_5,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_6,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_7,
        FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_8,
        FilingProducerKey.M200_REALIZA_ACTIVIDADES_AGRICOLAS_Y_O_GANADERAS,
        FilingProducerKey.M200_REG_ENTIDADES_NAVIERAS_EN_FUNCION_DEL_TONELA,
        FilingProducerKey.M200_RENUNCIA_O_POR_TRANSFERENCIA,
        FilingProducerKey.M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN,
        FilingProducerKey.M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN_2,
        FilingProducerKey.M200_RESULTADO_CERO,
        FilingProducerKey.M200_SOCIMIS_REGIMEN_FISCAL_DE_ENTRADA_SALIDA_REN,
        FilingProducerKey.M200_TIPO_DE_DECLARACION_VER_NOTA,
        FilingProducerKey.M200_TIPO_DE_EJERCICIO,
        FilingProducerKey.M200_TIPO_DOCUMENTO_IDENTIFICATIVO,
        FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_CITY,
        FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_COUNTRY_CODE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_DATE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_CITY,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COMPLEMENT,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COUNTRY_CODE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_EMAIL,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_FAX,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_MOBILE_PHONE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_PHONE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_POSTAL_CODE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_REGION,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_STREET,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_TAX_ID,
        FilingProducerKey.IRNR_CONTRIBUYENTE_FULL_NAME,
        FilingProducerKey.IRNR_CONTRIBUYENTE_PERSON_TYPE,
        FilingProducerKey.IRNR_CONTRIBUYENTE_TAX_ID,
        FilingProducerKey.IRNR_CONTRIBUYENTE_TAX_RESIDENCE_COUNTRY_CODE,
        FilingProducerKey.IRNR_DECLARACION_TIPO,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_CONTRIBUYENTE,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_DEPOSITARIO,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_GESTOR,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_PAGADOR,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_REPRESENTANTE,
        FilingProducerKey.IRNR_DECLARANTE_CAPACITY_RETENEDOR,
        FilingProducerKey.IRNR_DECLARANTE_FULL_NAME,
        FilingProducerKey.IRNR_DECLARANTE_TAX_ID,
        FilingProducerKey.IRNR_DEVENGO_AGRUPACION,
        FilingProducerKey.IRNR_DEVENGO_FECHA_DEVENGO,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_BANCO,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_CIUDAD,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_CODIGO_PAIS,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_DIRECCION_BANCO,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_NUMERO_CUENTA,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_SWIFT_BIC,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_SEPA_IBAN,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_SEPA_SWIFT_BIC,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_TITULAR_FULL_NAME,
        FilingProducerKey.IRNR_DEVOLUCION_CUENTA_TITULAR_TAX_ID,
        FilingProducerKey.IRNR_DEVOLUCION_RENUNCIA_A_FAVOR_DEL_TESORO,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CONYUGE_FULL_NAME,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CONYUGE_TAX_ID,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONTRIBUYENTE,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONYUGE,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_FECHA_ADQUISICION,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_FECHA_MEJORA,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_JUSTIFICANTE_MODELO_211,
        FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_TITULARIDAD,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_BANCO,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_CIUDAD,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_CODIGO_PAIS,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_DIRECCION_BANCO,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_NUMERO_CUENTA,
        FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_SWIFT_BIC,
        FilingProducerKey.IRNR_INGRESO_CUENTA_SEPA_IBAN,
        FilingProducerKey.IRNR_INGRESO_CUENTA_SEPA_SWIFT_BIC,
        FilingProducerKey.IRNR_INGRESO_CUENTA_TITULAR_FULL_NAME,
        FilingProducerKey.IRNR_INGRESO_CUENTA_TITULAR_TAX_ID,
        FilingProducerKey.IRNR_INGRESO_FORMA_PAGO,
        FilingProducerKey.IRNR_INMUEBLE_REFERENCIA_CATASTRAL,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_BLOQUE,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_CALIFICADOR_NUMERO,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_INE_MUNICIPIO,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_POSTAL,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_PROVINCIA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_DATOS_COMPLEMENTARIOS,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_ESCALERA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_LOCALIDAD,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_NOMBRE_VIA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_NUMERO_CASA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_PLANTA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_PORTAL,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_PUERTA,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_TIPO_NUMERACION,
        FilingProducerKey.IRNR_INMUEBLE_SITUACION_TIPO_VIA,
        FilingProducerKey.IRNR_PAGADOR_FULL_NAME,
        FilingProducerKey.IRNR_PAGADOR_PERSON_TYPE,
        FilingProducerKey.IRNR_PAGADOR_TAX_ID,
        FilingProducerKey.IRNR_RENTA_CLAVE_DIVISA,
        FilingProducerKey.IRNR_REPRESENTANTE_APPOINTMENT_KIND,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_BLOQUE,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CALIFICADOR_NUMERO,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_INE_MUNICIPIO,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_POSTAL,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_PROVINCIA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_DATOS_COMPLEMENTARIOS,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_ESCALERA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_LOCALIDAD,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_NOMBRE_VIA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_NUMERO_CASA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PLANTA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PORTAL,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PUERTA,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_TIPO_NUMERACION,
        FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_TIPO_VIA,
        FilingProducerKey.IRNR_REPRESENTANTE_FAX,
        FilingProducerKey.IRNR_REPRESENTANTE_FULL_NAME,
        FilingProducerKey.IRNR_REPRESENTANTE_MOBILE_PHONE,
        FilingProducerKey.IRNR_REPRESENTANTE_PERSON_TYPE,
        FilingProducerKey.IRNR_REPRESENTANTE_PHONE,
        FilingProducerKey.IRNR_REPRESENTANTE_TAX_ID,
        FilingProducerKey.IRNR_SIN_INGRESO_NI_DEVOLUCION_CUOTA_CERO,
        FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA,
        FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA,
        FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT,
        FilingProducerKey.AMENDMENT_SUSTITUTIVA_OR_COMPLEMENTARIA_MARKER,
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES,
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO,
        FilingProducerKey.SELECTED_ACCOUNT_IBAN,
        FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE,
        FilingProducerKey.PRIOR_DOMICILIATION_ACTION,
        FilingProducerKey.M303_REDEME_ENROLLED,
        FilingProducerKey.M303_EXCLUSIVELY_FORAL,
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO,
        FilingProducerKey.M303_JOINT_RETURN_ELECTED,
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED,
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS,
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION,
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION,
        FilingProducerKey.M303_INSOLVENCY_DECLARED,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE,
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED,
        FilingProducerKey.M111_COLEGIO_CONCERTADO,
        FilingProducerKey.M222_NUMERO_GRUPO,
        FilingProducerKey.M222_REPRESENTANTE_O_DOMINANTE,
        FilingProducerKey.M222_NORMATIVA_TERRITORIO_FORAL,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_IDENTIFICACION,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_PAIS_TERRITORIO_FORAL,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_RAZON_SOCIAL,
        FilingProducerKey.M222_FECHA_INICIO_PERIODO_IMPOSITIVO,
        FilingProducerKey.M222_CNAE_ACTIVIDAD_PRINCIPAL,
        FilingProducerKey.M222_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE,
        FilingProducerKey.M222_REGIMEN_REDUCIDA_DIMENSION,
        FilingProducerKey.M222_CIFRA_NEGOCIOS_GRUPO_DOCE_MESES,
        FilingProducerKey.M222_COOPERATIVA_FISCALMENTE_PROTEGIDA,
        FilingProducerKey.M222_REGIMEN_ENTIDADES_CAPITAL_RIESGO,
        FilingProducerKey.M222_CIRCUNSTANCIA_CONCURRENTE,
        FilingProducerKey.M222_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_TRAMO,
        FilingProducerKey.M222_MULTIPLES_TIPOS_IMPOSITIVOS,
        FilingProducerKey.M222_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES,
        FilingProducerKey.M222_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO,
        FilingProducerKey.M222_MODALIDAD_LIQUIDACION,
        FilingProducerKey.M222_COMUNICACION_DATOS_ADICIONALES,
        FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES,
        FilingProducerKey.M222_COMUNICACION_VARIACION_COMPOSICION_GRUPO,
        FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES_VARIACION,
        FilingProducerKey.M353_NUMERO_GRUPO,
        FilingProducerKey.M353_REGIMEN_ESPECIAL_AVANZADO_ELECTED,
        FilingProducerKey.M353_REGIMEN_ESPECIAL_INSCRITO_REDEME,
        FilingProducerKey.M353_SIN_ACTIVIDAD,
        FilingProducerKey.M353_GRUPO_NORMATIVA_FORAL,
        FilingProducerKey.M202_CNAE_ACTIVIDAD_PRINCIPAL,
        FilingProducerKey.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS,
        FilingProducerKey.M202_REGIMEN_LEY_11_2009_SOCIMI,
        FilingProducerKey.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE,
        FilingProducerKey.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION,
        FilingProducerKey.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO,
        FilingProducerKey.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL,
        FilingProducerKey.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL,
        FilingProducerKey.M202_COOPERATIVA_O_MULTIPLES_TIPOS,
        FilingProducerKey.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA,
        FilingProducerKey.M202_MULTIPLES_TIPOS_IMPOSITIVOS,
        FilingProducerKey.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES,
        FilingProducerKey.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO,
        FilingProducerKey.M202_MARCA_INSTRUMENTAL,
        FilingProducerKey.M202_DISCRIMINANTE_DECLARACION_NEGATIVA,
        FilingProducerKey.M202_NORMATIVA_TERRITORIO_FORAL,
        FilingProducerKey.M202_COMUNICACION_DATOS_ADICIONALES,
        FilingProducerKey.M202_NUMERO_REFERENCIA_SOCIEDADES,
        # Derived from the resolver's own map rather than restated: a second copy
        # here would let the ownership claim and the resolver drift apart, and the
        # exhaustiveness assertion below would then fire on a key one of them forgot.
        *_M296_DECLARANTE_FIELD_BY_KEY,
    }
)


_M222_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M222_NUMERO_GRUPO: "numero_grupo",
    FilingProducerKey.M222_REPRESENTANTE_O_DOMINANTE: "representante_o_dominante",
    FilingProducerKey.M222_NORMATIVA_TERRITORIO_FORAL: "normativa_territorio_foral",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_IDENTIFICACION: "entidad_dominante_identificacion",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_PAIS_TERRITORIO_FORAL: "entidad_dominante_pais_territorio_foral",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_RAZON_SOCIAL: "entidad_dominante_razon_social",
    FilingProducerKey.M222_FECHA_INICIO_PERIODO_IMPOSITIVO: "fecha_inicio_periodo_impositivo",
    FilingProducerKey.M222_CNAE_ACTIVIDAD_PRINCIPAL: "cnae_actividad_principal",
    FilingProducerKey.M222_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "regimen_entidades_navieras_tonelaje",
    FilingProducerKey.M222_REGIMEN_REDUCIDA_DIMENSION: "regimen_reducida_dimension",
    FilingProducerKey.M222_CIFRA_NEGOCIOS_GRUPO_DOCE_MESES: "cifra_negocios_grupo_doce_meses",
    FilingProducerKey.M222_COOPERATIVA_FISCALMENTE_PROTEGIDA: "cooperativa_fiscalmente_protegida",
    FilingProducerKey.M222_REGIMEN_ENTIDADES_CAPITAL_RIESGO: "regimen_entidades_capital_riesgo",
    FilingProducerKey.M222_CIRCUNSTANCIA_CONCURRENTE: "circunstancia_concurrente",
    FilingProducerKey.M222_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_TRAMO: "cifra_negocios_periodo_anterior_tramo",
    FilingProducerKey.M222_MULTIPLES_TIPOS_IMPOSITIVOS: "multiples_tipos_impositivos",
    FilingProducerKey.M222_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES: "tipo_gravamen_impuesto_sociedades",
    FilingProducerKey.M222_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO: "importe_neto_cifra_negocios_tramo",
    FilingProducerKey.M222_MODALIDAD_LIQUIDACION: "modalidad_liquidacion",
    FilingProducerKey.M222_COMUNICACION_DATOS_ADICIONALES: "comunicacion_datos_adicionales",
    FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES: "numero_referencia_sociedades",
    FilingProducerKey.M222_COMUNICACION_VARIACION_COMPOSICION_GRUPO: "comunicacion_variacion_composicion_grupo",
    FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES_VARIACION: "numero_referencia_sociedades_variacion",
}


def m222_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the grupo-fiscal producer identities Modelo 222's layout cites.

    Every one of these keys was declared in the vocabulary and produced by nothing, so the
    layout's twenty-three header fields -- numero de grupo and entidad dominante among
    them -- rendered blank on a return that exists to identify a fiscal group.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 222's snapshot validator may decide
    that a 222 filing without group facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo222ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M222_FIELD_BY_KEY.items()
    }


def m296_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the declarante identities Modelo 296's tipo-1 record cites.

    All twelve ``m296.dec.*`` keys were declared in the vocabulary and produced by nothing,
    so the ejercicio, the declarante NIF and the razon social rendered blank on the IRNR
    annual withholding summary.

    This covers the declarante record only. The four detail records -- perceptor,
    perceptor-intereses and the two anexos -- cite a further hundred keys that are NOT
    header facts: they are per-payee and per-pago rows, and each of those records is
    published as a single non-repeating record, so a resolver here would put one payee into
    a one-row layout and drop the rest. They are deliberately left unresolved until the
    records repeat.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 296's snapshot validator may decide
    that a 296 filing without declarante facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo296ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None)
        for key, field in _M296_DECLARANTE_FIELD_BY_KEY.items()
    }


_M353_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M353_NUMERO_GRUPO: "numero_grupo",
    FilingProducerKey.M353_REGIMEN_ESPECIAL_AVANZADO_ELECTED: "regimen_especial_avanzado_elected",
    FilingProducerKey.M353_REGIMEN_ESPECIAL_INSCRITO_REDEME: "regimen_especial_inscrito_redeme",
    FilingProducerKey.M353_SIN_ACTIVIDAD: "sin_actividad",
    FilingProducerKey.M353_GRUPO_NORMATIVA_FORAL: "grupo_normativa_foral",
}


def m353_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the grupo de entidades producer identities Modelo 353's layout cites.

    All five ``m353.*`` keys were declared in the vocabulary and produced by nothing, so
    the número de grupo at offset 109 and the sin-actividad and normativa-foral marks
    rendered blank on the aggregate return of a régimen especial del grupo de entidades.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 353's snapshot validator may decide
    that a 353 filing without group facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo353ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M353_FIELD_BY_KEY.items()
    }


_M202_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M202_CNAE_ACTIVIDAD_PRINCIPAL: "principal_cnae",
    FilingProducerKey.M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS: "regimen_ley_49_2002_sin_fines_lucrativos",
    FilingProducerKey.M202_REGIMEN_LEY_11_2009_SOCIMI: "regimen_ley_11_2009_socimi",
    FilingProducerKey.M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "regimen_entidades_navieras_tonelaje",
    FilingProducerKey.M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION: "regimen_articulo_101_lis_reducida_dimension",
    FilingProducerKey.M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO: "regimen_entidad_capital_riesgo",
    FilingProducerKey.M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL: "cifra_negocios_doce_meses_umbral",
    FilingProducerKey.M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL: "cifra_negocios_periodo_anterior_bajo_umbral",
    FilingProducerKey.M202_COOPERATIVA_O_MULTIPLES_TIPOS: "cooperativa_o_multiples_tipos",
    FilingProducerKey.M202_COOPERATIVA_FISCALMENTE_PROTEGIDA: "cooperativa_fiscalmente_protegida",
    FilingProducerKey.M202_MULTIPLES_TIPOS_IMPOSITIVOS: "multiples_tipos_impositivos",
    FilingProducerKey.M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES: "tipo_gravamen_impuesto_sociedades",
    FilingProducerKey.M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO: "importe_neto_cifra_negocios_tramo",
    FilingProducerKey.M202_MARCA_INSTRUMENTAL: "marca_instrumental",
    FilingProducerKey.M202_DISCRIMINANTE_DECLARACION_NEGATIVA: "discriminante_declaracion_negativa",
    FilingProducerKey.M202_NORMATIVA_TERRITORIO_FORAL: "normativa_territorio_foral",
    FilingProducerKey.M202_COMUNICACION_DATOS_ADICIONALES: "comunicacion_datos_adicionales",
    FilingProducerKey.M202_NUMERO_REFERENCIA_SOCIEDADES: "numero_referencia_sociedades",
}


def m202_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the régimen marks and principal CNAE modelo 202's layout cites.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    runs for every modelo, and only modelo 202's own snapshot validator may decide that a
    202 filing without these facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo202ProducerProfile) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M202_FIELD_BY_KEY.items()
    }


_M210_SCOPE_FIELD_BY_KEY: dict[FilingProducerKey, tuple[str, str]] = {
    FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_CITY: ("contribuyente", "birth_city"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_COUNTRY_CODE: ("contribuyente", "birth_country_code"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_BIRTH_DATE: ("contribuyente", "birth_date"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_CITY: ("contribuyente", "foreign_address_city"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COMPLEMENT: ("contribuyente", "foreign_address_complement"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COUNTRY_CODE: (
        "contribuyente",
        "foreign_address_country_code",
    ),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_EMAIL: ("contribuyente", "foreign_address_email"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_FAX: ("contribuyente", "foreign_address_fax"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_MOBILE_PHONE: (
        "contribuyente",
        "foreign_address_mobile_phone",
    ),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_PHONE: ("contribuyente", "foreign_address_phone"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_POSTAL_CODE: ("contribuyente", "foreign_address_postal_code"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_REGION: ("contribuyente", "foreign_address_region"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_STREET: ("contribuyente", "foreign_address_street"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FOREIGN_TAX_ID: ("contribuyente", "foreign_tax_id"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_FULL_NAME: ("contribuyente", "full_name"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_PERSON_TYPE: ("contribuyente", "person_type"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_TAX_ID: ("contribuyente", "tax_id"),
    FilingProducerKey.IRNR_CONTRIBUYENTE_TAX_RESIDENCE_COUNTRY_CODE: ("contribuyente", "tax_residence_country_code"),
    FilingProducerKey.IRNR_DECLARACION_TIPO: ("declaracion", "tipo"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_CONTRIBUYENTE: ("declarante", "capacity_contribuyente"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_DEPOSITARIO: ("declarante", "capacity_depositario"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_GESTOR: ("declarante", "capacity_gestor"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_PAGADOR: ("declarante", "capacity_pagador"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_REPRESENTANTE: ("declarante", "capacity_representante"),
    FilingProducerKey.IRNR_DECLARANTE_CAPACITY_RETENEDOR: ("declarante", "capacity_retenedor"),
    FilingProducerKey.IRNR_DECLARANTE_FULL_NAME: ("declarante", "full_name"),
    FilingProducerKey.IRNR_DECLARANTE_TAX_ID: ("declarante", "tax_id"),
    FilingProducerKey.IRNR_DEVENGO_AGRUPACION: ("devengo", "agrupacion"),
    FilingProducerKey.IRNR_DEVENGO_FECHA_DEVENGO: ("devengo", "fecha_devengo"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_BANCO: ("devolucion", "cuenta_resto_banco"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_CIUDAD: ("devolucion", "cuenta_resto_ciudad"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_CODIGO_PAIS: ("devolucion", "cuenta_resto_codigo_pais"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_DIRECCION_BANCO: ("devolucion", "cuenta_resto_direccion_banco"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_NUMERO_CUENTA: ("devolucion", "cuenta_resto_numero_cuenta"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_RESTO_SWIFT_BIC: ("devolucion", "cuenta_resto_swift_bic"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_SEPA_IBAN: ("devolucion", "cuenta_sepa_iban"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_SEPA_SWIFT_BIC: ("devolucion", "cuenta_sepa_swift_bic"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_TITULAR_FULL_NAME: ("devolucion", "cuenta_titular_full_name"),
    FilingProducerKey.IRNR_DEVOLUCION_CUENTA_TITULAR_TAX_ID: ("devolucion", "cuenta_titular_tax_id"),
    FilingProducerKey.IRNR_DEVOLUCION_RENUNCIA_A_FAVOR_DEL_TESORO: ("devolucion", "renuncia_a_favor_del_tesoro"),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CONYUGE_FULL_NAME: ("ganancia_inmobiliaria", "conyuge_full_name"),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CONYUGE_TAX_ID: ("ganancia_inmobiliaria", "conyuge_tax_id"),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONTRIBUYENTE: (
        "ganancia_inmobiliaria",
        "cuota_participacion_contribuyente",
    ),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONYUGE: (
        "ganancia_inmobiliaria",
        "cuota_participacion_conyuge",
    ),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_FECHA_ADQUISICION: ("ganancia_inmobiliaria", "fecha_adquisicion"),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_FECHA_MEJORA: ("ganancia_inmobiliaria", "fecha_mejora"),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_JUSTIFICANTE_MODELO_211: (
        "ganancia_inmobiliaria",
        "justificante_modelo_211",
    ),
    FilingProducerKey.IRNR_GANANCIA_INMOBILIARIA_TITULARIDAD: ("ganancia_inmobiliaria", "titularidad"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_BANCO: ("ingreso", "cuenta_resto_banco"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_CIUDAD: ("ingreso", "cuenta_resto_ciudad"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_CODIGO_PAIS: ("ingreso", "cuenta_resto_codigo_pais"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_DIRECCION_BANCO: ("ingreso", "cuenta_resto_direccion_banco"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_NUMERO_CUENTA: ("ingreso", "cuenta_resto_numero_cuenta"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_RESTO_SWIFT_BIC: ("ingreso", "cuenta_resto_swift_bic"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_SEPA_IBAN: ("ingreso", "cuenta_sepa_iban"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_SEPA_SWIFT_BIC: ("ingreso", "cuenta_sepa_swift_bic"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_TITULAR_FULL_NAME: ("ingreso", "cuenta_titular_full_name"),
    FilingProducerKey.IRNR_INGRESO_CUENTA_TITULAR_TAX_ID: ("ingreso", "cuenta_titular_tax_id"),
    FilingProducerKey.IRNR_INGRESO_FORMA_PAGO: ("ingreso", "forma_pago"),
    FilingProducerKey.IRNR_INMUEBLE_REFERENCIA_CATASTRAL: ("inmueble", "referencia_catastral"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_BLOQUE: ("inmueble", "situacion_bloque"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_CALIFICADOR_NUMERO: ("inmueble", "situacion_calificador_numero"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_INE_MUNICIPIO: ("inmueble", "situacion_codigo_ine_municipio"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_POSTAL: ("inmueble", "situacion_codigo_postal"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_CODIGO_PROVINCIA: ("inmueble", "situacion_codigo_provincia"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_DATOS_COMPLEMENTARIOS: ("inmueble", "situacion_datos_complementarios"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_ESCALERA: ("inmueble", "situacion_escalera"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_LOCALIDAD: ("inmueble", "situacion_localidad"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_NOMBRE_VIA: ("inmueble", "situacion_nombre_via"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_NUMERO_CASA: ("inmueble", "situacion_numero_casa"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_PLANTA: ("inmueble", "situacion_planta"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_PORTAL: ("inmueble", "situacion_portal"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_PUERTA: ("inmueble", "situacion_puerta"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_TIPO_NUMERACION: ("inmueble", "situacion_tipo_numeracion"),
    FilingProducerKey.IRNR_INMUEBLE_SITUACION_TIPO_VIA: ("inmueble", "situacion_tipo_via"),
    FilingProducerKey.IRNR_PAGADOR_FULL_NAME: ("pagador", "full_name"),
    FilingProducerKey.IRNR_PAGADOR_PERSON_TYPE: ("pagador", "person_type"),
    FilingProducerKey.IRNR_PAGADOR_TAX_ID: ("pagador", "tax_id"),
    FilingProducerKey.IRNR_RENTA_CLAVE_DIVISA: ("renta", "clave_divisa"),
    FilingProducerKey.IRNR_REPRESENTANTE_APPOINTMENT_KIND: ("representante", "appointment_kind"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_BLOQUE: ("representante", "domicilio_bloque"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CALIFICADOR_NUMERO: (
        "representante",
        "domicilio_calificador_numero",
    ),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_INE_MUNICIPIO: (
        "representante",
        "domicilio_codigo_ine_municipio",
    ),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_POSTAL: ("representante", "domicilio_codigo_postal"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_CODIGO_PROVINCIA: ("representante", "domicilio_codigo_provincia"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_DATOS_COMPLEMENTARIOS: (
        "representante",
        "domicilio_datos_complementarios",
    ),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_ESCALERA: ("representante", "domicilio_escalera"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_LOCALIDAD: ("representante", "domicilio_localidad"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_NOMBRE_VIA: ("representante", "domicilio_nombre_via"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_NUMERO_CASA: ("representante", "domicilio_numero_casa"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PLANTA: ("representante", "domicilio_planta"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PORTAL: ("representante", "domicilio_portal"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_PUERTA: ("representante", "domicilio_puerta"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_TIPO_NUMERACION: ("representante", "domicilio_tipo_numeracion"),
    FilingProducerKey.IRNR_REPRESENTANTE_DOMICILIO_TIPO_VIA: ("representante", "domicilio_tipo_via"),
    FilingProducerKey.IRNR_REPRESENTANTE_FAX: ("representante", "fax"),
    FilingProducerKey.IRNR_REPRESENTANTE_FULL_NAME: ("representante", "full_name"),
    FilingProducerKey.IRNR_REPRESENTANTE_MOBILE_PHONE: ("representante", "mobile_phone"),
    FilingProducerKey.IRNR_REPRESENTANTE_PERSON_TYPE: ("representante", "person_type"),
    FilingProducerKey.IRNR_REPRESENTANTE_PHONE: ("representante", "phone"),
    FilingProducerKey.IRNR_REPRESENTANTE_TAX_ID: ("representante", "tax_id"),
    FilingProducerKey.IRNR_SIN_INGRESO_NI_DEVOLUCION_CUOTA_CERO: ("sin_ingreso_ni_devolucion", "cuota_cero"),
}


def m210_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the twelve party, property and settlement scopes modelo 210's layout cites.

    A profile of the wrong type, or a scope the filing does not carry, yields ``None``
    rather than raising: AEAT writes an empty alphanumeric header field to blancos, and
    only a caller knows which scopes its filing has.
    """
    profile = model_profile if isinstance(model_profile, Modelo210ProfileFacts) else None
    values: dict[FilingProducerKey, object] = {}
    for key, (scope_name, field) in _M210_SCOPE_FIELD_BY_KEY.items():
        scope = getattr(profile, scope_name, None) if profile is not None else None
        values[key] = getattr(scope, field, None) if scope is not None else None
    return values


_M200_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio"
    ),
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_2: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio_2"
    ),
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_3: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio_3"
    ),
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_4: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio_4"
    ),
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_5: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio_5"
    ),
    FilingProducerKey.M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_6: (
        "apartado_6_deduc_evitar_doble_imposicion_participacio_6"
    ),
    FilingProducerKey.M200_ABONO_COMPENSACION_ABONO_POR_CONVERSION_DE_A: "abono_compensacion_abono_por_conversion_de_a",
    FilingProducerKey.M200_ABONO_COMPENSACION_COMPENSACION_POR_CONVERSI: "abono_compensacion_compensacion_por_conversi",
    FilingProducerKey.M200_APELLIDOS_Y_NOMBRE: "apellidos_y_nombre",
    FilingProducerKey.M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACION_DE: "b_2_suma_de_porcentajes_de_participacion_de",
    FilingProducerKey.M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACIONES_E: "b_2_suma_de_porcentajes_de_participaciones_e",
    FilingProducerKey.M200_BALANCE_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREV: "balance_0_no_consta_1_mod_normal_2_mod_abrev",
    FilingProducerKey.M200_CODIGO_CNAE_2025_ACTIVIDAD_PRINCIPAL: "codigo_cnae_2025_actividad_principal",
    FilingProducerKey.M200_CODIGO_PAIS_COUNTRY_CODE: "codigo_pais_country_code",
    FilingProducerKey.M200_COMO_CONSECUENCIA_DE_LA_PRESENTACION_DE_LA_A: "como_consecuencia_de_la_presentacion_de_la_a",
    FilingProducerKey.M200_CUENTA_BANCARIA_BANCO_BANK_NAME: "cuenta_bancaria_banco_bank_name",
    FilingProducerKey.M200_CUENTA_BANCARIA_CIUDAD_CITY: "cuenta_bancaria_ciudad_city",
    FilingProducerKey.M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC: "cuenta_bancaria_codigo_swift_bic",
    FilingProducerKey.M200_CUENTA_BANCARIA_MARCA_SEPA: "cuenta_bancaria_marca_sepa",
    FilingProducerKey.M200_CUENTA_CORRIENTE_TRIBUTARIA: "cuenta_corriente_tributaria",
    FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NIF: "datos_de_la_sociedad_matriz_ultima_nif",
    FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NOMBRE_DE: "datos_de_la_sociedad_matriz_ultima_nombre_de",
    FilingProducerKey.M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_RAZON_SOC: "datos_de_la_sociedad_matriz_ultima_razon_soc",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO: "deduccion_resto_del_grupo",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_10: "deduccion_resto_del_grupo_10",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_11: "deduccion_resto_del_grupo_11",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_12: "deduccion_resto_del_grupo_12",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_13: "deduccion_resto_del_grupo_13",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_14: "deduccion_resto_del_grupo_14",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_15: "deduccion_resto_del_grupo_15",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_16: "deduccion_resto_del_grupo_16",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_17: "deduccion_resto_del_grupo_17",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_18: "deduccion_resto_del_grupo_18",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_19: "deduccion_resto_del_grupo_19",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_2: "deduccion_resto_del_grupo_2",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_20: "deduccion_resto_del_grupo_20",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_21: "deduccion_resto_del_grupo_21",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_22: "deduccion_resto_del_grupo_22",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_23: "deduccion_resto_del_grupo_23",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_24: "deduccion_resto_del_grupo_24",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_25: "deduccion_resto_del_grupo_25",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_26: "deduccion_resto_del_grupo_26",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_3: "deduccion_resto_del_grupo_3",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_4: "deduccion_resto_del_grupo_4",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_5: "deduccion_resto_del_grupo_5",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_6: "deduccion_resto_del_grupo_6",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_7: "deduccion_resto_del_grupo_7",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_8: "deduccion_resto_del_grupo_8",
    FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO_9: "deduccion_resto_del_grupo_9",
    FilingProducerKey.M200_DIRECCION_DE_CORREO_ELECTRONICO_PARA_INCIDEN: "direccion_de_correo_electronico_para_inciden",
    FilingProducerKey.M200_DIRECCION_DEL_BANCO_BANK_ADDRESS: "direccion_del_banco_bank_address",
    FilingProducerKey.M200_ECPN_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREVIAD: "ecpn_0_no_consta_1_mod_normal_2_mod_abreviad",
    FilingProducerKey.M200_EJERCICIO: "ejercicio",
    FilingProducerKey.M200_ENTIDAD_CUYO_IMPORTE_NETO_DE_LA_CIFRA_DE_NEG: "entidad_cuyo_importe_neto_de_la_cifra_de_neg",
    FilingProducerKey.M200_ENTIDAD_SIN_OBLIGACION_DE_IDENTIFICAR_EL_TIT: "entidad_sin_obligacion_de_identificar_el_tit",
    FilingProducerKey.M200_F_IDENTIFICACION_DEL_TITULAR_REAL_DE_LA_ENTI: "f_identificacion_del_titular_real_de_la_enti",
    FilingProducerKey.M200_FECHA_DE_NACIMIENTO: "fecha_de_nacimiento",
    FilingProducerKey.M200_IDENTIFICACION_EJERCICIO: "identificacion_ejercicio",
    FilingProducerKey.M200_IDENTIFICACION_TIPO_DE_EJERCICIO: "identificacion_tipo_de_ejercicio",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO: "identificador_de_fin_de_registro",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_2: "identificador_de_fin_de_registro_2",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_3: "identificador_de_fin_de_registro_3",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_4: "identificador_de_fin_de_registro_4",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_5: "identificador_de_fin_de_registro_5",
    FilingProducerKey.M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_6: "identificador_de_fin_de_registro_6",
    FilingProducerKey.M200_IMPORTE_A_DEVOLVER: "importe_a_devolver",
    FilingProducerKey.M200_IMPORTE_A_INGRESAR: "importe_a_ingresar",
    FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS: "importe_neto_de_la_cifra_de_negocios_de_los",
    FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_2: (
        "importe_neto_de_la_cifra_de_negocios_de_los_2"
    ),
    FilingProducerKey.M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_3: (
        "importe_neto_de_la_cifra_de_negocios_de_los_3"
    ),
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG: "informacion_adicional_producciones_cinematog",
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_2: (
        "informacion_adicional_producciones_cinematog_2"
    ),
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_3: (
        "informacion_adicional_producciones_cinematog_3"
    ),
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_4: (
        "informacion_adicional_producciones_cinematog_4"
    ),
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_5: (
        "informacion_adicional_producciones_cinematog_5"
    ),
    FilingProducerKey.M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_6: (
        "informacion_adicional_producciones_cinematog_6"
    ),
    FilingProducerKey.M200_INOPERATIVIDAD_DEL_ORDEN_DE_CUMPLIMENTACION: "inoperatividad_del_orden_de_cumplimentacion",
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS: "inversiones_en_producciones_cinematograficas",
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_2: (
        "inversiones_en_producciones_cinematograficas_2"
    ),
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_3: (
        "inversiones_en_producciones_cinematograficas_3"
    ),
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_4: (
        "inversiones_en_producciones_cinematograficas_4"
    ),
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_5: (
        "inversiones_en_producciones_cinematograficas_5"
    ),
    FilingProducerKey.M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_6: (
        "inversiones_en_producciones_cinematograficas_6"
    ),
    FilingProducerKey.M200_MODALIDAD_DE_INGRESO_UNO_DE_LOS_SIGUIENTES_V: "modalidad_de_ingreso_uno_de_los_siguientes_v",
    FilingProducerKey.M200_MODELO_DE_ESTADOS_CONTABLES_QUE_SE_VA_A_CUMP: "modelo_de_estados_contables_que_se_va_a_cump",
    FilingProducerKey.M200_N_I_F_DE_LA_SOCIEDAD_REPRESENTANTE_DOMINANTE: "n_i_f_de_la_sociedad_representante_dominante",
    FilingProducerKey.M200_NIF_CODIGO_DE_IDENTIFICACION_EXTRANJERO: "nif_codigo_de_identificacion_extranjero",
    FilingProducerKey.M200_NIF_EN_EL_PAIS_DE_RESIDENCIA_TIN: "nif_en_el_pais_de_residencia_tin",
    FilingProducerKey.M200_NO_IDENTIFICACION_DE_LA_SOCIEDAD_DOMINANTE_E: "no_identificacion_de_la_sociedad_dominante_e",
    FilingProducerKey.M200_NO_RESIDENTES_MAS_DE_UN_ESTABLECIMIENTO_PERM: "no_residentes_mas_de_un_establecimiento_perm",
    FilingProducerKey.M200_NOMBRE_Y_APELLIDOS_DE_LA_PERSONA_DE_CONTACTO: "nombre_y_apellidos_de_la_persona_de_contacto",
    FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN: "numero_de_cuenta_iban",
    FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN_2: "numero_de_cuenta_iban_2",
    FilingProducerKey.M200_NUMERO_DE_PERIODO_IMPOSITIVO: "numero_de_periodo_impositivo",
    FilingProducerKey.M200_PAIS_DE_EXPEDICION_DEL_DOCUMENTO_DE_IDENTIFI: "pais_de_expedicion_del_documento_de_identifi",
    FilingProducerKey.M200_PAIS_DE_RESIDENCIA: "pais_de_residencia",
    FilingProducerKey.M200_PAIS_DE_RESIDENCIA_2: "pais_de_residencia_2",
    FilingProducerKey.M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS: "parte_de_la_base_imponible_del_periodo_impos",
    FilingProducerKey.M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS_2: (
        "parte_de_la_base_imponible_del_periodo_impos_2"
    ),
    FilingProducerKey.M200_PERDIDAS_Y_GANANCIAS_0_NO_CONSTA_1_MOD_NORMA: "perdidas_y_ganancias_0_no_consta_1_mod_norma",
    FilingProducerKey.M200_PERIODO: "periodo",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO: "periodo_impositivo",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_ANO_FINAL: "periodo_impositivo_ano_final",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_ANO_INICIO: "periodo_impositivo_ano_inicio",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_DIA_FINAL: "periodo_impositivo_dia_final",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_DIA_INICIO: "periodo_impositivo_dia_inicio",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_ANO: "periodo_impositivo_fin_ano",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_DIA: "periodo_impositivo_fin_dia",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_MES: "periodo_impositivo_fin_mes",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_ANO: "periodo_impositivo_inicio_ano",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_DIA: "periodo_impositivo_inicio_dia",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_MES: "periodo_impositivo_inicio_mes",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_MES_FINAL: "periodo_impositivo_mes_final",
    FilingProducerKey.M200_PERIODO_IMPOSITIVO_MES_INICIO: "periodo_impositivo_mes_inicio",
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S: "presentacion_de_documentacion_previa_en_la_s",
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_2: (
        "presentacion_de_documentacion_previa_en_la_s_2"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_3: (
        "presentacion_de_documentacion_previa_en_la_s_3"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_4: (
        "presentacion_de_documentacion_previa_en_la_s_4"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_5: (
        "presentacion_de_documentacion_previa_en_la_s_5"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_6: (
        "presentacion_de_documentacion_previa_en_la_s_6"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_7: (
        "presentacion_de_documentacion_previa_en_la_s_7"
    ),
    FilingProducerKey.M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_8: (
        "presentacion_de_documentacion_previa_en_la_s_8"
    ),
    FilingProducerKey.M200_REALIZA_ACTIVIDADES_AGRICOLAS_Y_O_GANADERAS: "realiza_actividades_agricolas_y_o_ganaderas",
    FilingProducerKey.M200_REG_ENTIDADES_NAVIERAS_EN_FUNCION_DEL_TONELA: "reg_entidades_navieras_en_funcion_del_tonela",
    FilingProducerKey.M200_RENUNCIA_O_POR_TRANSFERENCIA: "renuncia_o_por_transferencia",
    FilingProducerKey.M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN: "resultado_a_ingresar_correspondiente_a_la_an",
    FilingProducerKey.M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN_2: (
        "resultado_a_ingresar_correspondiente_a_la_an_2"
    ),
    FilingProducerKey.M200_RESULTADO_CERO: "resultado_cero",
    FilingProducerKey.M200_SOCIMIS_REGIMEN_FISCAL_DE_ENTRADA_SALIDA_REN: "socimis_regimen_fiscal_de_entrada_salida_ren",
    FilingProducerKey.M200_TIPO_DE_DECLARACION_VER_NOTA: "tipo_de_declaracion_ver_nota",
    FilingProducerKey.M200_TIPO_DE_EJERCICIO: "tipo_de_ejercicio",
    FilingProducerKey.M200_TIPO_DOCUMENTO_IDENTIFICATIVO: "tipo_documento_identificativo",
}


def m200_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the header facts modelo 200's layout cites.

    A profile of the wrong type yields every key as ``None`` rather than raising: this runs
    for every modelo, and AEAT writes an empty alphanumeric header field to blancos.
    """
    profile = model_profile if isinstance(model_profile, Modelo200ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M200_FIELD_BY_KEY.items()
    }


def filing_producer_values(snapshot: FilingProducerSnapshot) -> dict[FilingProducerKey, object]:
    """Resolve every canonical producer identity from one immutable snapshot."""
    identity = snapshot.taxpayer_identity
    amendment = snapshot.amendment_evidence
    account = selected_account_lexicals(snapshot)
    iva_profile = snapshot.model_profile if isinstance(snapshot.model_profile, ModeloIVAProfile) else None
    m303_profile = m303_profile_lexicals(iva_profile, snapshot.m303_filing_facts)
    m303_filing = m303_filing_lexicals(snapshot.m303_filing_facts)
    m303_motive = m303_rectificativa_motive_producer_values(amendment)
    values: dict[FilingProducerKey, object] = {
        FilingProducerKey.PRESENTER_TAX_ID: str(snapshot.presenter.tax_id),
        FilingProducerKey.FILING_RESULT_DISPOSITION: snapshot.elections.result_disposition.value,
        FilingProducerKey.TAXPAYER_TAX_ID: str(snapshot.taxpayer_tax_id),
        FilingProducerKey.TAXPAYER_LEGAL_NAME: identity.legal_name,
        FilingProducerKey.TAXPAYER_GIVEN_NAME: identity.given_name,
        FilingProducerKey.TAXPAYER_SURNAMES: identity.surnames,
        FilingProducerKey.TAXPAYER_FULL_NAME: identity.full_name,
        # "Apellidos o Razon Social": the two are mutually exclusive by
        # construction -- a natural person carries surnames and no legal_name,
        # an entity carries legal_name and no surnames -- so this resolves to
        # whichever the filer actually has, and stays absent only when both are.
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME: identity.surnames or identity.legal_name,
        # Read from the declaration's own contact fact, never from the taxpayer
        # or the presenter: under a gestor the persona con quien relacionarse is
        # routinely neither, and substituting either would name the wrong person
        # in AEAT's informativa header.
        FilingProducerKey.CONTACT_PERSON_PHONE: snapshot.declaration_contact.phone,
        FilingProducerKey.CONTACT_PERSON_NAME: snapshot.declaration_contact.full_name,
        FilingProducerKey.CONTACT_PERSON_SECONDARY_PHONE: snapshot.declaration_contact.secondary_phone,
        FilingProducerKey.CONTACT_PERSON_EMAIL: snapshot.declaration_contact.email,
        FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA: amendment.is_rectificativa if amendment else None,
        FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: amendment.is_complementaria if amendment else None,
        FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT: amendment.original_aeat_receipt if amendment else None,
        # ONE official slot holding "S", "C" or blank. Derived from the amendment KIND,
        # never from the boolean pair: rendering "S" because is_complementaria is false
        # would assert a substitution nobody declared, which is why this is its own key.
        FilingProducerKey.AMENDMENT_SUSTITUTIVA_OR_COMPLEMENTARIA_MARKER: (
            None
            if amendment is None
            else "S"
            if amendment.is_sustitutiva
            else "C"
            if amendment.is_complementaria
            else None
        ),
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES: m303_motive[
            FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES
        ],
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO: m303_motive[
            FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO
        ],
        FilingProducerKey.SELECTED_ACCOUNT_IBAN: account.iban,
        FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC: account.swift_bic,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME: account.bank_name,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS: account.bank_address,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY: account.bank_city,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE: account.bank_country_code,
        FilingProducerKey.PRIOR_DOMICILIATION_ACTION: (
            "X" if snapshot.elections.prior_domiciliation is PriorDomiciliationElection.CANCEL_OR_MODIFY else None
        ),
        FilingProducerKey.M303_REDEME_ENROLLED: m303_profile.redeme_enrolled,
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: m303_profile.exclusively_foral,
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: m303_profile.regime_composition_code,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: m303_filing.annual_volume_nonzero,
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: m303_filing.joint_return_elected,
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: m303_profile.cash_accounting_regime_enrolled,
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: (
            m303_filing.recipient_of_cash_accounting_operations
        ),
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: m303_filing.prorrata_special_option,
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: m303_filing.prorrata_special_revocation,
        FilingProducerKey.M303_INSOLVENCY_DECLARED: m303_filing.insolvency_declared,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: m303_filing.insolvency_judicial_order_date,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: m303_filing.insolvency_filing_subtype,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: m303_profile.voluntary_sii_enrolled,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: m303_filing.exonerado_390_applicable,
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: (
            m303_profile.hydrocarbon_deposit_advance_payment_deduction_entitled
        ),
        FilingProducerKey.M111_COLEGIO_CONCERTADO: (
            snapshot.model_profile.colegio_concertado
            if isinstance(snapshot.model_profile, Modelo111ProfileFacts)
            else None
        ),
    }
    if m303_profile.is_foral:
        foral = m303_foral_lexicals(m303_filing)
        values.update(
            {
                FilingProducerKey.M303_REDEME_ENROLLED: "2",
                FilingProducerKey.M303_EXCLUSIVELY_FORAL: "1",
                FilingProducerKey.M303_REGIME_COMPOSITION_CODE: "3",
                FilingProducerKey.M303_JOINT_RETURN_ELECTED: "2",
                FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: "2",
                FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: "2",
                FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: foral.prorrata_special_option,
                FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: foral.prorrata_special_revocation,
                FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
                FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
                FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
                FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: "2",
                FilingProducerKey.M303_EXONERADO_390_APPLICABLE: "2",
                FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: "2",
            },
        )
    values.update(m222_producer_values(snapshot.model_profile))
    values.update(m202_producer_values(snapshot.model_profile))
    values.update(m210_producer_values(snapshot.model_profile))
    values.update(m200_producer_values(snapshot.model_profile))
    values.update(m296_producer_values(snapshot.model_profile))
    values.update(m353_producer_values(snapshot.model_profile))
    shared_owned = {
        key
        for key, owner in _filing_producer_ownership(
            shared_snapshot_keys=_SHARED_SNAPSHOT_PRODUCER_KEYS,
        ).items()
        if owner == "shared_snapshot"
    }
    if set(values) != shared_owned:
        raise FilingExportValidationError("shared filing producer resolver is not exhaustive over its owned keys")
    return values


def m303_rectificativa_motive_producer_values(
    amendment: AmendmentEvidence | None,
) -> dict[FilingProducerKey, bool | None]:
    """Project the closed two-checkbox truth table from one persisted motive."""
    motive = amendment.m303_rectificativa_motive if amendment is not None else None
    return {
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES: (
            motive is M303RectificativaMotive.RECTIFICACIONES if motive is not None else None
        ),
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO: (
            motive is M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO if motive is not None else None
        ),
    }


def selected_account_lexicals(snapshot: FilingProducerSnapshot) -> SelectedAccountLexicals:
    selected = snapshot.selected_account
    if isinstance(selected, RefundAccountSelection):
        return SelectedAccountLexicals(
            iban=selected.account.iban,
            swift_bic=selected.account.swift_bic,
            bank_name=selected.account.bank_name,
            bank_address=selected.account.bank_address,
            bank_city=selected.account.bank_city,
            bank_country_code=selected.account.bank_country_code,
        )
    if isinstance(selected, ChargeAccountSelection):
        return SelectedAccountLexicals(iban=selected.account.iban)
    return SelectedAccountLexicals()


def m303_profile_lexicals(
    iva_profile: ModeloIVAProfile | None,
    m303_facts: M303FilingFacts | None,
) -> M303ProfileLexicals:
    if iva_profile is None:
        return M303ProfileLexicals()
    period = m303_facts.period if m303_facts is not None else None
    a30 = (
        yes_no(iva_profile.hydrocarbon_deposit_advance_payment_deduction_entitled)
        if period is not None and m303_a30_entitlement_applicable(period)
        else "0"
        if period is not None
        else None
    )
    return M303ProfileLexicals(
        redeme_enrolled=yes_no(iva_profile.redeme_enrolled),
        exclusively_foral="1" if iva_profile.tax_territory is M303TaxTerritory.FORAL else "2",
        regime_composition_code={
            M303RegimeComposition.SIMPLIFIED: "1",
            M303RegimeComposition.MIXED: "2",
            M303RegimeComposition.GENERAL: "3",
        }[iva_profile.regime_composition],
        cash_accounting_regime_enrolled=yes_no(iva_profile.cash_accounting_regime_enrolled),
        voluntary_sii_enrolled=yes_no(iva_profile.voluntary_sii_enrolled),
        hydrocarbon_deposit_advance_payment_deduction_entitled=a30,
        is_foral=iva_profile.tax_territory is M303TaxTerritory.FORAL,
    )


def m303_filing_lexicals(m303_facts: M303FilingFacts | None) -> M303FilingLexicals:
    if m303_facts is None:
        return M303FilingLexicals()
    transition = m303_facts.prorrata_transition
    insolvency = m303_facts.insolvency
    transition_applicable = transition.is_applicable
    return M303FilingLexicals(
        joint_return_elected=yes_no(m303_facts.joint_return_elected),
        annual_volume_nonzero="1" if m303_facts.annual_volume_nonzero else None,
        recipient_of_cash_accounting_operations=yes_no(
            m303_facts.supplier_regime.recipient_of_cash_accounting_operations,
        ),
        prorrata_special_option=(
            yes_no(transition.transition is ProrrataEspecialTransitionKind.OPCION) if transition_applicable else None
        ),
        prorrata_special_revocation=(
            yes_no(transition.transition is ProrrataEspecialTransitionKind.REVOCACION)
            if transition_applicable
            else None
        ),
        insolvency_declared="1" if insolvency is not None else "2",
        insolvency_judicial_order_date=(
            insolvency.judicial_order_date.strftime("%d%m%Y") if insolvency is not None else None
        ),
        insolvency_filing_subtype=(
            {
                M303InsolvencyFilingSubtype.PRE_ORDER: "1",
                M303InsolvencyFilingSubtype.POST_ORDER: "2",
            }[insolvency.subtype]
            if insolvency is not None
            else None
        ),
        exonerado_390_applicable=(
            yes_no(m303_facts.exonerado_390.applicable) if is_last_filing_period_of_year(m303_facts.period) else "0"
        ),
        prorrata_transition_applicable=transition_applicable,
    )


def m303_foral_lexicals(m303_filing: M303FilingLexicals) -> M303ForalLexicals:
    value = "2" if m303_filing.prorrata_transition_applicable else None
    return M303ForalLexicals(prorrata_special_option=value, prorrata_special_revocation=value)


def yes_no(value: bool) -> str:
    return "1" if value else "2"


def m303_a30_entitlement_applicable(period: Period) -> bool:
    return period.registry_token.isdigit() and int(period.registry_token) >= 2


__all__ = [
    "M303FilingLexicals",
    "M303ForalLexicals",
    "M303ProfileLexicals",
    "SelectedAccountLexicals",
    "filing_producer_values",
    "m303_filing_lexicals",
    "m303_foral_lexicals",
    "m303_profile_lexicals",
    "m303_rectificativa_motive_producer_values",
    "selected_account_lexicals",
]
