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
_VA42_DANOS_VIVIENDA_DANA_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana"
_VA42_DANOS_VIVIENDA_DANA_GENERADO_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana_generado"
_VA42_DANOS_VIVIENDA_DANA_PENDIENTE_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente"
_VA43_APORTACIONES_FONDOS_PROPIOS_ROLE = "irpf_deduccion_c_valenciana_aportaciones_fondos_propios"
_VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado"
)
_VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente"
)
_LEGACY_VALENCIANA_AUTOCONSUMO_YEAR_ROLES = frozenset(
    {
        "irpf_deduccion_c_valenciana_autoconsumo_2025_generado",
        "irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente",
        "irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente",
    }
)
_LEGACY_VALENCIANA_VA42_VA43_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_c_valenciana_generado_ejercicio_pendiente",
        "irpf_deduccion_c_valenciana_generado_2025_pendiente_2",
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


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_modelo_100_c_valenciana_va42_va43_pending_roles_follow_official_families(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    expected_ids = {"1690", "1691", "1702", "1703", "1704", "1705"}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_VALENCIANA_VA42_VA43_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == expected_ids

    dana_parent = casillas_by_id["1702"]
    assert dana_parent.label == (
        "Por destinar cantidades a paliar los daños materiales sobre la vivienda habitual derivados del temporal"
    )
    assert tuple(dana_parent.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert dana_parent.semantic_role == _VA42_DANOS_VIVIENDA_DANA_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in dana_parent.legal_refs

    dana_generated = casillas_by_id["1703"]
    assert dana_generated.label == f"Importe generado en {filing_year}"
    assert tuple(dana_generated.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert dana_generated.semantic_role == _VA42_DANOS_VIVIENDA_DANA_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in dana_generated.legal_refs

    dana_pending = casillas_by_id["1690"]
    assert dana_pending.label == f"Importe generado en {filing_year} pendiente de aplicación"
    assert tuple(dana_pending.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert dana_pending.semantic_role == _VA42_DANOS_VIVIENDA_DANA_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in dana_pending.legal_refs

    fondos_parent = casillas_by_id["1704"]
    assert fondos_parent.label.startswith("Por aportaciones a los fondos propios de entidades que desarrollen")
    assert tuple(fondos_parent.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert fondos_parent.semantic_role == _VA43_APORTACIONES_FONDOS_PROPIOS_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in fondos_parent.legal_refs

    fondos_generated = casillas_by_id["1705"]
    assert fondos_generated.label == f"Importe generado en {filing_year}"
    assert tuple(fondos_generated.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert fondos_generated.semantic_role == _VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in fondos_generated.legal_refs

    fondos_pending = casillas_by_id["1691"]
    assert fondos_pending.label == f"Importe generado en {filing_year} pendiente de aplicación"
    assert tuple(fondos_pending.section) == _C_VALENCIANA_DEDUCTION_SECTION
    assert fondos_pending.semantic_role == _VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in fondos_pending.legal_refs
