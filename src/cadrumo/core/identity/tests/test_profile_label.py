"""Profile display labels stay distinct from opaque machine identities."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from .. import ProfileLabel

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _ProfileLabelRecord(BaseModel):
    label: ProfileLabel


def test_profile_label_accepts_operator_facing_name() -> None:
    assert _ProfileLabelRecord(label="  operator  ").label == "operator"


@pytest.mark.parametrize(
    "value",
    (
        "123e4567-e89b-42d3-a456-426614174000",
        "123e4567-e89b-42d3-a456-426614174000".upper(),
    ),
)
def test_profile_label_rejects_uuid_shaped_machine_identity(value: str) -> None:
    with pytest.raises(ValidationError, match="profile label must not be UUID-shaped"):
        _ProfileLabelRecord(label=value)
