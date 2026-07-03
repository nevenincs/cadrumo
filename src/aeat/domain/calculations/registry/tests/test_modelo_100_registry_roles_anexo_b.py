"""Modelo 100 Anexo B semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _ANEXO_B_AAV_AMOUNT_ROWS,
    _ANEXO_B_AAV_SECTION,
    _ANEXO_B_ACCOUNT_ROWS,
    _ANEXO_B_ACCOUNT_SECTION,
    _ANEXO_B_BALEARES_NACIMIENTO_ROWS,
    _ANEXO_B_BALEARES_NACIMIENTO_SECTION,
    _ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL,
    _ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE,
    _ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE,
    _ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL,
    _ANEXO_B_EPS_SECTION,
    _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL,
    _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE,
    _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS,
    _ANEXO_B_IMPORTE_SATISFECHO_LABEL,
    _ANEXO_B_IMPORTE_SATISFECHO_ROLE,
    _ANEXO_B_IMPORTE_SATISFECHO_SECTIONS,
    _ANEXO_B_INVERSION_IMPORTE_LABEL,
    _ANEXO_B_INVERSION_IMPORTE_ROLE,
    _ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX,
    _ANEXO_B_INVERSION_TOTAL_ROLE,
    _ANEXO_B_INVERSION_TOTAL_SECTIONS,
    _ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE,
    _ANEXO_B_OTROS_GASTOS_LABELS,
    _ANEXO_B_OTROS_GASTOS_SECTION,
    _ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE,
    _ANEXO_B_PRIMA_SEGURO_LABEL,
    _ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE,
    _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL,
    _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE,
    _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS,
    _ANEXO_B_TOTAL_SATISFECHO_ROLE,
    _ANEXO_B_TOTAL_SATISFECHO_SECTIONS,
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_anexo_b_importe_satisfecho_role_is_not_rental_specific() -> None:
    for filing_year, expected_count in (
        (2020, 5),
        (2021, 5),
        (2022, 5),
        (2023, 5),
        (2024, 5),
        (2025, 7),
    ):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_IMPORTE_SATISFECHO_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_IMPORTE_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_IMPORTE_SATISFECHO_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_importe_anual_satisfecho_role_is_not_service_fee() -> None:
    for filing_year, expected_count in ((2024, 24), (2025, 32)):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL
            and casilla.semantic_role == _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_other_service_amount_role_is_otros_gastos_importe_anual() -> None:
    for filing_year in (2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        casilla = next(casilla for casilla in revision.casillas if casilla.id == "2140")

        assert casilla.label == _ANEXO_B_OTROS_GASTOS_LABELS[filing_year]
        assert tuple(casilla.section) == ("resultados", "datos_adicionales_anexo_b", _ANEXO_B_OTROS_GASTOS_SECTION)
        assert casilla.semantic_role == _ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE
        assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_aav_amount_roles_are_grounded_in_official_labels() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _ANEXO_B_AAV_AMOUNT_ROWS}

    assert set(casillas_by_id) == set(_ANEXO_B_AAV_AMOUNT_ROWS)
    for casilla_id, (expected_label, expected_role) in _ANEXO_B_AAV_AMOUNT_ROWS.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.label == expected_label
        assert tuple(casilla.section) == ("resultados", "datos_adicionales_anexo_b", _ANEXO_B_AAV_SECTION)
        assert casilla.semantic_role == expected_role
        assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_account_holder_role_is_cm_vivienda_habitual() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _ANEXO_B_ACCOUNT_ROWS}

    assert set(casillas_by_id) == set(_ANEXO_B_ACCOUNT_ROWS)
    for casilla_id, (expected_label, expected_role) in _ANEXO_B_ACCOUNT_ROWS.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.label == expected_label
        assert tuple(casilla.section) == ("resultados", "datos_adicionales_anexo_b", _ANEXO_B_ACCOUNT_SECTION)
        assert casilla.semantic_role == expected_role
        assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_baleares_birth_roles_are_spanish_and_label_grounded() -> None:
    for filing_year in (2023, 2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in _ANEXO_B_BALEARES_NACIMIENTO_ROWS
        }

        assert set(casillas_by_id) == set(_ANEXO_B_BALEARES_NACIMIENTO_ROWS), filing_year
        for casilla_id, (expected_label, expected_role) in _ANEXO_B_BALEARES_NACIMIENTO_ROWS.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label
            assert tuple(casilla.section) == (
                "resultados",
                "datos_adicionales_anexo_b",
                _ANEXO_B_BALEARES_NACIMIENTO_SECTION,
            )
            assert casilla.semantic_role == expected_role
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_total_cantidades_invertidas_role_is_not_service_fee() -> None:
    for filing_year, expected_count in ((2024, 3), (2025, 3)):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_contributor_key_role_is_spanish_code() -> None:
    for filing_year, expected_count in ((2024, 3), (2025, 4)):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_investment_amount_role_is_deduction_investment_amount() -> None:
    for filing_year, expected_count in (
        (2020, 10),
        (2021, 10),
        (2022, 10),
        (2023, 10),
        (2024, 16),
        (2025, 22),
    ):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_INVERSION_IMPORTE_LABEL
            and casilla.semantic_role == _ANEXO_B_INVERSION_IMPORTE_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_INVERSION_TOTAL_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_INVERSION_IMPORTE_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_investment_total_role_is_total_by_deduction_type() -> None:
    for filing_year, expected_count in (
        (2020, 5),
        (2021, 5),
        (2022, 5),
        (2023, 5),
        (2024, 8),
        (2025, 10),
    ):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label.startswith(_ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX)
            and casilla.semantic_role == _ANEXO_B_INVERSION_TOTAL_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_INVERSION_TOTAL_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_INVERSION_TOTAL_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_insurance_premium_role_is_credit_insurance() -> None:
    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_PRIMA_SEGURO_LABEL
            and casilla.semantic_role == _ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] == _ANEXO_B_EPS_SECTION
        ]

        assert len(checked) == 3, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_insurance_premium_total_role_is_spanish_eps_total() -> None:
    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == _ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] == _ANEXO_B_EPS_SECTION
        ]

        assert len(checked) == 1, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_total_satisfecho_role_is_not_rental_specific() -> None:
    for filing_year, expected_count in (
        (2020, 2),
        (2021, 2),
        (2022, 2),
        (2023, 2),
        (2024, 2),
        (2025, 3),
    ):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label.startswith("Importe total satisfecho")
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_TOTAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_TOTAL_SATISFECHO_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_cantidades_deducibles_role_is_amount_not_boolean() -> None:
    for filing_year, expected_count in (
        (2020, 2),
        (2021, 2),
        (2022, 2),
        (2023, 2),
        (2024, 2),
        (2025, 3),
    ):
        revision = _modelo_100_snapshot(filing_year).revision
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == _ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in _ANEXO_B_TOTAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == _ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
