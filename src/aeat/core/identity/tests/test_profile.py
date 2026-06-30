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


def test_rejects_operator_label() -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id="operator")


def test_rejects_uppercase_uuid() -> None:
    minted = str(uuid4()).upper()
    with pytest.raises(ValidationError):
        _Holder(profile_id=minted)


def test_strips_surrounding_whitespace_before_uuid_validation() -> None:
    minted = str(uuid4())
    assert _Holder(profile_id=f"  {minted}  ").profile_id == minted


def test_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id="")


def test_rejects_value_over_max_length() -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id=f"{uuid4()}-extra")


def test_rejects_value_with_disallowed_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder(profile_id="bad/id")
    with pytest.raises(ValidationError):
        _Holder(profile_id=" leading-space-after-strip-still-bad?")
