"""Shared support for Modelo 100 registry tests."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .....domain.contribuyente import compute_deduccion_maternidad_0611
from .....tests.aeat_literal_fixtures import aeat_url, configured_path
from .. import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    RegistryValidationError,
    RegistryValidator,
    build_snapshot,
    load_registry_tree,
)

_DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))
_UNKNOWN_CONSTRUCT_MEMBER_CASILLA: CasillaId = validated_casilla_id(
    "0000-ghost",
    surface="_UNKNOWN_CONSTRUCT_MEMBER_CASILLA",
)


def _m100_2024_deduccion_maternidad_bindings() -> Mapping[str, Decimal]:
    """Return M100 2024's empty-descendant maternity binding from domain law."""
    return {
        "renta-2024-profile-deduccion-maternidad": Decimal(
            compute_deduccion_maternidad_0611(
                [],
                filing_year=2024,
            ),
        ),
    }


@cache
def _source_root() -> Path:
    return bundled_path()


@cache
def _registry_root() -> Path:
    return _source_root() / "registry" / "aeat"


@cache
def _loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_registry_root())
    return {modelo.id: modelo for modelo in modelos}, catalogues


@cache
def _registry_validator() -> RegistryValidator:
    _modelos_by_id, catalogues = _loaded_registry()
    return RegistryValidator(catalogues, source_root=_source_root())


@cache
def _modelo_100_snapshot(filing_year: int = 2025) -> RegistrySnapshot:
    modelos_by_id, catalogues = _loaded_registry()
    return build_snapshot(
        modelos_by_id["100"],
        catalogues,
        source_root=_source_root(),
        filing_year=filing_year,
        period="0A",
    )


_PERSONAL_FAMILY_BINDINGS: frozenset[str] = frozenset(
    {
        "renta-2025-profile-tax-id",
        "renta-2025-profile-display-name",
        "renta-2025-profile-tax-residence-ccaa",
        "renta-2025-profile-declaration-type",
        "renta-2025-profile-taxpayer-sex",
        "renta-2025-profile-marital-status",
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-spouse-tax-id",
        "renta-2025-profile-spouse-display-name",
        "renta-2025-profile-spouse-birth-date",
        "renta-2025-profile-spouse-sex",
        "renta-2025-profile-taxpayer-disability-grade",
        "renta-2025-profile-taxpayer-death-date",
        "renta-2025-profile-spouse-disability-grade",
        "renta-2025-profile-spouse-non-resident-irpf",
        "renta-2025-profile-spouse-eu-eea-resident",
        "renta-2025-profile-spouse-eu-eea-country",
        "renta-2025-profile-family-descendants-eu-eea-deduction",
        "renta-2025-profile-family-minor-children-in-unit",
        "renta-2025-family-descendant-tax-id",
        "renta-2025-family-descendant-display-name",
        "renta-2025-family-descendant-birth-date",
        "renta-2025-family-descendant-disability-grade",
        "renta-2025-family-descendant-death-date",
        "renta-2025-family-ascendant-tax-id",
        "renta-2025-family-ascendant-display-name",
        "renta-2025-family-ascendant-birth-date",
        "renta-2025-family-ascendant-disability-grade",
        "renta-2025-family-ascendant-cohabiting-descendant-count",
        "renta-2025-family-ascendant-death-date",
    },
)


def _binding_map_by_casilla(*pairs: tuple[object, str]) -> Mapping[CasillaId, str]:
    return {
        validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla"): binding_id
        for casilla_id, binding_id in pairs
    }


_PERSONAL_FAMILY_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in (
        "DPNIF_D",
        "DP_APENOM_D",
        "ZCCAD",
        "TIPOTRIBUTACION",
        "SEXO_D",
        "ECIVIL",
        "DPFNAC_D",
        "DPNIF_C",
        "DP_APENOM_C",
        "DPFNAC_C",
        "SEXO_C",
        "DPGMIN_D",
        "DECFAL",
        "DPGMIN_C",
        "NORESIDENTE",
        "RESIDENTEUE",
        "ZRUE2",
        "HIJOSUE",
        "PH18",
        "NIFDLG",
        "APENOMDLG",
        "FNACDLG",
        "MINUSDLG",
        "FALLDLG",
        "DNIASDLG",
        "APENOMDLG_ASC",
        "ANOASDLG",
        "PCTMINASDLG",
        "CONVASDLG",
        "FALLASDLG",
    )
)

_SOURCE_FOUNDATION_APPLICATION_LINKS: frozenset[str] = frozenset(
    {
        "modelo-100-renta-web-open-cross-reference",
        "modelo-100-export",
        "modelo-100-filed-declarations-observation",
        "modelo-100-calculation",
        "modelo-100-review",
        "modelo-100-approval",
        "modelo-100-reconciliation",
        "modelo-100-workflow",
    },
)


def _modelo_100_revision_2025() -> tuple[ModeloDefinition, ModeloRevision]:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    return modelo, modelo.revisions["2025"]


def _modelo_100_with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _assert_registry_validation_error(modelo: ModeloDefinition, *, match: str) -> None:
    with pytest.raises(RegistryValidationError, match=match):
        _registry_validator().validate_modelo(modelo)


_GENERAL_BASE_ART_48_REF = "ley-35-2006:art-48"
_SAVINGS_BASE_ART_49_REF = "ley-35-2006:art-49"
_BASE_LIQUIDABLE_ART_50_REF = "ley-35-2006:art-50"
_PERSONAL_FAMILY_MINIMUM_ART_56_REF = "ley-35-2006:art-56"
_STATE_INTEGRAL_QUOTA_ART_62_REF = "ley-35-2006:art-62"
_GENERAL_SCALE_ART_63_REF = "ley-35-2006:art-63"
_STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF = "ley-35-2006:art-64"
_SAVINGS_STATE_SCALE_ART_66_REF = "ley-35-2006:art-66"
_STATE_DEDUCTION_ART_67_REF = "ley-35-2006:art-67"
_BROAD_DEDUCTION_ART_68_REF = "ley-35-2006:art-68"
_NEW_COMPANY_INVESTMENT_ART_68_1_REF = "ley-35-2006:art-68.1"
_BUSINESS_INVESTMENT_ART_68_2_REF = "ley-35-2006:art-68.2"
_DONATION_DEDUCTION_ART_68_3_REF = "ley-35-2006:art-68.3"
_CEUTA_MELILLA_DEDUCTION_ART_68_4_REF = "ley-35-2006:art-68.4"
_CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF = "ley-35-2006:art-68.5"
_DEDUCTION_LIMITS_ART_69_REF = "ley-35-2006:art-69"
_ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF = "ley-35-2006:da-50"
_EV_CHARGING_POINT_DEDUCTION_DA_58_REF = "ley-35-2006:da-58"
_HOME_INVESTMENT_DEDUCTION_DT_18_REF = "ley-35-2006:dt-18"
_RENTAL_HOUSING_DEDUCTION_DT_15_REF = "ley-35-2006:dt-15"
_AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF = "ley-35-2006:art-73"
_AUTONOMIC_GENERAL_SCALE_ART_74_REF = "ley-35-2006:art-74"
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF = "ley-35-2006:art-75"
_AUTONOMIC_SAVINGS_SCALE_ART_76_REF = "ley-35-2006:art-76"
_AUTONOMIC_DEDUCTION_ART_77_REF = "ley-35-2006:art-77"
_ATTRIBUTION_REGIME_ART_86_REF = "ley-35-2006:art-86"
_OBJECTIVE_ESTIMATION_ART_31_REF = "ley-35-2006:art-31"
_ATTRIBUTION_OBJECTIVE_ESTIMATION_ART_39_REF = "rd-439-2007:art-39"
_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF = "ley-35-2006:da-60"
_FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"
_FRACTIONAL_PAYMENT_AMOUNT_ARTICLE_REF = "rd-439-2007:art-110"
_PAYMENTS_ON_ACCOUNT_ARTICLE_REF = "ley-35-2006:art-99"
_MODELO_100_2025_FORM_ORDER_REF = "orden-hac-277-2026:art-3"
_BROAD_INCOME_CHAPTER_SPAN_REFS = frozenset(
    {
        "ley-35-2006:art-17",
        "ley-35-2006:art-18",
        "ley-35-2006:art-19",
        "ley-35-2006:art-20",
        "ley-35-2006:art-22",
        "ley-35-2006:art-23",
        "ley-35-2006:art-24",
        "ley-35-2006:art-25",
        "ley-35-2006:art-26",
    }
)
_CAPITAL_GAINS_SECTION_REFS = frozenset(
    {
        "ley-35-2006:art-33",
        "ley-35-2006:art-34",
        _MODELO_100_2025_FORM_ORDER_REF,
    }
)
_RIC_RESERVA_SECTION = ("resultados", "anexo_a_res", "reserva_inversiones_canarias_res")
_RIB_RESERVA_SECTION = ("resultados", "anexo_a_res", "reserva_inversiones_baleares_res")
_RIB_BALEARES_DA70_REF = "ley-31-2022:da-70"
_RIC_DOTACION_IMPORTE_ROLE = "irpf_anexo_a_ric_dotacion_importe"
_RIC_DOTACION_ANIO_ROLE = "irpf_anexo_a_ric_dotacion_anio"
_RIC_INVERSION_TIPO_ABD_ROLE = "irpf_anexo_a_ric_inversion_tipo_abd"
_RIC_INVERSION_TIPO_CD_ROLE = "irpf_anexo_a_ric_inversion_tipo_cd"
_RIB_DOTACION_IMPORTE_ROLE = "irpf_anexo_a_rib_dotacion_importe"
_RIB_DOTACION_ANIO_ROLE = "irpf_rib_baleares_dotacion_anio"
_RIB_INVERSION_TIPO_AB_ROLE = "irpf_anexo_a_rib_inversion_tipo_ab"
_RIB_INVERSION_TIPO_C_ROLE = "irpf_rib_baleares_inversion_tipo_c"
_LEGACY_RIB_SPLIT_ROLES = frozenset(
    {
        "irpf_anexo_a_rib_dotacion_anio",
        "irpf_anexo_a_rib_inversion_tipo_c",
    }
)
_HOUSING_ENERGY_RESULTS_SECTION = ("resultados", "anexo_a_res", "deduccion_mejoras_energeticas_viv_res")
_HOUSING_ENERGY_DEDUCTION_RESULT_ROLE = "irpf_anexo_a_mejora_energia_deduccion_importe"
_EV_CHARGING_POINT_RESULTS_SECTION = ("resultados", "anexo_a_res", "vehiculos_elec_y_puntos_carga_res")
_EV_CHARGING_POINT_DEDUCTION_ROLE = "irpf_deduccion_vehiculo_electrico_importe"
_ANEXO_C_ENERGY_EXCESS_SECTION = ("resultados", "anexo_c_res", "excesos_eficiencia_energetica_res")
_ANEXO_C_ENERGY_EXCESS_ROLE_PREFIX = "irpf_anexo_c_exceso_eficiencia_energetica_"
_ANEXO_C_ENERGY_EXCESS_ROLES = frozenset(
    {
        "irpf_anexo_c_exceso_eficiencia_energetica_pendiente_inicio",
        "irpf_anexo_c_exceso_eficiencia_energetica_aplicado",
        "irpf_anexo_c_exceso_eficiencia_energetica_pendiente_fin",
        "irpf_anexo_c_exceso_eficiencia_energetica_generado",
    }
)
_ANEXO_B_IMPORTE_SATISFECHO_ROLE = "irpf_anexo_b_importe_satisfecho"
_ANEXO_B_IMPORTE_SATISFECHO_LABEL = "Cantidades satisfechas"
_ANEXO_B_IMPORTE_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_ctrd",
        "an_b_inf_adc_arr",
        "an_b_inf_adc_avh",
        "an_b_inf_adc_arrvm",
    }
)
_ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE = "irpf_anexo_b_importe_anual_satisfecho"
_ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL = "Importe anual satisfecho"
_ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_enf",
        "an_b_inf_adc_dep",
        "an_b_inf_adc_aia",
        "an_b_inf_adc_aav",
    }
)
_ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE = "irpf_anexo_b_otros_gastos_importe_anual"
_ANEXO_B_OTROS_GASTOS_SECTION = "an_b_inf_adc_aia"
_ANEXO_B_OTROS_GASTOS_LABELS = {
    2024: "Importe anual satisfecho",
    2025: "Importe anual satisfecho de otros gastos",
}
_ANEXO_B_AAV_SECTION = "an_b_inf_adc_aav"
_ANEXO_B_AAV_IMPORTE_SATISFECHO_ROLE = "irpf_anexo_b_aav_importe_satisfecho"
_ANEXO_B_AAV_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_aav_importe_aplicado"
_ANEXO_B_AAV_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_aav_importe_pendiente"
_ANEXO_B_AAV_AMOUNT_ROWS = {
    "2202": ("Importe total satisfecho en 2025", _ANEXO_B_AAV_IMPORTE_SATISFECHO_ROLE),
    "2203": ("Importe satisfecho que se aplica en el ejercicio", _ANEXO_B_AAV_IMPORTE_APLICADO_ROLE),
    "2204": (
        "Importe satisfecho en 2025 pendiente de aplicación en ejercicios futuros",
        _ANEXO_B_AAV_IMPORTE_PENDIENTE_ROLE,
    ),
}
_ANEXO_B_BALEARES_NACIMIENTO_SECTION = "an_b_inf_ad_i_baleares"
_ANEXO_B_BALEARES_NACIMIENTO_ROWS = {
    "1990": (
        "Deducción por nacimiento: Importe de la deducción",
        "irpf_anexo_b_baleares_deduccion_nacimiento_importe",
    ),
    "1991": (
        "Deducción por nacimiento: Importe del abono anticipado",
        "irpf_anexo_b_deduccion_nacimiento_abono_anticipado",
    ),
    "1992": (
        "Deducción por nacimiento: Importe pendiente a solicitar por el contribuyente",
        "irpf_baleares_deduccion_nacimiento_importe_pendiente",
    ),
    "1993": (
        "Deducción por nacimiento: Importe del cobro anticipado a regularizar (casilla [0504])",
        "irpf_anexo_b_deduccion_nacimiento_cobro_anticipado_regularizar",
    ),
}
_ANEXO_B_ACCOUNT_SECTION = "an_b_inf_ad_cm_viv_hab"
_ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE = "irpf_anexo_b_cm_viv_hab_titular_cuenta"
_ANEXO_B_ACCOUNT_OPENING_DATE_ROLE = "irpf_anexo_b_account_opening_date"
_ANEXO_B_ACCOUNT_IDENTIFIER_ROLE = "irpf_anexo_b_account_identifier"
_ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE = "irpf_anexo_b_account_foreign_flag"
_ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE = "irpf_anexo_b_account_balance_increase"
_ANEXO_B_ACCOUNT_ROWS = {
    "2214": ("Titular de la cuenta", _ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE),
    "2215": ("Fecha de apertura", _ANEXO_B_ACCOUNT_OPENING_DATE_ROLE),
    "2216": ("Identificación de la cuenta", _ANEXO_B_ACCOUNT_IDENTIFIER_ROLE),
    "2217": (
        'Marque una "X" si se trata de cuenta abierta en el extranjero',
        _ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE,
    ),
    "2218": ("Incremento del saldo en el ejercicio", _ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE),
    "2219": ("Titular de la cuenta", _ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE),
    "2220": ("Fecha de apertura", _ANEXO_B_ACCOUNT_OPENING_DATE_ROLE),
    "2221": ("Identificación de la cuenta", _ANEXO_B_ACCOUNT_IDENTIFIER_ROLE),
    "2222": (
        'Marque una "X" si se trata de cuenta abierta en el extranjero',
        _ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE,
    ),
    "2223": ("Incremento del saldo en el ejercicio", _ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE),
}
_ANEXO_B_CARRY_FORWARD_PENDING_ROLE = "irpf_anexo_b_carry_forward_pending"
_MADRID_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "madrid_res")
_C_VALENCIANA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "c_valenciana_res")
_GALICIA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "galicia_res")
_ANEXO_B_INST_AUTO_SECTION = ("resultados", "datos_adicionales_anexo_b", "an_b_inf_adc_inst_auto")
_MADRID_CUIDADO_ASCENDIENTES_ROLE = "irpf_deduccion_madrid_cuidado_ascendientes"
_LEGACY_MADRID_CUIDADO_ASCENDIENTES_PENDING_ROLE = "irpf_deduccion_autonomica_cuidado_ascendientes_pendiente"
_MADRID_INTERESES_PRESTAMOS_ESTUDIOS_ROLE = "irpf_deduccion_madrid_intereses_prestamos_estudios"
_LEGACY_MADRID_INTERESES_PRESTAMOS_ESTUDIOS_PENDING_ROLE = "irpf_deduccion_estudios_intereses_prestamo_pendiente"
_GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE = "irpf_deduccion_galicia_inmueble_vacio_adecuacion"
_LEGACY_GALICIA_INMUEBLE_VACIO_ADECUACION_PENDING_ROLE = "irpf_deduccion_inmueble_vacio_adecuacion_pendiente"
_MADRID_GASTOS_ARRENDAMIENTO_ROLE = "irpf_deduccion_madrid_gastos_arrendamiento"
_MADRID_INTERESES_PRESTAMOS_VIVIENDA_ROLE = "irpf_deduccion_madrid_intereses_prestamos_vivienda"
_MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ROLE = "irpf_deduccion_madrid_vivienda_nacimiento_adopcion"
_MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ANIO_ROLE = "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_anio"
_MADRID_FAMILIA_NUMEROSA_ROLE = "irpf_deduccion_madrid_familia_numerosa"
_MADRID_VIVIENDA_NACIMIENTO_ADOPCION_IMPORTE_ROLE = "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_importe"
_MADRID_VIVIENDA_NACIMIENTO_ADOPCION_PRECIO_ROLE = "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_precio"
_MADRID_VIVIENDA_MUNICIPIO_RIESGO_ROLE = "irpf_deduccion_madrid_vivienda_municipio_riesgo"
_MADRID_VIVIENDA_MUNICIPIO_RIESGO_ANIO_ROLE = "irpf_deduccion_madrid_vivienda_municipio_riesgo_anio"
_MADRID_VIVIENDA_MUNICIPIO_RIESGO_PRECIO_ROLE = "irpf_deduccion_madrid_vivienda_municipio_riesgo_precio"
_ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE = "irpf_anexo_b_inst_auto_importe_pendiente_anterior"
_LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_arrendamiento_importe_aplicado"
_LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_arrendamiento_importe_pendiente"
_LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_nacimiento_vivienda_importe_aplicado"
_LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_nacimiento_vivienda_importe_pendiente"
_LEGACY_ANEXO_B_ENERGIA_SATISFECHO_APLICADO_ROLE = "irpf_anexo_b_energia_satisfecho_aplicado"
_LEGACY_ANEXO_B_ENERGIA_SATISFECHO_PENDIENTE_ROLE = "irpf_anexo_b_energia_satisfecho_pendiente"
_LEGACY_ANEXO_B_VIVIENDA_REINVERSION_PENDIENTE_ROLE = "irpf_anexo_b_vivienda_reinversion_pendiente"
_CARRY_FORWARD_PENDING_OUTLIERS = {
    2023: {
        "1115": (
            "Por cuidado de ascendientes",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_CUIDADO_ASCENDIENTES_ROLE,
        ),
        "1118": (
            "Por el pago de intereses de préstamos a estudios de Grado, Master y Doctorado",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_INTERESES_PRESTAMOS_ESTUDIOS_ROLE,
        ),
    },
    2024: {
        "1115": (
            "Por cuidado de ascendientes",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_CUIDADO_ASCENDIENTES_ROLE,
        ),
        "1118": (
            "Por el pago de intereses de préstamos a estudios de Grado, Master y Doctorado",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_INTERESES_PRESTAMOS_ESTUDIOS_ROLE,
        ),
    },
    2025: {
        "1078": (
            (
                "Por gastos derivados de la adecuación de un inmueble vacío con destino al arrendamiento como vivienda "
                "(información adicional en el anexo B.15)"
            ),
            _GALICIA_DEDUCTION_SECTION,
            _GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE,
        ),
        "1115": (
            "Por cuidado de ascendientes",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_CUIDADO_ASCENDIENTES_ROLE,
        ),
        "1118": (
            "Por el pago de intereses de préstamos a estudios de Grado, Master y Doctorado",
            _MADRID_DEDUCTION_SECTION,
            _MADRID_INTERESES_PRESTAMOS_ESTUDIOS_ROLE,
        ),
    },
}
_MADRID_REUSED_ID_DEDUCTION_ROWS = {
    2023: {
        "1116": (
            "Por gastos derivados de arrendamiento de vivienda",
            _MADRID_GASTOS_ARRENDAMIENTO_ROLE,
        ),
        "1117": (
            "Por el pago de intereses de préstamos para adquisición de vivienda por jóvenes menores de 30 años",
            _MADRID_INTERESES_PRESTAMOS_VIVIENDA_ROLE,
        ),
        "1119": (
            "Por adquisición de vivienda habitual por nacimiento o adopción de hijos",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ROLE,
        ),
        "1120": (
            "Por la obtención de la condición de familia numerosa",
            _MADRID_FAMILIA_NUMEROSA_ROLE,
        ),
    },
    2024: {
        "1116": (
            "Por gastos derivados de arrendamiento de vivienda",
            _MADRID_GASTOS_ARRENDAMIENTO_ROLE,
        ),
        "1117": (
            "Por el pago de intereses de préstamos para adquisición de vivienda por jóvenes menores de 30 años",
            _MADRID_INTERESES_PRESTAMOS_VIVIENDA_ROLE,
        ),
        "1119": (
            "Por adquisición de vivienda habitual por nacimiento o adopción de hijos",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ROLE,
        ),
        "1120": (
            "Importe de la deducción",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_IMPORTE_ROLE,
        ),
    },
    2025: {
        "1116": (
            "Por gastos derivados de arrendamiento de vivienda",
            _MADRID_GASTOS_ARRENDAMIENTO_ROLE,
        ),
        "1117": (
            "Por el pago de intereses de préstamos para adquisición de vivienda por jóvenes menores de 30 años",
            _MADRID_INTERESES_PRESTAMOS_VIVIENDA_ROLE,
        ),
        "1119": (
            "Por adquisición de vivienda habitual por nacimiento o adopción de hijos",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ROLE,
        ),
        "1120": (
            "Importe de la deducción",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_IMPORTE_ROLE,
        ),
    },
}
_MADRID_VIVIENDA_ACQUISITION_DETAIL_ROWS = {
    2024: {
        "2027": (
            "Por adquisición de vivienda habitual por nacimiento o adopción de hijos",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ROLE,
        ),
        "2028": (
            "Precio de adquisición/cantidades invertidas",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_PRECIO_ROLE,
        ),
        "2029": (
            "Año de adquisición",
            _MADRID_VIVIENDA_NACIMIENTO_ADOPCION_ANIO_ROLE,
        ),
    },
    2025: {
        "2027": (
            "Por adquisición de vivienda habitual en municipios en riesgo de despoblación",
            _MADRID_VIVIENDA_MUNICIPIO_RIESGO_ROLE,
        ),
        "2028": (
            "Precio de adquisición/cantidades invertidas",
            _MADRID_VIVIENDA_MUNICIPIO_RIESGO_PRECIO_ROLE,
        ),
        "2029": (
            "Año de adquisición",
            _MADRID_VIVIENDA_MUNICIPIO_RIESGO_ANIO_ROLE,
        ),
    },
}
_CARRY_FORWARD_REMAINING_INST_AUTO_ROWS = {
    2021: {
        "1117": "Importe satisfecho en 2018 pendiente de aplicación en ejercicios futuros",
        "1120": "Importe satisfecho en 2021 pendiente de aplicación en ejercicios futuros",
        "1186": "Importe satisfecho en 2019 y/o 2020 pendiente de aplicación en ejercicios futuros",
    },
    2022: {
        "1120": "Importe satisfecho en 2022 pendiente de aplicación en ejercicios futuros",
        "1186": "Importe satisfecho en 2019 y/o 2020 pendiente de aplicación en ejercicios futuros",
        "1709": "Importe satisfecho en 2021 pendiente de aplicación en ejercicios futuros",
    },
    2023: {
        "1186": "Importe satisfecho en 2020 pendiente de aplicación en ejercicios futuros",
        "1709": "Importe satisfecho en 2021 y/o 2022 pendiente de aplicación en ejercicios futuros",
    },
    2024: {
        "1709": "Importe satisfecho en 2021 y/o 2022 pendiente de aplicación en ejercicios futuros",
    },
    2025: {
        "1709": "Importe satisfecho en 2022 pendiente de aplicación en ejercicios futuros",
    },
}
_LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES = frozenset(
    {
        _ANEXO_B_CARRY_FORWARD_PENDING_ROLE,
        _LEGACY_MADRID_CUIDADO_ASCENDIENTES_PENDING_ROLE,
        _LEGACY_MADRID_INTERESES_PRESTAMOS_ESTUDIOS_PENDING_ROLE,
        _LEGACY_GALICIA_INMUEBLE_VACIO_ADECUACION_PENDING_ROLE,
    }
)
_LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES = frozenset(
    {
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_ENERGIA_SATISFECHO_APLICADO_ROLE,
        _LEGACY_ANEXO_B_ENERGIA_SATISFECHO_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_VIVIENDA_REINVERSION_PENDIENTE_ROLE,
    }
)
_LEGACY_MADRID_REUSED_ID_ROLES = frozenset(
    {
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_APLICADO_ROLE,
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_APLICADO_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE,
    }
)
_ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE = "irpf_anexo_b_total_cantidades_invertidas_deduccion"
_ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL = "Importe total de las cantidades invertidas con derecho a deducción"
_ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS = frozenset(
    {
        "an_b_inf_adc_enf",
        "an_b_inf_adc_dep",
        "an_b_inf_adc_aia",
    }
)
_ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE = "irpf_anexo_b_contribuyente_con_derecho_clave"
_ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL = "Contribuyente con derecho a deducción"
_ANEXO_B_INVERSION_TOTAL_ROLE = "irpf_anexo_b_importe_total_deduccion_por_tipo"
_ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX = "Importe total de las cantidades"
_ANEXO_B_INVERSION_IMPORTE_ROLE = "irpf_anexo_b_deduccion_inversion_importe"
_ANEXO_B_INVERSION_IMPORTE_LABEL = "Importe de la inversión con derecho a deducción"
_ANEXO_B_INVERSION_TOTAL_SECTIONS = frozenset(
    {
        "an_b_inf_adc_enc",
        "an_b_inf_adc_mab",
        "an_b_inf_adc_rcf",
        "an_b_inf_adc_agt",
        "an_b_inf_adc_ides",
        "an_b_inf_ad_ref_cat",
        "an_b_inf_adc_ipse",
        "an_b_inf_adc_afp",
        "an_b_inf_adc_scav",
        "an_b_inf_adc_rcince",
    }
)
_ANEXO_B_EPS_SECTION = "an_b_inf_adc_eps"
_ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE = "irpf_anexo_b_prima_seguro_credito_arrendamiento"
_ANEXO_B_PRIMA_SEGURO_LABEL = "Primas satisfechas"
_ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE = "irpf_eps_primas_seguro_deducibles_total"
_ANEXO_B_TOTAL_SATISFECHO_ROLE = "irpf_anexo_b_importe_total_satisfecho"
_ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE = "irpf_anexo_b_cantidades_deducibles_satisfechas"
_ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL = "Cantidades satisfechas con derecho a deducción"
_ANEXO_B_TOTAL_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_ctrd",
        "an_b_inf_adc_arr",
        "an_b_inf_adc_arrvm",
    }
)
_DONATION_DEDUCTION_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0552", "0553", "0722", "0723", "0724", "0725")
)
_CASILLA_0921 = validated_casilla_id("0921", surface="test_modelo_100_registry.casilla")
_CANARIAS_DONACION_DESCENDIENTES_ROLE = "irpf_deduccion_canarias_donacion_descendientes"
_ANDALUCIA_EJERCICIO_FISICO_ROLE = "irpf_deduccion_andalucia_ejercicio_fisico"
_CASILLA_1091 = validated_casilla_id("1091", surface="test_modelo_100_registry.casilla")
_C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE = "irpf_deduccion_c_valenciana_labores_no_remuneradas_hogar"
_EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE = "irpf_deduccion_extremadura_vivienda_zonas_rurales"
_CASILLA_0581 = validated_casilla_id("0581", surface="test_modelo_100_registry.casilla")
_CASILLA_0575 = validated_casilla_id("0575", surface="test_modelo_100_registry.casilla")
_CASILLA_0580 = validated_casilla_id("0580", surface="test_modelo_100_registry.casilla")
_INCENTIVO_ART_33_REGULARIZATION_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0568", "0569")
)
_REGULARIZACION_PREVIOUS_INTEREST_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0582", "0583")
)
_REGULARIZACION_DEDUCTION_LOSS_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0572", "0574", "0577", "0579")
)
_REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0573", "0576", "0578", "0581")
)
_DEDUCTION_LOSS_INTEREST_STATE_ROLE = "irpf_intereses_demora_perdida_deduccion_estatal"
_DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE = "irpf_intereses_demora_perdida_deduccion_autonomica"
_LIRPF_CAPITAL_GAINS_ART_33_REF = "ley-35-2006:art-33"
_DA45_CLAUSULA_SUELO_REF = "ley-35-2006:da-45"
_RIRPF_DEDUCTION_LOSS_ART_59_REF = "rd-439-2007:art-59"
_LGT_INTEREST_ART_26_REF = "ley-58-2003:art-26"
_ATTRIBUTION_REGIME_MODE_FLAG_REFS = frozenset(
    {
        _ATTRIBUTION_REGIME_ART_86_REF,
        _MODELO_100_2025_FORM_ORDER_REF,
    }
)
_ATTRIBUTION_REGIME_AGRICULTURAL_MODE_FLAG_REFS = frozenset(
    {
        _OBJECTIVE_ESTIMATION_ART_31_REF,
        _ATTRIBUTION_REGIME_ART_86_REF,
        _ATTRIBUTION_OBJECTIVE_ESTIMATION_ART_39_REF,
        _MODELO_100_2025_FORM_ORDER_REF,
    }
)
_ECONOMIC_ACTIVITY_SECTION_REFS = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
        _MODELO_100_2025_FORM_ORDER_REF,
    }
)
_GENERAL_BASE_GYP_LIMIT_CASILLA = validated_casilla_id("0433", surface="test_modelo_100_registry.casilla")
_SAVINGS_BASE_GYP_LIMIT_CASILLA = validated_casilla_id("0446", surface="test_modelo_100_registry.casilla")
_GENERAL_BASE_IMPONIBLE_CASILLA = validated_casilla_id("0435", surface="test_modelo_100_registry.casilla")
_BASE_IMPONIBLE_AHORRO_CASILLA = validated_casilla_id("0460", surface="test_modelo_100_registry.casilla")
_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA = validated_casilla_id("0505", surface="test_modelo_100_registry.casilla")
_ANUALIDADES_ALIMENTOS_TOTAL_CASILLA = validated_casilla_id("0527", surface="test_modelo_100_registry.casilla")
_CAPITAL_MOBILIARIO_AHORRO_CASILLA = validated_casilla_id("0041", surface="test_modelo_100_registry.casilla")
_ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA = validated_casilla_id("0259", surface="test_modelo_100_registry.casilla")
_GENERAL_BASE_IMPONIBLE_ROLE = "irpf_base_imponible_general"
_ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE = "irpf_re_agrup_interes_economico_base_imponible_imputada"
_ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    validated_casilla_id("0161", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    validated_casilla_id("0162", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    validated_casilla_id(
        "0163", surface="test_modelo_100_registry.casilla"
    ): _ATTRIBUTION_REGIME_AGRICULTURAL_MODE_FLAG_REFS,
    validated_casilla_id("0164", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
}
_INMUEBLE_ART_22_FORM_ORDER_REFS = frozenset({"ley-35-2006:art-22", _MODELO_100_2025_FORM_ORDER_REF})
_INMUEBLE_2025_CONTINUITY_REFS: Mapping[str, frozenset[str]] = {
    "irpf-inmueble-porcentaje-propiedad": _INMUEBLE_ART_22_FORM_ORDER_REFS,
    "irpf-inmueble-vivienda-habitual-flag": _INMUEBLE_ART_22_FORM_ORDER_REFS,
}
_ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID = "renta-anexo-c-base-liquidable-negativa-general"
_ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID = "renta-2025-base-liquidable-negativa-general-anterior"
# The base liquidable general negativa carry is grounded in Art. 50.3 LIRPF
# (4-year carry-forward of a negative base liquidable general); Art. 48
# (within-year integración) is a distinct mechanism and does not ground it.
_ANEXO_C_BASE_NEGATIVE_GENERAL_REFS = frozenset(
    {
        _BASE_LIQUIDABLE_ART_50_REF,
        _MODELO_100_2025_FORM_ORDER_REF,
    }
)
_MEMBER_GROUNDED_2025_CONSTRUCT_IDS = frozenset(
    {
        "renta-final-settlement",
        "renta-dependent-modelos",
        "renta-payments-retentions",
        _ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID,
    }
)
_GENERAL_BASE_CUOTA_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0532", "0533")
)
_ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    validated_casilla_id("0058", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}
    ),
    validated_casilla_id("0237", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}
    ),
    validated_casilla_id("0384", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF, _MODELO_100_2025_FORM_ORDER_REF}
    ),
}
_CAPITAL_GAINS_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
}
_OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
}
_AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("resultados", "deduccion_autonomica_res"): 482,
    ("resultados", "datos_adicionales_anexo_b"): 230,
}
_NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("resultados", "anexo_a_res"): 173,
    ("resultados", "anexo_c_res"): 180,
    ("resultados", "base_imponible_res"): 25,
    ("resultados", "base_liquidable_res"): 13,
    ("resultados", "calculo_impuesto_res"): 110,
    ("resultados", "compensacion_conyuges_res"): 12,
    ("resultados", "datos_adicionales_res"): 33,
    ("resultados", "g_cambio_residencia_ext_res"): 1,
    ("resultados", "gp_acciones_res"): 2,
    ("resultados", "gp_derechos_res"): 2,
    ("resultados", "gp_fondos_coti_res"): 2,
    ("resultados", "gp_fondos_res"): 2,
    ("resultados", "gp_otras_ganancias_ejer_ant_res"): 2,
    ("resultados", "gp_otras_ganancias_res"): 1,
    ("resultados", "gp_otros_criptomonedas_res"): 2,
    ("resultados", "gp_otros_elementos_res"): 3,
    ("resultados", "gp_otros_inmuebles_res"): 3,
    ("resultados", "gp_premios_res"): 6,
    ("resultados", "gp_reinversion_res"): 1,
    ("resultados", "ingreso_devolucion_res"): 1,
    ("resultados", "integracion_res"): 9,
    ("resultados", "irpf_ccaa_res"): 3,
    ("resultados", "red_base_imponible_res"): 9,
    ("resultados", "reg_estima_obj_agricola_res"): 3,
    ("resultados", "reg_estima_obj_res"): 3,
    ("resultados", "regimenes_especiales_res"): 13,
    ("resultados", "regularizacion_res"): 3,
}
_NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS: Mapping[tuple[str, ...], int] = {
    ("toma_datos_ampliada",): 36,
    ("toma_datos_ampliada", "anexo_a"): 49,
    ("toma_datos_ampliada", "dt9"): 1,
    ("toma_datos_ampliada", "g_cambio_residencia_ext"): 10,
    ("toma_datos_ampliada", "gp_acciones"): 12,
    ("toma_datos_ampliada", "gp_derechos"): 12,
    ("toma_datos_ampliada", "gp_fondos"): 12,
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otras_ganancias"): 1,
    ("toma_datos_ampliada", "gp_otras_ganancias_ejer_ant"): 2,
    ("toma_datos_ampliada", "gp_otros_criptomonedas"): 34,
    ("toma_datos_ampliada", "gp_otros_elementos"): 47,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
    ("toma_datos_ampliada", "gp_reinversion"): 1,
    ("toma_datos_ampliada", "inmuebles"): 128,
    ("toma_datos_ampliada", "rdto_capital_mobiliario"): 3,
    ("toma_datos_ampliada", "rdto_trabajo"): 7,
    ("toma_datos_ampliada", "red_base_imponible"): 25,
    ("toma_datos_ampliada", "reg_estima_directa"): 5,
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
    ("toma_datos_ampliada", "regimen_especial"): 19,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
_NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
_M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE: Mapping[str, frozenset[str]] = {
    "borrador_pdf": frozenset(
        {
            _BASE_LIQUIDABLE_ART_50_REF,
            _GENERAL_SCALE_ART_63_REF,
            _STATE_DEDUCTION_ART_67_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
        }
    ),
    "declaracion_pdf": frozenset(
        {
            "ley-35-2006:art-27",
            "ley-35-2006:art-28",
            "ley-35-2006:art-30",
            _OBJECTIVE_ESTIMATION_ART_31_REF,
            "ley-35-2006:art-32",
            _GENERAL_BASE_ART_48_REF,
            _BASE_LIQUIDABLE_ART_50_REF,
            _GENERAL_SCALE_ART_63_REF,
            _STATE_DEDUCTION_ART_67_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            "ley-35-2006:art-79",
            # art-99 (obligacion de pagos a cuenta) plus its RIRPF implementing
            # articles: casilla 0604 (pagos fraccionados ingresados) is a
            # computed casilla whose formula is grounded in RD 439/2007
            # art-109 (obligados al pago fraccionado) and art-110 (importe
            # del fraccionamiento), not just the LIRPF framework article.
            "ley-35-2006:art-99",
            "ley-35-2006:art-103",
            "rd-439-2007:art-109",
            "rd-439-2007:art-110",
        }
    ),
}
_PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS: Mapping[CasillaId, tuple[str, ...]] = {
    validated_casilla_id("0153", surface="test_modelo_100_registry.casilla"): (
        "rendimientos_capital_inmobiliario",
        "retenciones",
    ),
    validated_casilla_id("0591", surface="test_modelo_100_registry.casilla"): ("resultado_declaracion",),
    validated_casilla_id("0592", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0593", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0594", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0596", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0597", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0598", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0599", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0600", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0601", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0602", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0603", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0604", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0605", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0606", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
    validated_casilla_id("0609", surface="test_modelo_100_registry.casilla"): (
        "retenciones_ingresos_cuenta_pagos_fraccionados",
    ),
}
_NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS = frozenset(
    {
        "renta-2025-base-liquidable-negativa-general-anterior",
    }
)
_NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS = frozenset(
    {
        "renta-anexo-c-base-liquidable-negativa-general",
        "renta-movable-capital",
        "renta-real-estate-capital",
        "renta-work-income",
    }
)
_NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS = frozenset({"modelo-100-deadline"})
_SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025: Mapping[CasillaId, str] = {
    validated_casilla_id("0528", surface="test_modelo_100_registry.casilla"): _GENERAL_SCALE_ART_63_REF,
    validated_casilla_id("0529", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    validated_casilla_id("0530", surface="test_modelo_100_registry.casilla"): _GENERAL_SCALE_ART_63_REF,
    validated_casilla_id("0531", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    validated_casilla_id("0536", surface="test_modelo_100_registry.casilla"): _SAVINGS_STATE_SCALE_ART_66_REF,
    validated_casilla_id("0537", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
    validated_casilla_id("0538", surface="test_modelo_100_registry.casilla"): _SAVINGS_STATE_SCALE_ART_66_REF,
    validated_casilla_id("0539", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
}
_ATTRIBUTION_DETAIL_ART_86_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0259", "0264", "0265", "1597", "1598", "1599", "1600")
)
_ATTRIBUTION_DETAIL_SECTIONS = frozenset(
    {
        "re_at_rentas",
        "re_agrup_interes_economico",
        "re_agrup_interes_economico_res",
    }
)
_GENERAL_BASE_ART_48_ONLY_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0431", "0432", "0433", "0434", "0435")
)
_SAVINGS_BASE_ART_49_ONLY_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in (
        "0429",
        "0436",
        "0439",
        "0440",
        "0441",
        "0442",
        "0443",
        "0444",
        "0445",
        "0446",
        "0447",
        "0448",
        "0449",
        "0450",
        "0451",
        "0452",
        "0453",
        "0454",
        "0455",
        "0460",
    )
)
_SAVINGS_BASE_ART_49_ONLY_ROLES = frozenset(
    {
        "irpf_base_imponible_ahorro",
        "irpf_saldo_neto_gyp_ahorro_limite_25pct",
        "irpf_saldo_neto_gyp_ahorro_pendiente",
        "irpf_saldo_neto_gyp_ahorro_pendiente_resto",
        "irpf_saldo_neto_rdto_capital_mobiliario_ahorro",
        "irpf_saldo_neto_rdto_capital_mobiliario_ahorro_pendiente_reduccion",
        "irpf_saldo_neto_rdto_capital_mobiliario_ejercicios_anteriores",
        "irpf_saldo_neto_rdto_capital_mobiliario_resto_pendiente",
    }
)
