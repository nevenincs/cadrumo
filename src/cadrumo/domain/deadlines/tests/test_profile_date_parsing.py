from datetime import date

import pytest

from .. import profiles as profiles
from ..errors import ProfileError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_profiles_parse_date_delegates_to_canonical() -> None:
    assert profiles._parse_date("2024-03-15") == date(2024, 3, 15)
    with pytest.raises(ProfileError, match="expected ISO-8601"):
        profiles._parse_date("15-03-2024")
