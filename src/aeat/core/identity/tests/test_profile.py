"""Real-behavior tests for the :data:`ProfileId` alias."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model, single_field_value
from .. import ProfileId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("profile_id", ProfileId)
_VALID_PROFILE_ID = str(uuid4())
_UPPERCASE_PROFILE_ID = str(uuid4()).upper()
_EXTRA_SUFFIX_PROFILE_ID = f"{uuid4()}-extra"


@pytest.mark.parametrize(
    ("profile_id", "expected"),
    (
        pytest.param(_VALID_PROFILE_ID, _VALID_PROFILE_ID, id="canonical"),
        pytest.param(f"  {_VALID_PROFILE_ID}  ", _VALID_PROFILE_ID, id="trimmed"),
    ),
)
def test_profile_id_constraint_accepts_valid_values(profile_id: str, expected: str) -> None:
    assert single_field_value(_Holder(profile_id=profile_id), "profile_id") == expected


@pytest.mark.parametrize(
    "profile_id",
    (
        pytest.param("operator", id="plain-label"),
        pytest.param(_UPPERCASE_PROFILE_ID, id="uppercase-uuid"),
        pytest.param("", id="empty"),
        pytest.param(_EXTRA_SUFFIX_PROFILE_ID, id="extra-suffix"),
        pytest.param("bad/id", id="slash"),
        pytest.param(" leading-space-after-strip-still-bad?", id="invalid-after-trim"),
    ),
)
def test_profile_id_constraint_rejects_invalid_values(profile_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id=profile_id)
