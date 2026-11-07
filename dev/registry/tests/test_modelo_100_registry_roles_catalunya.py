"""Modelo 100 Catalunya semantic-role registry tests."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id

from .authored_edition_support import newest_authored_edition
from .modelo_100_registry_support import (
    AUTONOMIC_DEDUCTION_ART_77_REF,
    modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The newest Modelo 100 edition the registry authors; its printed labels name its own exercise and the one before it.
_REVIEWED_EDITION = newest_authored_edition("100")

_CATALUNYA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "catalunya_res")
_CATALUNYA_COOPERATIVAS_AGRARIAS_ROLE = "irpf_deduccion_catalunya_cooperativas_agrarias"
_CATALUNYA_COOPERATIVAS_AGRARIAS_GENERADO_ROLE = "irpf_deduccion_catalunya_cooperativas_agrarias_generado"
_CATALUNYA_COOPERATIVAS_AGRARIAS_PENDIENTE_ROLE = "irpf_deduccion_catalunya_cooperativas_agrarias_pendiente"
_LEGACY_CATALUNYA_COOPERATIVAS_CHILD_ROLES = frozenset(
    {
        "irpf_deduccion_catalunya_generado_2025",
        "irpf_deduccion_catalunya_generado_2025_pendiente",
        "irpf_deduccion_catalunya_pendiente_ejercicio_anterior",
    }
)


def _casilla(number: int) -> CasillaId:
    """Return the id of the casilla the official design numbers ``number``; a box number, not a year."""
    return validated_casilla_id(f"{number:04d}", surface="casilla.id")


_PARENT_CASILLA, _GENERADO_CASILLA, _PENDIENTE_CASILLA = _casilla(2003), _casilla(2004), _casilla(2005)
_COOPERATIVAS_CASILLAS = {_PARENT_CASILLA, _GENERADO_CASILLA, _PENDIENTE_CASILLA}


def test_modelo_100_catalunya_cooperativas_agrarias_roles_are_family_specific() -> None:
    revision = modelo_100_snapshot(_REVIEWED_EDITION).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _COOPERATIVAS_CASILLAS}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_CATALUNYA_COOPERATIVAS_CHILD_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == _COOPERATIVAS_CASILLAS

    parent = casillas_by_id[_PARENT_CASILLA]
    assert parent.label.startswith("Por inversión en sociedades cooperativas agrarias y de vivienda")
    assert tuple(parent.section) == _CATALUNYA_DEDUCTION_SECTION
    assert parent.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id[_GENERADO_CASILLA]
    assert generated.label == f"Importe generado en {_REVIEWED_EDITION}"
    assert tuple(generated.section) == _CATALUNYA_DEDUCTION_SECTION
    assert generated.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_GENERADO_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id[_PENDIENTE_CASILLA]
    assert pending.label == f"Importe generado en {_REVIEWED_EDITION} pendiente de aplicación"
    assert tuple(pending.section) == _CATALUNYA_DEDUCTION_SECTION
    assert pending.semantic_role == _CATALUNYA_COOPERATIVAS_AGRARIAS_PENDIENTE_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
