"""Real-behavior tests for the :data:`SnapshotId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model, single_field_value
from .. import SnapshotId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("snapshot_id", SnapshotId)


def test_snapshot_id_constraint_accepts_canonical_digest_and_rejects_invalid_values() -> None:
    digest = hashlib.sha256(b"payload").hexdigest()
    assert single_field_value(_Holder(snapshot_id=digest), "snapshot_id") == digest

    cases = (
        hashlib.sha256(b"payload").hexdigest().upper(),
        "a" * 63,
        "a" * 65,
        "g" * 64,
    )

    for snapshot_id in cases:
        with pytest.raises(ValidationError):
            _Holder(snapshot_id=snapshot_id)
