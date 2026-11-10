"""Scenario bodies for test_casilla_keying_convention, called by its authored-source and published-authority tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..casilla_membership import casilla_noncanonical_reference_targets, format_noncanonical_casilla_reference
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..schema import RegistrySnapshot

M303_SEMANTIC_INPUT_CASILLA: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="M303_SEMANTIC_INPUT_CASILLA",
)

M303_REGIMEN_GENERAL_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="M303_REGIMEN_GENERAL_RESULT_CASILLA",
)

M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)

M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)

M303_PREVIOUS_COMPENSATION_BINDING = "modelo-303-compensacion-pendiente-anteriores"


def check_runtime_accepts_canonical_casilla_id_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == M303_SEMANTIC_INPUT_CASILLA)
    assert casilla.number != casilla.id

    result = calculate_registry_snapshot(
        snapshot,
        inputs={casilla.id: Decimal("1")},
        binding_values={M303_PREVIOUS_COMPENSATION_BINDING: Decimal("0")},
        date_context={"filing_period": date(snapshot.filing_year, 3, 31)},
    )

    assert result.values[casilla.id] == Decimal("1")


def check_runtime_rejects_casilla_number_for_semantic_input(_m303_2025_1t_snapshot: RegistrySnapshot) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == M303_SEMANTIC_INPUT_CASILLA)
    assert casilla.number != casilla.id

    with pytest.raises(RegistryValidationError, match="unknown registry input casilla ids") as exc_info:
        calculate_registry_snapshot(
            snapshot,
            inputs={casilla.number: Decimal("1")},
            binding_values={M303_PREVIOUS_COMPENSATION_BINDING: Decimal("0")},
            date_context={"filing_period": date(snapshot.filing_year, 3, 31)},
        )

    assert exc_info.value.context == {"casilla_ids": casilla.number}


def check_noncanonical_reference_targets_include_export_refs_without_accepting_them_as_ids(
    _m303_2025_1t_snapshot: RegistrySnapshot,
) -> None:
    snapshot = _m303_2025_1t_snapshot
    casilla = next(
        casilla for casilla in snapshot.revision.casillas if casilla.id == M303_REGIMEN_GENERAL_RESULT_CASILLA
    )
    export_ref = next(ref for ref in casilla.export_refs if ref != casilla.id)

    targets = casilla_noncanonical_reference_targets(snapshot.revision, export_ref)

    assert targets == (casilla.id,)
    assert format_noncanonical_casilla_reference(export_ref, targets) == f"{export_ref!r} -> {casilla.id}"


def check_noncanonical_reference_targets_expose_ambiguous_reused_printed_number(
    _m200_2024_snapshot: RegistrySnapshot,
) -> None:
    snapshot = _m200_2024_snapshot
    ecpn_casilla = next(
        casilla for casilla in snapshot.revision.casillas if casilla.id == M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA
    )
    liquidacion_casilla = next(
        casilla
        for casilla in snapshot.revision.casillas
        if casilla.id == M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA
    )

    assert ecpn_casilla.number == liquidacion_casilla.number
    targets = casilla_noncanonical_reference_targets(snapshot.revision, ecpn_casilla.number)
    # Every sheet that prints the number has its own casilla, and each is a candidate.
    printing_the_number = {
        casilla.id for casilla in snapshot.revision.casillas if casilla.number == ecpn_casilla.number
    }

    assert {M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA, M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA} <= set(targets)
    assert set(targets) == printing_the_number
    assert len(targets) == len(printing_the_number)
    assert format_noncanonical_casilla_reference(ecpn_casilla.number, targets) == (
        f"{ecpn_casilla.number!r} is ambiguous; candidate casilla.id values: {', '.join(targets)}"
    )
