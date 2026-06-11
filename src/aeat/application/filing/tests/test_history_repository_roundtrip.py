"""Strict roundtrip across the encrypted ModeloHistoryRepository boundary.

``ModeloHistoryRepository`` persists :class:`ModeloHistory` (a typed
tuple of ``ModeloHistoryEntry`` rows) per modelo at
``SensitivityClass.AUDIT``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core import Period
from ....domain._identifiers import ModeloIdentifier
from ....tests.secure_sql import isolated_runtime_profile
from .._history_models import ModeloHistory, ModeloHistoryEntry
from .._history_repository import ModeloHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "filing-runtime"


def _populated_history() -> ModeloHistory:
    """Build a ModeloHistory with multiple entries spanning distinct periods."""

    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloHistory(
        modelo=ModeloIdentifier("303"),
        entries=(
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "1T"),
                submitted_at=now - timedelta(days=90),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "2T"),
                submitted_at=now - timedelta(days=30),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo=ModeloIdentifier("303"),
                period=Period.from_year_and_code(2025, "3T"),
                submitted_at=now,
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
