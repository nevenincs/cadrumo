"""The pending value applies until the element has left service, not merely until a baja is recorded."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetRegisterState

from .test_baja_correction import ASSET, sale
from .test_register import FIRST_YEAR, NAME, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _listed(*, today: date, baja_on: date | None):
    operations, _ = register_operations(today=today)
    operations.create(register_revision(), NAME)
    if baja_on is not None:
        operations.dispose(ASSET, sale(baja_on))
    (row,) = operations.list_elements()
    return row


def test_a_future_baja_leaves_the_element_in_service_with_its_pending_value_applying() -> None:
    row = _listed(today=date(FIRST_YEAR, 6, 1), baja_on=date(FIRST_YEAR, 9, 30))

    assert row.disposal is not None
    assert row.state is ActivityAssetRegisterState.IN_SERVICE
    assert row.pending_applies is True


def test_a_baja_already_past_takes_the_pending_value_away() -> None:
    row = _listed(today=date(FIRST_YEAR, 12, 31), baja_on=date(FIRST_YEAR, 9, 30))

    assert row.state is ActivityAssetRegisterState.OUT_OF_SERVICE
    assert row.pending_applies is False


def test_an_element_with_no_baja_has_a_pending_value() -> None:
    assert _listed(today=date(FIRST_YEAR, 6, 1), baja_on=None).pending_applies is True
