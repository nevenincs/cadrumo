"""Modelo 100 Anexo B semantic-role registry tests."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import single_exercise_editions

from .modelo_100_registry_support import (
    ANEXO_B_AAV_AMOUNT_ROWS,
    ANEXO_B_AAV_SECTION,
    ANEXO_B_ACCOUNT_ROWS,
    ANEXO_B_ACCOUNT_SECTION,
    ANEXO_B_BALEARES_NACIMIENTO_ROWS,
    ANEXO_B_BALEARES_NACIMIENTO_SECTION,
    ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL,
    ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE,
    ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE,
    ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL,
    ANEXO_B_EPS_SECTION,
    ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL,
    ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE,
    ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS,
    ANEXO_B_IMPORTE_SATISFECHO_LABEL,
    ANEXO_B_IMPORTE_SATISFECHO_ROLE,
    ANEXO_B_IMPORTE_SATISFECHO_SECTIONS,
    ANEXO_B_INVERSION_IMPORTE_LABEL,
    ANEXO_B_INVERSION_IMPORTE_ROLE,
    ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX,
    ANEXO_B_INVERSION_TOTAL_ROLE,
    ANEXO_B_INVERSION_TOTAL_SECTIONS,
    ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE,
    ANEXO_B_OTROS_GASTOS_SECTION,
    ANEXO_B_OTROS_GASTOS_VARIABLE,
    ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE,
    ANEXO_B_PRIMA_SEGURO_LABEL,
    ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE,
    ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL,
    ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE,
    ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS,
    ANEXO_B_TOTAL_SATISFECHO_ROLE,
    ANEXO_B_TOTAL_SATISFECHO_SECTIONS,
    AUTONOMIC_DEDUCTION_ART_77_REF,
    modelo_100_revision,
    modelo_100_snapshot,
    official_dictionary_years,
    official_row,
    same_printed_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Every exercise the registry authors a Modelo 100 edition for, oldest first.
_ALL_EXERCISES = single_exercise_editions("100")


def test_modelo_100_anexo_b_importe_satisfecho_role_is_not_rental_specific() -> None:
    for filing_year, expected_count in (
        (2020, 5),
        (2021, 5),
        (2022, 5),
        (2023, 5),
        (2024, 5),
        (2025, 7),
    ):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_IMPORTE_SATISFECHO_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_IMPORTE_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_IMPORTE_SATISFECHO_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_importe_anual_satisfecho_role_is_not_service_fee() -> None:
    for filing_year, expected_count in ((2024, 24), (2025, 32)):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_IMPORTE_ANUAL_SATISFECHO_LABEL
            and casilla.semantic_role == ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_IMPORTE_ANUAL_SATISFECHO_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_other_service_amount_role_is_otros_gastos_importe_anual() -> None:
    checked_years = 0
    for filing_year in official_dictionary_years():
        printed = official_row(filing_year, ANEXO_B_OTROS_GASTOS_VARIABLE)
        if printed is None:
            continue
        checked_years += 1
        revision = modelo_100_revision(filing_year)
        casilla = next(casilla for casilla in revision.casillas if casilla.id == printed.box)

        assert same_printed_label(casilla.label, printed.label)
        assert tuple(casilla.section) == printed.section
        assert casilla.section[-1] == ANEXO_B_OTROS_GASTOS_SECTION
        assert casilla.semantic_role == ANEXO_B_OTROS_GASTOS_IMPORTE_ANUAL_ROLE
        assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs

    assert checked_years


def test_modelo_100_anexo_b_aav_amount_roles_are_grounded_in_official_labels() -> None:
    revision = modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in ANEXO_B_AAV_AMOUNT_ROWS}

    assert set(casillas_by_id) == set(ANEXO_B_AAV_AMOUNT_ROWS)
    for casilla_id, (expected_label, expected_role) in ANEXO_B_AAV_AMOUNT_ROWS.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.label == expected_label
        assert tuple(casilla.section) == ("resultados", "datos_adicionales_anexo_b", ANEXO_B_AAV_SECTION)
        assert casilla.semantic_role == expected_role
        assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_account_holder_role_is_cm_vivienda_habitual() -> None:
    revision = modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in ANEXO_B_ACCOUNT_ROWS}

    assert set(casillas_by_id) == set(ANEXO_B_ACCOUNT_ROWS)
    for casilla_id, (expected_label, expected_role) in ANEXO_B_ACCOUNT_ROWS.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.label == expected_label
        assert tuple(casilla.section) == ("resultados", "datos_adicionales_anexo_b", ANEXO_B_ACCOUNT_SECTION)
        assert casilla.semantic_role == expected_role
        assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_baleares_birth_roles_are_spanish_and_label_grounded() -> None:
    for filing_year in _ALL_EXERCISES[-3:]:
        revision = modelo_100_revision(filing_year)
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in ANEXO_B_BALEARES_NACIMIENTO_ROWS
        }

        assert set(casillas_by_id) == set(ANEXO_B_BALEARES_NACIMIENTO_ROWS), filing_year
        for casilla_id, (expected_label, expected_role) in ANEXO_B_BALEARES_NACIMIENTO_ROWS.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label
            assert tuple(casilla.section) == (
                "resultados",
                "datos_adicionales_anexo_b",
                ANEXO_B_BALEARES_NACIMIENTO_SECTION,
            )
            assert casilla.semantic_role == expected_role
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_total_cantidades_invertidas_role_is_not_service_fee() -> None:
    for filing_year, expected_count in ((2024, 3), (2025, 3)):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_SERVICE_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_TOTAL_CANTIDADES_INVERTIDAS_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_contributor_key_role_is_spanish_code() -> None:
    for filing_year, expected_count in ((2024, 3), (2025, 4)):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_CONTRIBUYENTE_DERECHO_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_IMPORTE_ANUAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_CONTRIBUYENTE_DERECHO_CLAVE_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_investment_amount_role_is_deduction_investment_amount() -> None:
    for filing_year, expected_count in (
        (2020, 10),
        (2021, 10),
        (2022, 10),
        (2023, 10),
        (2024, 16),
        (2025, 22),
    ):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_INVERSION_IMPORTE_LABEL
            and casilla.semantic_role == ANEXO_B_INVERSION_IMPORTE_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_INVERSION_TOTAL_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_INVERSION_IMPORTE_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_investment_total_role_is_total_by_deduction_type() -> None:
    for filing_year, expected_count in (
        (2020, 5),
        (2021, 5),
        (2022, 5),
        (2023, 5),
        (2024, 8),
        (2025, 10),
    ):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label.startswith(ANEXO_B_INVERSION_TOTAL_LABEL_PREFIX)
            and casilla.semantic_role == ANEXO_B_INVERSION_TOTAL_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_INVERSION_TOTAL_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_INVERSION_TOTAL_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_insurance_premium_role_is_credit_insurance() -> None:
    for filing_year in _ALL_EXERCISES:
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_PRIMA_SEGURO_LABEL
            and casilla.semantic_role == ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] == ANEXO_B_EPS_SECTION
        ]

        assert len(checked) == 3, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_PRIMA_SEGURO_CREDITO_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_insurance_premium_total_role_is_spanish_eps_total() -> None:
    for filing_year in _ALL_EXERCISES:
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] == ANEXO_B_EPS_SECTION
        ]

        assert len(checked) == 1, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_PRIMAS_SEGURO_TOTAL_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_total_satisfecho_role_is_not_rental_specific() -> None:
    for filing_year, expected_count in (
        (2020, 2),
        (2021, 2),
        (2022, 2),
        (2023, 2),
        (2024, 2),
        (2025, 3),
    ):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label.startswith("Importe total satisfecho")
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_TOTAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_TOTAL_SATISFECHO_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_anexo_b_cantidades_deducibles_role_is_amount_not_boolean() -> None:
    for filing_year, expected_count in (
        (2020, 2),
        (2021, 2),
        (2022, 2),
        (2023, 2),
        (2024, 2),
        (2025, 3),
    ):
        revision = modelo_100_revision(filing_year)
        checked = [
            casilla
            for casilla in revision.casillas
            if casilla.label == ANEXO_B_CANTIDADES_DEDUCIBLES_LABEL
            and len(casilla.section) >= 3
            and tuple(casilla.section[:2]) == ("resultados", "datos_adicionales_anexo_b")
            and casilla.section[2] in ANEXO_B_TOTAL_SATISFECHO_SECTIONS
        ]

        assert len(checked) == expected_count, filing_year
        for casilla in checked:
            assert casilla.semantic_role == ANEXO_B_CANTIDADES_DEDUCIBLES_ROLE
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
