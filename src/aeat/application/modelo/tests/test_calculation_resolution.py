from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._calculation_resolution import build_calculation_replay_payloads

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
