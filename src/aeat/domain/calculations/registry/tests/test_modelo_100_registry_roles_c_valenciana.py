"""Modelo 100 Comunitat Valenciana semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _C_VALENCIANA_DEDUCTION_SECTION,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VA35_ACCIONES_PARTICIPACIONES_ROLE = "irpf_deduccion_c_valenciana_acciones_participaciones"
_VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_pendiente"
)
_VA39_AUTOCONSUMO_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_desde_2023"
_VA39_AUTOCONSUMO_GENERADO_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_generado"
_VA39_AUTOCONSUMO_PENDIENTE_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_pendiente"
_LEGACY_VALENCIANA_AUTOCONSUMO_YEAR_ROLES = frozenset(
    {
        "irpf_deduccion_c_valenciana_autoconsumo_2025_generado",
        "irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente",
        "irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente",
    }
)
_EXPECTED_VA35_PENDING_LABELS = {
    2023: "Importe generado en 2023 pendiente de aplicación",
    2024: "Importe generado en 2024 pendiente de aplicación",
    2025: "Importe generado en 2025 pendiente de aplicación",
}
_EXPECTED_VA39_PENDING_LABELS = {
    2023: "Importe generado en 2023 pendiente de aplicación",
    2024: "Importe generado en 2023 pendiente de aplicación",
    2025: "Importe generado en 2024 pendiente de aplicación",
}


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025])
def test_modelo_100_c_valenciana_autoconsumo_roles_follow_va39_family(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"1962", "1963", "1965"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_VALENCIANA_AUTOCONSUMO_YEAR_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"1962", "1963", "1965"}

    parent = casillas_by_id["1962"]
    assert "autoconsumo" in parent.label
    assert "a partir de 2023" in parent.label
    assert tuple(parent.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert parent.semantic_role == _VA39_AUTOCONSUMO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["1963"]
    assert generated.label == f"Importe generado en {filing_year}"
    assert tuple(generated.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert generated.semantic_role == _VA39_AUTOCONSUMO_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["1965"]
    assert pending.label == _EXPECTED_VA39_PENDING_LABELS[filing_year]
    assert tuple(pending.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert pending.semantic_role == _VA39_AUTOCONSUMO_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025])
def test_modelo_100_c_valenciana_1964_remains_va35_pending_not_autoconsumo(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"1183", "1964"}}

    assert set(casillas_by_id) == {"1183", "1964"}

    parent = casillas_by_id["1183"]
    assert parent.semantic_role == _VA35_ACCIONES_PARTICIPACIONES_ROLE
    assert tuple(parent.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    pending = casillas_by_id["1964"]
    assert pending.label == _EXPECTED_VA35_PENDING_LABELS[filing_year]
    assert tuple(pending.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert pending.semantic_role == _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE
    assert pending.semantic_role not in _LEGACY_VALENCIANA_AUTOCONSUMO_YEAR_ROLES
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
