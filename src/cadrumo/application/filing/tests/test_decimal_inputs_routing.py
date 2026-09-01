"""Regression tests for enum-typed binding routing in build_filing_draft.

Before the fix, ``_decimal_inputs_for_ids`` attempted to coerce every formula
binding value through ``Decimal()``. String-valued enum bindings (e.g.
``modelo-200-2024-profile-legal-entity-form="sl"``) triggered a
``ModeloBuilderError`` because ``Decimal("sl")`` raises ``InvalidOperation``.

The fix routes enum-consumed bindings via the ``enum_binding_values`` channel
in ``calculate_registry_snapshot``, bypassing the Decimal coercion path.
The same fix skips enum bindings in ``_filing_binding_values`` because they
carry no fichero-BOE addressing and must not be coerced to Decimal there either.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.runtime_graph import enum_consumed_binding_ids
from ....domain.calculations.registry.schema import RegistrySnapshot
from ..draft_construction import _filing_binding_values, _string_inputs_for_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id(
    "00501",
    surface="_M200_RESULTADO_CONTABLE_CASILLA",
)
_M200_CORRECCIONES_AUMENTO_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01033",
    surface="_M200_CORRECCIONES_AUMENTO_CASILLA",
)
_M200_CORRECCIONES_DISMINUCION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01034",
    surface="_M200_CORRECCIONES_DISMINUCION_CASILLA",
)
_M200_BIN_APLICADA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00547",
    surface="_M200_BIN_APLICADA_CASILLA",
)
_M200_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_CUOTA_INTEGRA_CASILLA",
)


def _m200_snapshot() -> RegistrySnapshot:
    """Return the modelo 200 snapshot at the rung this module's questions need.

    Every test here asks how INPUTS are routed -- which binding ids the enum
    channel consumes, how string inputs resolve to enum bindings, what the
    calculation does with a compensation value. None of them renders a fichero
    record or reads an export layout, so the calculation rung is the authority
    they exercise. Modelo 200 declares exactly that rung and deliberately
    withholds filing while its revision spans two AEAT layouts.
    """
    return bundled_authority().snapshot(
        "200",
        filing_year=2025,
        period="0A",
        on=None,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def test_enum_consumed_binding_ids_identifies_legal_entity_form() -> None:
    """enum_consumed_binding_ids must identify legal_entity_form as enum-routed.

    This is the authoritative discriminator that separates the string
    enum channel from the Decimal channel.  A regression here would
    silently re-introduce the ``Decimal("sl")`` crash on any M200 verify.
    """
    snap = _m200_snapshot()
    enum_ids = enum_consumed_binding_ids(snap.revision)
    assert "modelo-200-2024-profile-legal-entity-form" in enum_ids


def test_string_inputs_for_ids_extracts_enum_binding() -> None:
    """_string_inputs_for_ids must extract string enum values from ModeloInputs."""
    from ....domain.filing.protocols import ModeloInputs

    inputs: ModeloInputs = {
        "modelo-200-2024-profile-legal-entity-form": "sl",
        "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
        "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
    }
    snap = _m200_snapshot()
    enum_ids = enum_consumed_binding_ids(snap.revision)
    result = _string_inputs_for_ids(inputs, enum_ids)

    assert result == {"modelo-200-2024-profile-legal-entity-form": "sl"}


def test_filing_binding_values_skips_enum_bindings() -> None:
    """_filing_binding_values must not attempt Decimal coercion on enum bindings."""
    snap = _m200_snapshot()
    bindings = {binding.id: binding for binding in snap.revision.bindings}
    enum_ids = enum_consumed_binding_ids(snap.revision)
    inputs = {
        "modelo-200-2024-profile-legal-entity-form": "sl",
        "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
        "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
    }

    # Must not raise ModeloBuilderError for the string enum binding
    binding_values = _filing_binding_values(inputs, bindings, enum_ids)

    # The enum binding should be absent from the returned binding values
    binding_ids = {bv.binding_id for bv in binding_values}
    assert "modelo-200-2024-profile-legal-entity-form" not in binding_ids
    # Decimal bindings are still present
    assert "modelo-200-2024-profile-incn-prior-12-months" in binding_ids


def test_calculate_registry_snapshot_accepts_enum_binding_via_enum_channel() -> None:
    """calculate_registry_snapshot must succeed when legal_entity_form is enum-routed.

    This exercises the full calculation path that build_filing_draft now
    calls: enum-consumed bindings go to enum_binding_values, not binding_values.
    relation_values are supplied explicitly as they are required by the M200 formula.
    """
    snap = _m200_snapshot()
    result = calculate_registry_snapshot(
        snap,
        inputs={
            # Base imponible 00552 is now computed from the base-determination
            # chain, so the resultado contable 00501 is the operator input;
            # with zero correcciones/reserva/BIN it computes 00552 = 100000.
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("100000.00"),
            _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0.00"),
            _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0.00"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            # Fresh-filer scenario: no prior-period BIN to compensate.
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            # Fresh filer: no prior-year unfulfilled credit-impairment balance (casilla 01494).
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        enum_binding_values={
            "modelo-200-2024-profile-legal-entity-form": "sl",
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
    )

    # SL at 23 % bracket: cuota integra = 100000 * 0.23 = 23000
    # Source: AEAT Modelo 200 manual 2024, art. 29 LIS tipo general 25 %
    # reduced to 23 % for PYME (INCN <= 1M EUR within SL entity type).
    cuota = result.values[_M200_CUOTA_INTEGRA_CASILLA]
    assert cuota == Decimal("23000.00")


def test_calculate_registry_snapshot_applies_non_zero_bin_pendiente_compensation() -> None:
    """Non-zero BIN-pendiente compensation reduces base imponible accordingly.

    A SL with resultado contable 100000 and 10000 of prior-period BIN
    pendiente elects to apply 10000 of BIN per LIS art. 26 (subject to
    the 70% / 1M EUR floor, which is non-binding at this scale).
    Binding `bin-pendiente-ejercicios-anteriores` carries the stock
    (00670); the operator's elective application amount is casilla
    00547 (input). Base imponible = 100000 - 10000 = 90000. Cuota at
    23% PYME bracket = 20700. This proves the BIN-pendiente binding +
    elective application propagate through the base-determination chain
    to the cuota; the prior test passes BIN = 0 (fresh-filer) and
    cannot prove the chain is active.
    """
    snap = _m200_snapshot()
    result = calculate_registry_snapshot(
        snap,
        inputs={
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("100000.00"),
            _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0.00"),
            _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0.00"),
            _M200_BIN_APLICADA_CASILLA: Decimal("10000.00"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("10000"),
            # No prior-year unfulfilled credit-impairment balance (casilla 01494).
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        enum_binding_values={
            "modelo-200-2024-profile-legal-entity-form": "sl",
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
    )

    cuota = result.values[_M200_CUOTA_INTEGRA_CASILLA]
    assert cuota == Decimal("20700.00"), (
        f"BIN compensation did not propagate: expected 20700 (= (100000 - 10000) * 0.23), got {cuota}"
    )
