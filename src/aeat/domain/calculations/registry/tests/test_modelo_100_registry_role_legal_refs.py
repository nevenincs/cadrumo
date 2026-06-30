"""Modelo 100 role and regularization legal-reference registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_legal_refs_support import (
    _ANDALUCIA_EJERCICIO_FISICO_ROLE,
    _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
    _CANARIAS_DONACION_DESCENDIENTES_ROLE,
    _CASILLA_0575,
    _CASILLA_0580,
    _CASILLA_0581,
    _CASILLA_0921,
    _CASILLA_1091,
    _DA45_CLAUSULA_SUELO_REF,
    _DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE,
    _DEDUCTION_LOSS_INTEREST_STATE_ROLE,
    _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
    _INCENTIVO_ART_33_REGULARIZATION_CASILLAS,
    _LGT_INTEREST_ART_26_REF,
    _LIRPF_CAPITAL_GAINS_ART_33_REF,
    _REGULARIZACION_DEDUCTION_LOSS_CASILLAS,
    _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS,
    _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS,
    _RIRPF_DEDUCTION_LOSS_ART_59_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        (2020, _DEDUCTION_LOSS_INTEREST_STATE_ROLE, "Parte estatal"),
        (2021, _DEDUCTION_LOSS_INTEREST_STATE_ROLE, "Parte estatal"),
        (2022, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE, "Parte autonómica"),
        (2023, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE, "Parte autonómica"),
        (2024, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE, "Parte autonómica"),
        (2025, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_ROLE, "Parte autonómica"),
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
    assert not casilla.semantic_role.endswith("_2")
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_da45_regularization_flags_cite_their_named_legal_basis(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in {_CASILLA_0575, _CASILLA_0580}
    }

    assert set(casillas_by_id) == {_CASILLA_0575, _CASILLA_0580}
    for casilla_id, expected_role in (
        (_CASILLA_0575, "irpf_flag_regularizacion_da45_estatal"),
        (_CASILLA_0580, "irpf_flag_regularizacion_da45"),
    ):
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert casilla.semantic_role == expected_role
        assert "D.A. 45" in casilla.label
        assert _DA45_CLAUSULA_SUELO_REF in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2022, 2026))
def test_modelo_100_art_33_incentive_loss_rows_cite_named_legal_basis(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _INCENTIVO_ART_33_REGULARIZATION_CASILLAS
    }

    assert set(casillas_by_id) == _INCENTIVO_ART_33_REGULARIZATION_CASILLAS
    for casilla in casillas_by_id.values():
        assert casilla.section[-1] == "gravamenes_res"
        assert "artículo 33.3" in casilla.label
        assert _LIRPF_CAPITAL_GAINS_ART_33_REF in casilla.legal_refs
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF not in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF not in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2022, 2026))
def test_modelo_100_previous_regularization_interest_rows_cite_lgt_interest_basis(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS
    }

    assert set(casillas_by_id) == _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS
    for casilla in casillas_by_id.values():
        assert casilla.section[-1] == "gravamenes_res"
        assert "Intereses de demora" in casilla.label
        assert "regularización anterior" in casilla.label
        assert _LGT_INTEREST_ART_26_REF in casilla.legal_refs
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF not in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_deduction_loss_regularization_rows_cite_exact_procedure(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    tracked_ids = _REGULARIZACION_DEDUCTION_LOSS_CASILLAS | _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in tracked_ids}

    assert set(casillas_by_id) == tracked_ids
    for casilla_id in _REGULARIZACION_DEDUCTION_LOSS_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert "deducciones" in casilla.label.lower()
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF not in casilla.legal_refs

    for casilla_id in _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert "Intereses de demora" in casilla.label
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF in casilla.legal_refs
