"""Modelo 100 Madrid semantic-role registry tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.modelo.profile_derived_facts import madrid_nacimiento_adopcion_candidate_weighted_count
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_value_contract import BindingDataType, BindingValueChannel

from .authored_edition_support import newest_authored_edition
from .modelo_100_registry_support import (
    AUTONOMIC_DEDUCTION_ART_77_REF,
    MADRID_DEDUCTION_SECTION,
    modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The newest Modelo 100 edition the registry authors; its printed labels name its own exercise and the one before it.
_REVIEWED_EDITION = newest_authored_edition("100")

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


def _casilla(number: int) -> CasillaId:
    """Return the id of the casilla the official design numbers ``number``; a box number, not a year."""
    return validated_casilla_id(f"{number:04d}", surface="casilla.id")


_PENDIENTE_1_CASILLA = _casilla(2022)
_PENDIENTE_ANTERIOR_CASILLA = _casilla(2023)
_PARENT_CASILLA = _casilla(2030)
_GENERADO_CASILLA = _casilla(2031)
_PENDIENTE_CASILLA = _casilla(2032)


def test_modelo_100_madrid_m26_nuevos_contribuyentes_pending_roles_follow_official_family() -> None:
    revision = modelo_100_snapshot(_REVIEWED_EDITION).revision
    expected_ids = {
        _PENDIENTE_1_CASILLA,
        _PENDIENTE_ANTERIOR_CASILLA,
        _PARENT_CASILLA,
        _GENERADO_CASILLA,
        _PENDIENTE_CASILLA,
    }
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_ids}
    legacy_roles = [
        casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_MADRID_M26_PENDING_ROLES
    ]

    assert not legacy_roles
    assert set(casillas_by_id) == expected_ids

    previous_pending_1 = casillas_by_id[_PENDIENTE_1_CASILLA]
    assert previous_pending_1.label == f"Importe generado en {_REVIEWED_EDITION - 1} pendiente de aplicación"
    assert tuple(previous_pending_1.section) == MADRID_DEDUCTION_SECTION
    assert previous_pending_1.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_1_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending_1.legal_refs

    previous_pending = casillas_by_id[_PENDIENTE_ANTERIOR_CASILLA]
    assert previous_pending.label == f"Importe generado en {_REVIEWED_EDITION - 1} pendiente de aplicación"
    assert tuple(previous_pending.section) == MADRID_DEDUCTION_SECTION
    assert previous_pending.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_EJERCICIO_ANTERIOR_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in previous_pending.legal_refs

    parent = casillas_by_id[_PARENT_CASILLA]
    assert parent.label == "Por inversiones de nuevos contribuyentes procedentes del extranjero"
    assert tuple(parent.section) == MADRID_DEDUCTION_SECTION
    assert parent.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in parent.legal_refs

    generated = casillas_by_id[_GENERADO_CASILLA]
    assert generated.label == f"Importe generado en {_REVIEWED_EDITION}"
    assert tuple(generated.section) == MADRID_DEDUCTION_SECTION
    assert generated.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_GENERADO_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in generated.legal_refs

    current_pending = casillas_by_id[_PENDIENTE_CASILLA]
    assert current_pending.label == f"Importe generado en {_REVIEWED_EDITION} pendiente de aplicación"
    assert tuple(current_pending.section) == MADRID_DEDUCTION_SECTION
    assert current_pending.semantic_role == _MADRID_NUEVOS_CONTRIBUYENTES_PENDIENTE_ROLE
    assert AUTONOMIC_DEDUCTION_ART_77_REF in current_pending.legal_refs


_NACIMIENTO_ADOPCION_COUNT_BINDING = "renta-profile-madrid-nacimiento-adopcion-eligible-count"


def test_madrid_nacimiento_adopcion_count_binding_declares_a_non_monetary_decimal() -> None:
    """The prorrateo-weighted count is a fractional quantity, neither money nor a whole count.

    The injector behind this binding shares a descendant's nacimiento/adopción
    window between two custodians (DL 1/2010 arts. 4 y 18.1), so the value it
    produces is genuinely fractional: an ``integer`` contract would truncate
    the prorrata away, and ``money`` would label a count as currency.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        revision = modelo_100_snapshot(_REVIEWED_EDITION).revision
        binding = next(item for item in revision.bindings if item.id == _NACIMIENTO_ADOPCION_COUNT_BINDING)

        assert binding.value.data_type is BindingDataType.DECIMAL
        assert binding.value.channel is BindingValueChannel.DECIMAL

        shared_custody_facts = {
            "renta_family.descendiente.0.birth_date": date(_REVIEWED_EDITION, 6, 1).isoformat(),
            "renta_family.descendiente.0.convivencia": "true",
            "renta_family.descendiente.0.custodia_compartida": "true",
        }
        weighted_count = madrid_nacimiento_adopcion_candidate_weighted_count(
            shared_custody_facts, _REVIEWED_EDITION, operation=_authority_operation_for_test
        )

        assert weighted_count == Decimal("0.5")
        assert weighted_count != weighted_count.to_integral_value()
