"""Modelo 100 Madrid semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _MADRID_DEDUCTION_SECTION,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MADRID_NUEVOS_CONTRIBUYENTES_ROLE = "irpf_deduccion_madrid_nuevos_contribuyentes_extranjero"
_MADRID_NUEVOS_CONTRIBUYENTES_GENERADO_ROLE = "irpf_deduccion_madrid_nuevos_contribuyentes_generado"
_MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_ROLE = "irpf_deduccion_madrid_nuevos_contribuyentes_pendiente"
_MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_1_ROLE = "irpf_deduccion_madrid_nuevos_contribuyentes_pendiente_1"
_MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_EJERCICIO_ANTERIOR_ROLE = (
    "irpf_deduccion_madrid_nuevos_contribuyentes_pendiente_ejercicio_anterior"
)
_LEGACY_MADRID_M26_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_madrid_generado_pendiente_aplicacion",
        "irpf_deduccion_madrid_generado_2024_pendiente_2",
    }
)


def test_modelo_100_madrid_2025_m26_nuevos_contribuyentes_pending_roles_follow_official_family() -> None:
    revision = _modelo_100_snapshot(2025).revision
    expected_ids = {"2022", "2023", "2030", "2031", "2032"}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MADRID_M26_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == expected_ids

    previous_pending_1 = casillas_by_id["2022"]
    assert previous_pending_1.label == "Importe generado en 2024 pendiente de aplicación"
    assert tuple(previous_pending_1.section) == _MADRID_DEDUCTION_SECTION
    assert previous_pending_1.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_1_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending_1.legal_refs

    previous_pending = casillas_by_id["2023"]
    assert previous_pending.label == "Importe generado en 2024 pendiente de aplicación"
    assert tuple(previous_pending.section) == _MADRID_DEDUCTION_SECTION
    assert previous_pending.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_EJERCICIO_ANTERIOR_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending.legal_refs

    parent = casillas_by_id["2030"]
    assert parent.label == "Por inversiones de nuevos contribuyentes procedentes del extranjero"
    assert tuple(parent.section) == _MADRID_DEDUCTION_SECTION
    assert parent.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["2031"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _MADRID_DEDUCTION_SECTION
    assert generated.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    current_pending = casillas_by_id["2032"]
    assert current_pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(current_pending.section) == _MADRID_DEDUCTION_SECTION
    assert current_pending.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in current_pending.legal_refs
