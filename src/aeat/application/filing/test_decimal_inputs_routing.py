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

from ...core.resources import resources
from ...domain.calculations.registry import (
    calculate_registry_snapshot,
    enum_consumed_binding_ids,
)
from . import _filing_binding_values, _string_inputs_for_ids

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _m200_snapshot():  # type: ignore[return]
    return resources().modelos.authority.snapshot("200", filing_year=2024, period="0A", on=None)


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
    from ...domain.filing._protocols import ModeloInputs

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
            "DP200014:00552": Decimal("100000.00"),
            "DP200014:01033": Decimal("0.00"),
            "DP200014:01034": Decimal("0.00"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
        },
        enum_binding_values={
            "modelo-200-2024-profile-legal-entity-form": "sl",
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
        },
    )

    # SL at 23 % bracket: cuota integra = 100000 * 0.23 = 23000
    # Source: AEAT Modelo 200 manual 2024, art. 29 LIS tipo general 25 %
    # reduced to 23 % for PYME (INCN <= 1M EUR within SL entity type).
    cuota = result.values.get("DP200014:00562")
    assert cuota is not None
    assert cuota == Decimal("23000.00")
