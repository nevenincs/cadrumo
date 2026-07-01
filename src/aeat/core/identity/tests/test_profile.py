"""Real-behavior tests for the :data:`ProfileId` alias."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .. import ProfileId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("profile_id", ProfileId)


def test_accepts_valid_profile_ids() -> None:
    minted = str(uuid4())
    cases = (
        (minted, minted),
        (f"  {minted}  ", minted),
    )

    for profile_id, expected in cases:
        assert _Holder(profile_id=profile_id).profile_id == expected


def test_rejects_invalid_profile_ids() -> None:
    cases = (
        "operator",
        str(uuid4()).upper(),
        "",
        f"{uuid4()}-extra",
        "bad/id",
        " leading-space-after-strip-still-bad?",
    )

    for profile_id in cases:
        with pytest.raises(ValidationError):
            _Holder(profile_id=profile_id)
