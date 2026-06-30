"""Modelo 100 Murcia semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MURCIA_DEDUCTION_SECTION = ("resultados", "deduccion_autonomica_res", "murcia_res")
_MURCIA_RECURSOS_ENERGETICOS_ROLE = "irpf_deduccion_murcia_recursos_energeticos_renovables"
_MURCIA_RECURSOS_ENERGETICOS_GENERADO_ROLE = (
    "irpf_deduccion_murcia_recursos_energeticos_renovables_generado"
)
_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_ROLE = (
    "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente"
)
_MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_1_ROLE = (
    "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_1"
)
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
_EXPECTED_MURCIA_MU4_LABELS = {
    2024: {
        "1055": "Por inversión en instalaciones de recursos energéticos renovables",
        "2038": "Importe generado en 2024",
        "2039": "Importe generado en 2024 pendiente de aplicación",
    },
    2025: {
        "1055": "Por inversión en instalaciones de recursos energéticos renovables",
        "2038": "Importe generado en 2025",
        "2039": "Importe generado en 2025 pendiente de aplicación",
    },
}


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_modelo_100_murcia_mu4_recursos_energeticos_roles_are_family_specific(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"1055", "2038", "2039"}}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MURCIA_GENERATED_PENDING_ROLES
    ]
    expected_labels = _EXPECTED_MURCIA_MU4_LABELS[filing_year]

    assert not legacy_roles
    assert set(casillas_by_id) == {"1055", "2038", "2039"}

    parent = casillas_by_id["1055"]
    assert parent.label.startswith(expected_labels["1055"])
    assert tuple(parent.section) == _MURCIA_DEDUCTION_SECTION
    assert parent.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["2038"]
    assert generated.label == expected_labels["2038"]
    assert tuple(generated.section) == _MURCIA_DEDUCTION_SECTION
    assert generated.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending = casillas_by_id["2039"]
    assert pending.label == expected_labels["2039"]
    assert tuple(pending.section) == _MURCIA_DEDUCTION_SECTION
    assert pending.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending.legal_refs


def test_modelo_100_murcia_2025_generated_pending_rows_follow_official_mu_families() -> None:
    revision = _modelo_100_snapshot(2025).revision
    expected_ids = {"2155", "2156", "2157", "2162", "2163", "2164", "2165", "2166"}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MURCIA_GENERATED_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == expected_ids

    mu4_previous = casillas_by_id["2163"]
    assert mu4_previous.label == "Importe generado en 2024 pendiente de aplicación"
    assert tuple(mu4_previous.section) == _MURCIA_DEDUCTION_SECTION
    assert mu4_previous.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_1_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in mu4_previous.legal_refs

    mu4_previous_extra = casillas_by_id["2166"]
    assert mu4_previous_extra.label == "Importe generado en 2024 pendiente de aplicación"
    assert tuple(mu4_previous_extra.section) == _MURCIA_DEDUCTION_SECTION
    assert mu4_previous_extra.semantic_role == _MURCIA_RECURSOS_ENERGETICOS_PENDIENTE_EJERCICIO_ANTERIOR_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in mu4_previous_extra.legal_refs

    vehicle_amount = casillas_by_id["2155"]
    assert vehicle_amount.label == "Importe de la deducción"
    assert tuple(vehicle_amount.section) == _MURCIA_DEDUCTION_SECTION
    assert vehicle_amount.semantic_role == _MURCIA_VEHICULO_IMPORTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in vehicle_amount.legal_refs

    vehicle_generated = casillas_by_id["2156"]
    assert vehicle_generated.label == "Importe generado en 2025"
    assert tuple(vehicle_generated.section) == _MURCIA_DEDUCTION_SECTION
    assert vehicle_generated.semantic_role == _MURCIA_VEHICULO_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in vehicle_generated.legal_refs

    vehicle_pending = casillas_by_id["2164"]
    assert vehicle_pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(vehicle_pending.section) == _MURCIA_DEDUCTION_SECTION
    assert vehicle_pending.semantic_role == _MURCIA_VEHICULO_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in vehicle_pending.legal_refs

    infrastructure = casillas_by_id["2157"]
    assert infrastructure.label == "Por gastos en la instalación de infraestructuras de recarga de vehículos eléctricos"
    assert tuple(infrastructure.section) == _MURCIA_DEDUCTION_SECTION
    assert infrastructure.semantic_role == _MURCIA_INFRAESTRUCTURAS_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in infrastructure.legal_refs

    infrastructure_generated = casillas_by_id["2162"]
    assert infrastructure_generated.label == "Importe generado en 2025"
    assert tuple(infrastructure_generated.section) == _MURCIA_DEDUCTION_SECTION
    assert infrastructure_generated.semantic_role == _MURCIA_INFRAESTRUCTURAS_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in infrastructure_generated.legal_refs

    infrastructure_pending = casillas_by_id["2165"]
    assert infrastructure_pending.label == "Importe generado en 2025 pendiente de aplicación"
    assert tuple(infrastructure_pending.section) == _MURCIA_DEDUCTION_SECTION
    assert infrastructure_pending.semantic_role == _MURCIA_INFRAESTRUCTURAS_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in infrastructure_pending.legal_refs
