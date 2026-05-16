"""Strict roundtrip across the encrypted bucket-event-history boundary.

:class:`BucketEventHistoryRepository` persists the append-only audit
log of bucket events through :class:`SecureObjectRepository`. This
test asserts the save / load cycle preserves every event, the
catalogue keying by content-addressed event_id, and the per-event
typed payload mapping.

Real :class:`EphemeralMasterKeyProvider`, real SQLite, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
from ._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ._event_repository import BucketEventHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _build_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: dict[str, str],
) -> BucketEvent:
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )


def test_bucket_event_history_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """The full event-history catalogue round-trips strictly under encryption."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "events-roundtrip.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        bucket_id = "b" * 32
        now = datetime.now(UTC).replace(microsecond=0)
        # Two events with different shapes: one with a small payload
        # of three string keys, one with no payload at all. Both
        # must survive identity-preserving across the boundary.
        event_a = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.MODELO_CALCULATION_CREATED,
            occurred_at=now,
            actor="cli/aeat",
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="r" * 64,
            payload={"modelo": "303", "filing_year": "2025", "period": "1T"},
        )
        event_b = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.PROFILE_SELECTED,
            occurred_at=now,
            actor="cli/aeat",
            object_type=BucketEventObjectType.PROFILE,
            object_id="profile-active",
            payload={},
        )
        catalogue = BucketEventHistoryCatalogue(
            events={event_a.event_id: event_a, event_b.event_id: event_b},
        )

        repo = BucketEventHistoryRepository()
        repo.save(catalogue)
        loaded = repo.load()

        assert loaded == catalogue
        loaded_a = loaded.events[event_a.event_id]
        assert loaded_a.payload == {"modelo": "303", "filing_year": "2025", "period": "1T"}
        assert loaded_a.event_type is BucketEventType.MODELO_CALCULATION_CREATED
        assert loaded_a.object_type is BucketEventObjectType.CALCULATION_REVISION
        # Empty-payload event survives as an empty mapping, not as
        # missing or None — guards against a future encoder change
        # that drops empty dicts to None.
        loaded_b = loaded.events[event_b.event_id]
        assert loaded_b.payload == {}
        assert loaded_b.event_type is BucketEventType.PROFILE_SELECTED
    finally:
        engine.dispose()
        override_master_key_provider(None)
