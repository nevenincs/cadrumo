"""Modelo 100 Cantabria semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CANTABRIA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "cantabria_res")
_CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_ROLE = (
    "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes"
)
_CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_GENERADO_ROLE = (
    "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_generado"
)
_CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_PENDIENTE_ROLE = (
    "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_pendiente"
)
_CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_ROLE = (
    "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero"
)
_CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_GENERADO_ROLE = (
    "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_generado"
)
_CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_PENDIENTE_ROLE = (
    "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_pendiente"
)
_LEGACY_CANTABRIA_GENERATED_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_cantabria_generado_pendiente",
        "irpf_deduccion_cantabria_generado_2025",
        "irpf_deduccion_cantabria_generado_2025_pendiente",
        "irpf_deduccion_cantabria_generado_2025_pendiente_2",
    }
)


def test_modelo_100_cantabria_2025_desplazamiento_nuevos_residentes_roles_follow_cant20_family() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0773", "0776", "1715"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_CANTABRIA_GENERATED_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"0773", "0776", "1715"}

    parent = casillas_by_id["0773"]
    assert parent.label == "Para compensar los gastos de desplazamiento y permanencia de nuevos residentes en Cantabria"
    assert tuple(parent.section) == _CANTABRIA_DEDUCTION_SECTION
    assert parent.semantic_role == _CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["0776"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _CANTABRIA_DEDUCTION_SECTION
    assert generated.semantic_role == _CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["1715"]
    assert pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert pending.semantic_role == _CANTABRIA_DESPLAZAMIENTO_NUEVOS_RESIDENTES_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs


def test_modelo_100_cantabria_2025_nuevos_contribuyentes_extranjero_roles_follow_cant23_family() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"1708", "1714", "1717"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_CANTABRIA_GENERATED_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"1708", "1714", "1717"}

    parent = casillas_by_id["1708"]
    assert parent.label == (
        "Por inversiones de nuevos contribuyentes procedentes del extranjero (información adicional en el anexo B.15)"
    )
    assert tuple(parent.section) == _CANTABRIA_DEDUCTION_SECTION
    assert parent.semantic_role == _CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["1714"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _CANTABRIA_DEDUCTION_SECTION
    assert generated.semantic_role == _CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["1717"]
    assert pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert pending.semantic_role == _CANTABRIA_NUEVOS_CONTRIBUYENTES_EXTRANJERO_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
