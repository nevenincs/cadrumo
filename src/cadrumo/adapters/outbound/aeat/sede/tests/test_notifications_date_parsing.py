from datetime import date

import pytest

from .. import notifications

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_notifications_parse_date_delegates_to_canonical() -> None:
    assert notifications._parse_date_local("15-03-2024") == date(2024, 3, 15)
    assert notifications._parse_date_local("not-a-date") is None
