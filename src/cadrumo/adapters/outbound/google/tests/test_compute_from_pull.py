"""Retirement does not turn historical pull records into calculation authority."""

from typing import cast

import pytest

from .....domain.calculations.registry.schema import RegistrySnapshot
from ...storage.errors import OutboundStorageConflictError
from ..calc_sheets_pull import compute_from_pull
from ..calc_sheets_pull_records import PullResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_legacy_calculation_refuses_without_reading_the_supplied_record() -> None:
    with pytest.raises(OutboundStorageConflictError) as raised:
        compute_from_pull(cast(RegistrySnapshot, object()), cast(PullResult, object()))
    assert raised.value.context == {"reason": "remote_business_calculation_retired", "effect_uncertain": False}
