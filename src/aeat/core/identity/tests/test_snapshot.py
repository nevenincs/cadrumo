"""Real-behavior tests for the :data:`SnapshotId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model
from .. import SnapshotId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("snapshot_id", SnapshotId)


def test_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"payload").hexdigest()
    assert _Holder(snapshot_id=digest).snapshot_id == digest


def test_rejects_uppercase_hex() -> None:
    digest = hashlib.sha256(b"payload").hexdigest().upper()
    with pytest.raises(ValidationError):
        _Holder(snapshot_id=digest)


def test_rejects_short_value() -> None:
    with pytest.raises(ValidationError):
        _Holder(snapshot_id="a" * 63)


def test_rejects_long_value() -> None:
    with pytest.raises(ValidationError):
        _Holder(snapshot_id="a" * 65)


def test_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _Holder(snapshot_id="g" * 64)
