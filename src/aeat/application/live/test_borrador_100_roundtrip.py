"""Strict roundtrip across the Modelo 100 borrador snapshot repository.

Persists :class:`Borrador100Snapshot` records under
``aeat.application.live.borrador_100_snapshot`` at
``SensitivityClass.FINANCIAL``. Flagged as untested in the
persistence-boundary identity audit.

Anti-tautology: the fixture populates ``binding_values`` with one
``Decimal`` and one ``str`` value to stress the
``_BorradorValue = Decimal | str`` union — the same drift pattern that
silently coerced ``UserProfileFact.value`` Decimals to ``str`` on JSON
re-parse. Also exercises the ``SUPERSEDED`` lifecycle (a state the
model_validator enforces with ``superseded_by_snapshot_id``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotState,
    derive_borrador_100_snapshot_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_snapshot(*, bucket_id: str) -> Borrador100Snapshot:
    captured_at = datetime(2024, 4, 12, 11, 30, 0, tzinfo=UTC)
    binding_values = {
        "casilla.0500": Decimal("42500.00"),
        "casilla.0501": Decimal("8750.50"),
        "casilla.identity.declarant_label": "Gergely Wootsch",
    }
    source_url = (
        "https://www2.agenciatributaria.gob.es/wlpl/PROC-RENTA/borrador/2024?expediente=202410013522456T"
    )
    snapshot_id = derive_borrador_100_snapshot_id(
        filing_year=2024,
        period="0A",
        captured_at=captured_at,
        source_url=source_url,
        binding_values=binding_values,
    )
    return Borrador100Snapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2024,
        period="0A",
        captured_at=captured_at,
        source_url=source_url,
        state=Borrador100SnapshotState.ACTIVE,
        binding_values=binding_values,
    )


def test_borrador_100_snapshot_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated borrador snapshot round-trips through the encrypted store."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "borrador-100-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        bucket_id = "renta-2024-bucket"
        repo = Borrador100SnapshotRepository(bucket_id=bucket_id)
        original = _populated_snapshot(bucket_id=bucket_id)
        repo.save(original)
        loaded = repo.load(original.snapshot_id)

        assert loaded == original
        # Witness the Decimal entries survive the union resolution.
        assert loaded.binding_values["casilla.0500"] == Decimal("42500.00")
        assert isinstance(loaded.binding_values["casilla.0500"], Decimal)
        assert loaded.binding_values["casilla.0501"] == Decimal("8750.50")
        assert isinstance(loaded.binding_values["casilla.0501"], Decimal)
        # And the str entries are still str (not coerced to Decimal).
        assert loaded.binding_values["casilla.identity.declarant_label"] == "Gergely Wootsch"
        assert isinstance(loaded.binding_values["casilla.identity.declarant_label"], str)
    finally:
        engine.dispose()
        override_master_key_provider(None)
