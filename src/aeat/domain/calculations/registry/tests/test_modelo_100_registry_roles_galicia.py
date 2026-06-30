"""Modelo 100 Galicia semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _GALICIA_DEDUCTION_SECTION,
    _GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GALICIA_INMUEBLE_VACIO_ADECUACION_GENERADO_ROLE = (
    "irpf_deduccion_galicia_inmueble_vacio_adecuacion_generado"
)
_GALICIA_INMUEBLE_VACIO_ADECUACION_PENDIENTE_ROLE = (
    "irpf_deduccion_galicia_inmueble_vacio_adecuacion_pendiente"
)
_GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_ROLE = "irpf_deduccion_galicia_arrendamiento_viviendas_vacias"
_GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_GENERADO_ROLE = (
    "irpf_deduccion_galicia_arrendamiento_viviendas_vacias_generado"
)
_GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_PENDIENTE_ROLE = (
    "irpf_deduccion_galicia_arrendamiento_viviendas_vacias_pendiente"
)
_LEGACY_GALICIA_2025_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_galicia_eficiencia_energetica_generado",
        "irpf_deduccion_galicia_generado_2025_pendiente",
        "irpf_deduccion_galicia_pendiente_ejercicio_anterior_2",
        "irpf_deduccion_galicia_generado_linea_2",
    }
)


def test_modelo_100_galicia_2025_inmueble_vacio_adecuacion_roles_follow_ga21_family() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0829", "0981", "1078"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_GALICIA_2025_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"0829", "0981", "1078"}

    parent = casillas_by_id["1078"]
    assert parent.label.startswith("Por gastos derivados de la adecuación de un inmueble vacío")
    assert tuple(parent.section) == _GALICIA_DEDUCTION_SECTION
    assert parent.semantic_role == _GALICIA_INMUEBLE_VACIO_ADECUACION_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["0829"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _GALICIA_DEDUCTION_SECTION
    assert generated.semantic_role == _GALICIA_INMUEBLE_VACIO_ADECUACION_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["0981"]
    assert pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(pending.section) == _GALICIA_DEDUCTION_SECTION
    assert pending.semantic_role == _GALICIA_INMUEBLE_VACIO_ADECUACION_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs


def test_modelo_100_galicia_2025_arrendamiento_viviendas_vacias_roles_follow_ga22_family() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0982", "1036", "1037"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_GALICIA_2025_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"0982", "1036", "1037"}

    parent = casillas_by_id["1036"]
    assert parent.label.startswith("Por el arrendamiento de viviendas vacías")
    assert tuple(parent.section) == _GALICIA_DEDUCTION_SECTION
    assert parent.semantic_role == _GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["1037"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _GALICIA_DEDUCTION_SECTION
    assert generated.semantic_role == _GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["0982"]
    assert pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(pending.section) == _GALICIA_DEDUCTION_SECTION
    assert pending.semantic_role == _GALICIA_ARRENDAMIENTO_VIVIENDAS_VACIAS_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
