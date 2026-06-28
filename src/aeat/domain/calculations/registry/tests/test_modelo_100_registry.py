"""Tests for the Modelo 100 registry foundation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from typing import Any, cast

import pytest
from pydantic import AnyUrl

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....contribuyente import PROFILE_KEYS, TaxResidenceProfile
from ....contribuyente.family import RentaAscendantProfile, RentaDescendantProfile, RentaFamilyProfile
from .. import (
    CasillaDefinition,
    CasillaId,
    DataBindingDefinition,
    InputKind,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    RegistryValidator,
    RemoteOperation,
    assert_remote_operation_allowed,
    build_snapshot,
    calculation_closure_legal_refs,
    load_registry_tree,
    parse_export_payload,
    remote_state_policy_from_cross_reference,
    resolve_construct,
    resolve_export_layout,
    resolve_revision_constructs,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DECLARATIONS_LISTING_URL = aeat_url("www6", configured_path("sede_paths", "declarations_listing"))
_UNKNOWN_CONSTRUCT_MEMBER_CASILLA: CasillaId = validated_casilla_id(
    "0000-ghost",
    surface="_UNKNOWN_CONSTRUCT_MEMBER_CASILLA",
)


@cache
def _loaded_registry() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return {modelo.id: modelo for modelo in modelos}, catalogues


@cache
def _modelo_100_snapshot(filing_year: int = 2025) -> RegistrySnapshot:
    modelos_by_id, catalogues = _loaded_registry()
    return build_snapshot(
        modelos_by_id["100"],
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )


def test_modelo_100_revisions_match_record_design_manifest() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    manifest_path = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    years_with_complete_layout = set[str]()
    for year in range(2020, 2026):
        artefact_names = {
            item["original_filename"]
            for item in manifest["artefacts"]
            if f"_{year}" in item["original_filename"] or f"{year}.xsd" in item["original_filename"]
        }
        assert {
            f"diccionarioXSD_{year}.properties",
            f"diccionarioDlgXSD_{year}.properties",
            f"Renta{year}.xsd",
        }.issubset(artefact_names)
        years_with_complete_layout.add(str(year))

    assert set(modelo.revisions) == years_with_complete_layout

    for year_str in years_with_complete_layout:
        revision = modelo.revisions[year_str]
        expected_sources = {
            f"aeat-dr-100-{year_str}-dictionary",
            f"aeat-dr-100-{year_str}-input-dictionary",
            f"aeat-dr-100-{year_str}-xsd",
        }

        assert expected_sources.issubset(revision.source_refs)
        assert expected_sources.issubset(catalogues.sources)
        assert revision.period_selector.years == (int(year_str),)
        assert revision.period_selector.periods == ("0A",)


def test_modelo_100_dependency_relations_resolve_against_registered_modelos() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert revision.relations

    for relation in revision.relations:
        source_modelo = modelos_by_id[relation.source_modelo]
        source_revisions = _select_source_revisions(source_modelo, relation.source_revision_selector)
        assert source_revisions, relation.id
        for source_revision in source_revisions:
            outputs = {casilla.id for casilla in source_revision.casillas}
            for binding in source_revision.algorithm_bindings:
                outputs.update(binding.output_casilla_ids.values())

            assert relation.source_casilla_id in outputs, relation.id
            assert set(relation.source_periods).issubset(source_revision.period_selector.periods), relation.id
        assert relation.target_binding in {binding.id for binding in revision.bindings}
        assert set(relation.target_periods).issubset(revision.period_selector.periods)


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


def _casilla_id(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test_modelo_100_registry.casilla")


def _casilla_ids(*values: object) -> frozenset[CasillaId]:
    return frozenset(_casilla_id(value) for value in values)


def _binding_map_by_casilla(*pairs: tuple[object, str]) -> Mapping[CasillaId, str]:
    return {_casilla_id(casilla_id): binding_id for casilla_id, binding_id in pairs}


_GENERAL_BASE_ART_48_REF = "ley-35-2006:art-48"
_SAVINGS_BASE_ART_49_REF = "ley-35-2006:art-49"
_BASE_LIQUIDABLE_ART_50_REF = "ley-35-2006:art-50"
_GENERAL_SCALE_ART_63_REF = "ley-35-2006:art-63"
_SAVINGS_STATE_SCALE_ART_66_REF = "ley-35-2006:art-66"
_STATE_DEDUCTION_ART_67_REF = "ley-35-2006:art-67"
_NEW_COMPANY_INVESTMENT_ART_68_1_REF = "ley-35-2006:art-68.1"
_BUSINESS_INVESTMENT_ART_68_2_REF = "ley-35-2006:art-68.2"
_DONATION_DEDUCTION_ART_68_3_REF = "ley-35-2006:art-68.3"
_CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF = "ley-35-2006:art-68.5"
_DEDUCTION_LIMITS_ART_69_REF = "ley-35-2006:art-69"
_ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF = "ley-35-2006:da-50"
_RENTAL_HOUSING_DEDUCTION_DT_15_REF = "ley-35-2006:dt-15"
_AUTONOMIC_GENERAL_SCALE_ART_74_REF = "ley-35-2006:art-74"
_AUTONOMIC_SAVINGS_SCALE_ART_76_REF = "ley-35-2006:art-76"
_AUTONOMIC_DEDUCTION_ART_77_REF = "ley-35-2006:art-77"
_ATTRIBUTION_REGIME_ART_86_REF = "ley-35-2006:art-86"
_OBJECTIVE_ESTIMATION_ART_31_REF = "ley-35-2006:art-31"
_ATTRIBUTION_OBJECTIVE_ESTIMATION_ART_39_REF = "rd-439-2007:art-39"
_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF = "ley-35-2006:da-60"
_FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"
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
_DONATION_DEDUCTION_CASILLAS = _casilla_ids("0552", "0553", "0722", "0723", "0724", "0725")
_CASILLA_0921 = _casilla_id("0921")
_CANARIAS_DONACION_DESCENDIENTES_ROLE = "irpf_deduccion_canarias_donacion_descendientes"
_ANDALUCIA_EJERCICIO_FISICO_ROLE = "irpf_deduccion_andalucia_ejercicio_fisico"
_CASILLA_1091 = _casilla_id("1091")
_C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE = "irpf_deduccion_c_valenciana_labores_no_remuneradas_hogar"
_EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE = "irpf_deduccion_extremadura_vivienda_zonas_rurales"
_CASILLA_0581 = _casilla_id("0581")
_DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE = "irpf_intereses_demora_perdida_deduccion_estatal_2"
_DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE = "irpf_intereses_demora_perdida_deduccion_autonomica_2"
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
_GENERAL_BASE_GYP_LIMIT_CASILLA = _casilla_id("0433")
_SAVINGS_BASE_GYP_LIMIT_CASILLA = _casilla_id("0446")
_GENERAL_BASE_IMPONIBLE_CASILLA = _casilla_id("0435")
_BASE_IMPONIBLE_AHORRO_CASILLA = _casilla_id("0460")
_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA = _casilla_id("0505")
_CAPITAL_MOBILIARIO_AHORRO_CASILLA = _casilla_id("0041")
_ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA = _casilla_id("0259")
_GENERAL_BASE_IMPONIBLE_ROLE = "irpf_base_imponible_general"
_ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE = "irpf_re_agrup_interes_economico_base_imponible_imputada"
_ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    _casilla_id("0161"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    _casilla_id("0162"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
    _casilla_id("0163"): _ATTRIBUTION_REGIME_AGRICULTURAL_MODE_FLAG_REFS,
    _casilla_id("0164"): _ATTRIBUTION_REGIME_MODE_FLAG_REFS,
}
_INMUEBLE_ART_22_FORM_ORDER_REFS = frozenset({"ley-35-2006:art-22", _MODELO_100_2025_FORM_ORDER_REF})
_INMUEBLE_2025_CONTINUITY_REFS: Mapping[str, frozenset[str]] = {
    "irpf.inmueble.porcentaje-propiedad": _INMUEBLE_ART_22_FORM_ORDER_REFS,
    "irpf.inmueble.vivienda-habitual-flag": _INMUEBLE_ART_22_FORM_ORDER_REFS,
}
_ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID = "renta-anexo-c-base-liquidable-negativa-general"
_ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID = "renta-2025-base-liquidable-negativa-general-anterior"
_ANEXO_C_BASE_NEGATIVE_GENERAL_REFS = frozenset(
    {
        _GENERAL_BASE_ART_48_REF,
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
_GENERAL_BASE_CUOTA_CASILLAS = _casilla_ids("0532", "0533")
_ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS: Mapping[CasillaId, frozenset[str]] = {
    _casilla_id("0058"): frozenset({_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}),
    _casilla_id("0237"): frozenset({_ARTISTIC_ACTIVITY_EXCEPTIONAL_REDUCTION_REF}),
    _casilla_id("0384"): frozenset(
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
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 74,
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
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 74,
    ("toma_datos_ampliada", "regimen_especial"): 19,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
_NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS: Mapping[tuple[str, str], int] = {
    ("toma_datos_ampliada", "gp_fondos_coti"): 10,
    ("toma_datos_ampliada", "gp_otros_inmuebles"): 67,
    ("toma_datos_ampliada", "gp_premios"): 25,
    ("toma_datos_ampliada", "reg_estima_obj"): 39,
    ("toma_datos_ampliada", "reg_estima_obj_agricola"): 74,
    ("toma_datos_ampliada", "regimenes_especiales"): 66,
}
_PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS: Mapping[CasillaId, tuple[str, ...]] = {
    _casilla_id("0153"): ("rendimientos_capital_inmobiliario", "retenciones"),
    _casilla_id("0591"): ("resultado_declaracion",),
    _casilla_id("0592"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0593"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0594"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0596"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0597"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0598"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0599"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0600"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0601"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0602"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0603"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0604"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0605"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0606"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
    _casilla_id("0609"): ("retenciones_ingresos_cuenta_pagos_fraccionados",),
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
    _casilla_id("0528"): _GENERAL_SCALE_ART_63_REF,
    _casilla_id("0529"): _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    _casilla_id("0530"): _GENERAL_SCALE_ART_63_REF,
    _casilla_id("0531"): _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    _casilla_id("0536"): _SAVINGS_STATE_SCALE_ART_66_REF,
    _casilla_id("0537"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
    _casilla_id("0538"): _SAVINGS_STATE_SCALE_ART_66_REF,
    _casilla_id("0539"): _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
}
_ATTRIBUTION_DETAIL_ART_86_CASILLAS = _casilla_ids(
    "0259",
    "0264",
    "0265",
    "1597",
    "1598",
    "1599",
    "1600",
)
_ATTRIBUTION_DETAIL_SECTIONS = frozenset(
    {
        "re_at_rentas",
        "re_agrup_interes_economico",
        "re_agrup_interes_economico_res",
    }
)
_GENERAL_BASE_ART_48_ONLY_CASILLAS = _casilla_ids(
    "0431",
    "0432",
    "0433",
    "0434",
    "0435",
)
_SAVINGS_BASE_ART_49_ONLY_CASILLAS = _casilla_ids(
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


def _expression_casilla_refs(expression: Any) -> frozenset[CasillaId]:
    refs: set[CasillaId] = set()
    casilla_id = getattr(expression, "casilla_id", None)
    if casilla_id is not None:
        refs.add(casilla_id)
    for arg in getattr(expression, "args", ()):
        refs.update(_expression_casilla_refs(arg))
    return frozenset(refs)


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_general_base_gains_cap_uses_general_base_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formula_id = f"renta-{filing_year}-saldo-gp-base-general-cap-25"
    formula = next(formula for formula in revision.formulas if formula.id == formula_id)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _GENERAL_BASE_GYP_LIMIT_CASILLA)

    for refs in (formula.legal_refs, casilla.legal_refs):
        assert _GENERAL_BASE_ART_48_REF in refs
        assert _SAVINGS_BASE_ART_49_REF not in refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_general_base_casillas_do_not_cite_savings_base_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _GENERAL_BASE_ART_48_ONLY_CASILLAS
    }

    assert set(casillas_by_id) == _GENERAL_BASE_ART_48_ONLY_CASILLAS
    for casilla in casillas_by_id.values():
        assert _GENERAL_BASE_ART_48_REF in casilla.legal_refs, casilla.id
        assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert _ATTRIBUTION_REGIME_ART_86_REF not in casilla.legal_refs, casilla.id

    base_general = casillas_by_id[_GENERAL_BASE_IMPONIBLE_CASILLA]
    assert base_general.semantic_role == _GENERAL_BASE_IMPONIBLE_ROLE
    assert base_general.label == "Base imponible general"


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_savings_base_gains_cap_uses_savings_base_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formula_id = f"renta-{filing_year}-saldo-gp-base-ahorro-cap-25"
    formula = next(formula for formula in revision.formulas if formula.id == formula_id)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _SAVINGS_BASE_GYP_LIMIT_CASILLA)

    for refs in (formula.legal_refs, casilla.legal_refs):
        assert _SAVINGS_BASE_ART_49_REF in refs
        assert _GENERAL_BASE_ART_48_REF not in refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_savings_base_casillas_do_not_cite_general_base_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla
        for casilla in revision.casillas
        if casilla.semantic_role in _SAVINGS_BASE_ART_49_ONLY_ROLES
    }

    assert set(casillas_by_id) == _SAVINGS_BASE_ART_49_ONLY_CASILLAS
    for casilla in casillas_by_id.values():
        assert _SAVINGS_BASE_ART_49_REF in casilla.legal_refs, casilla.id
        assert _GENERAL_BASE_ART_48_REF not in casilla.legal_refs, casilla.id


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_attribution_regime_base_imputada_uses_attribution_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(
        casilla for casilla in revision.casillas if casilla.id == _ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA
    )

    assert _ATTRIBUTION_REGIME_ART_86_REF in casilla.legal_refs
    assert casilla.semantic_role == _ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE
    assert casilla.label == "Base imponible imputada"
    assert _GENERAL_BASE_ART_48_REF not in casilla.legal_refs
    assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs
    assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_attribution_detail_casillas_do_not_cite_fractional_payment_article(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _ATTRIBUTION_DETAIL_ART_86_CASILLAS
    }

    assert set(casillas_by_id) == _ATTRIBUTION_DETAIL_ART_86_CASILLAS
    for casilla in casillas_by_id.values():
        assert _ATTRIBUTION_REGIME_ART_86_REF in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_attribution_detail_sections_do_not_cite_fractional_payment_article(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    checked = [
        casilla
        for casilla in revision.casillas
        if _ATTRIBUTION_DETAIL_SECTIONS & frozenset(casilla.section)
    ]

    assert checked
    for casilla in checked:
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_savings_base_includes_current_capital_mobiliario(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formula = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _BASE_IMPONIBLE_AHORRO_CASILLA
    )

    assert _SAVINGS_BASE_ART_49_REF in formula.legal_refs
    assert _CAPITAL_MOBILIARIO_AHORRO_CASILLA in _expression_casilla_refs(formula.expression)


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_donation_deduction_surface_cites_art_68_3(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _DONATION_DEDUCTION_CASILLAS
    }

    assert set(casillas_by_id) == _DONATION_DEDUCTION_CASILLAS
    for casilla in casillas_by_id.values():
        assert _DONATION_DEDUCTION_ART_68_3_REF in casilla.legal_refs, casilla.id

    formula_by_id = {
        formula.id: formula
        for formula in revision.formulas
        if formula.id
        in {
            f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento",
            f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento",
        }
    }

    assert set(formula_by_id) == {
        f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento",
        f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento",
    }
    estatal = formula_by_id[f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento"]
    autonomica = formula_by_id[f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento"]
    assert _DONATION_DEDUCTION_ART_68_3_REF in estatal.legal_refs
    assert _STATE_DEDUCTION_ART_67_REF in estatal.legal_refs
    assert _DONATION_DEDUCTION_ART_68_3_REF in autonomica.legal_refs
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in autonomica.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_cultural_interest_deduction_cites_art_68_5(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_interes_cultural_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_interes_cultural_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_interes_cultural_estatal": "estatal",
        "irpf_deduccion_interes_cultural_autonomica": "autonomica",
    }

    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    assert set(casillas_by_role) == set(role_refs)

    anexo_casilla = next(
        casilla
        for casilla in revision.casillas
        if casilla.semantic_role == "irpf_anexo_a_interes_cultural_deduccion_importe"
    )
    assert anexo_casilla.id == _casilla_id("0726")
    assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in anexo_casilla.legal_refs
    assert _DEDUCTION_LIMITS_ART_69_REF in anexo_casilla.legal_refs

    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    for role, quota_ref in role_refs.items():
        suffix = formula_suffixes[role]
        formula_id = f"renta-{filing_year}-deduccion-cultural-{suffix}-50-porciento"
        casilla = casillas_by_role[role]
        formula = formulas_by_id[formula_id]

        assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in casilla.legal_refs
        assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in formula.legal_refs
        assert quota_ref in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_new_company_investment_deduction_cites_art_68_1(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    anexo_section = ("resultados", "anexo_a_res", "deduccion_empresas_nueva_creacion_res")
    state_casilla = next(
        casilla
        for casilla in revision.casillas
        if casilla.semantic_role == "irpf_deduccion_empresa_nueva_creacion"
    )
    detail_casillas = [casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == anexo_section]

    assert state_casilla.id == _casilla_id("0549")
    assert {casilla.id for casilla in detail_casillas} == _casilla_ids("0711", "0712", "0713", "0714")

    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in [state_casilla, *detail_casillas]
        if _NEW_COMPANY_INVESTMENT_ART_68_1_REF not in casilla.legal_refs
        or "ley-35-2006:art-68" in casilla.legal_refs
    }
    assert not offenders


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_business_investment_deductions_cite_art_68_2(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    section = ("resultados", "anexo_a_res", "deducciones_inversion_empresarial_res")
    checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == section]

    assert checked
    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in checked
        if _BUSINESS_INVESTMENT_ART_68_2_REF not in casilla.legal_refs
        or "ley-35-2006:art-68" in casilla.legal_refs
    }
    assert not offenders

    formula = next(
        formula
        for formula in revision.formulas
        if formula.id == f"renta-{filing_year}-deduccion-incentivos-inversion-empresarial-total"
    )
    assert _BUSINESS_INVESTMENT_ART_68_2_REF in formula.legal_refs
    assert "ley-35-2006:art-68" not in formula.legal_refs


@pytest.mark.parametrize("filing_year", range(2021, 2026))
def test_modelo_100_energy_efficiency_deduction_formula_cites_da_50(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(
        casilla
        for casilla in revision.casillas
        if casilla.semantic_role == "irpf_deduccion_eficiencia_energetica_viviendas"
    )
    formula = next(
        formula
        for formula in revision.formulas
        if formula.id == f"renta-{filing_year}-deduccion-eficiencia-energetica-vivienda-suma"
    )

    assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in casilla.legal_refs
    assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in formula.legal_refs
    assert _STATE_DEDUCTION_ART_67_REF in formula.legal_refs
    assert "ley-35-2006:art-68" not in formula.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_rental_housing_transitional_deduction_cites_dt_15(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": "estatal",
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": "autonomica",
    }

    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    assert set(casillas_by_role) == set(role_refs)

    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    for role, quota_ref in role_refs.items():
        suffix = formula_suffixes[role]
        formula_id = f"renta-{filing_year}-deduccion-alquiler-vivienda-{suffix}-50-porciento"
        casilla = casillas_by_role[role]
        formula = formulas_by_id[formula_id]

        assert _RENTAL_HOUSING_DEDUCTION_DT_15_REF in casilla.legal_refs
        assert _RENTAL_HOUSING_DEDUCTION_DT_15_REF in formula.legal_refs
        assert quota_ref in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


@pytest.mark.parametrize(
    ("filing_year", "expected_section_tail", "expected_role", "expected_label_snippet"),
    (
        (
            2020,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2021,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2022,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2023,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2024,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2025,
            "andalucia_res",
            _ANDALUCIA_EJERCICIO_FISICO_ROLE,
            "ejercicio físico",
        ),
    ),
)
def test_modelo_100_casilla_0921_role_tracks_year_specific_official_meaning(
    filing_year: int,
    expected_section_tail: str,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_0921)

    assert casilla.number == "0921"
    assert casilla.section[-1] == expected_section_tail
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize(
    ("filing_year", "expected_section_tail", "expected_role", "expected_label_snippet"),
    (
        (
            2020,
            "c_valenciana_res",
            _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
            "labores no remuneradas en el hogar",
        ),
        (
            2021,
            "c_valenciana_res",
            _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
            "labores no remuneradas en el hogar",
        ),
        (
            2022,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2023,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2024,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2025,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
    ),
)
def test_modelo_100_casilla_1091_role_tracks_year_specific_official_meaning(
    filing_year: int,
    expected_section_tail: str,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_1091)

    assert casilla.number == "1091"
    assert casilla.section[-1] == expected_section_tail
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize(
    ("filing_year", "expected_role", "expected_label_snippet"),
    (
        (2020, _DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE, "Parte estatal"),
        (2021, _DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE, "Parte estatal"),
        (2022, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2023, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2024, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2025, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
    ),
)
def test_modelo_100_casilla_0581_role_tracks_year_specific_state_autonomic_column(
    filing_year: int,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_0581)

    assert casilla.number == "0581"
    assert casilla.section[-1] == "gravamenes_res"
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_general_liquidable_and_cuota_chain_exclude_unrelated_articles(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    checked_casilla_ids = {_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA, *_GENERAL_BASE_CUOTA_CASILLAS}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in checked_casilla_ids}

    assert set(casillas_by_id) == checked_casilla_ids
    base_casilla = casillas_by_id[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]
    assert _BASE_LIQUIDABLE_ART_50_REF in base_casilla.legal_refs
    assert _SAVINGS_BASE_ART_49_REF not in base_casilla.legal_refs
    assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in base_casilla.legal_refs

    formula_by_target = {
        formula.target_casilla_id: formula
        for formula in revision.formulas
        if formula.target_casilla_id in checked_casilla_ids
    }
    base_formula = formula_by_target.get(_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA)
    if base_formula is not None:
        assert _BASE_LIQUIDABLE_ART_50_REF in base_formula.legal_refs
        assert _SAVINGS_BASE_ART_49_REF not in base_formula.legal_refs
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in base_formula.legal_refs

    for casilla_id in _GENERAL_BASE_CUOTA_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        formula = formula_by_target[casilla_id]
        assert _GENERAL_SCALE_ART_63_REF in casilla.legal_refs, casilla.id
        assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id
        assert _SAVINGS_BASE_ART_49_REF not in formula.legal_refs, formula.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, formula.id


def test_modelo_100_2025_scale_result_casillas_use_scale_articles_not_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {
        casilla.id: casilla
        for casilla in revision.casillas
        if casilla.id in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }
    formula_by_target = {
        formula.target_casilla_id: formula
        for formula in revision.formulas
        if formula.target_casilla_id in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }

    assert set(casillas_by_id) == set(_SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    assert set(formula_by_target) == set(_SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    for casilla_id, expected_ref in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025.items():
        casilla = casillas_by_id[casilla_id]
        formula = formula_by_target[casilla_id]
        assert expected_ref in casilla.legal_refs, casilla.id
        assert expected_ref in formula.legal_refs, formula.id
        assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, formula.id


def test_modelo_100_2025_cuota_chain_casillas_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    checked = [
        casilla
        for casilla in revision.casillas
        if casilla.id.isdigit() and "0500" <= casilla.id <= "0546"
    ]

    assert {casilla.id for casilla in checked} == {f"{number:04d}" for number in range(500, 547)}
    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in checked
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
    }
    assert not offenders


def test_modelo_100_2025_autonomic_deduction_sections_use_art77_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    expected_refs = {_AUTONOMIC_DEDUCTION_ART_77_REF, "orden-hac-277-2026:art-3"}
    for section, expected_count in _AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if set(casilla.legal_refs) != expected_refs
        }
        assert not offenders


def test_modelo_100_2025_result_sections_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_input_sections_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_input_sections_do_not_cite_payments_on_account_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _PAYMENTS_ON_ACCOUNT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_payments_on_account_article_stays_on_payment_casillas_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    observed = {
        casilla.id: tuple(casilla.section[:2])
        for casilla in revision.casillas
        if _PAYMENTS_ON_ACCOUNT_ARTICLE_REF in casilla.legal_refs
    }

    assert observed == _PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS


def test_modelo_100_2025_gain_sections_use_capital_gains_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _CAPITAL_GAINS_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if set(casilla.legal_refs) != _CAPITAL_GAINS_SECTION_REFS
        }
        assert not offenders


def test_modelo_100_2025_attribution_mode_flags_use_attribution_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    offenders = {
        casilla_id: casillas[casilla_id].legal_refs
        for casilla_id, expected_refs in _ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS.items()
        if set(casillas[casilla_id].legal_refs) != expected_refs
    }

    assert not offenders


def test_modelo_100_2025_casillas_do_not_retain_full_income_chapter_span() -> None:
    revision = _modelo_100_snapshot(2025).revision
    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in revision.casillas
        if _BROAD_INCOME_CHAPTER_SPAN_REFS.issubset(casilla.legal_refs)
    }

    assert not offenders


def test_modelo_100_2025_inmueble_continuity_uses_inmueble_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    checked = [
        evolution
        for evolution in revision.casilla_continuidad_evolutions
        if str(evolution.continuidad_id) in _INMUEBLE_2025_CONTINUITY_REFS
    ]

    assert len(checked) == 10
    offenders = {
        evolution.id: evolution.legal_refs
        for evolution in checked
        if set(evolution.legal_refs) != _INMUEBLE_2025_CONTINUITY_REFS[str(evolution.continuidad_id)]
    }
    assert not offenders


def test_modelo_100_2025_anexo_c_base_negative_general_uses_member_refs_only() -> None:
    snapshot = _modelo_100_snapshot(2025)
    revision = snapshot.revision
    construct = snapshot.constructs[_ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}
    bindings = {binding.id: binding for binding in revision.bindings}
    member_refs: set[str] = set()

    for casilla_id in construct.casilla_ids:
        member_refs.update(casillas[casilla_id].legal_refs)
    for formula_id in construct.formulas:
        member_refs.update(formulas[formula_id].legal_refs)
    for binding_id in construct.bindings:
        member_refs.update(bindings[binding_id].legal_refs)

    assert set(bindings[_ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID].legal_refs) == {
        _GENERAL_BASE_ART_48_REF,
        _MODELO_100_2025_FORM_ORDER_REF,
    }
    assert member_refs == _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS
    assert set(construct.legal_refs) == _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS


def test_modelo_100_2025_completeness_manifest_legal_refs_match_calculation_closure() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    manifest = revision.completeness_manifest

    assert manifest is not None
    assert set(manifest.legal_refs) == calculation_closure_legal_refs(revision, modelo.id)


def test_modelo_100_2025_objective_estimation_sections_use_activity_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if set(casilla.legal_refs) != _ECONOMIC_ACTIVITY_SECTION_REFS
        }
        assert not offenders


def test_modelo_100_2025_artistic_activity_reductions_use_da60_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    offenders = {
        casilla_id: casillas[casilla_id].legal_refs
        for casilla_id, expected_refs in _ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS.items()
        if set(casillas[casilla_id].legal_refs) != expected_refs
    }

    assert not offenders


def test_modelo_100_2025_non_payment_metadata_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision

    bindings = {binding.id: binding for binding in revision.bindings}
    constructs = {construct.id: construct for construct in revision.constructs}
    application_links = {link.id: link for link in revision.application_links}

    binding_offenders = {
        binding_id: bindings[binding_id].legal_refs
        for binding_id in _NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in bindings[binding_id].legal_refs
    }
    construct_offenders = {
        construct_id: constructs[construct_id].legal_refs
        for construct_id in _NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in constructs[construct_id].legal_refs
    }
    application_link_offenders = {
        link_id: application_links[link_id].legal_refs
        for link_id in _NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in application_links[link_id].legal_refs
    }
    deadline_offenders = {
        deadline.id: deadline.legal_refs
        for deadline in revision.deadline_windows
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in deadline.legal_refs
    }
    continuity_offenders = {
        evolution.id: evolution.legal_refs
        for evolution in revision.casilla_continuidad_evolutions
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in evolution.legal_refs
    }

    assert not binding_offenders
    assert not construct_offenders
    assert not application_link_offenders
    assert not deadline_offenders
    assert not continuity_offenders


_PERSONAL_FAMILY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
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

_SOURCE_FOUNDATION_APPLICATION_LINKS: frozenset[str] = frozenset(
    {
        "modelo-100-renta-web-open-cross-reference",
        "modelo-100-export",
        "modelo-100-filed-declarations-observation",
        "modelo-100-calculation",
        "modelo-100-verification",
        "modelo-100-review",
        "modelo-100-approval",
        "modelo-100-reconciliation",
        "modelo-100-workflow",
    },
)


def test_modelo_100_source_foundation_inherits_revision_legal_and_source_refs() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(snapshot.revision.legal_refs).issubset(source_foundation.legal_refs)
    assert set(snapshot.revision.source_refs).issubset(source_foundation.source_refs)


def test_modelo_100_source_foundation_carries_workbook_and_live_cross_references() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(source_foundation.workbook_parity_refs) == set(snapshot.workbook_parity_refs)
    assert set(source_foundation.live_cross_references) == set(snapshot.live_cross_references)


def test_modelo_100_source_foundation_application_links_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    source_foundation = snapshot.constructs["renta-source-foundation"]
    assert set(source_foundation.application_links) == _SOURCE_FOUNDATION_APPLICATION_LINKS


def test_modelo_100_personal_family_construct_bindings_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    personal_family = snapshot.constructs["renta-personal-family"]
    assert set(personal_family.bindings) == _PERSONAL_FAMILY_BINDINGS


def test_modelo_100_personal_family_construct_casillas_match_expected_set() -> None:
    snapshot = _modelo_100_snapshot()
    personal_family = snapshot.constructs["renta-personal-family"]
    assert set(personal_family.casilla_ids) == _PERSONAL_FAMILY_CASILLAS


def test_modelo_100_dependent_modelos_construct_covers_every_previous_filing_binding() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    # The dependent-modelos construct covers every observation-backed slot: the
    # direct same-modelo previous_filing carries (BIN N-1) AND the cross-modelo
    # relation_prefill fold-in slots (130/131/111/115/123/180/184/190/193). The
    # latter were re-stamped from previous_filing to relation_prefill when the
    # relation became canonical for cross-modelo fold-ins (aggregation-taxonomy
    # decision ruling 3).
    filed_dependency_bindings = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
    }
    assert set(dependencies.bindings) == filed_dependency_bindings


def test_modelo_100_dependent_modelos_construct_covers_every_revision_relation() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    assert set(dependencies.relations) == {relation.id for relation in snapshot.revision.relations}


def test_modelo_100_2025_member_grounded_constructs_do_not_declare_extra_legal_refs() -> None:
    snapshot = _modelo_100_snapshot()
    revision = snapshot.revision
    resolved_constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    member_indexes = {
        "casilla": {item.id: item for item in revision.casillas},
        "formula": {item.id: item for item in revision.formulas},
        "binding": {item.id: item for item in revision.bindings},
        "relation": {item.id: item for item in revision.relations},
        "dependency classification": {item.id: item for item in revision.dependency_classifications},
    }
    offenders: dict[str, list[str]] = {}

    for construct_id in _MEMBER_GROUNDED_2025_CONSTRUCT_IDS:
        construct = resolved_constructs[construct_id]
        member_refs: set[str] = set()
        for member in construct.members:
            member_refs.update(getattr(member_indexes[member.kind][member.id], "legal_refs", ()))
        extra_refs = sorted(set(construct.legal_refs) - member_refs)
        if extra_refs:
            offenders[construct_id] = extra_refs

    assert not offenders


def test_modelo_100_payments_retentions_construct_covers_classified_payment_bindings() -> None:
    """payments_retentions covers retention + pagos-a-cuenta filings only.

    Some previous_filing bindings are not payment/retention sources:
    Modelo 184 belongs to economic-activities attribution semantics, and
    prior-year Modelo 100 base-liquidation carry-forward belongs to Anexo C.
    """
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    payment_source_modelos = {
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if "renta-payments-retentions" in classification.target_constructs
    }
    expected = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source in {"previous_filing", "relation_prefill"}
        and binding.selector.get("source_modelo") in payment_source_modelos
    }

    assert set(payments_retentions.bindings) == expected
    assert "renta-2025-base-liquidable-negativa-general-anterior" not in payments_retentions.bindings
    assert (
        "renta-2025-base-liquidable-negativa-general-anterior"
        in snapshot.constructs["renta-anexo-c-base-liquidable-negativa-general"].bindings
    )


def test_modelo_100_payments_retentions_construct_excludes_atribucion_relations() -> None:
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    payment_source_modelos = {
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if "renta-payments-retentions" in classification.target_constructs
    }
    expected = {
        relation.id for relation in snapshot.revision.relations if relation.source_modelo in payment_source_modelos
    }
    assert set(payments_retentions.relations) == expected


def test_modelo_100_economic_activities_construct_pins_estimacion_directa_binding() -> None:
    snapshot = _modelo_100_snapshot()
    economic_activities = snapshot.constructs["renta-economic-activities"]
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in economic_activities.bindings
    assert {"1479", "1553", "1577"}.issubset(economic_activities.casilla_ids)


def test_modelo_100_observation_parsing_construct_lists_filed_declarations_read() -> None:
    snapshot = _modelo_100_snapshot()
    observation_parsing = snapshot.constructs["renta-observation-parsing"]
    assert observation_parsing.live_cross_references == ("modelo-100-filed-declarations-read",)


def test_modelo_100_dependent_modelos_construct_carries_every_dependency_classification() -> None:
    snapshot = _modelo_100_snapshot()
    dependencies = snapshot.constructs["renta-dependent-modelos"]
    assert set(dependencies.dependency_classifications) == set(snapshot.dependency_classifications)


def test_modelo_100_payments_retentions_construct_dependency_classifications_target_payments() -> None:
    snapshot = _modelo_100_snapshot()
    payments_retentions = snapshot.constructs["renta-payments-retentions"]
    expected = {
        classification.id
        for classification in snapshot.dependency_classifications.values()
        if "renta-payments-retentions" in classification.target_constructs
    }
    assert set(payments_retentions.dependency_classifications) == expected


_CASILLA_TO_PROFILE_BINDING: Mapping[CasillaId, str] = _binding_map_by_casilla(
    ("DPNIF_D", "renta-2025-profile-tax-id"),
    ("DP_APENOM_D", "renta-2025-profile-display-name"),
    ("ZCCAD", "renta-2025-profile-tax-residence-ccaa"),
    ("TIPOTRIBUTACION", "renta-2025-profile-declaration-type"),
    ("SEXO_D", "renta-2025-profile-taxpayer-sex"),
    ("ECIVIL", "renta-2025-profile-marital-status"),
    ("DPFNAC_D", "renta-2025-profile-taxpayer-birth-date"),
    ("DPNIF_C", "renta-2025-profile-spouse-tax-id"),
    ("DP_APENOM_C", "renta-2025-profile-spouse-display-name"),
    ("DPFNAC_C", "renta-2025-profile-spouse-birth-date"),
    ("SEXO_C", "renta-2025-profile-spouse-sex"),
    ("DPGMIN_D", "renta-2025-profile-taxpayer-disability-grade"),
    ("DECFAL", "renta-2025-profile-taxpayer-death-date"),
    ("DPGMIN_C", "renta-2025-profile-spouse-disability-grade"),
    ("NORESIDENTE", "renta-2025-profile-spouse-non-resident-irpf"),
    ("RESIDENTEUE", "renta-2025-profile-spouse-eu-eea-resident"),
    ("ZRUE2", "renta-2025-profile-spouse-eu-eea-country"),
    ("HIJOSUE", "renta-2025-profile-family-descendants-eu-eea-deduction"),
    ("PH18", "renta-2025-profile-family-minor-children-in-unit"),
    ("NIFDLG", "renta-2025-family-descendant-tax-id"),
    ("APENOMDLG", "renta-2025-family-descendant-display-name"),
    ("FNACDLG", "renta-2025-family-descendant-birth-date"),
    ("MINUSDLG", "renta-2025-family-descendant-disability-grade"),
    ("FALLDLG", "renta-2025-family-descendant-death-date"),
    ("DNIASDLG", "renta-2025-family-ascendant-tax-id"),
    ("APENOMDLG_ASC", "renta-2025-family-ascendant-display-name"),
    ("ANOASDLG", "renta-2025-family-ascendant-birth-date"),
    ("PCTMINASDLG", "renta-2025-family-ascendant-disability-grade"),
    ("CONVASDLG", "renta-2025-family-ascendant-cohabiting-descendant-count"),
    ("FALLASDLG", "renta-2025-family-ascendant-death-date"),
)
"""Maps each personal/family casilla id to the profile binding that feeds it.

Single source of truth for the binding-presence, casilla-binding link,
and bound-input-kind checks in
:func:`test_modelo_100_personal_family_profile_bindings_target_profile_schema`.
Adding a new profile-bound casilla means adding one row here.
"""

_PROFILE_KEY_BINDINGS: tuple[str, ...] = (
    "renta-2025-profile-tax-id",
    "renta-2025-profile-declaration-type",
    "renta-2025-profile-taxpayer-sex",
    "renta-2025-profile-marital-status",
    "renta-2025-profile-taxpayer-birth-date",
    "renta-2025-profile-spouse-tax-id",
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
)
"""Bindings whose selector carries a single ``profile_key`` (vs ``profile_keys`` tuple)."""

_SPOUSE_REQUIRED_BINDINGS: tuple[str, ...] = (
    "renta-2025-profile-spouse-tax-id",
    "renta-2025-profile-spouse-display-name",
    "renta-2025-profile-spouse-birth-date",
    "renta-2025-profile-spouse-sex",
)
"""Bindings whose ``required_when_*`` selector is keyed on declaration type == joint."""

_FAMILY_ROW_BINDINGS: Mapping[str, tuple[str, str]] = {
    "renta-2025-family-descendant-tax-id": ("descendants", "tax_id"),
    "renta-2025-family-descendant-display-name": ("descendants", "display_name"),
    "renta-2025-family-descendant-birth-date": ("descendants", "birth_date"),
    "renta-2025-family-descendant-disability-grade": ("descendants", "disability_grade"),
    "renta-2025-family-descendant-death-date": ("descendants", "death_date"),
    "renta-2025-family-ascendant-tax-id": ("ascendants", "tax_id"),
    "renta-2025-family-ascendant-display-name": ("ascendants", "display_name"),
    "renta-2025-family-ascendant-birth-date": ("ascendants", "birth_date"),
    "renta-2025-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
    "renta-2025-family-ascendant-cohabiting-descendant-count": ("ascendants", "cohabiting_descendant_count"),
    "renta-2025-family-ascendant-death-date": ("ascendants", "death_date"),
}
"""Family row bindings → (collection name on RentaFamilyProfile, field name on the row model)."""


def test_modelo_100_personal_family_profile_bindings_target_profile_schema() -> None:
    snapshot = _modelo_100_snapshot()
    profile_keys = {entry.key for entry in PROFILE_KEYS}
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings if binding.source == "profile"}
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    _assert_profile_bindings_present(bindings_by_id)
    _assert_casilla_binding_links(casillas_by_id)
    _assert_casillas_are_bound_input(casillas_by_id)
    _assert_selector_profile_keys(bindings_by_id, profile_keys=profile_keys)
    _assert_spouse_joint_gating(bindings_by_id)
    _assert_eu_eea_gating(bindings_by_id)
    _assert_tax_residence_selector(bindings_by_id)
    _assert_family_row_selectors(bindings_by_id, casillas_by_id)


def _assert_profile_bindings_present(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """Every casilla-mapped profile binding is declared on the snapshot."""
    missing = set(_CASILLA_TO_PROFILE_BINDING.values()) - bindings_by_id.keys()
    assert not missing, f"missing profile bindings: {sorted(missing)}"


def _assert_casilla_binding_links(casillas_by_id: Mapping[CasillaId, CasillaDefinition]) -> None:
    """Each personal/family casilla links to its declared profile binding."""
    mismatches = [
        f"{casilla_id}: expected binding {expected_binding!r}, got {casillas_by_id[casilla_id].binding!r}"
        for casilla_id, expected_binding in _CASILLA_TO_PROFILE_BINDING.items()
        if casillas_by_id[casilla_id].binding != expected_binding
    ]
    assert not mismatches, "casilla-binding link mismatches:\n  " + "\n  ".join(mismatches)


def _assert_casillas_are_bound_input(casillas_by_id: Mapping[CasillaId, CasillaDefinition]) -> None:
    """Every personal/family casilla is ``input_kind='bound'`` (profile-fed)."""
    non_bound = [
        f"{casilla_id}: input_kind={casillas_by_id[casilla_id].input_kind!r}"
        for casilla_id in _CASILLA_TO_PROFILE_BINDING
        if casillas_by_id[casilla_id].input_kind != InputKind.BOUND
    ]
    assert not non_bound, "casillas not marked bound:\n  " + "\n  ".join(non_bound)


def _assert_selector_profile_keys(
    bindings_by_id: Mapping[str, DataBindingDefinition],
    *,
    profile_keys: set[str],
) -> None:
    """Single-key + many-key selector references all land inside the declared profile keyset."""
    for binding_id in _PROFILE_KEY_BINDINGS:
        selector_key = bindings_by_id[binding_id].selector["profile_key"]
        assert selector_key in profile_keys, f"{binding_id}: selector profile_key {selector_key!r} is unknown"
    for binding_id in ("renta-2025-profile-display-name", "renta-2025-profile-spouse-display-name"):
        many_keys = cast(tuple[str, ...], bindings_by_id[binding_id].selector["profile_keys"])
        unknown = set(many_keys) - profile_keys
        assert not unknown, f"{binding_id}: selector profile_keys outside known set: {sorted(unknown)}"


def _assert_spouse_joint_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """Spouse-only bindings gate on declaration type 2 (joint)."""
    for binding_id in _SPOUSE_REQUIRED_BINDINGS:
        selector = bindings_by_id[binding_id].selector
        assert selector["required_when_profile_key"] == "filing_export.declaration_type", (
            f"{binding_id}: required_when_profile_key={selector['required_when_profile_key']!r}"
        )
        assert selector["required_when_value"] == "2", (
            f"{binding_id}: required_when_value={selector['required_when_value']!r}"
        )


def _assert_eu_eea_gating(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The two EU-EEA bindings chain their gating predicates correctly."""
    eu_resident_selector = bindings_by_id["renta-2025-profile-spouse-eu-eea-resident"].selector
    assert eu_resident_selector["required_when_profile_key"] == "renta_spouse.non_resident_irpf"
    assert eu_resident_selector["required_when_value"] == "true"
    eu_country_selector = bindings_by_id["renta-2025-profile-spouse-eu-eea-country"].selector
    assert eu_country_selector["required_when_profile_key"] == "renta_spouse.eu_eea_resident"
    assert eu_country_selector["required_when_value"] == "true"


def _assert_tax_residence_selector(bindings_by_id: Mapping[str, DataBindingDefinition]) -> None:
    """The tax-residence-ccaa binding's selector targets the TaxResidenceProfile model."""
    selector = bindings_by_id["renta-2025-profile-tax-residence-ccaa"].selector
    assert selector["profile_model"] == "TaxResidenceProfile"
    assert selector["field"] in TaxResidenceProfile.model_fields


def _assert_family_row_selectors(
    bindings_by_id: Mapping[str, DataBindingDefinition],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> None:
    """Family-row bindings address a repeating collection + field pair on RentaFamilyProfile."""
    for binding_id, (collection, field) in _FAMILY_ROW_BINDINGS.items():
        selector = bindings_by_id[binding_id].selector
        assert selector["profile_model"] == "RentaFamilyProfile", binding_id
        assert selector["collection"] == collection, binding_id
        assert collection in RentaFamilyProfile.model_fields, binding_id
        assert selector["field"] == field, binding_id
        assert selector["repeating"] is True, binding_id
        assert selector["dictionary_field"] in casillas_by_id, binding_id
        row_model_fields = (
            RentaDescendantProfile.model_fields if collection == "descendants" else RentaAscendantProfile.model_fields
        )
        assert field in row_model_fields, f"{binding_id}: row field {field!r} missing on {collection} model"


def test_modelo_100_application_links_route_current_workflows_through_snapshots() -> None:
    snapshot = _modelo_100_snapshot()
    links_by_surface = {link.surface: link for link in snapshot.revision.application_links}

    assert {
        "calculation",
        "export",
        "filing",
        "verification",
        "review",
        "approval",
        "reconciliation",
        "workflow",
        "portal",
    }.issubset(links_by_surface)
    assert all(link.requires_snapshot is True for link in snapshot.revision.application_links)
    assert links_by_surface["calculation"].consumer == "aeat.domain.calculations.registry.calculate_registry_snapshot"
    assert links_by_surface["export"].consumer == "aeat.application.filing.export_draft"
    assert links_by_surface["filing"].consumer == "aeat.application.filing"
    assert links_by_surface["verification"].consumer == "aeat.application.verification"
    assert links_by_surface["review"].consumer == "aeat.application.filing.review"
    assert links_by_surface["approval"].consumer == "aeat.application.filing.approval"
    assert links_by_surface["reconciliation"].consumer == "aeat.application.modelo.modelo_reconcile"
    assert links_by_surface["workflow"].consumer == "aeat.application.workflow"


def test_modelo_100_construct_reader_resolves_revision_member_objects() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    dependencies = constructs["renta-dependent-modelos"]
    economic_activities = constructs["renta-economic-activities"]
    filed_dependency_binding_ids = {
        binding.id for binding in revision.bindings if binding.source in {"previous_filing", "relation_prefill"}
    }

    assert {member.id for member in dependencies.members_of_kind("binding")} == filed_dependency_binding_ids
    assert {member.id for member in dependencies.members_of_kind("relation")} == {
        relation.id for relation in revision.relations
    }
    assert "renta-2025-modelo-100-estimacion-directa-es-normal" in {
        member.id for member in economic_activities.members_of_kind("binding")
    }
    for member in dependencies.members:
        assert cast(Any, member.value).id == member.id


def test_modelo_100_renta_section_constructs_classify_registered_relation_sources() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    relations_by_id = {relation.id: relation for relation in revision.relations}
    constructs = {construct.id: construct for construct in resolve_revision_constructs(revision)}
    source_modelos_by_construct = {
        construct_id: {
            relations_by_id[member.id].source_modelo for member in constructs[construct_id].members_of_kind("relation")
        }
        for construct_id in (
            "renta-work-income",
            "renta-real-estate-capital",
            "renta-movable-capital",
            "renta-economic-activities",
        )
    }

    assert source_modelos_by_construct == {
        "renta-work-income": {"111", "190"},
        "renta-real-estate-capital": {"115", "180"},
        "renta-movable-capital": {"123", "193"},
        "renta-economic-activities": {"130", "131", "184"},
    }


def test_modelo_100_dependency_classifications_cover_registered_relation_sources() -> None:
    snapshot = _modelo_100_snapshot()
    relations_by_source: dict[str, set[str]] = {}
    for relation in snapshot.revision.relations:
        relations_by_source.setdefault(relation.source_modelo, set()).add(relation.id)
    classifications_by_source = {
        classification.source_modelo: classification
        for classification in snapshot.revision.dependency_classifications
        if classification.relation_refs
    }

    assert set(classifications_by_source) == set(relations_by_source)
    for source_modelo, relation_ids in relations_by_source.items():
        classification = classifications_by_source[source_modelo]
        assert set(classification.relation_refs) == relation_ids
        assert "renta-dependent-modelos" in classification.target_constructs
        assert all(construct_id in snapshot.constructs for construct_id in classification.target_constructs)


def test_modelo_100_authenticated_filed_data_cross_reference_is_guarded_read_only() -> None:
    _modelos_by_id, catalogues = _loaded_registry()
    source = catalogues.sources["aeat-modelo-100-procedure"]
    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")

    assert "Consulta de declaraciones presentadas" in source_text
    assert "Datos fiscales" in source_text

    for year in range(2020, 2026):
        snapshot = _modelo_100_snapshot(year)
        cross_reference = snapshot.live_cross_references["modelo-100-filed-declarations-read"]
        policy = remote_state_policy_from_cross_reference(cross_reference)

        assert cross_reference.surface == "authenticated_read_surface"
        assert cross_reference.synthetic_data_allowed is False
        assert cross_reference.requires_authentication is True
        assert cross_reference.requires_aeat_authorization is True
        assert "aeat-modelo-100-procedure" in cross_reference.source_refs
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl(_DECLARATIONS_LISTING_URL),
            ),
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(
                    kind="http",
                    method="POST",
                    url=AnyUrl(_DECLARATIONS_LISTING_URL),
                ),
            )


def test_modelo_100_live_cross_references_block_declared_forbidden_actions() -> None:
    snapshot = _modelo_100_snapshot()
    expected_by_id = {
        "modelo-100-renta-web-open": {
            "authenticated-renta-web",
            "fiscal-data-read",
            "borrador-read",
            "filed-declaration-read",
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
        },
        "modelo-100-filed-declarations-read": {
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "borrador-confirmation",
            "declaration-submission",
        },
    }

    for cross_reference_id, expected_actions in expected_by_id.items():
        cross_reference = snapshot.live_cross_references[cross_reference_id]
        policy = remote_state_policy_from_cross_reference(cross_reference)

        assert expected_actions.issubset(cross_reference.forbidden_actions)
        for action in expected_actions:
            with pytest.raises(RegistryValidationError, match="forbidden action"):
                assert_remote_operation_allowed(
                    policy,
                    RemoteOperation(kind="browser_action", action=f"operator attempts {action}"),
                )


def test_modelo_100_xml_dictionary_layout_reads_official_casilla_paths() -> None:
    snapshot = _modelo_100_snapshot(2023)
    resolved = resolve_export_layout(snapshot)
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<Renta>
  <DatosIdentificativos>
    <Declarante>
      <DPNIF_D>12345678Z</DPNIF_D>
    </Declarante>
  </DatosIdentificativos>
    <DatosEconomicos>
      <TomaDatosAmpliada>
        <RegEstimaDirecta>
          <ActividadEstDirecta>
            <E1INGRESO>1234.56</E1INGRESO>
          </ActividadEstDirecta>
        </RegEstimaDirecta>
        <RegEstimaObj>
          <ActividadEstObj>
            <E4AL>2000.00</E4AL>
          </ActividadEstObj>
        </RegEstimaObj>
        <RegEstimaObjAgricola>
          <ActividadAgr>
            <E5AK>1500.00</E5AK>
          </ActividadAgr>
        </RegEstimaObjAgricola>
        <Inmuebles>
          <Inmueble>
            <DisposicionTitulares>
              <C_RII>10.00</C_RII>
            </DisposicionTitulares>
        </Inmueble>
      </Inmuebles>
    </TomaDatosAmpliada>
    <Resultados>
      <InmueblesRes>
        <IRIM>10.00</IRIM>
      </InmueblesRes>
    </Resultados>
  </DatosEconomicos>
</Renta>
"""

    parsed = parse_export_payload(
        resolved.layout,
        payload,
        source_root=bundled_path(),
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "0089": Decimal("10.00"),
        "0155": Decimal("10.00"),
        "0180": Decimal("1234.56"),
        "1479": Decimal("2000.00"),
        "1553": Decimal("1500.00"),
    }
    assert all(item.casilla_id != "01" for item in parsed.casillas)


def test_modelo_100_objective_estimation_record_design_paths_roundtrip_from_export_layout() -> None:
    snapshot = _modelo_100_snapshot()
    resolved = resolve_export_layout(snapshot)
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<Renta>
  <DatosEconomicos>
    <TomaDatosAmpliada>
      <RegEstimaObj>
        <ActividadEstObj>
          <E4AL>214.00</E4AL>
        </ActividadEstObj>
      </RegEstimaObj>
      <RegEstimaObjAgricola>
        <ActividadAgr>
          <E5AK>315.00</E5AK>
        </ActividadAgr>
      </RegEstimaObjAgricola>
      <RegimenesEspeciales>
        <REAtRentas>
          <ENTIDADAR>
            <F1EH>128.00</F1EH>
          </ENTIDADAR>
        </REAtRentas>
      </RegimenesEspeciales>
    </TomaDatosAmpliada>
  </DatosEconomicos>
</Renta>
"""

    parsed = parse_export_payload(
        resolved.layout,
        payload,
        source_root=bundled_path(),
        sources=snapshot.sources,
    )

    assert {item.casilla_id: item.value for item in parsed.casillas} == {
        "1479": Decimal("214.00"),
        "1553": Decimal("315.00"),
        "1577": Decimal("128.00"),
    }


def test_construct_reader_rejects_unknown_construct_id() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]

    with pytest.raises(RegistrySnapshotError, match="has no construct"):
        resolve_construct(revision, "missing-construct")


def test_construct_reader_rejects_unknown_member_id_at_runtime() -> None:
    """`resolve_construct` carries a defence-in-depth runtime check: if a
    construct's member tuple references an id absent from the matching
    revision index, it raises `RegistrySnapshotError` mentioning the
    construct id, the member kind, and the unknown id. The pre-flight
    validator should normally catch this, but the runtime gate must hold
    independently — this test pins the message format and the runtime
    branch."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.casilla_ids)
    mutated_construct = construct.model_copy(
        update={"casilla_ids": (*construct.casilla_ids, _UNKNOWN_CONSTRUCT_MEMBER_CASILLA)},
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )

    with pytest.raises(
        RegistrySnapshotError,
        match=rf"construct '{construct.id}' references unknown casilla '{_UNKNOWN_CONSTRUCT_MEMBER_CASILLA}'",
    ):
        resolve_construct(mutated_revision, construct.id)


def test_validator_rejects_construct_member_outside_revision() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(update={"relations": (*construct.relations, "missing-relation")})
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="references unknown relation"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_validator_rejects_construct_dependency_classification_outside_revision() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    construct = next(item for item in revision.constructs if item.id == "renta-dependent-modelos")
    mutated_construct = construct.model_copy(
        update={"dependency_classifications": (*construct.dependency_classifications, "missing-dependency")},
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="references unknown dependency classification"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_validator_rejects_dependency_classification_source_drift() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = revision.dependency_classifications[0].model_copy(update={"source_modelo": "115"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (classification, *revision.dependency_classifications[1:])},
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="does not match relation"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_validator_rejects_unclassified_relation_source() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in revision.dependency_classifications if item.source_modelo != "130"
            ),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="relation source modelo '130' has no dependency classification"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_validator_rejects_partial_dependency_classification_relation_coverage() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "111")
    mutated_classification = classification.model_copy(update={"relation_refs": classification.relation_refs[:1]})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                mutated_classification if item.id == classification.id else item
                for item in revision.dependency_classifications
            ),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="does not cover relation refs"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_schema_rejects_direct_dependency_classification_without_relation_refs() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")

    with pytest.raises(ValueError, match="must declare relation_refs"):
        classification.__class__.model_validate({**classification.model_dump(mode="python"), "relation_refs": ()})


def test_validator_rejects_duplicate_dependency_classification_source() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    duplicate = classification.model_copy(update={"id": "renta-2025-dep-130-duplicate"})
    mutated_revision = revision.model_copy(
        update={"dependency_classifications": (*revision.dependency_classifications, duplicate)},
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="duplicate dependency classification source modelo '130'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_validator_rejects_dependency_classification_target_construct_drift() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "190")
    construct = next(item for item in revision.constructs if item.id == "renta-work-income")
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            ),
        },
    )
    mutated_revision = revision.model_copy(
        update={
            "constructs": tuple(mutated_construct if item.id == construct.id else item for item in revision.constructs),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(RegistryValidationError, match="but the construct does not list it"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_modelo_100_renta_web_open_cross_reference_is_read_only_simulator_evidence() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    revision = modelos_by_id["100"].revisions["2025"]
    cross_reference = next(item for item in revision.live_cross_references if item.id == "modelo-100-renta-web-open")
    source = catalogues.sources[cross_reference.source_refs[0]]
    source_text = (bundled_path() / source.corpus_path).read_text(encoding="utf-8")

    assert cross_reference.surface == "open_simulator"
    assert cross_reference.synthetic_data_allowed is False
    assert cross_reference.requires_authentication is False
    assert "presentation" in cross_reference.forbidden_actions
    assert "payment" in cross_reference.forbidden_actions
    assert "funciona como un simulador" in source_text
    assert "no permite la presentaci&oacute;n de la declaraci&oacute;n" in source_text


def _select_source_revisions(
    modelo: ModeloDefinition,
    selector: Mapping[str, str | int],
) -> tuple[ModeloRevision, ...]:
    year = selector.get("year")
    revision_id = selector.get("revision_id", selector.get("revision"))
    selected: list[ModeloRevision] = []
    for revision in modelo.revisions.values():
        if isinstance(revision_id, str) and revision.id != revision_id:
            continue
        if isinstance(year, int) and not revision.period_selector.includes_year(year):
            continue
        selected.append(revision)
    return tuple(selected)
