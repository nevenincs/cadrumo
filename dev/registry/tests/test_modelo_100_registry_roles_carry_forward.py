"""Modelo 100 carry-forward semantic-role registry tests."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .modelo_100_registry_support import (
    ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE,
    ANEXO_B_INST_AUTO_SECTION,
    AUTONOMIC_DEDUCTION_ART_77_REF,
    LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES,
    LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES,
    LEGACY_MADRID_REUSED_ID_ROLES,
    MADRID_DEDUCTION_SECTION,
    carry_forward_pending_outliers,
    carry_forward_remaining_inst_auto_rows,
    madrid_reused_id_deduction_rows,
    madrid_vivienda_acquisition_detail_rows,
    modelo_100_revision,
    official_dictionary_years,
    same_printed_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_carry_forward_pending_outliers_are_regional_deductions() -> None:
    checked_years = 0
    for filing_year in official_dictionary_years():
        revision = modelo_100_revision(filing_year)
        expected_rows = carry_forward_pending_outliers(filing_year)
        checked_years += bool(expected_rows)
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id
            for casilla in casillas_by_id.values()
            if casilla.semantic_role in LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, (expected_label, expected_section, expected_role) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert same_printed_label(casilla.label, expected_label), (filing_year, casilla_id)
            assert tuple(casilla.section) == expected_section, (filing_year, casilla_id)
            assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)

    assert checked_years


def _assert_madrid_deduction_rows(
    filing_year: int,
    casillas_by_id: dict[CasillaId, CasillaDefinition],
    expected_rows: dict[str, tuple[str, str]],
) -> None:
    for casilla_id, (expected_label, expected_role) in expected_rows.items():
        casilla = casillas_by_id[casilla_id]
        assert same_printed_label(casilla.label, expected_label), (filing_year, casilla_id)
        assert tuple(casilla.section) == MADRID_DEDUCTION_SECTION, (filing_year, casilla_id)
        assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
        assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)


def test_modelo_100_madrid_reused_ids_are_regional_deductions() -> None:
    checked_years = 0
    for filing_year in official_dictionary_years():
        revision = modelo_100_revision(filing_year)
        expected_rows = madrid_reused_id_deduction_rows(filing_year)
        checked_years += bool(expected_rows)
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id for casilla in casillas_by_id.values() if casilla.semantic_role in LEGACY_MADRID_REUSED_ID_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        _assert_madrid_deduction_rows(filing_year, casillas_by_id, expected_rows)

    assert checked_years


def test_modelo_100_madrid_vivienda_acquisition_detail_roles_follow_current_deduction() -> None:
    checked_years = 0
    for filing_year in official_dictionary_years():
        revision = modelo_100_revision(filing_year)
        expected_rows = madrid_vivienda_acquisition_detail_rows(filing_year)
        checked_years += bool(expected_rows)
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}

        assert set(casillas_by_id) == set(expected_rows), filing_year
        _assert_madrid_deduction_rows(filing_year, casillas_by_id, expected_rows)

    assert checked_years


def test_modelo_100_carry_forward_remaining_inst_auto_rows_use_inst_auto_role() -> None:
    checked_years = 0
    for filing_year in official_dictionary_years():
        revision = modelo_100_revision(filing_year)
        expected_rows = carry_forward_remaining_inst_auto_rows(filing_year)
        checked_years += bool(expected_rows)
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id
            for casilla in casillas_by_id.values()
            if casilla.semantic_role in LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, expected_label in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert same_printed_label(casilla.label, expected_label), (filing_year, casilla_id)
            assert tuple(casilla.section) == ANEXO_B_INST_AUTO_SECTION, (filing_year, casilla_id)
            assert casilla.semantic_role == ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE, (
                filing_year,
                casilla_id,
            )
            assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)

    assert checked_years
