"""Modelo 100 carry-forward semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE,
    _ANEXO_B_INST_AUTO_SECTION,
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _CARRY_FORWARD_PENDING_OUTLIERS,
    _CARRY_FORWARD_REMAINING_INST_AUTO_ROWS,
    _LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES,
    _LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES,
    _LEGACY_MADRID_REUSED_ID_ROLES,
    _MADRID_DEDUCTION_SECTION,
    _MADRID_REUSED_ID_DEDUCTION_ROWS,
    _MADRID_VIVIENDA_ACQUISITION_DETAIL_ROWS,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_carry_forward_pending_outliers_are_regional_deductions() -> None:
    for filing_year in (2023, 2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        expected_rows = _CARRY_FORWARD_PENDING_OUTLIERS[filing_year]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id
            for casilla in casillas_by_id.values()
            if casilla.semantic_role in _LEGACY_CARRY_FORWARD_PENDING_OUTLIER_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, (expected_label, expected_section, expected_role) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label, (filing_year, casilla_id)
            assert tuple(casilla.section) == expected_section, (filing_year, casilla_id)
            assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)


def test_modelo_100_madrid_reused_ids_are_regional_deductions() -> None:
    for filing_year in (2023, 2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        expected_rows = _MADRID_REUSED_ID_DEDUCTION_ROWS[filing_year]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id for casilla in casillas_by_id.values() if casilla.semantic_role in _LEGACY_MADRID_REUSED_ID_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, (expected_label, expected_role) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label, (filing_year, casilla_id)
            assert tuple(casilla.section) == _MADRID_DEDUCTION_SECTION, (filing_year, casilla_id)
            assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)


def test_modelo_100_madrid_vivienda_acquisition_detail_roles_follow_current_deduction() -> None:
    for filing_year in (2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        expected_rows = _MADRID_VIVIENDA_ACQUISITION_DETAIL_ROWS[filing_year]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}

        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, (expected_label, expected_role) in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label, (filing_year, casilla_id)
            assert tuple(casilla.section) == _MADRID_DEDUCTION_SECTION, (filing_year, casilla_id)
            assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)


def test_modelo_100_carry_forward_remaining_inst_auto_rows_use_inst_auto_role() -> None:
    for filing_year in (2021, 2022, 2023, 2024, 2025):
        revision = _modelo_100_snapshot(filing_year).revision
        expected_rows = _CARRY_FORWARD_REMAINING_INST_AUTO_ROWS[filing_year]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
        legacy_rows = [
            casilla.id
            for casilla in casillas_by_id.values()
            if casilla.semantic_role in _LEGACY_CARRY_FORWARD_REMAINING_SPLIT_ROLES
        ]

        assert not legacy_rows, filing_year
        assert set(casillas_by_id) == set(expected_rows), filing_year
        for casilla_id, expected_label in expected_rows.items():
            casilla = casillas_by_id[casilla_id]
            assert casilla.label == expected_label, (filing_year, casilla_id)
            assert tuple(casilla.section) == _ANEXO_B_INST_AUTO_SECTION, (filing_year, casilla_id)
            assert casilla.semantic_role == _ANEXO_B_INST_AUTO_IMPORTE_PENDIENTE_ANTERIOR_ROLE, (
                filing_year,
                casilla_id,
            )
            assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs, (filing_year, casilla_id)
