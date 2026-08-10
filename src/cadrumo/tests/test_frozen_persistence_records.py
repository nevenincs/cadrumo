"""Runtime contracts for frozen persistence records.

Bucket path records and raw secure-object rows are immutable once built, and the
raw row enforces its hash width on the way in. Both matter for the same reason:
these records are handed around after construction, so a mutable one lets a
caller change where bytes are read from or what digest they are attributed to,
long after the value was validated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..adapters.persistence.storage.bucket import bucket_paths
from ..adapters.persistence.storage.sql import SecureObjectRawRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HASH_64 = "a" * 64


def test_bucket_paths_record_is_frozen(tmp_path: Path) -> None:
    """Bucket path records are immutable after path resolution."""
    paths = bucket_paths(root=tmp_path, bucket_id="profile")

    assert paths.bucket_dir.as_posix().endswith("buckets/profile")
    with pytest.raises(ValidationError, match="Instance is frozen"):
        paths.db_dir = paths.root


def test_secure_object_raw_row_is_frozen_and_validates_revision_hashes() -> None:
    """Raw secure-object records freeze payload metadata and enforce hash width."""
    row = SecureObjectRawRow(
        row_id=1,
        namespace="aeat.test",
        object_key=b"object-key",
        classification="cache",
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"payload",
        revision_id=_HASH_64,
    )

    assert row.revision_id == _HASH_64
    with pytest.raises(ValidationError, match="Instance is frozen"):
        row.payload = b"changed"
    with pytest.raises(ValidationError, match="String should have at least 64 characters"):
        SecureObjectRawRow(
            row_id=1,
            namespace="aeat.test",
            object_key=b"object-key",
            classification="cache",
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"payload",
            revision_id="short",
        )
