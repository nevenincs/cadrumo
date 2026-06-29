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
