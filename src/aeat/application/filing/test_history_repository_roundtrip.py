"""Strict roundtrip across the encrypted ModeloHistoryRepository boundary.

``ModeloHistoryRepository`` persists :class:`ModeloHistory` (a typed
tuple of ``ModeloHistoryEntry`` rows) per modelo at
``SensitivityClass.AUDIT``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._history_models import ModeloHistory, ModeloHistoryEntry
from ._history_repository import ModeloHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_history() -> ModeloHistory:
    """Build a ModeloHistory with multiple entries spanning distinct periods."""

    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloHistory(
        modelo="303",
        entries=(
            ModeloHistoryEntry(
                modelo="303",
                period="2025Q1",
                submitted_at=now - timedelta(days=90),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo="303",
                period="2025Q2",
                submitted_at=now - timedelta(days=30),
                status="ACEPTADA",
            ),
            ModeloHistoryEntry(
                modelo="303",
                period="2025Q3",
                submitted_at=now,
                status="RECHAZADA",
            ),
        ),
    )


def test_filing_history_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ModeloHistory entries tuple round-trips strictly with non-default statuses."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "filing-history-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_history()
            repo = ModeloHistoryRepository()
            repo.save(original)
            loaded = repo.load("303")

            assert loaded is not None
            assert loaded == original
            # Per-field witnesses on the tuple ordering (entries
            # preserve insertion order on the wire — drop-and-reload
            # would otherwise stay invisible).
            assert len(loaded.entries) == 3
            assert tuple(e.period for e in loaded.entries) == ("2025Q1", "2025Q2", "2025Q3")
            assert tuple(e.status for e in loaded.entries) == (
                "ACEPTADA",
                "ACEPTADA",
                "RECHAZADA",
            )
        finally:
            engine.dispose()
