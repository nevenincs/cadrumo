"""Modelo 100 semantic-role and label registry tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import CasillaId
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
    _casilla_id,
    _loaded_registry,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        casilla.id: casilla for casilla in revision.casillas if casilla.semantic_role in _SAVINGS_BASE_ART_49_ONLY_ROLES
    }

    assert set(casillas_by_id) == _SAVINGS_BASE_ART_49_ONLY_CASILLAS
    for casilla in casillas_by_id.values():
        assert _SAVINGS_BASE_ART_49_REF in casilla.legal_refs, casilla.id
        assert _GENERAL_BASE_ART_48_REF not in casilla.legal_refs, casilla.id


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_attribution_regime_base_imputada_uses_attribution_article(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _ATTRIBUTION_REGIME_BASE_IMPUTADA_CASILLA)

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
    checked = [casilla for casilla in revision.casillas if _ATTRIBUTION_DETAIL_SECTIONS & frozenset(casilla.section)]

    assert checked
    for casilla in checked:
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id


@pytest.mark.parametrize(
    ("filing_year", "expected_order_ref"),
    (
        (2020, "orden-hac-248-2021:art-10"),
        (2021, "orden-hfp-207-2022:art-10"),
        (2022, "orden-hfp-310-2023:art-11"),
        (2023, "orden-hac-265-2024:art-11"),
        (2024, "orden-hac-242-2025:art-11"),
        (2025, "orden-hac-277-2026:art-10"),
    ),
)
def test_modelo_100_tfi_detail_fields_cite_revision_order_documentation_article(
    filing_year: int,
    expected_order_ref: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    detail_roles = {"irpf_re_tfi_entidad_denominacion", "irpf_re_tfi_imputacion_importe"}
    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in detail_roles
    }

    assert set(casillas_by_role) == detail_roles
    for casilla in casillas_by_role.values():
        assert "ley-35-2006:art-91" in casilla.legal_refs, casilla.id
        assert expected_order_ref in casilla.legal_refs, casilla.id


@pytest.mark.parametrize(
    ("filing_year", "expected_order_ref"),
    (
        (2020, "orden-hac-248-2021:art-3"),
        (2021, "orden-hfp-207-2022:art-3"),
        (2022, "orden-hfp-310-2023:art-3"),
        (2023, "orden-hac-265-2024:art-3"),
        (2024, "orden-hac-242-2025:art-3"),
        (2025, "orden-hac-277-2026:art-3"),
    ),
)
def test_modelo_100_revision_declares_annual_form_order(
    filing_year: int,
    expected_order_ref: str,
) -> None:
    modelos_by_id, catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions[str(filing_year)]

    assert expected_order_ref in catalogues.legal
    assert expected_order_ref in modelo.legal_refs
    assert expected_order_ref in revision.legal_refs
    assert revision.orden_aplicabilidad == (expected_order_ref,)


def test_modelo_100_2025_zec_reduced_rate_parameter_cites_special_rate_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    parameters_by_id = {parameter.id: parameter for parameter in revision.parameters}
    parameter = parameters_by_id["renta-2025-zec-tipo-gravamen-reducido"]

    assert parameter.legal_refs == ("ley-19-1994:art-43",)
    assert "ley-19-1994:art-50" not in parameter.legal_refs
    assert [dated_value.value for dated_value in parameter.values] == [Decimal("4")]


@pytest.mark.parametrize(
    (
        "filing_year",
        "casilla_id",
        "expected_section",
        "label_fragment",
        "expected_role",
        "required_ref",
        "forbidden_ref",
    ),
    [
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
    ],
)
def test_modelo_100_reserva_inversiones_roles_follow_official_section(
    filing_year: int,
    casilla_id: str,
    expected_section: tuple[str, ...],
    label_fragment: str,
    expected_role: str,
    required_ref: str,
    forbidden_ref: str | None,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id(casilla_id))

    assert tuple(casilla.section) == expected_section
    assert label_fragment in casilla.label
    assert casilla.semantic_role == expected_role
    assert required_ref in casilla.legal_refs
    if forbidden_ref is not None:
        assert forbidden_ref not in casilla.legal_refs


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


@pytest.mark.parametrize("filing_year", range(2023, 2026))
def test_modelo_100_ev_charging_point_deduction_keeps_da_58_grounding(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("1935"))

    assert tuple(casilla.section) == _EV_CHARGING_POINT_RESULTS_SECTION
    assert casilla.semantic_role == _EV_CHARGING_POINT_DEDUCTION_ROLE
    assert _EV_CHARGING_POINT_DEDUCTION_DA_58_REF in casilla.legal_refs
    assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF not in casilla.legal_refs


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


@pytest.mark.parametrize("filing_year", range(2022, 2026))
def test_modelo_100_anexo_c_energy_excess_roles_are_spelled_and_grounded(filing_year: int) -> None:
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
    assert _ANEXO_C_ENERGY_EXCESS_ROLES.issubset(set(roles_by_casilla.values()))
    assert not missing_da50


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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0383"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0343"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0303"))

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
    casilla = next(casilla for casilla in revision_2020.casillas if casilla.id == _casilla_id("0356"))

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
            if casilla.id == _casilla_id("0356")
        )
        for filing_year in range(2022, 2026)
    }

    assert set(later_revision_roles.values()) == {"irpf_ganancia_premios_ayuda_200_euros"}


def test_modelo_100_tfi_operation_counts_are_integer_until_restructure() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_roles = {
        _casilla_id("0414"): "irpf_re_especial_tfi_declarante_num_operaciones",
        _casilla_id("0416"): "irpf_re_especial_tfi_conyuge_num_operaciones",
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
    casilla_0414_2025 = next(casilla for casilla in revision_2025.casillas if casilla.id == _casilla_id("0414"))

    assert casilla_0414_2025.semantic_role == "irpf_deduccion_obtencion_rendimientos_trabajo"
    assert tuple(casilla_0414_2025.section) == ("resultado_declaracion",)


def test_modelo_100_2025_coti_fund_loss_role_matches_loss_label() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    coti_loss = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("2233"))
    general_loss = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0321"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0080"))

        assert (
            casilla.label
            == "Número de días en que ha tenido este uso: Bien inmueble afecto a actividades económicas"
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


def test_modelo_100_inmueble_0076_habitual_residence_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_role = "irpf_inmueble_dias_vivienda_habitual"

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0076"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0079"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0085"))

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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0088"))

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
                casilla for casilla in revision.casillas if casilla.id == _casilla_id(casilla_id)
            )

            assert casilla.label == expected_label
            assert tuple(casilla.section) == ("toma_datos_ampliada", "inmuebles", "inmueble")
            assert casilla.data_type == "integer"
            assert casilla.semantic_role == "irpf_inmueble_dias_arrendado"
            assert "ley-35-2006:art-23" in casilla.legal_refs
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_eo_module_units_are_decimal() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        for casilla_id in ("1445", "1448", "1451", "1454", "1457", "1460", "1463"):
            casilla = next(
                casilla for casilla in revision.casillas if casilla.id == _casilla_id(casilla_id)
            )

            assert casilla.label == "Nº de unidades"
            assert tuple(casilla.section) == (
                "toma_datos_ampliada",
                "reg_estima_obj",
                "actividad_est_obj",
            )
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == "irpf_eo_modulo_num_unidades"
            assert expected_legal_refs.issubset(casilla.legal_refs)
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_re_attribution_inmueble_days_are_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("1618"))

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
        _casilla_id("1911"): "irpf_num_hijos_maternidad_2020",
        _casilla_id("1914"): "irpf_num_hijos_maternidad_2021",
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
        casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("1971"))

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
