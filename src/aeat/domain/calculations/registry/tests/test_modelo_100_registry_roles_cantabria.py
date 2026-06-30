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
_CANTABRIA_OBRAS_MEJORA_ROLE = "irpf_deduccion_cantabria_obras_mejora"
_CANTABRIA_OBRAS_MEJORA_PENDIENTE_EJERCICIOS_ANTERIORES_ROLE = (
    "irpf_deduccion_cantabria_obras_mejora_pendiente_ejercicios_anteriores"
)
_CANTABRIA_OBRAS_MEJORA_IMPORTE_ROLE = "irpf_deduccion_cantabria_obras_mejora_importe"
_CANTABRIA_OBRAS_MEJORA_GENERADO_ROLE = "irpf_deduccion_cantabria_obras_mejora_generado"
_CANTABRIA_OBRAS_MEJORA_GENERADO_EJERCICIO_PENDIENTE_ROLE = (
    "irpf_deduccion_cantabria_obras_mejora_generado_ejercicio_pendiente"
)
_CANTABRIA_OBRAS_MEJORA_PENDIENTE_1_ROLE = "irpf_deduccion_cantabria_obras_mejora_pendiente_1"
_CANTABRIA_OBRAS_MEJORA_PENDIENTE_2_ROLE = "irpf_deduccion_cantabria_obras_mejora_pendiente_2"
_CANTABRIA_OBRAS_MEJORA_PENDIENTE_EJERCICIO_ANTERIOR_ROLE = (
    "irpf_deduccion_cantabria_obras_mejora_pendiente_ejercicio_anterior"
)
_LEGACY_CANTABRIA_GENERATED_PENDING_ROLES = frozenset(
    {
        "irpf_deduccion_cantabria_generado_pendiente",
        "irpf_deduccion_cantabria_generado_2025",
        "irpf_deduccion_cantabria_generado_2025_pendiente",
        "irpf_deduccion_cantabria_generado_2025_pendiente_2",
    }
)
_LEGACY_CANTABRIA_OBRAS_MEJORA_ROLES = frozenset(
    {
        "irpf_deduccion_cantabria_importe",
        "irpf_deduccion_cantabria_generado_ejercicio_pendiente",
        "irpf_deduccion_cantabria_generado_2023_pendiente",
        "irpf_deduccion_cantabria_pendiente_aplicacion",
        "irpf_deduccion_cantabria_ayuda_domestica_pendiente_ejercicio_anterior",
    }
)
_EXPECTED_CANTABRIA_OBRAS_MEJORA_HISTORICAL_LABELS = {
    2020: "Por obras de mejora: importes generados en 2017 y/o 2018 pendientes de aplicación",
    2021: "Por obras de mejora en viviendas: importes generados en 2019 y/o 2020 pendientes de aplicación",
    2022: "Por obras de mejora en viviendas: importes generados en 2020 y/o 2021 pendientes de aplicación",
    2023: "Por obras de mejora en viviendas: importes generados en 2021 y/o 2022 pendientes de aplicación",
}
_EXPECTED_CANTABRIA_OBRAS_MEJORA_CURRENT_LABELS = {
    2024: {
        "0997": "Importe generado en 2022 pendiente de aplicación",
        "0998": "Importe generado en 2023 pendiente de aplicación",
        "0956": "Importe generado en 2024 pendiente de aplicación",
        "1713": "Importe generado en 2023 pendiente de aplicación",
    },
    2025: {
        "0997": "Importe generado en 2023 pendiente de aplicación",
        "0998": "Importe generado en 2024 pendiente de aplicación",
        "0956": "Importe generado en 2025 pendiente de aplicación",
        "1713": "Importe generado en 2024 pendiente de aplicación",
    },
}


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


@pytest.mark.parametrize("filing_year", [2020, 2021, 2022, 2023])
def test_modelo_100_cantabria_2020_2023_obras_mejora_slots_keep_historical_cant3aa_shape(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0948", "0950", "0956"}}

    assert set(casillas_by_id) == {"0948", "0950", "0956"}

    previous_pending = casillas_by_id["0948"]
    assert previous_pending.label == _EXPECTED_CANTABRIA_OBRAS_MEJORA_HISTORICAL_LABELS[filing_year]
    assert tuple(previous_pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert previous_pending.semantic_role == _CANTABRIA_OBRAS_MEJORA_PENDIENTE_EJERCICIOS_ANTERIORES_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending.legal_refs

    amount = casillas_by_id["0950"]
    assert amount.label == "Importe de la deducción"
    assert tuple(amount.section) == _CANTABRIA_DEDUCTION_SECTION
    assert amount.semantic_role == _CANTABRIA_OBRAS_MEJORA_IMPORTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in amount.legal_refs

    current_pending = casillas_by_id["0956"]
    assert current_pending.label == f"Por obras de mejora generada en {filing_year} a deducir en los 2 años siguientes"
    assert tuple(current_pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert current_pending.semantic_role == _CANTABRIA_OBRAS_MEJORA_GENERADO_EJERCICIO_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in current_pending.legal_refs


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_modelo_100_cantabria_2024_2025_obras_mejora_roles_follow_cant3_family(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla
        for casilla in revision.casillas
        if casilla.id in {"0948", "0950", "0956", "0997", "0998", "1713"}
    }
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_CANTABRIA_OBRAS_MEJORA_ROLES
    ]
    expected_labels = _EXPECTED_CANTABRIA_OBRAS_MEJORA_CURRENT_LABELS[filing_year]

    assert not legacy_roles
    assert set(casillas_by_id) == {"0948", "0950", "0956", "0997", "0998", "1713"}

    parent = casillas_by_id["0948"]
    assert parent.label == "Por obras de mejora en viviendas"
    assert tuple(parent.section) == _CANTABRIA_DEDUCTION_SECTION
    assert parent.semantic_role == _CANTABRIA_OBRAS_MEJORA_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id["0950"]
    assert generated.label == "Importe generado"
    assert tuple(generated.section) == _CANTABRIA_DEDUCTION_SECTION
    assert generated.semantic_role == _CANTABRIA_OBRAS_MEJORA_GENERADO_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    pending_1 = casillas_by_id["0997"]
    assert pending_1.label == expected_labels["0997"]
    assert tuple(pending_1.section) == _CANTABRIA_DEDUCTION_SECTION
    assert pending_1.semantic_role == _CANTABRIA_OBRAS_MEJORA_PENDIENTE_1_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending_1.legal_refs

    pending_2 = casillas_by_id["0998"]
    assert pending_2.label == expected_labels["0998"]
    assert tuple(pending_2.section) == _CANTABRIA_DEDUCTION_SECTION
    assert pending_2.semantic_role == _CANTABRIA_OBRAS_MEJORA_PENDIENTE_2_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in pending_2.legal_refs

    previous_pending = casillas_by_id["1713"]
    assert previous_pending.label == expected_labels["1713"]
    assert tuple(previous_pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert previous_pending.semantic_role == _CANTABRIA_OBRAS_MEJORA_PENDIENTE_EJERCICIO_ANTERIOR_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending.legal_refs

    current_pending = casillas_by_id["0956"]
    assert current_pending.label == expected_labels["0956"]
    assert tuple(current_pending.section) == _CANTABRIA_DEDUCTION_SECTION
    assert current_pending.semantic_role == _CANTABRIA_OBRAS_MEJORA_GENERADO_EJERCICIO_PENDIENTE_ROLE
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in current_pending.legal_refs
