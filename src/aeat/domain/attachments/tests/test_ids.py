"""Real-behavior tests for the :data:`AttachmentId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ValidationError

from .._ids import AttachmentId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Holder(BaseModel):
    attachment_id: AttachmentId


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"attachment-bytes").hexdigest()
    assert _Holder(attachment_id=digest).attachment_id == digest


def test_rejects_uppercase_hex() -> None:
    with pytest.raises(ValidationError):
        _Holder(attachment_id="A" * 64)


def test_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        _Holder(attachment_id="a" * 63)
    with pytest.raises(ValidationError):
        _Holder(attachment_id="a" * 65)


def test_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder(attachment_id="g" * 64)
