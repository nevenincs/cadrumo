"""Real-behavior tests for the :data:`ProfileId` alias."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .. import ProfileId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("profile_id", ProfileId)


def test_accepts_canonical_uuid_minted_value() -> None:
    minted = str(uuid4())
    assert _Holder(profile_id=minted).profile_id == minted


def test_strips_surrounding_whitespace_before_uuid_validation() -> None:
    minted = str(uuid4())
    assert _Holder(profile_id=f"  {minted}  ").profile_id == minted


@pytest.mark.parametrize(
    "profile_id",
    (
        pytest.param("operator", id="operator-label"),
        pytest.param(str(uuid4()).upper(), id="uppercase-uuid"),
        pytest.param("", id="empty"),
        pytest.param(f"{uuid4()}-extra", id="too-long"),
        pytest.param("bad/id", id="slash"),
        pytest.param(" leading-space-after-strip-still-bad?", id="stripped-disallowed"),
    ),
)
def test_rejects_invalid_profile_id(profile_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id=profile_id)
