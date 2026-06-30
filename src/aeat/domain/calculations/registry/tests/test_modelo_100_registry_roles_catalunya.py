"""Modelo 100 Catalunya semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATALUNYA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "catalunya_res")
_CATALUNYA_COOPERATIVAS_AGRARIAS_ROLE = "irpf_deduccion_catalunya_cooperativas_agrarias"
_CATALUNYA_COOPERATIVAS_AGRARIAS_GENERADO_ROLE = (
    "irpf_deduccion_catalunya_cooperativas_agrarias_generado"
)
_CATALUNYA_COOPERATIVAS_AGRARIAS_PENDIENTE_ROLE = (
    "irpf_deduccion_catalunya_cooperativas_agrarias_pendiente"
)
_LEGACY_CATALUNYA_COOPERATIVAS_CHILD_ROLES = frozenset(
    {
        "irpf_deduccion_catalunya_generado_2025",
        "irpf_deduccion_catalunya_generado_2025_pendiente",
        "irpf_deduccion_catalunya_pendiente_ejercicio_anterior",
    }
)


def test_modelo_100_catalunya_2025_cooperativas_agrarias_roles_are_family_specific() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"2003", "2004", "2005"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_CATALUNYA_COOPERATIVAS_CHILD_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"2003", "2004", "2005"}

    parent = casillas_by_id["2003"]
    assert parent.label.startswith("Por inversión en sociedades cooperativas agrarias y de vivienda")
    assert tuple(parent.section) == _CATALUNYA_DEDUCTION_SECTION
    assert parent.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["2004"]
    assert generated.label == "Importe generado en 2025"
    assert tuple(generated.section) == _CATALUNYA_DEDUCTION_SECTION
    assert generated.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["2005"]
    assert pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(pending.section) == _CATALUNYA_DEDUCTION_SECTION
    assert pending.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
