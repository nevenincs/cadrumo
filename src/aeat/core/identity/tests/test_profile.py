"""Real-behavior tests for the :data:`ProfileId` alias."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model, single_field_value
from .. import ProfileId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("profile_id", ProfileId)


def test_profile_id_constraint_accepts_valid_values_and_rejects_invalid_values() -> None:
    minted = str(uuid4())
    valid_cases = (
        (minted, minted),
        (f"  {minted}  ", minted),
    )

    for profile_id, expected in valid_cases:
        assert single_field_value(_Holder(profile_id=profile_id), "profile_id") == expected

    invalid_cases = (
        "operator",
        str(uuid4()).upper(),
        "",
        f"{uuid4()}-extra",
        "bad/id",
        " leading-space-after-strip-still-bad?",
    )

    for profile_id in invalid_cases:
        with pytest.raises(ValidationError):
            _Holder(profile_id=profile_id)
