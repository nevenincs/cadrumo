"""Shared support for Modelo 100 registry tests."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ccaa_catalogue import ccaa_choices
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot import legal_window_covers_devengo
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    newest_authored_edition,
    newest_authored_editions,
    revision_covering,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.contribuyente.ccaa import CCAA
from cadrumo.domain.contribuyente.deduccion_maternidad import compute_deduccion_maternidad_0611
from cadrumo.tests.aeat_literal_fixtures import aeat_url, configured_path

from ..compiler.authority import compiled_bundled_authority
from ..compiler.validator import RegistryValidator
from .profile_schema_support import load_user_profile_schema

DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))
_UNKNOWN_CONSTRUCT_MEMBER_CASILLA: CasillaId = validated_casilla_id(
    "0000-ghost",
    surface="_UNKNOWN_CONSTRUCT_MEMBER_CASILLA",
)


def m100_second_newest_deduccion_maternidad_bindings() -> Mapping[str, Decimal]:
    """Return the empty-descendant maternity binding of the second-newest Modelo 100 edition from domain law."""
    return {
        "renta-profile-deduccion-maternidad": Decimal(
            compute_deduccion_maternidad_0611(
                [],
                filing_year=newest_authored_editions("100", 2)[0],
                authority=compiled_bundled_authority(),
            ),
        ),
    }


class OfficialRow(NamedTuple):
    """One casilla row of the AEAT record-design dictionary printed for an exercise."""

    name: str
    section: tuple[str, ...]
    box: str
    label: str


_OFFICIAL_ROW = re.compile(r"^(?P<name>[^=\[]+)=\[(?P<path>[^\]]*)\]\[[^\]]*\]\[(?P<box>[^\]]*)\]\[(?P<label>.*)\]\s*$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _snake(part: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", part).lower()


@cache
def official_rows(filing_year: int) -> tuple[OfficialRow, ...]:
    """Read the official Modelo 100 declaration dictionary the AEAT published for one exercise.

    The section is the dictionary path between the economic-data root and the
    variable, in the registry's snake-case spelling. Nothing here is read from
    the registry under test.
    """
    directory = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files")
    (dictionary,) = directory.glob(f"*-100-diccionario-declaracion-individual-ejercicio-{filing_year}-*.properties")
    rows: list[OfficialRow] = []
    for line in dictionary.read_text(encoding="cp1252", errors="replace").splitlines():
        matched = _OFFICIAL_ROW.match(line)
        if matched is None:
            continue
        parts = matched["path"].strip("/").split("/")
        rows.append(
            OfficialRow(matched["name"], tuple(_snake(part) for part in parts[1:-1]), matched["box"], matched["label"])
        )
    return tuple(rows)


def official_dictionary_years() -> tuple[int, ...]:
    """Every authored Modelo 100 exercise the AEAT published a declaration dictionary for."""
    directory = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files")
    return tuple(
        revision.valid_from.year
        for revision in authored_revisions("100")
        if any(
            directory.glob(
                f"*-100-diccionario-declaracion-individual-ejercicio-{revision.valid_from.year}-*.properties"
            )
        )
    )


def same_printed_label(registry_label: str, printed_label: str) -> bool:
    """Whether a registry label is the one the dictionary prints, ignoring the accents some dictionaries drop."""

    def fold(label: str) -> str:
        return "".join(
            char for char in unicodedata.normalize("NFKD", label) if not unicodedata.combining(char)
        ).casefold()

    return fold(registry_label) == fold(printed_label)


def official_row(filing_year: int, name: str) -> OfficialRow | None:
    """Return the dictionary row of one variable name in one exercise, if the exercise prints it."""
    return next((row for row in official_rows(filing_year) if row.name == name), None)


@cache
def source_root() -> Path:
    return bundled_path()


@cache
def _registry_root() -> Path:
    return source_root() / "registry" / "aeat"


@cache
def loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    # The compiled authority carries the supplementary annual-Orden legal ids
    # that governed facts cite; the raw tree load does not.
    authority = compiled_bundled_authority()
    return {modelo.id: modelo for modelo in authority.modelos}, authority.catalogues


@cache
def authored_ccaa_choices() -> tuple[CCAA, ...]:
    """Return the residence tokens the authored catalogue declares, in its own order.

    A case that walks every recorded IRPF residence asks the catalogue instead of
    listing tokens, so a territory joining or leaving the fact reaches the case.
    """
    _modelos_by_id, catalogues = loaded_registry()
    return ccaa_choices(
        authority=CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years()),
    )


@cache
def registry_validator() -> RegistryValidator:
    _modelos_by_id, catalogues = loaded_registry()
    return RegistryValidator(
        catalogues,
        source_root=source_root(),
        user_profile_schema=load_user_profile_schema(),
    )


@cache
def modelo_100_revision(filing_year: int | None = None) -> ModeloRevision:
    """Return the authored, hydrated edition for one ejercicio, the newest authored one by default.

    Content assertions about an authored edition read the canonical authoring
    load, which is not gated by the runtime support floor; a filing snapshot is
    only for questions about what runtime would select.
    """
    exercise = newest_authored_edition("100") if filing_year is None else filing_year
    return loaded_registry()[0]["100"].revisions[str(exercise)]


def governing_redaction(reference_id: str, revision: ModeloRevision) -> str:
    """Return ``reference_id`` when it governs ``revision``, else the one row of its article that does.

    An article the catalogue records in several redactions is cited in the one in
    force at the edition's devengo, so an expectation written against the current
    redaction resolves to the historical row for an earlier edition.
    """
    legal = loaded_registry()[1].legal
    cited = legal[reference_id]
    if legal_window_covers_devengo(revision, cited):
        return reference_id
    article = (cited.document_id, cited.article, cited.section)
    governing = [
        reference.id
        for reference in legal.values()
        if (reference.document_id, reference.article, reference.section) == article
        and legal_window_covers_devengo(revision, reference)
    ]
    assert len(governing) == 1, (reference_id, revision.id, governing)
    return governing[0]


def modelo_100_snapshot(filing_year: int | None = None) -> RegistrySnapshot:
    """Return the snapshot of one ejercicio at the grade that year reaches, the newest authored one by default.

    An authored edition is built at its declared grade; a year the registry
    carries across from the nearest edition reaches calculation grade at most,
    so the grade comes from the authority rather than being requested here.
    """
    modelos_by_id, catalogues = loaded_registry()
    filing_year = newest_authored_edition("100") if filing_year is None else filing_year
    with bundled_indexed_authority().operation() as operation:
        grade = operation.reachable_authority_grade("100", filing_year=filing_year, period="0A")
    return build_snapshot(
        modelos_by_id["100"],
        catalogues,
        source_root=source_root(),
        filing_year=filing_year,
        period="0A",
        grade=grade,
    )


PERSONAL_FAMILY_BINDINGS: frozenset[str] = frozenset(
    {
        "renta-profile-tax-id",
        "renta-profile-display-name",
        "renta-profile-tax-residence-ccaa",
        "renta-profile-declaration-type",
        "renta-profile-taxpayer-sex",
        "renta-profile-marital-status",
        "renta-profile-taxpayer-birth-date",
        "renta-profile-spouse-tax-id",
        "renta-profile-spouse-display-name",
        "renta-profile-spouse-birth-date",
        "renta-profile-spouse-sex",
        "renta-profile-taxpayer-disability-grade",
        "renta-profile-taxpayer-death-date",
        "renta-profile-spouse-disability-grade",
        "renta-profile-spouse-non-resident-irpf",
        "renta-profile-spouse-eu-eea-resident",
        "renta-profile-spouse-eu-eea-country",
        "renta-profile-family-descendants-eu-eea-deduction",
        "renta-profile-family-minor-children-in-unit",
        "renta-family-descendant-tax-id",
        "renta-family-descendant-display-name",
        "renta-family-descendant-birth-date",
        "renta-family-descendant-disability-grade",
        "renta-family-descendant-death-date",
        "renta-family-ascendant-tax-id",
        "renta-family-ascendant-display-name",
        "renta-family-ascendant-birth-date",
        "renta-family-ascendant-disability-grade",
        "renta-family-ascendant-cohabiting-descendant-count",
        "renta-family-ascendant-death-date",
    },
)


def binding_map_by_casilla(*pairs: tuple[object, str]) -> Mapping[CasillaId, str]:
    return {
        validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla"): binding_id
        for casilla_id, binding_id in pairs
    }


PERSONAL_FAMILY_CASILLAS: frozenset[CasillaId] = frozenset(
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

SOURCE_FOUNDATION_APPLICATION_LINKS: frozenset[str] = frozenset(
    {
        "modelo-100-portal",
        "modelo-100-export",
        "modelo-100-filed-declarations-observation",
        "modelo-100-calculation",
        "modelo-100-review",
        "modelo-100-approval",
        "modelo-100-reconciliation",
        "modelo-100-workflow",
    },
)


def modelo_100_newest_authored_revision() -> tuple[ModeloDefinition, ModeloRevision]:
    modelos_by_id, _catalogues = loaded_registry()
    modelo = modelos_by_id["100"]
    return modelo, modelo.revisions[revision_covering("100", newest_authored_edition("100")).id]


def modelo_100_with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def assert_registry_validation_error(modelo: ModeloDefinition, *, match: str) -> None:
    with pytest.raises(RegistryValidationError, match=match):
        registry_validator().validate_modelo(modelo)


GENERAL_BASE_ART_48_REF = "ley-35-2006:art-48"
SAVINGS_BASE_ART_49_REF = "ley-35-2006:art-49"
BASE_LIQUIDABLE_ART_50_REF = "ley-35-2006:art-50"
PERSONAL_FAMILY_MINIMUM_ART_56_REF = "ley-35-2006:art-56"
STATE_INTEGRAL_QUOTA_ART_62_REF = "ley-35-2006:art-62"
GENERAL_SCALE_ART_63_REF = "ley-35-2006:art-63"
STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF = "ley-35-2006:art-64"
_SAVINGS_STATE_SCALE_ART_66_REF = "ley-35-2006:art-66"
STATE_DEDUCTION_ART_67_REF = "ley-35-2006:art-67"
BROAD_DEDUCTION_ART_68_REF = "ley-35-2006:art-68"
NEW_COMPANY_INVESTMENT_ART_68_1_REF = "ley-35-2006:art-68.1"
BUSINESS_INVESTMENT_ART_68_2_REF = "ley-35-2006:art-68.2"
DONATION_DEDUCTION_ART_68_3_REF = "ley-35-2006:art-68.3"
CEUTA_MELILLA_DEDUCTION_ART_68_4_REF = "ley-35-2006:art-68.4"
CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF = "ley-35-2006:art-68.5"
DEDUCTION_LIMITS_ART_69_REF = "ley-35-2006:art-69"
ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF = "ley-35-2006:da-50"
EV_CHARGING_POINT_DEDUCTION_DA_58_REF = "ley-35-2006:da-58"
HOME_INVESTMENT_DEDUCTION_DT_18_REF = "ley-35-2006:dt-18"
RENTAL_HOUSING_DEDUCTION_DT_15_REF = "ley-35-2006:dt-15"
AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF = "ley-35-2006:art-73"
AUTONOMIC_GENERAL_SCALE_ART_74_REF = "ley-35-2006:art-74"
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF = "ley-35-2006:art-75"
_AUTONOMIC_SAVINGS_SCALE_ART_76_REF = "ley-35-2006:art-76"
AUTONOMIC_DEDUCTION_ART_77_REF = "ley-35-2006:art-77"
ATTRIBUTION_REGIME_ART_86_REF = "ley-35-2006:art-86"
_OBJECTIVE_ESTIMATION_ART_31_REF = "ley-35-2006:art-31"
_ATTRIBUTION_OBJECTIVE_ESTIMATION_ART_39_REF = "rd-439-2007:art-39"
_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF = "ley-35-2006:da-60"
FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"
FRACTIONAL_PAYMENT_AMOUNT_ARTICLE_REF = "rd-439-2007:art-110"
PAYMENTS_ON_ACCOUNT_ARTICLE_REF = "ley-35-2006:art-99"
MODELO_100_2025_FORM_ORDER_REF = "orden-hac-277-2026:art-3"
BROAD_INCOME_CHAPTER_SPAN_REFS = frozenset(
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
CAPITAL_GAINS_SECTION_REFS = frozenset(
    {
        "ley-35-2006:art-33",
        "ley-35-2006:art-34",
    }
)
RIC_RESERVA_SECTION = ("resultados", "anexo_a_res", "reserva_inversiones_canarias_res")
RIB_RESERVA_SECTION = ("resultados", "anexo_a_res", "reserva_inversiones_baleares_res")
RIB_BALEARES_DA70_REF = "ley-31-2022:da-70"
RIC_DOTACION_IMPORTE_ROLE = "irpf_anexo_a_ric_dotacion_importe"
RIC_DOTACION_ANIO_ROLE = "irpf_anexo_a_ric_dotacion_anio"
RIC_INVERSION_TIPO_ABD_ROLE = "irpf_anexo_a_ric_inversion_tipo_abd"
RIC_INVERSION_TIPO_CD_ROLE = "irpf_anexo_a_ric_inversion_tipo_cd"
RIB_DOTACION_IMPORTE_ROLE = "irpf_anexo_a_rib_dotacion_importe"
RIB_DOTACION_ANIO_ROLE = "irpf_rib_baleares_dotacion_anio"
RIB_INVERSION_TIPO_AB_ROLE = "irpf_anexo_a_rib_inversion_tipo_ab"
RIB_INVERSION_TIPO_C_ROLE = "irpf_rib_baleares_inversion_tipo_c"
LEGACY_RIB_SPLIT_ROLES = frozenset(
    {
        "irpf_anexo_a_rib_dotacion_anio",
        "irpf_anexo_a_rib_inversion_tipo_c",
    }
)
HOUSING_ENERGY_RESULTS_SECTION = ("resultados", "anexo_a_res", "deduccion_mejoras_energeticas_viv_res")
HOUSING_ENERGY_DEDUCTION_RESULT_ROLE = "irpf_anexo_a_mejora_energia_deduccion_importe"
EV_CHARGING_POINT_RESULTS_SECTION = ("resultados", "anexo_a_res", "vehiculos_elec_y_puntos_carga_res")
EV_CHARGING_POINT_DEDUCTION_ROLE = "irpf_deduccion_vehiculo_electrico_importe"
ANEXO_C_ENERGY_EXCESS_SECTION = ("resultados", "anexo_c_res", "excesos_eficiencia_energetica_res")
ANEXO_C_ENERGY_EXCESS_ROLE_PREFIX = "irpf_anexo_c_exceso_eficiencia_energetica_"
ANEXO_C_ENERGY_EXCESS_ROLES = frozenset(
    {
        "irpf_anexo_c_exceso_eficiencia_energetica_pendiente_inicio",
        "irpf_anexo_c_exceso_eficiencia_energetica_aplicado",
        "irpf_anexo_c_exceso_eficiencia_energetica_pendiente_fin",
        "irpf_anexo_c_exceso_eficiencia_energetica_generado",
    }
)
ANEXO_B_IMPORTE_SATISFECHO_ROLE = "irpf_anexo_b_importe_satisfecho"
ANEXO_B_IMPORTE_SATISFECHO_LABEL = "Cantidades satisfechas"
ANEXO_B_IMPORTE_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_ctrd",
        "an_b_inf_adc_arr",
        "an_b_inf_adc_avh",
        "an_b_inf_adc_arrvm",
    }
)
ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE = "irpf_anexo_b_importe_anual_satisfecho"
ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL = "Importe anual satisfecho"
ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_enf",
        "an_b_inf_adc_dep",
        "an_b_inf_adc_aia",
        "an_b_inf_adc_aav",
    }
)
ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE = "irpf_anexo_b_otros_gastos_importe_anual"
ANEXO_B_OTROS_GASTOS_SECTION = "an_b_inf_adc_aia"
ANEXO_B_OTROS_GASTOS_VARIABLE = "CANTAIAOG"
ANEXO_B_AAV_SECTION = "an_b_inf_adc_aav"
_ANEXO_B_AAV_IMPORTE_SATISFECHO_ROLE = "irpf_anexo_b_aav_importe_satisfecho"
_ANEXO_B_AAV_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_aav_importe_aplicado"
_ANEXO_B_AAV_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_aav_importe_pendiente"
ANEXO_B_AAV_AMOUNT_ROWS = {
    "2202": ("Importe total satisfecho en 2025", _ANEXO_B_AAV_IMPORTE_SATISFECHO_ROLE),
    "2203": ("Importe satisfecho que se aplica en el ejercicio", _ANEXO_B_AAV_IMPORTE_APLICADO_ROLE),
    "2204": (
        "Importe satisfecho en 2025 pendiente de aplicación en ejercicios futuros",
        _ANEXO_B_AAV_IMPORTE_PENDIENTE_ROLE,
    ),
}
ANEXO_B_BALEARES_NACIMIENTO_SECTION = "an_b_inf_ad_i_baleares"
ANEXO_B_BALEARES_NACIMIENTO_ROWS = {
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
ANEXO_B_ACCOUNT_SECTION = "an_b_inf_ad_cm_viv_hab"
_ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE = "irpf_anexo_b_cm_viv_hab_titular_cuenta"
_ANEXO_B_ACCOUNT_OPENING_DATE_ROLE = "irpf_anexo_b_account_opening_date"
_ANEXO_B_ACCOUNT_IDENTIFIER_ROLE = "irpf_anexo_b_account_identifier"
_ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE = "irpf_anexo_b_account_foreign_flag"
_ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE = "irpf_anexo_b_account_balance_increase"
ANEXO_B_ACCOUNT_ROWS = {
    "2214": ("Titular de la cuenta", _ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE),
    "2215": ("Fecha de apertura", _ANEXO_B_ACCOUNT_OPENING_DATE_ROLE),
    "2216": ("Identificación de la cuenta", _ANEXO_B_ACCOUNT_IDENTIFIER_ROLE),
    "2217": (
        'Marca una "X" si se trata de cuenta abierta en el extranjero',
        _ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE,
    ),
    "2218": ("Incremento del saldo en el ejercicio", _ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE),
    "2219": ("Titular de la cuenta", _ANEXO_B_CM_VIV_HAB_TITULAR_CUENTA_ROLE),
    "2220": ("Fecha de apertura", _ANEXO_B_ACCOUNT_OPENING_DATE_ROLE),
    "2221": ("Identificación de la cuenta", _ANEXO_B_ACCOUNT_IDENTIFIER_ROLE),
    "2222": (
        'Marca una "X" si se trata de cuenta abierta en el extranjero',
        _ANEXO_B_ACCOUNT_FOREIGN_FLAG_ROLE,
    ),
    "2223": ("Incremento del saldo en el ejercicio", _ANEXO_B_ACCOUNT_BALANCE_INCREASE_ROLE),
}
_ANEXO_B_CARRY_FORWARD_PENDING_ROLE = "irpf_anexo_b_carry_forward_pending"
MADRID_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "madrid_res")
C_VALENCIANA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "c_valenciana_res")
GALICIA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "galicia_res")
ANEXO_B_INST_AUTO_SECTION = ("resultados", "datos_adicionales_anexo_b", "an_b_inf_adc_inst_auto")
_LEGACY_MADRID_CUIDADO_ASCENDIENTES_PENDING_ROLE = "irpf_deduccion_autonomica_cuidado_ascendientes_pendiente"
_LEGACY_MADRID_INTERESES_PRESTAMOS_ESTUDIOS_PENDING_ROLE = "irpf_deduccion_estudios_intereses_prestamo_pendiente"
GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE = "irpf_deduccion_galicia_inmueble_vacio_adecuacion"
_LEGACY_GALICIA_INMUEBLE_VACIO_ADECUACION_PENDING_ROLE = "irpf_deduccion_inmueble_vacio_adecuacion_pendiente"
ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE = "irpf_anexo_b_inst_auto_importe_pendiente_anterior"
_LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_arrendamiento_importe_aplicado"
_LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_arrendamiento_importe_pendiente"
_LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_APLICADO_ROLE = "irpf_anexo_b_nacimiento_vivienda_importe_aplicado"
_LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE = "irpf_anexo_b_nacimiento_vivienda_importe_pendiente"
_LEGACY_ANEXO_B_ENERGIA_SATISFECHO_APLICADO_ROLE = "irpf_anexo_b_energia_satisfecho_aplicado"
_LEGACY_ANEXO_B_ENERGIA_SATISFECHO_PENDIENTE_ROLE = "irpf_anexo_b_energia_satisfecho_pendiente"
_LEGACY_ANEXO_B_VIVIENDA_REINVERSION_PENDIENTE_ROLE = "irpf_anexo_b_vivienda_reinversion_pendiente"
_PENDING_OUTLIER_SECTIONS_AND_ROLES = {
    "1115": (MADRID_DEDUCTION_SECTION, "irpf_deduccion_madrid_cuidado_ascendientes"),
    "1118": (MADRID_DEDUCTION_SECTION, "irpf_deduccion_madrid_intereses_prestamos_estudios"),
    "1078": (GALICIA_DEDUCTION_SECTION, GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE),
}
_MADRID_REUSED_ID_ROLES = {
    ("1116", "Por gastos derivados de arrendamiento de vivienda"): "irpf_deduccion_madrid_gastos_arrendamiento",
    (
        "1117",
        "Por el pago de intereses de préstamos para adquisición de vivienda por jóvenes menores de 30 años",
    ): "irpf_deduccion_madrid_intereses_prestamos_vivienda",
    (
        "1119",
        "Por adquisición de vivienda habitual por nacimiento o adopción de hijos",
    ): "irpf_deduccion_madrid_vivienda_nacimiento_adopcion",
    ("1120", "Por la obtención de la condición de familia numerosa"): "irpf_deduccion_madrid_familia_numerosa",
    ("1120", "Importe de la deducción"): "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_importe",
}
_MADRID_VIVIENDA_PARENT_ROLES = {
    "Por adquisición de vivienda habitual por nacimiento o adopción de hijos": (
        "irpf_deduccion_madrid_vivienda_nacimiento_adopcion"
    ),
    "Por adquisición de vivienda habitual en municipios en riesgo de despoblación": (
        "irpf_deduccion_madrid_vivienda_municipio_riesgo"
    ),
}
_MADRID_VIVIENDA_PRECIO_LABEL = "Precio de adquisición/cantidades invertidas"
_MADRID_VIVIENDA_ANIO_LABEL = "Año de adquisición"
_INST_AUTO_REMAINING_BOXES = ("1117", "1120", "1186", "1709")
_INST_AUTO_REMAINING_LABEL = re.compile(r"^Importe satisfecho en .* pendiente de aplicación en ejercicios futuros$")


def carry_forward_pending_outliers(filing_year: int) -> dict[str, tuple[str, tuple[str, ...], str]]:
    """Pending carry-forward boxes the exercise prints in a regional-deduction section: box to label, section, role."""
    return {
        row.box: (row.label, row.section, _PENDING_OUTLIER_SECTIONS_AND_ROLES[row.box][1])
        for row in official_rows(filing_year)
        if row.box in _PENDING_OUTLIER_SECTIONS_AND_ROLES
        and row.section == _PENDING_OUTLIER_SECTIONS_AND_ROLES[row.box][0]
    }


def madrid_reused_id_deduction_rows(filing_year: int) -> dict[str, tuple[str, str]]:
    """Madrid deduction boxes whose number an earlier layout used for another row: box to label and role."""
    rows: dict[str, tuple[str, str]] = {}
    for row in official_rows(filing_year):
        role = _MADRID_REUSED_ID_ROLES.get((row.box, row.label))
        if role is not None and row.section == MADRID_DEDUCTION_SECTION:
            rows[row.box] = (row.label, role)
    return rows


def madrid_vivienda_acquisition_detail_rows(filing_year: int) -> dict[str, tuple[str, str]]:
    """The acquisition detail rows that follow a Madrid vivienda deduction: box to label and role.

    A detail block is the deduction's own row followed, in the printed order, by
    the purchase price and the year of acquisition.
    """
    rows = official_rows(filing_year)
    detail: dict[str, tuple[str, str]] = {}
    for index, row in enumerate(rows[:-2]):
        role = _MADRID_VIVIENDA_PARENT_ROLES.get(row.label)
        price, acquired = rows[index + 1], rows[index + 2]
        if (
            role is not None
            and (row.box, row.label) not in _MADRID_REUSED_ID_ROLES
            and row.section == MADRID_DEDUCTION_SECTION
            and (price.label, acquired.label) == (_MADRID_VIVIENDA_PRECIO_LABEL, _MADRID_VIVIENDA_ANIO_LABEL)
        ):
            detail[row.box] = (row.label, role)
            detail[price.box] = (price.label, f"{role}_precio")
            detail[acquired.box] = (acquired.label, f"{role}_anio")
    return detail


def carry_forward_remaining_inst_auto_rows(filing_year: int) -> dict[str, str]:
    """Remaining-amount boxes the exercise prints in the installation-and-automation block: box to label."""
    return {
        row.box: row.label
        for row in official_rows(filing_year)
        if row.box in _INST_AUTO_REMAINING_BOXES
        and row.section == ANEXO_B_INST_AUTO_SECTION
        and _INST_AUTO_REMAINING_LABEL.match(row.label)
    }


LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES = frozenset(
    {
        _ANEXO_B_CARRY_FORWARD_PENDING_ROLE,
        _LEGACY_MADRID_CUIDADO_ASCENDIENTES_PENDING_ROLE,
        _LEGACY_MADRID_INTERESES_PRESTAMOS_ESTUDIOS_PENDING_ROLE,
        _LEGACY_GALICIA_INMUEBLE_VACIO_ADECUACION_PENDING_ROLE,
    }
)
LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES = frozenset(
    {
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_ENERGIA_SATISFECHO_APLICADO_ROLE,
        _LEGACY_ANEXO_B_ENERGIA_SATISFECHO_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_VIVIENDA_REINVERSION_PENDIENTE_ROLE,
    }
)
LEGACY_MADRID_REUSED_ID_ROLES = frozenset(
    {
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_APLICADO_ROLE,
        _LEGACY_ANEXO_B_ARRENDAMIENTO_IMPORTE_PENDIENTE_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_APLICADO_ROLE,
        _LEGACY_ANEXO_B_NACIMIENTO_VIVIENDA_IMPORTE_PENDIENTE_ROLE,
    }
)
ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE = "irpf_anexo_b_total_cantidades_invertidas_deduccion"
ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL = "Importe total de las cantidades invertidas con derecho a deducción"
ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS = frozenset(
    {
        "an_b_inf_adc_enf",
        "an_b_inf_adc_dep",
        "an_b_inf_adc_aia",
    }
)
ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE = "irpf_anexo_b_contribuyente_con_derecho_clave"
ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL = "Contribuyente con derecho a deducción"
ANEXO_B_INVERSION_TOTAL_ROLE = "irpf_anexo_b_importe_total_deduccion_por_tipo"
ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX = "Importe total de las cantidades"
ANEXO_B_INVERSION_IMPORTE_ROLE = "irpf_anexo_b_deduccion_inversion_importe"
ANEXO_B_INVERSION_IMPORTE_LABEL = "Importe de la inversión con derecho a deducción"
ANEXO_B_INVERSION_TOTAL_SECTIONS = frozenset(
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
ANEXO_B_EPS_SECTION = "an_b_inf_adc_eps"
ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE = "irpf_anexo_b_prima_seguro_credito_arrendamiento"
ANEXO_B_PRIMA_SEGURO_LABEL = "Primas satisfechas"
ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE = "irpf_eps_primas_seguro_deducibles_total"
ANEXO_B_TOTAL_SATISFECHO_ROLE = "irpf_anexo_b_importe_total_satisfecho"
ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE = "irpf_anexo_b_cantidades_deducibles_satisfechas"
ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL = "Cantidades satisfechas con derecho a deducción"
ANEXO_B_TOTAL_SATISFECHO_SECTIONS = frozenset(
    {
        "an_b_inf_adc_ctrd",
        "an_b_inf_adc_arr",
        "an_b_inf_adc_arrvm",
    }
)
DONATION_DEDUCTION_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0552", "0553", "0722", "0723", "0724", "0725")
)
CASILLA_0921 = validated_casilla_id("0921", surface="test_modelo_100_registry.casilla")
CANARIAS_DONACION_DESCENDIENTES_ROLE = "irpf_deduccion_canarias_donacion_descendientes"
ANDALUCIA_EJERCICIO_FISICO_ROLE = "irpf_deduccion_andalucia_ejercicio_fisico"
CASILLA_1091 = validated_casilla_id("1091", surface="test_modelo_100_registry.casilla")
C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE = "irpf_deduccion_c_valenciana_labores_no_remuneradas_hogar"
EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE = "irpf_deduccion_extremadura_vivienda_zonas_rurales"
CASILLA_0581 = validated_casilla_id("0581", surface="test_modelo_100_registry.casilla")
CASILLA_0575 = validated_casilla_id("0575", surface="test_modelo_100_registry.casilla")
CASILLA_0580 = validated_casilla_id("0580", surface="test_modelo_100_registry.casilla")
INCENTIVO_ART_33_REGULARIZATION_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0568", "0569")
)
REGULARIZACION_PREVIOUS_INTEREST_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0582", "0583")
)
REGULARIZACION_DEDUCTION_LOSS_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0572", "0574", "0577", "0579")
)
REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0573", "0576", "0578", "0581")
)
_DEDUCTION_LOSS_INTEREST_STATE_ROLE = "irpf_intereses_demora_perdida_deduccion_estatal"
DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE = "irpf_intereses_demora_perdida_deduccion_autonomica"
LIRPF_CAPITAL_GAINS_ART_33_REF = "ley-35-2006:art-33"
DA45_CLAUSULA_SUELO_REF = "ley-35-2006:da-45"
RIRPF_DEDUCTION_LOSS_ART_59_REF = "rd-439-2007:art-59"
LGT_INTEREST_ART_26_REF = "ley-58-2003:art-26"
_ATTRIBUTION_REGIME_MODE_FLAG_REFS = frozenset({ATTRIBUTION_REGIME_ART_86_REF})
_ATTRIBUTION_REGIME_AGRICULTURAL_MODE_FLAG_REFS = frozenset(
    {
        _OBJECTIVE_ESTIMATION_ART_31_REF,
        ATTRIBUTION_REGIME_ART_86_REF,
        _ATTRIBUTION_OBJECTIVE_ESTIMATION_ART_39_REF,
    }
)
ECONOMIC_ACTIVITY_SECTION_REFS = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }
)
GENERAL_BASE_GYP_LIMIT_CASILLA = validated_casilla_id("0433", surface="test_modelo_100_registry.casilla")
SAVINGS_BASE_GYP_LIMIT_CASILLA = validated_casilla_id("0446", surface="test_modelo_100_registry.casilla")
GENERAL_BASE_IMPONIBLE_CASILLA = validated_casilla_id("0435", surface="test_modelo_100_registry.casilla")
BASE_IMPONIBLE_AHORRO_CASILLA = validated_casilla_id("0460", surface="test_modelo_100_registry.casilla")
BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA = validated_casilla_id("0505", surface="test_modelo_100_registry.casilla")
ANUALIDADES_ALIMENTOS_TOTAL_CASILLA = validated_casilla_id("0527", surface="test_modelo_100_registry.casilla")
CAPITAL_MOBILIARIO_AHORRO_CASILLA = validated_casilla_id("0041", surface="test_modelo_100_registry.casilla")
ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA = validated_casilla_id("0259", surface="test_modelo_100_registry.casilla")
GENERAL_BASE_IMPONIBLE_ROLE = "irpf_base_imponible_general"
ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE = "irpf_re_agrup_interes_economico_base_imponible_imputada"
ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    validated_casilla_id("0161", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    validated_casilla_id("0162", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    validated_casilla_id(
        "0163", surface="test_modelo_100_registry.casilla"
    ): _ATTRIBUTION_REGIME_AGRICULTURAL_MODE_FLAG_REFS,
    validated_casilla_id("0164", surface="test_modelo_100_registry.casilla"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
}
_INMUEBLE_ART_22_REFS = frozenset({"ley-35-2006:art-22"})
INMUEBLE_2025_CONTINUITY_REFS: Mapping[str, frozenset[str]] = {
    "irpf-inmueble-porcentaje-propiedad": _INMUEBLE_ART_22_REFS,
    "irpf-inmueble-vivienda-habitual-flag": _INMUEBLE_ART_22_REFS,
}
ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID = "renta-anexo-c-base-liquidable-negativa-general"
ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID = "renta-base-liquidable-negativa-general-anterior"
# The base liquidable general negativa carry is grounded in Art. 50.3 LIRPF
# (4-year carry-forward of a negative base liquidable general); Art. 48
# (within-year integración) is a distinct mechanism and does not ground it.
# Art. 49 arrives through the previous-return dependency the construct shares with the savings carries.
ANEXO_C_BASE_NEGATIVE_GENERAL_REFS = frozenset(
    {
        BASE_LIQUIDABLE_ART_50_REF,
        SAVINGS_BASE_ART_49_REF,
        MODELO_100_2025_FORM_ORDER_REF,
    }
)
MEMBER_GROUNDED_2025_CONSTRUCT_IDS = frozenset(
    {
        "renta-final-settlement",
        "renta-dependent-modelos",
        "renta-payments-retentions",
        ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID,
    }
)
GENERAL_BASE_CUOTA_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla") for _v in ("0532", "0533")
)
ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    validated_casilla_id("0058", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}
    ),
    validated_casilla_id("0237", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}
    ),
    validated_casilla_id("0384", surface="test_modelo_100_registry.casilla"): frozenset(
        {_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}
    ),
}
CAPITAL_GAINS_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
}
OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
}
AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("resultados", "deduccion_autonomica_res"): 482,
    ("resultados", "datos_adicionales_anexo_b"): 230,
}
NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("resultados", "anexo_a_res"): 173,
    ("resultados", "anexo_c_res"): 184,
    # 25 printed boxes and the 28 working rows of the art. 49.2 compensation of pending negative savings balances.
    ("resultados", "base_imponible_res"): 53,
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
NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS: Mapping[tuple[str, ...], int] = {
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
    # Seven printed work-income boxes plus the internal maritime-exemption node.
    ("toma_datos_ampliada", "rdto_trabajo"): 8,
    ("toma_datos_ampliada", "red_base_imponible"): 25,
    ("toma_datos_ampliada", "reg_estima_directa"): 5,
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
    ("toma_datos_ampliada", "regimen_especial"): 19,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 76,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE: Mapping[str, frozenset[str]] = {
    "borrador_pdf": frozenset(
        {
            BASE_LIQUIDABLE_ART_50_REF,
            GENERAL_SCALE_ART_63_REF,
            STATE_DEDUCTION_ART_67_REF,
            AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            AUTONOMIC_DEDUCTION_ART_77_REF,
        }
    ),
    "declaracion_pdf": frozenset(
        {
            "ley-35-2006:art-27",
            "ley-35-2006:art-28",
            "ley-35-2006:art-30",
            _OBJECTIVE_ESTIMATION_ART_31_REF,
            "ley-35-2006:art-32",
            GENERAL_BASE_ART_48_REF,
            BASE_LIQUIDABLE_ART_50_REF,
            GENERAL_SCALE_ART_63_REF,
            STATE_DEDUCTION_ART_67_REF,
            AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            AUTONOMIC_DEDUCTION_ART_77_REF,
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
PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS: Mapping[CasillaId, tuple[str, ...]] = {
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
NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS = frozenset(
    {
        "renta-base-liquidable-negativa-general-anterior",
    }
)
NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS = frozenset(
    {
        "renta-anexo-c-base-liquidable-negativa-general",
        "renta-movable-capital",
        "renta-real-estate-capital",
        "renta-work-income",
    }
)
NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS = frozenset({"modelo-100-deadline"})
SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025: Mapping[CasillaId, str] = {
    validated_casilla_id("0528", surface="test_modelo_100_registry.casilla"): GENERAL_SCALE_ART_63_REF,
    validated_casilla_id("0529", surface="test_modelo_100_registry.casilla"): AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    validated_casilla_id("0530", surface="test_modelo_100_registry.casilla"): GENERAL_SCALE_ART_63_REF,
    validated_casilla_id("0531", surface="test_modelo_100_registry.casilla"): AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    validated_casilla_id("0536", surface="test_modelo_100_registry.casilla"): _SAVINGS_STATE_SCALE_ART_66_REF,
    validated_casilla_id("0537", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
    validated_casilla_id("0538", surface="test_modelo_100_registry.casilla"): _SAVINGS_STATE_SCALE_ART_66_REF,
    validated_casilla_id("0539", surface="test_modelo_100_registry.casilla"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
}
ATTRIBUTION_DETAIL_ART_86_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0259", "0264", "0265", "1597", "1598", "1599", "1600")
)
ATTRIBUTION_DETAIL_SECTIONS = frozenset(
    {
        "re_at_rentas",
        "re_agrup_interes_economico",
        "re_agrup_interes_economico_res",
    }
)
GENERAL_BASE_ART_48_ONLY_CASILLAS = frozenset(
    validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
    for _v in ("0431", "0432", "0433", "0434", "0435")
)
SAVINGS_BASE_ART_49_ONLY_CASILLAS = frozenset(
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
SAVINGS_BASE_ART_49_ONLY_ROLES = frozenset(
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
