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


def test_bucket_event_payload_tampering_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: mutating an event's payload must surface.

    Every :class:`BucketEvent` carries a content-addressed
    ``event_id`` derived from the full event shape including its
    payload. The model_validator re-derives the id on every
    construction. A persisted event whose payload is mutated post-
    save MUST fail the id check on load — that's the audit-trail
    integrity guarantee the catalogue relies on.

    Persists one event, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically rewrites a payload value (changing
    ``modelo`` from ``"303"`` to ``"100"`` without touching the
    event_id), and asserts the load path catches the drift via the
    model_validator's derived-id check.

    If this test passes silently with a tampered payload, the bucket-
    event-history boundary is tautological and the audit trail is
    not actually content-addressed.
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._event_repository import _NAMESPACE as _BUCKET_EVENT_NAMESPACE

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "bucket-events-anti-tautology.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        bucket_id = "b" * 32
        now = datetime.now(UTC).replace(microsecond=0)
        event = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.MODELO_CALCULATION_CREATED,
            occurred_at=now,
            actor="cli/aeat",
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="r" * 64,
            payload={"modelo": "303", "filing_year": "2025", "period": "1T"},
        )
        catalogue = BucketEventHistoryCatalogue(events={event.event_id: event})
        repo = BucketEventHistoryRepository()
        repo.save(catalogue)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _BUCKET_EVENT_NAMESPACE,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(row.payload.decode("utf-8"))
            events = envelope["payload"]["events"]
            event_dict = events[event.event_id]
            assert event_dict["payload"]["modelo"] == "303", (
                "fixture must serialise the modelo payload key as '303' "
                "for this proof test to be meaningful"
            )
            # Tamper with the payload without recomputing the event_id.
            # The content-addressed id derivation must fail on load.
            event_dict["payload"]["modelo"] = "100"
            row.payload = _json.dumps(envelope).encode("utf-8")

        regression_caught = False
        try:
            repo.load()
        except Exception:  # noqa: BLE001 - boundary may raise different types
            regression_caught = True
        assert regression_caught, (
            "anti-tautology proof failed: mutating the payload without "
            "recomputing event_id did NOT surface on load. The bucket-"
            "event-history boundary is tautological and the audit "
            "trail is not actually content-addressed."
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)
