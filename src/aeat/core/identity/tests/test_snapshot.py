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


@pytest.mark.parametrize(
    "snapshot_id",
    (
        pytest.param(hashlib.sha256(b"payload").hexdigest().upper(), id="uppercase"),
        pytest.param("a" * 63, id="short"),
        pytest.param("a" * 65, id="long"),
        pytest.param("g" * 64, id="non-hex"),
    ),
)
def test_rejects_invalid_snapshot_id(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(snapshot_id=snapshot_id)
