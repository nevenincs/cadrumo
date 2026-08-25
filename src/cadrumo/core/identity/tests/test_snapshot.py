"""Real-behavior tests for the :data:`~core.identity.SnapshotId` alias.

The suite pins ``SnapshotId`` as a lowercase hex-64 content-addressed identity
for live snapshot records that are persisted by application services and read by
storage adapters. It accepts the canonical SHA-256 digest shape and rejects
uppercase, wrong-length, and non-hex values at the pydantic boundary.

See Also:
    :data:`~core.identity.SnapshotId`
        Alias definition under test.
    :class:`~application.live.PersistedNotificationsSnapshot`
        Bucket-scoped live snapshot payload that stores a ``SnapshotId``.
    :mod:`~application.live.snapshot_base`
        Shared secure snapshot persistence base for live capture services.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .. import SnapshotId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_holder("snapshot_id", SnapshotId)
_CANONICAL_DIGEST = hashlib.sha256(b"payload").hexdigest()


def test_snapshot_id_constraint_accepts_canonical_digest() -> None:
    assert _Holder.value_of(_Holder.build(_CANONICAL_DIGEST)) == _CANONICAL_DIGEST


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
        _Holder.build(snapshot_id)
