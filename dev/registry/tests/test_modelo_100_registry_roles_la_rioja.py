"""Modelo 100 La Rioja semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _modelo_100_snapshot,
)
from .authored_edition_support import newest_authored_edition

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


def test_modelo_100_la_rioja_fijacion_poblacion_rural_roles_are_family_specific() -> None:
    revision = _modelo_100_snapshot(_REVIEWED_EDITION).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"2057", "2058", "2059"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_LA_RIOJA_GENERADO_2025_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == {"2057", "2058", "2059"}

    parent = casillas_by_id["2057"]
    assert parent.label == "Para fomentar la fijación de población ocupada en el medio rural"
    assert tuple(parent.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert parent.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["2058"]
    assert generated.label == f"Importe generado en {_REVIEWED_EDITION}"
    assert tuple(generated.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert generated.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["2059"]
    assert pending.label == f"Importe generado en {_REVIEWED_EDITION} pendiente de aplicación"
    assert tuple(pending.section) == _LA_RIOJA_DEDUCTION_SECTION
    assert pending.semantic_role == _LA_RIOJA_FIJACION_POBLACION_RURAL_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs
