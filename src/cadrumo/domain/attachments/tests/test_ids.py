"""Real-behavior tests for the canonical core hex-64 identity type."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....core.hex import Hex64Str
from ....tests.fixtures.identity_holder import single_field_holder

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_holder("attachment_id", Hex64Str)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"attachment-bytes").hexdigest()
    holder = _Holder.build(digest)
    assert holder.model_dump()["attachment_id"] == digest


def test_rejects_uppercase_hex() -> None:
    with pytest.raises(ValidationError):
        _Holder.build("A" * 64)


def test_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        _Holder.build("a" * 63)
    with pytest.raises(ValidationError):
        _Holder.build("a" * 65)


def test_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder.build("g" * 64)
