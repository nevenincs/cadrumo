"""Real-behavior tests for the :data:`SnapshotId` alias."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_model, single_field_value
from .. import SnapshotId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_model("snapshot_id", SnapshotId)
_CANONICAL_DIGEST = hashlib.sha256(b"payload").hexdigest()


def test_snapshot_id_constraint_accepts_canonical_digest() -> None:
    assert single_field_value(_Holder(snapshot_id=_CANONICAL_DIGEST), "snapshot_id") == _CANONICAL_DIGEST


@pytest.mark.parametrize(
    "snapshot_id",
    (
        pytest.param(_CANONICAL_DIGEST.upper(), id="uppercase"),
        pytest.param("a" * 63, id="too-short"),
        pytest.param("a" * 65, id="too-long"),
        pytest.param("g" * 64, id="non-hex"),
    ),
)
def test_snapshot_id_constraint_rejects_invalid_values(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder(snapshot_id=snapshot_id)
