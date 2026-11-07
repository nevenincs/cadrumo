from datetime import date

import pytest

from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .. import notifications

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_notifications_parse_date_delegates_to_canonical() -> None:
    year = filing_year_envelope().horizon
    assert notifications.parse_date_local(f"15-03-{year}") == date(year, 3, 15)
    assert notifications.parse_date_local("not-a-date") is None
