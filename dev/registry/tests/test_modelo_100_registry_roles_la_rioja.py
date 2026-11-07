"""Modelo 100 La Rioja semantic-role registry tests."""

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

_LA_RIOJA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "la_rioja_res")
_LA_RIOJA_FIJACION_POBLACION_RURAL_ROLE = "irpf_deduccion_la_rioja_fijacion_poblacion_rural"
_LA_RIOJA_FIJACION_POBLACION_RURAL_GENERADO_ROLE = "irpf_deduccion_la_rioja_fijacion_poblacion_rural_generado"
_LA_RIOJA_FIJACION_POBLACION_RURAL_PENDIENTE_ROLE = "irpf_deduccion_la_rioja_fijacion_poblacion_rural_pendiente"
_LEGACY_LA_RIOJA_GENERADO_2025_ROLES = frozenset(
    {
        "irpf_deduccion_la_rioja_generado_2025",
        "irpf_deduccion_la_rioja_generado_2025_pendiente",
    }
)


def _casilla(number: int) -> CasillaId:
    """Return the id of the casilla the official design numbers ``number``; a box number, not a year."""
    return validated_casilla_id(f"{number:04d}", surface="casilla.id")


_PARENT_CASILLA, _GENERADO_CASILLA, _PENDIENTE_CASILLA = _casilla(2057), _casilla(2058), _casilla(2059)
_FIJACION_CASILLAS = {_PARENT_CASILLA, _GENERADO_CASILLA, _PENDIENTE_CASILLA}


def test_modelo_100_la_rioja_fijacion_poblacion_rural_roles_are_family_specific() -> None:
    revision = modelo_100_snapshot(_REVIEWED_EDITION).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _FIJACION_CASILLAS}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_LA_RIOJA_GENERADO_2025_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == _FIJACION_CASILLAS

    parent = casillas_by_id[_PARENT_CASILLA]
    assert parent.label == "Para fomentar la fijación de población ocupada en el medio rural"
    assert tuple(parent.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert parent.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id[_GENERADO_CASILLA]
    assert generated.label == f"Importe generado en {_REVIEWED_EDITION}"
    assert tuple(generated.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert generated.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_GENERADO_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id[_PENDIENTE_CASILLA]
    assert pending.label == f"Importe generado en {_REVIEWED_EDITION} pendiente de aplicación"
    assert tuple(pending.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert pending.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_PENDIENTE_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
