"""Modelo 100 Murcia semantic-role registry tests."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id

from .authored_edition_support import newest_authored_edition, newest_authored_editions
from .modelo_100_registry_support import (
    AUTONOMIC_DEDUCTION_ART_77_REF,
    modelo_100_revision,
    modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The newest Modelo 100 edition the registry authors; its printed labels name its own exercise and the one before it.
_REVIEWED_EDITION = newest_authored_edition("100")

_MURCIA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "murcia_res")
_MURCIA_RECURSOS_ENERGETICOS_ROLE = "irpf_deduccion_murcia_recursos_energeticos_renovables"
_MURCIA_RECURSOS_ENERGETICOS_GENERADO_ROLE = "irpf_deduccion_murcia_recursos_energeticos_renovables_generado"
_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_ROLE = "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente"
_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_1_ROLE = "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_1"
_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_EJERCICIO_ANTERIOR_ROLE = (
    "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_ejercicio_anterior"
)
_MURCIA_VEHICULO_IMPORTE_ROLE = "irpf_deduccion_murcia_vehiculo_importe"
_MURCIA_VEHICULO_GENERADO_ROLE = "irpf_deduccion_murcia_vehiculo_generado"
_MURCIA_VEHICULO_PENDIENTE_ROLE = "irpf_deduccion_murcia_vehiculo_pendiente"
_MURCIA_INFRAESTRUCTURAS_ROLE = "irpf_deduccion_murcia_infraestructuras_recarga"
_MURCIA_INFRAESTRUCTURAS_GENERADO_ROLE = "irpf_deduccion_murcia_infraestructuras_generado"
_MURCIA_INFRAESTRUCTURAS_PENDIENTE_ROLE = "irpf_deduccion_murcia_infraestructuras_pendiente"
_LEGACY_MURCIA_GENERATED_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_murcia_importe_generado",
        "irpf_deduccion_murcia_generado_pendiente_aplicacion",
        "irpf_deduccion_murcia_infraestructuras_2024_pendiente",
        "irpf_deduccion_murcia_infraestructuras_2025_pendiente",
        "irpf_deduccion_murcia_generado_2025_pendiente_2",
        "irpf_deduccion_murcia_generado_2024_pendiente",
    }
)


def _casilla(number: int) -> CasillaId:
    """Return the id of the casilla the official design numbers ``number``; a box number, not a year."""
    return validated_casilla_id(f"{number:04d}", surface="casilla.id")


_GENERADO_MU4_CASILLA, _PENDIENTE_MU4_CASILLA = _casilla(2038), _casilla(2039)
_MU4_EDITIONS = newest_authored_editions("100", 2)
_MU4_CASILLAS = {"1055", _GENERADO_MU4_CASILLA, _PENDIENTE_MU4_CASILLA}
_EXPECTED_MURCIA_MU4_LABELS = {
    filing_year: {
        "1055": "Por inversión en instalaciones de recursos energéticos renovables",
        _GENERADO_MU4_CASILLA: f"Importe generado en {filing_year}",
        _PENDIENTE_MU4_CASILLA: f"Importe generado en {filing_year} pendiente de aplicación",
    }
    for filing_year in _MU4_EDITIONS
}


@pytest.mark.parametrize("filing_year", _MU4_EDITIONS)
def test_modelo_100_murcia_mu4_recursos_energeticos_roles_are_family_specific(filing_year: int) -> None:
    revision = modelo_100_revision(filing_year)
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in _MU4_CASILLAS}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MURCIA_GENERATED_PENDING_ROLES
    ]
    expected_labels = _EXPECTED_MURCIA_MU4_LABELS[filing_year]

    assert not legacy_roles
    assert set(casillas_by_id) == _MU4_CASILLAS

    parent = casillas_by_id["1055"]
    assert parent.label.startswith(expected_labels["1055"])
    assert tuple(parent.section) == _MURCIA_DEDUCTION_SECTION
    assert parent.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id[_GENERADO_MU4_CASILLA]
    assert generated.label == expected_labels[_GENERADO_MU4_CASILLA]
    assert tuple(generated.section) == _MURCIA_DEDUCTION_SECTION
    assert generated.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_GENERADO_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id[_PENDIENTE_MU4_CASILLA]
    assert pending.label == expected_labels[_PENDIENTE_MU4_CASILLA]
    assert tuple(pending.section) == _MURCIA_DEDUCTION_SECTION
    assert pending.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs


def _assert_murcia_deduction_casilla(casilla, *, label: str, role: str) -> None:
    assert casilla.label == label
    assert tuple(casilla.section) == _MURCIA_DEDUCTION_SECTION
    assert casilla.semantic_role == role
    assert AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


def test_modelo_100_murcia_generated_pending_rows_follow_official_mu_families() -> None:
    revision = modelo_100_snapshot(_REVIEWED_EDITION).revision
    expected_ids = {"2155", "2156", "2157", "2162", "2163", "2164", "2165", "2166"}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MURCIA_GENERATED_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == expected_ids

    previous_pending_label = f"Importe generado en {_REVIEWED_EDITION - 1} pendiente de aplicación"
    generated_label = f"Importe generado en {_REVIEWED_EDITION}"
    pending_label = f"Importe generado en {_REVIEWED_EDITION} pendiente de aplicación"
    _assert_murcia_deduction_casilla(
        casillas_by_id["2163"], label=previous_pending_label, role=_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_1_ROLE
    )
    _assert_murcia_deduction_casilla(
        casillas_by_id["2166"],
        label=previous_pending_label,
        role=_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_EJERCICIO_ANTERIOR_ROLE,
    )
    _assert_murcia_deduction_casilla(
        casillas_by_id["2155"], label="Importe de la deducción", role=_MURCIA_VEHICULO_IMPORTE_ROLE
    )
    _assert_murcia_deduction_casilla(casillas_by_id["2156"], label=generated_label, role=_MURCIA_VEHICULO_GENERADO_ROLE)
    _assert_murcia_deduction_casilla(casillas_by_id["2164"], label=pending_label, role=_MURCIA_VEHICULO_PENDIENTE_ROLE)
    _assert_murcia_deduction_casilla(
        casillas_by_id["2157"],
        label="Por gastos en la instalación de infraestructuras de recarga de vehículos eléctricos",
        role=_MURCIA_INFRAESTRUCTURAS_ROLE,
    )
    _assert_murcia_deduction_casilla(
        casillas_by_id["2162"], label=generated_label, role=_MURCIA_INFRAESTRUCTURAS_GENERADO_ROLE
    )
    _assert_murcia_deduction_casilla(
        casillas_by_id["2165"], label=pending_label, role=_MURCIA_INFRAESTRUCTURAS_PENDIENTE_ROLE
    )
