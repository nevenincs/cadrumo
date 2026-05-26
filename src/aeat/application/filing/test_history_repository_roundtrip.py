"""Strict roundtrip across the encrypted ModeloHistoryRepository boundary.

``ModeloHistoryRepository`` persists :class:`ModeloHistory` (a typed
tuple of ``ModeloHistoryEntry`` rows) per modelo at
``SensitivityClass.AUDIT``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...core.config import override_settings
from ...domain._identifiers import ModeloIdentifier
from ._history_models import ModeloHistory, ModeloHistoryEntry
from ._history_repository import ModeloHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_BUCKET_ID = "filing-runtime"
_KEK = b"k" * 32
_DEK = b"d" * 32


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _populated_history() -> ModeloHistory:
    """Build a ModeloHistory with multiple entries spanning distinct periods."""

    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloHistory(
        modelo=ModeloIdentifier("303"),
        entries=(
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period="2025Q1",
                submitted_at=now - timedelta(days=90),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period="2025Q2",
                submitted_at=now - timedelta(days=30),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period="2025Q3",
                submitted_at=now,
                status="RECHAZADA",
            ),
        ),
    )


def test_filing_history_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """ModeloHistory entries tuple round-trips strictly with non-default statuses."""

    with override_settings(aeat_local_storage_root=tmp_path), activate_session(_session()):
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
    assert tuple(e.period for e in loaded.entries) == ("2025Q1", "2025Q2", "2025Q3")
    assert tuple(e.status for e in loaded.entries) == (
        "ACEPTADA",
        "ACEPTADA",
        "RECHAZADA",
    )
