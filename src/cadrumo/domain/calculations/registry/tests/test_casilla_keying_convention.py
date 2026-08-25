"""Behavioral gate for canonical casilla lookup."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from .....core.resources import resources
from .. import (
    RegistrySnapshot,
    RegistryValidationError,
    calculate_registry_snapshot,
    casilla_noncanonical_reference_targets,
    format_noncanonical_casilla_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M303_SEMANTIC_INPUT_CASILLA: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="_M303_SEMANTIC_INPUT_CASILLA",
)
_M303_REGIMEN_GENERAL_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="_M303_REGIMEN_GENERAL_RESULT_CASILLA",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)
_M303_PREVIOUS_COMPENSATION_BINDING = "modelo-303-compensacion-pendiente-anteriores"


@pytest.fixture(scope="module")
def _m303_2025_1t_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("303", filing_year=2025, period="1T")


@pytest.fixture(scope="module")
def _m200_2024_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot(
        "200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )


def test_runtime_accepts_canonical_casilla_id_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M303_SEMANTIC_INPUT_CASILLA)
    assert casilla.number != casilla.id

    result = calculate_registry_snapshot(
        snapshot,
        inputs={casilla.id: Decimal("1")},
        binding_values={_M303_PREVIOUS_COMPENSATION_BINDING: Decimal("0")},
        date_context={"filing_period": date(2025, 3, 31)},
    )

    assert result.values[casilla.id] == Decimal("1")


def test_runtime_rejects_casilla_number_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M303_SEMANTIC_INPUT_CASILLA)
    assert casilla.number != casilla.id

    with pytest.raises(RegistryValidationError, match="unknown registry input casilla ids") as exc_info:
        calculate_registry_snapshot(
            snapshot,
            inputs={casilla.number: Decimal("1")},
            binding_values={_M303_PREVIOUS_COMPENSATION_BINDING: Decimal("0")},
            date_context={"filing_period": date(2025, 3, 31)},
        )

    assert exc_info.value.context == {"casilla_ids": casilla.number}


def test_noncanonical_reference_targets_include_export_refs_without_accepting_them_as_ids(
    _m303_2025_1t_snapshot: RegistrySnapshot,
) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(
        casilla for casilla in snapshot.revision.casillas if casilla.id == _M303_REGIMEN_GENERAL_RESULT_CASILLA
    )
    export_ref = next(ref for ref in casilla.export_refs if ref != casilla.id)

    targets = casilla_noncanonical_reference_targets(snapshot.revision, export_ref)

    assert targets == (casilla.id,)
    assert format_noncanonical_casilla_reference(export_ref, targets) == f"{export_ref!r} -> {casilla.id}"


def test_noncanonical_reference_targets_expose_ambiguous_reused_printed_number(
    _m200_2024_snapshot: RegistrySnapshot,
) -> None:
    snapshot = _m200_2024_snapshot
    ecpn_casilla = next(
        casilla for casilla in snapshot.revision.casillas if casilla.id == _M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA
    )
    liquidacion_casilla = next(
        casilla
        for casilla in snapshot.revision.casillas
        if casilla.id == _M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA
    )

    assert ecpn_casilla.number == liquidacion_casilla.number
    targets = casilla_noncanonical_reference_targets(snapshot.revision, ecpn_casilla.number)

    assert targets == (
        _M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA,
        _M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA,
    )
    assert format_noncanonical_casilla_reference(ecpn_casilla.number, targets) == (
        f"{ecpn_casilla.number!r} is ambiguous; candidate casilla.id values: "
        f"{_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA}, {_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA}"
    )
