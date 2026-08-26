"""Regression coverage for row-indexed calculation replay payloads.

See Also:
    :func:`~application.modelo._calculation_resolution.build_calculation_replay_payloads`
        Helper under test, separating scalar binding overrides from structured
        row-binding replay values.
    :class:`~application.modelo._calculation_resolution.CalculationReplayPayloads`
        Persisted replay bundle that stores ``row_binding_values`` beside
        scalar calculation inputs.
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh envelope that carries row-indexed Modelo 720 values into
        the calculate path.
    :class:`~domain.modelos.CalculationRevision`
        Draft calculation record whose content hash and replay surface include
        the row-binding values.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._calculation_resolution import build_calculation_replay_payloads, resolve_calculation_binding_channels
from .._calculation_resolution import (
    resolve_calculation_binding_channels as _owner_resolve_calculation_binding_channels,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_calculation_binding_channel_resolver_is_the_public_owner_identity() -> None:
    assert resolve_calculation_binding_channels is _owner_resolve_calculation_binding_channels


def test_replay_payloads_keep_row_bindings_out_of_scalar_overrides() -> None:
    payloads = build_calculation_replay_payloads(
        resolved_inputs={},
        resolved_bindings={"modelo-720-threshold-total": Decimal("60000.00")},
        resolved_enum_bindings={"profile.iva_regime": "general"},
        resolved_date_bindings={"taxpayer.birth_date": date(1980, 1, 2)},
        resolved_relations={},
        resolved_row_bindings={
            ("modelo-720-asset-row-class", 2): "C",
            ("modelo-720-asset-row-valuation", 2): Decimal("60000.00"),
        },
    )

    assert payloads.binding_overrides == {
        "modelo-720-threshold-total": "60000",
        "profile.iva_regime": "general",
        "taxpayer.birth_date": "1980-01-02",
    }
    assert "modelo-720-asset-row-valuation" not in payloads.binding_overrides
    assert payloads.row_binding_values == {
        "modelo-720-asset-row-class": {"2": "C"},
        "modelo-720-asset-row-valuation": {"2": "60000"},
    }
