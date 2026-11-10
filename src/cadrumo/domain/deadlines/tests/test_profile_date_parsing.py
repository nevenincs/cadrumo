from datetime import date

import pytest

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from .. import profiles as profiles
from ..errors import ProfileError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_profiles_parse_date_delegates_to_canonical() -> None:
    expected = date(filing_year_envelope().horizon, 3, 15)
    assert profiles.profiles_parse_date(expected.isoformat()) == expected
    with pytest.raises(ProfileError, match="expected ISO-8601"):
        profiles.profiles_parse_date(expected.strftime("%d-%m-%Y"))
