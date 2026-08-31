"""Modelo 100 semantic-role and label registry tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ._modelo_100_registry_support import (
    _ANEXO_C_ENERGY_EXCESS_ROLE_PREFIX,
    _ANEXO_C_ENERGY_EXCESS_ROLES,
    _ANEXO_C_ENERGY_EXCESS_SECTION,
    _ATTRIBUTION_DETAIL_ART_86_CASILLAS,
    _ATTRIBUTION_DETAIL_SECTIONS,
    _ATTRIBUTION_REGIME_ART_86_REF,
    _ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA,
    _ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE,
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF,
    _EV_CHARGING_POINT_DEDUCTION_DA_58_REF,
    _EV_CHARGING_POINT_DEDUCTION_ROLE,
    _EV_CHARGING_POINT_RESULTS_SECTION,
    _FRACTIONAL_PAYMENT_ARTICLE_REF,
    _GENERAL_BASE_ART_48_ONLY_CASILLAS,
    _GENERAL_BASE_ART_48_REF,
    _GENERAL_BASE_GYP_LIMIT_CASILLA,
    _GENERAL_BASE_IMPONIBLE_CASILLA,
    _GENERAL_BASE_IMPONIBLE_ROLE,
    _HOUSING_ENERGY_DEDUCTION_RESULT_ROLE,
    _HOUSING_ENERGY_RESULTS_SECTION,
    _LEGACY_RIB_SPLIT_ROLES,
    _RIB_BALEARES_DA70_REF,
    _RIB_DOTACION_ANIO_ROLE,
    _RIB_DOTACION_IMPORTE_ROLE,
    _RIB_INVERSION_TIPO_AB_ROLE,
    _RIB_INVERSION_TIPO_C_ROLE,
    _RIB_RESERVA_SECTION,
    _RIC_DOTACION_ANIO_ROLE,
    _RIC_DOTACION_IMPORTE_ROLE,
    _RIC_INVERSION_TIPO_ABD_ROLE,
    _RIC_INVERSION_TIPO_CD_ROLE,
    _RIC_RESERVA_SECTION,
    _SAVINGS_BASE_ART_49_ONLY_CASILLAS,
    _SAVINGS_BASE_ART_49_ONLY_ROLES,
    _SAVINGS_BASE_ART_49_REF,
    _SAVINGS_BASE_GYP_LIMIT_CASILLA,
    _loaded_registry,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_trabajo_otros_gastos_role_is_decimal_across_revisions() -> None:
    """Art. 19 work-income amount fields use M100 decimal precision consistently."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    role = "irpf_rendimiento_trabajo_gasto_otros"
    expected_years = {str(year) for year in range(2020, 2026)}
    found_years: set[str] = set()

    for revision_id, revision in modelo.revisions.items():
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        otros_gastos = next(casilla for casilla in revision.casillas if casilla.semantic_role == role)
        found_years.add(revision_id)

        assert otros_gastos.id == validated_casilla_id("0019", surface="test_modelo_100_registry.casilla")
        assert otros_gastos.data_type == "decimal"
        assert "ley-35-2006:art-19" in otros_gastos.legal_refs
        assert (
            casillas_by_id[validated_casilla_id("0018", surface="test_modelo_100_registry.casilla")].data_type
            == "decimal"
        )
        assert (
            casillas_by_id[validated_casilla_id("0022", surface="test_modelo_100_registry.casilla")].data_type
            == "decimal"
        )

    assert found_years == expected_years


def test_modelo_100_base_and_attribution_roles_are_legally_grounded_across_revisions() -> None:
    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        general_formula_id = f"renta-{filing_year}-saldo-gp-base-general-cap-25"
        savings_formula_id = f"renta-{filing_year}-saldo-gp-base-ahorro-cap-25"
        general_formula = next(formula for formula in revision.formulas if formula.id == general_formula_id)
        savings_formula = next(formula for formula in revision.formulas if formula.id == savings_formula_id)
        general_gyp_limit = next(
            casilla for casilla in revision.casillas if casilla.id == _GENERAL_BASE_GYP_LIMIT_CASILLA
        )
        savings_gyp_limit = next(
            casilla for casilla in revision.casillas if casilla.id == _SAVINGS_BASE_GYP_LIMIT_CASILLA
        )

        for refs in (general_formula.legal_refs, general_gyp_limit.legal_refs):
            assert _GENERAL_BASE_ART_48_REF in refs, filing_year
            assert _SAVINGS_BASE_ART_49_REF not in refs, filing_year
        for refs in (savings_formula.legal_refs, savings_gyp_limit.legal_refs):
            assert _SAVINGS_BASE_ART_49_REF in refs, filing_year
            assert _GENERAL_BASE_ART_48_REF not in refs, filing_year

        general_casillas = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in _GENERAL_BASE_ART_48_ONLY_CASILLAS
        }
        assert set(general_casillas) == _GENERAL_BASE_ART_48_ONLY_CASILLAS, filing_year
        for casilla in general_casillas.values():
            assert _GENERAL_BASE_ART_48_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, (filing_year, casilla.id)
            assert _ATTRIBUTION_REGIME_ART_86_REF not in casilla.legal_refs, (filing_year, casilla.id)

        base_general = general_casillas[_GENERAL_BASE_IMPONIBLE_CASILLA]
        assert base_general.semantic_role == _GENERAL_BASE_IMPONIBLE_ROLE, filing_year
        assert base_general.label == "Base imponible general", filing_year

        savings_casillas = {
            casilla.id: casilla
            for casilla in revision.casillas
            if casilla.semantic_role in _SAVINGS_BASE_ART_49_ONLY_ROLES
        }
        assert set(savings_casillas) == _SAVINGS_BASE_ART_49_ONLY_CASILLAS, filing_year
        for casilla in savings_casillas.values():
            assert _SAVINGS_BASE_ART_49_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _GENERAL_BASE_ART_48_REF not in casilla.legal_refs, (filing_year, casilla.id)

        attribution_base = next(
            casilla for casilla in revision.casillas if casilla.id == _ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA
        )
        assert _ATTRIBUTION_REGIME_ART_86_REF in attribution_base.legal_refs, filing_year
        assert attribution_base.semantic_role == _ATTRIBUTION_REGIME_BASE_IMPUTADA_ROLE, filing_year
        assert attribution_base.label == "Base imponible imputada", filing_year
        assert _GENERAL_BASE_ART_48_REF not in attribution_base.legal_refs, filing_year
        assert _SAVINGS_BASE_ART_49_REF not in attribution_base.legal_refs, filing_year
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in attribution_base.legal_refs, filing_year

        attribution_detail_casillas = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in _ATTRIBUTION_DETAIL_ART_86_CASILLAS
        }
        assert set(attribution_detail_casillas) == _ATTRIBUTION_DETAIL_ART_86_CASILLAS, filing_year
        for casilla in attribution_detail_casillas.values():
            assert _ATTRIBUTION_REGIME_ART_86_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, (filing_year, casilla.id)

        checked_sections = [
            casilla for casilla in revision.casillas if _ATTRIBUTION_DETAIL_SECTIONS & frozenset(casilla.section)
        ]
        assert checked_sections, filing_year
        for casilla in checked_sections:
            assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, (filing_year, casilla.id)


def test_modelo_100_annual_order_refs_are_declared_and_cited() -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    detail_roles = {"irpf_re_tfi_entidad_denominacion", "irpf_re_tfi_imputacion_importe"}
    expected_refs = {
        2020: ("orden-hac-248-2021:art-3", "orden-hac-248-2021:art-10"),
        2021: ("orden-hfp-207-2022:art-3", "orden-hfp-207-2022:art-10"),
        2022: ("orden-hfp-310-2023:art-3", "orden-hfp-310-2023:art-11"),
        2023: ("orden-hac-265-2024:art-3", "orden-hac-265-2024:art-11"),
        2024: ("orden-hac-242-2025:art-3", "orden-hac-242-2025:art-11"),
        2025: ("orden-hac-277-2026:art-3", "orden-hac-277-2026:art-10"),
    }

    for filing_year, (annual_order_ref, tfi_order_ref) in expected_refs.items():
        revision = modelo.revisions[str(filing_year)]

        assert annual_order_ref in catalogues.legal, filing_year
        assert annual_order_ref in modelo.legal_refs, filing_year
        assert annual_order_ref in revision.legal_refs, filing_year
        assert revision.orden_aplicabilidad == (annual_order_ref,), filing_year

        # The 2020 revision's applicability window (closes_on 2021-06-30) predates
        # art. 91's current redaction (effective_from 2021-07-11, Ley 11/2021 art.
        # 3.4); it cites the version-scoped 2015-2021-07-10 redaction instead. Every
        # later revision cites the current bare id.
        art_91_ref = "ley-35-2006:art-91-2015" if filing_year == 2020 else "ley-35-2006:art-91"

        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in detail_roles
        }
        assert set(casillas_by_role) == detail_roles, filing_year
        for casilla in casillas_by_role.values():
            assert art_91_ref in casilla.legal_refs, (filing_year, casilla.id)
            assert tfi_order_ref in casilla.legal_refs, (filing_year, casilla.id)


def test_modelo_100_2025_zec_reduced_rate_parameter_cites_special_rate_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    parameters_by_id = {parameter.id: parameter for parameter in revision.parameters}
    parameter = parameters_by_id["renta-2025-zec-tipo-gravamen-reducido"]

    assert parameter.legal_refs == ("ley-19-1994:art-43",)
    assert "ley-19-1994:art-50" not in parameter.legal_refs
    assert [dated_value.value for dated_value in parameter.values] == [Decimal("4")]


def test_modelo_100_reserva_inversiones_roles_follow_official_section() -> None:
    expected_cases = (
        (
            2022,
            "1692",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_ABD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2022,
            "1696",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_CD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2023,
            "1681",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_DOTACION_IMPORTE_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2023,
            "1682",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_DOTACION_ANIO_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2023,
            "1684",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_ABD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2023,
            "1685",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_CD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2024,
            "1681",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_DOTACION_IMPORTE_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2024,
            "1682",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_DOTACION_ANIO_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2024,
            "1684",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_ABD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2024,
            "1685",
            _RIC_RESERVA_SECTION,
            "Canarias",
            _RIC_INVERSION_TIPO_CD_ROLE,
            _AUTONOMIC_DEDUCTION_ART_77_REF,
            _RIB_BALEARES_DA70_REF,
        ),
        (
            2023,
            "1938",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2023,
            "1940",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2023,
            "1943",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2024,
            "1781",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2024,
            "1783",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2024,
            "1938",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2024,
            "1940",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2024,
            "1943",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1681",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_IMPORTE_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1682",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1684",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_AB_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1685",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1781",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1783",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1938",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_DOTACION_ANIO_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1940",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
        (
            2025,
            "1943",
            _RIB_RESERVA_SECTION,
            "Illes Balears",
            _RIB_INVERSION_TIPO_C_ROLE,
            _RIB_BALEARES_DA70_REF,
            None,
        ),
    )

    for (
        filing_year,
        casilla_id,
        expected_section,
        label_fragment,
        expected_role,
        required_ref,
        forbidden_ref,
    ) in expected_cases:
        revision = _modelo_100_snapshot(filing_year).revision
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == expected_section, (filing_year, casilla_id)
        assert label_fragment in casilla.label, (filing_year, casilla_id)
        assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
        assert required_ref in casilla.legal_refs, (filing_year, casilla_id)
        if forbidden_ref is not None:
            assert forbidden_ref not in casilla.legal_refs, (filing_year, casilla_id)


def test_modelo_100_reserva_inversiones_split_axes_use_regime_specific_roles() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    reserva_sections = {_RIC_RESERVA_SECTION[-1], _RIB_RESERVA_SECTION[-1]}
    offences: list[str] = []

    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if not reserva_sections.intersection(casilla.section):
                continue
            if casilla.semantic_role in _LEGACY_RIB_SPLIT_ROLES:
                offences.append(f"{revision_id}/{casilla.id}: {casilla.semantic_role}")

    assert not offences, "legacy RIB split semantic roles remain:\n  " + "\n  ".join(offences)


def test_modelo_100_ev_charging_point_deduction_keeps_da_58_grounding() -> None:
    for filing_year in range(2023, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("1935", surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == _EV_CHARGING_POINT_RESULTS_SECTION, filing_year
        assert casilla.semantic_role == _EV_CHARGING_POINT_DEDUCTION_ROLE, filing_year
        assert _EV_CHARGING_POINT_DEDUCTION_DA_58_REF in casilla.legal_refs, filing_year
        assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF not in casilla.legal_refs, filing_year


def test_modelo_100_housing_energy_result_role_stays_in_housing_energy_section() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    offences: list[str] = []

    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if casilla.semantic_role != _HOUSING_ENERGY_DEDUCTION_RESULT_ROLE:
                continue
            if tuple(casilla.section) != _HOUSING_ENERGY_RESULTS_SECTION:
                offences.append(f"{revision_id}/{casilla.id}: section={tuple(casilla.section)}")
            if _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF not in casilla.legal_refs:
                offences.append(f"{revision_id}/{casilla.id}: missing {_ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF}")
            if _EV_CHARGING_POINT_DEDUCTION_DA_58_REF in casilla.legal_refs:
                offences.append(f"{revision_id}/{casilla.id}: carries {_EV_CHARGING_POINT_DEDUCTION_DA_58_REF}")

    assert not offences, "housing energy result role escaped its legal section:\n  " + "\n  ".join(offences)


def test_modelo_100_anexo_c_energy_excess_roles_are_spelled_and_grounded() -> None:
    for filing_year in range(2022, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        offences: list[str] = []
        roles_by_casilla: dict[CasillaId, str] = {}
        for casilla in revision.casillas:
            semantic_role = casilla.semantic_role
            if semantic_role is None:
                continue
            if "eeficiencia" in semantic_role:
                offences.append(f"{filing_year}/{casilla.id}: {semantic_role}")
            if tuple(casilla.section) == _ANEXO_C_ENERGY_EXCESS_SECTION and semantic_role.startswith(
                _ANEXO_C_ENERGY_EXCESS_ROLE_PREFIX,
            ):
                roles_by_casilla[casilla.id] = semantic_role
        missing_da50 = {
            casilla.id: casilla.legal_refs
            for casilla in revision.casillas
            if casilla.id in roles_by_casilla and _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF not in casilla.legal_refs
        }

        assert not offences, "misspelled Anexo C energy-efficiency roles remain:\n  " + "\n  ".join(offences)
        assert _ANEXO_C_ENERGY_EXCESS_ROLES.issubset(set(roles_by_casilla.values())), filing_year
        assert not missing_da50, filing_year


def test_modelo_100_anexo_c_protected_patrimony_current_year_excess_role_is_grounded() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    current_year_role = "irpf_anexo_c_exceso_patrim_protegido_ejercicio_actual"
    old_role = "irpf_anexo_c_exceso_patrim_protegido_generado"
    expected_section = ("resultados", "anexo_c_res", "excesos_patrim_protegidos_res")

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("1362", surface="test_modelo_100_registry.casilla")
        )
        expected_sources = {
            f"aeat-dr-100-{filing_year}-dictionary",
            f"aeat-dr-100-{filing_year}-input-dictionary",
            f"aeat-dr-100-{filing_year}-xsd",
        }

        assert casilla.label == (
            f"Aportaciones de {filing_year} no aplicadas cuyo importe se solicita poder reducir "
            "en los 4 ejercicios siguientes"
        )
        assert tuple(casilla.section) == expected_section
        assert casilla.semantic_role == current_year_role
        assert "ley-35-2006:art-54" in casilla.legal_refs
        assert expected_sources.issubset(casilla.source_refs)

    assert all(
        casilla.semantic_role != old_role for revision in modelo.revisions.values() for casilla in revision.casillas
    )


def test_modelo_100_prevision_social_0383_splits_income_threshold_polarity() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_by_year = {
        2023: (
            "irpf_red_prevision_social_rendimientos_trabajo_igual_inferior_60000_flag",
            "iguales o inferiores a 60.000",
        ),
        2024: (
            "irpf_red_prevision_social_rendimientos_trabajo_igual_inferior_60000_flag",
            "iguales o inferiores a 60.000",
        ),
        2025: (
            "irpf_red_prevision_social_rendimientos_trabajo_superior_60000_flag",
            "superiores a 60.000",
        ),
    }

    for filing_year, (expected_role, label_fragment) in expected_by_year.items():
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0383", surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == ("toma_datos_ampliada", "red_base_imponible", "red_prevision_social")
        assert casilla.semantic_role == expected_role
        assert label_fragment in casilla.label
        if filing_year == 2025:
            assert casilla.semantic_role_cardinality == "intentional_singleton"
            assert casilla.semantic_role_cardinality_reason
            assert "flips casilla 0383" in casilla.semantic_role_cardinality_reason
        else:
            assert casilla.semantic_role_cardinality == "shared"
        assert {"ley-35-2006:art-51", "ley-35-2006:art-52"}.issubset(casilla.legal_refs)
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )

    assert all(
        casilla.semantic_role != "irpf_red_prevision_social_rendimientos_trabajo_rango_flag"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_derechos_transmission_global_role_spans_revisions() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_ganancia_derechos_valor_transmision_global"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0343", surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == ("toma_datos_ampliada", "gp_derechos", "entidad_derecho")
        assert casilla.semantic_role == expected_role
        assert casilla.label.startswith("Importe global de las transmisiones efectuadas en ")
        assert {"ley-35-2006:art-33", "ley-35-2006:art-34"}.issubset(casilla.legal_refs)
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )

    assert all(
        casilla.semantic_role != "irpf_ganancia_transmisiones_importe_global_2024"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_premios_0303_splits_historical_emancipation_grant_from_rental_aid() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_by_year = {
        2020: ("irpf_ganancia_premios_renta_basica_emancipacion", "emancipaci"),
        2021: ("irpf_ganancia_premios_renta_basica_emancipacion", "emancipaci"),
        2022: ("irpf_ganancia_premios_ayuda_alquiler", "al alquiler"),
        2023: ("irpf_ganancia_premios_ayuda_alquiler", "al alquiler"),
        2024: ("irpf_ganancia_premios_ayuda_alquiler", "al alquiler"),
        2025: ("irpf_ganancia_premios_ayuda_alquiler", "al alquiler"),
    }

    for filing_year, (expected_role, label_fragment) in expected_by_year.items():
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0303", surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == ("toma_datos_ampliada", "gp_premios", "otras")
        assert casilla.semantic_role == expected_role
        assert label_fragment in casilla.label
        assert {"ley-35-2006:art-33", "ley-35-2006:art-34"}.issubset(casilla.legal_refs)
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )

    assert all(
        casilla.semantic_role != "irpf_ganancia_renta_basica_emancipacion"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_2020_0356_is_gp_otros_ordinal_element_number() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision_2020 = modelo.revisions["2020"]
    casilla = next(
        casilla
        for casilla in revision_2020.casillas
        if casilla.id == validated_casilla_id("0356", surface="test_modelo_100_registry.casilla")
    )

    assert casilla.label == "Número de orden del elemento"
    assert tuple(casilla.section) == ("toma_datos_ampliada", "gp_otros_elementos", "elemento_patrimonial")
    assert casilla.data_type == "integer"
    assert casilla.semantic_role == "irpf_gp_elemento_numero_orden"
    assert tuple(casilla.legal_refs) == ("ley-35-2006:art-33", "ley-35-2006:art-34")
    assert {"aeat-dr-100-2020-dictionary", "aeat-dr-100-2020-xsd"}.issubset(casilla.source_refs)

    later_revision_roles = {
        filing_year: next(
            casilla.semantic_role
            for casilla in modelo.revisions[str(filing_year)].casillas
            if casilla.id == validated_casilla_id("0356", surface="test_modelo_100_registry.casilla")
        )
        for filing_year in range(2022, 2026)
    }

    assert set(later_revision_roles.values()) == {"irpf_ganancia_premios_ayuda_200_euros"}


def test_modelo_100_tfi_operation_counts_are_integer_until_restructure() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_roles = {
        validated_casilla_id(
            "0414", surface="test_modelo_100_registry.casilla"
        ): "irpf_re_especial_tfi_declarante_num_operaciones",
        validated_casilla_id(
            "0416", surface="test_modelo_100_registry.casilla"
        ): "irpf_re_especial_tfi_conyuge_num_operaciones",
    }

    for filing_year in range(2020, 2023):
        revision = modelo.revisions[str(filing_year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_roles}

        assert set(casillas_by_id) == set(expected_roles)
        for casilla_id, expected_role in expected_roles.items():
            casilla = casillas_by_id[casilla_id]

            assert casilla.label.endswith("Nº de operaciones")
            assert tuple(casilla.section) == ("toma_datos_ampliada", "regimen_especial")
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == expected_role
            assert "ley-35-2006:art-37" in casilla.legal_refs
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )

    revision_2025 = modelo.revisions["2025"]
    casilla_0414_2025 = next(
        casilla
        for casilla in revision_2025.casillas
        if casilla.id == validated_casilla_id("0414", surface="test_modelo_100_registry.casilla")
    )

    assert casilla_0414_2025.semantic_role == "irpf_deduccion_obtencion_rendimientos_trabajo"
    assert tuple(casilla_0414_2025.section) == ("resultado_declaracion",)


def test_modelo_100_2025_coti_fund_loss_role_matches_loss_label() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    coti_loss = next(
        casilla
        for casilla in revision.casillas
        if casilla.id == validated_casilla_id("2233", surface="test_modelo_100_registry.casilla")
    )
    general_loss = next(
        casilla
        for casilla in revision.casillas
        if casilla.id == validated_casilla_id("0321", surface="test_modelo_100_registry.casilla")
    )

    assert coti_loss.label == "Pérdidas patrimoniales"
    assert tuple(coti_loss.section) == ("toma_datos_ampliada", "gp_fondos_coti", "fondo")
    assert coti_loss.semantic_role == "irpf_perdida_fondos_coti_importe"
    assert coti_loss.semantic_role_cardinality == "intentional_singleton"
    assert coti_loss.semantic_role_cardinality_reason
    assert "quoted-fund coti capital-loss slot" in coti_loss.semantic_role_cardinality_reason
    assert {"ley-35-2006:art-33", "ley-35-2006:art-34"}.issubset(coti_loss.legal_refs)
    assert {"aeat-dr-100-2025-dictionary", "aeat-dr-100-2025-xsd"}.issubset(coti_loss.source_refs)

    assert general_loss.label == coti_loss.label
    assert general_loss.semantic_role == "irpf_perdida_fondos_importe"
    assert all(
        casilla.semantic_role != "irpf_perdida_fondos_coti_importe_obtenido"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_inmueble_0080_activity_use_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_afecto_actividades_economicas"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0080", surface="test_modelo_100_registry.casilla")
        )

        assert (
            casilla.label == "Número de días en que ha tenido este uso: Bien inmueble afecto a actividades económicas"
        )
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert {"ley-35-2006:art-27", "ley-35-2006:art-28", "ley-35-2006:art-30"}.issubset(
            casilla.legal_refs,
        )
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_spouse_disability_marriage_months_are_integer_months() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_rows = {
        validated_casilla_id("0246", surface="test_modelo_100_registry.casilla"): (
            "Primer mes",
            "irpf_conyuge_discapacidad_matrimonio_mes_inicio",
        ),
        validated_casilla_id("0247", surface="test_modelo_100_registry.casilla"): (
            "Último mes completo",
            "irpf_conyuge_discapacidad_matrimonio_mes_fin",
        ),
    }
    expected_section = ("resultados", "calculo_impuesto_res", "deduc_conyuge_disc_res")

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}

        assert set(casillas_by_id) == set(expected_rows)
        for casilla_id, (label_prefix, expected_role) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            constraints = casilla.constraints
            expected_sources = {
                f"aeat-dr-100-{filing_year}-dictionary",
                f"aeat-dr-100-{filing_year}-input-dictionary",
                f"aeat-dr-100-{filing_year}-xsd",
            }

            assert casilla.label.startswith(label_prefix)
            assert "vigente el matrimonio" in casilla.label
            assert tuple(casilla.section) == expected_section
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == expected_role
            assert "ley-35-2006:art-81-bis" in casilla.legal_refs
            assert expected_sources.issubset(casilla.source_refs)
            assert constraints is not None
            assert constraints.sign == "non_negative"
            assert constraints.min_value is None
            assert constraints.max_value == Decimal("12")
            assert "ley-35-2006:art-81-bis" in constraints.legal_refs
            assert expected_sources.issubset(constraints.source_refs)

        formulas_by_target = {
            formula.target_casilla_id: formula
            for formula in revision.formulas
            if formula.target_casilla_id in expected_rows
        }
        for formula in formulas_by_target.values():
            assert "ley-35-2006:art-82" in formula.legal_refs
            assert f"aeat-dr-100-{filing_year}-dictionary" in formula.source_refs
            assert f"aeat-dr-100-{filing_year}-xsd" in formula.source_refs

    assert all(
        casilla.semantic_role != "irpf_matrimonio_mes_fin"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )


def test_modelo_100_disability_minimum_headcounts_are_integer_counts() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_rows = {
        validated_casilla_id("0618", surface="test_modelo_100_registry.casilla"): (
            "descendientes",
            ("resultados", "calculo_impuesto_res", "deduc_descendiente_disc_res"),
            "irpf_descendiente_num_contribuyentes_derecho",
            Decimal("1"),
            Decimal("9"),
        ),
        validated_casilla_id("0629", surface="test_modelo_100_registry.casilla"): (
            "ascendientes",
            ("resultados", "calculo_impuesto_res", "deduc_ascendiente_disc_res"),
            "irpf_ascendiente_num_contribuyentes_derecho",
            None,
            Decimal("99"),
        ),
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}

        assert set(casillas_by_id) == set(expected_rows)
        for casilla_id, (
            label_fragment,
            expected_section,
            expected_role,
            min_value,
            max_value,
        ) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            constraints = casilla.constraints
            expected_sources = {
                f"aeat-dr-100-{filing_year}-dictionary",
                f"aeat-dr-100-{filing_year}-input-dictionary",
                f"aeat-dr-100-{filing_year}-xsd",
            }

            assert "número de personas con derecho al mínimo" in casilla.label
            assert label_fragment in casilla.label
            assert tuple(casilla.section) == expected_section
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == expected_role
            assert "ley-35-2006:art-81-bis" in casilla.legal_refs
            assert expected_sources.issubset(casilla.source_refs)
            assert constraints is not None
            assert constraints.sign == "non_negative"
            assert constraints.min_value == min_value
            assert constraints.max_value == max_value
            assert "ley-35-2006:art-81-bis" in constraints.legal_refs
            assert expected_sources.issubset(constraints.source_refs)


def test_modelo_100_family_numerosa_ascendant_count_is_integer_count() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0652", surface="test_modelo_100_registry.casilla")
        )
        constraints = casilla.constraints
        expected_sources = {
            f"aeat-dr-100-{filing_year}-dictionary",
            f"aeat-dr-100-{filing_year}-input-dictionary",
            f"aeat-dr-100-{filing_year}-xsd",
        }

        assert casilla.label == "Indique el número de ascendientes que forman parte de la misma familia numerosa"
        assert tuple(casilla.section) == ("resultados", "calculo_impuesto_res", "deduc_familia_numerosa_res")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == "irpf_familia_numerosa_num_ascendientes"
        assert "ley-35-2006:art-81-bis" in casilla.legal_refs
        assert expected_sources.issubset(casilla.source_refs)
        assert constraints is not None
        assert constraints.sign == "non_negative"
        assert constraints.min_value is None
        assert constraints.max_value == Decimal("99")
        assert "ley-35-2006:art-81-bis" in constraints.legal_refs
        assert expected_sources.issubset(constraints.source_refs)


def test_modelo_100_inmueble_0076_habitual_residence_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_vivienda_habitual"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0076", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == f"Número de días en que el inmueble ha sido su vivienda habitual en {filing_year}"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert "ley-35-2006:art-22" in casilla.legal_refs
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_inmueble_0079_use_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_uso"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0079", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == "Número de días en que la vivienda ha tenido este uso"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert "ley-35-2006:art-22" in casilla.legal_refs
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_inmueble_0085_disposal_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_a_disposicion"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0085", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == "Número de días a disposición del contribuyente"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert "ley-35-2006:art-22" in casilla.legal_refs
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_inmueble_0088_mixed_use_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_otros_usos"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("0088", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == "Número de días"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert "ley-35-2006:art-22" in casilla.legal_refs
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_inmueble_rented_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_labels = {
        "0101": "Número de días en que el inmueble ha estado arrendado",
        "0122": "Número de días en que el inmueble ha estado arrendado",
        "0137": "Número de días en que el inmueble accesorio ha estado arrendado",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        for casilla_id, expected_label in expected_labels.items():
            casilla = next(
                casilla
                for casilla in revision.casillas
                if casilla.id == validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
            )

            assert casilla.label == expected_label
            assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == "irpf_inmueble_dias_arrendado"
            assert "ley-35-2006:art-23" in casilla.legal_refs
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_re_attribution_inmueble_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("1618", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == "Nº de días"
        assert tuple(casilla.section) == ("toma_datos_ampliada", "regimenes_especiales", "re_at_rentas")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == "irpf_re_atrib_inmueble_num_dias"
        assert "ley-35-2006:art-86" in casilla.legal_refs
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_2022_maternity_child_counts_are_integer() -> None:
    revision = _modelo_100_snapshot(2022).revision
    expected_roles = {
        validated_casilla_id("1911", surface="test_modelo_100_registry.casilla"): "irpf_num_hijos_maternidad_2020",
        validated_casilla_id("1914", surface="test_modelo_100_registry.casilla"): "irpf_num_hijos_maternidad_2021",
    }
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_roles}

    assert set(casillas_by_id) == set(expected_roles)
    for casilla_id, expected_role in expected_roles.items():
        casilla = casillas_by_id[casilla_id]

        assert casilla.label == "Número de hijos que dan derecho a la deducción por maternidad"
        assert tuple(casilla.section) == ("resultados", "calculo_impuesto_res", "ampliacion_deduc_mater_res")
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == expected_role
        assert casilla.semantic_role_cardinality == "intentional_singleton"
        assert casilla.semantic_role_cardinality_reason
        assert "ley-35-2006:art-81" in casilla.legal_refs
        assert {"aeat-dr-100-2022-dictionary", "aeat-dr-100-2022-xsd"}.issubset(casilla.source_refs)


def test_modelo_100_la_rioja_municipality_codes_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    common_expected_roles = {
        "1064": "irpf_deduccion_la_rioja_vivienda_codigo_municipio",
        "1067": "irpf_deduccion_la_rioja_adecuacion_municipio_codigo",
        "1162": "irpf_deduccion_la_rioja_arrendamiento_municipio_codigo",
        "1164": "irpf_deduccion_la_rioja_municipio_pequeno_codigo",
        "1204": "irpf_deduccion_la_rioja_municipio_pequeno_codigo_2",
        "1205": "irpf_deduccion_la_rioja_municipio_pequeno_codigo_3",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        expected_roles = dict(common_expected_roles)
        if filing_year >= 2021:
            expected_roles["1071"] = "irpf_deduccion_la_rioja_guarderia_municipio_codigo"

        casillas_by_id = {
            casilla.id: casilla
            for casilla in revision.casillas
            if casilla.id
            in {
                validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
                for casilla_id in expected_roles
            }
        }

        assert set(casillas_by_id) == {
            validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
            for casilla_id in expected_roles
        }
        for casilla_id, expected_role in expected_roles.items():
            casilla = casillas_by_id[validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")]

            assert casilla.label in {"Código del municipio", "Código del municipio:", "Código del pequeño municipio:"}
            assert tuple(casilla.section) == ("resultados", "deduccion_autonomica_res", "la_rioja_res")
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == expected_role
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_retrib_especie_no_exenta_total_role_names_aggregate() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_retrib_especie_no_exenta_importe_integro_pendiente_imputacion"
    expected_legal_refs = {
        "ley-35-2006:art-17",
        "ley-35-2006:art-42.3.f",
        "ley-35-2006:art-14.2.m",
    }

    for filing_year in range(2023, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("1971", surface="test_modelo_100_registry.casilla")
        )

        assert tuple(casilla.section) == ("toma_datos_ampliada", "rdto_trabajo", "retrib_especie_anexo_c")
        assert casilla.semantic_role == expected_role
        assert "42.3.f" in casilla.label
        assert "14.2.m" in casilla.label
        assert casilla.label.endswith("Impo...")
        assert expected_legal_refs.issubset(casilla.legal_refs)
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )

    assert all(
        casilla.semantic_role != "irpf_retrib_especie_importe_no_exenta_4"
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    )
