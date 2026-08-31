"""Strict roundtrip across the encrypted ModeloHistoryRepository boundary.

``ModeloHistoryRepository`` persists :class:`ModeloHistory` (a typed
tuple of ``ModeloHistoryEntry`` rows) per modelo at
``SensitivityClass.AUDIT``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ....domain.identifiers import ModeloIdentifier
from ....tests.secure_sql import isolated_runtime_profile
from ..history_models import ModeloHistory, ModeloHistoryEntry
from ..history_repository import ModeloHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_LATEST_SUBMITTED_AT = datetime(2026, 5, 28, 11, 25, 0, tzinfo=UTC)


def _populated_history() -> ModeloHistory:
    """Build a ModeloHistory with multiple entries spanning distinct periods."""

    return ModeloHistory(
        modelo=ModeloIdentifier("303"),
        entries=(
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "1T"),
                submitted_at=_LATEST_SUBMITTED_AT - timedelta(days=90),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "2T"),
                submitted_at=_LATEST_SUBMITTED_AT - timedelta(days=30),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "3T"),
                submitted_at=_LATEST_SUBMITTED_AT,
                status="RECHAZADA",
            ),
        ),
    )


def test_filing_history_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """ModeloHistory entries tuple round-trips strictly with non-default statuses."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _populated_history()
        repo = ModeloHistoryRepository(bucket_id=_BUCKET_ID)
        repo.save(original)
        loaded = ModeloHistoryRepository(bucket_id=_BUCKET_ID).load("303")

    assert loaded is not None
    assert loaded == original
    # Per-field witnesses on the tuple ordering (entries preserve
    # insertion order on the wire - drop-and-reload would otherwise
    # stay invisible).
    assert len(loaded.entries) == 3
    assert tuple(e.period for e in loaded.entries) == (
        Period.from_year_and_code(2025, "1T"),
        Period.from_year_and_code(2025, "2T"),
        Period.from_year_and_code(2025, "3T"),
    )
    assert tuple(e.status for e in loaded.entries) == (
        "ACEPTADA",
        "ACEPTADA",
        "RECHAZADA",
    )


def test_filing_history_persists_only_to_the_secure_database_object(
    tmp_path: Path,
) -> None:
    """A saved history never reaches the plaintext ``filing-history`` directory.

    :data:`StorageCategory.FILING_HISTORY` now declares
    no consumer at all. Its only one was the master-key rotation sweep,
    deleted with the shared-master model it belonged to, and even then that
    module only walked the directory looking for ``.envelope.json`` files to
    re-encrypt -- it was a sweep, never a writer. :class:`ModeloHistoryRepository`'s own module
    docstring states "plaintext filing-history JSON or envelope file lands
    on disk" is what it avoids; this proves it, mirroring
    ``test_put_file_reads_source_but_persists_only_secure_database_object``
    for the attachments store. The assertion routes through
    :func:`storage_path` rather than a literal so a future taxonomy subpath
    move is tracked automatically instead of silently passing vacuously
    against a stale path.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _populated_history()
        repo = ModeloHistoryRepository(bucket_id=_BUCKET_ID)
        repo.save(original)

        assert repo.load("303") == original
        assert not storage_path(StorageCategory.FILING_HISTORY).exists()
