"""Strict roundtrip across the WorkflowStateRepository encrypted boundary.

:class:`WorkflowStateRepository` persists the operator-facing
:class:`WorkflowState` through :class:`SecureObjectRepository` at
``SensitivityClass.FINANCIAL``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ..auth._models import AuthState
from ..review._models import InvoiceReviewRecord, LedgerReviewRecord
from ._models import (
    DeclaracionPointer,
    WorkflowEvent,
    WorkflowState,
)
from ._persistence import WorkflowStateRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_workflow_state() -> WorkflowState:
    """Build a WorkflowState with every typed field populated.

    Includes:

    * an AuthState with non-default values
    * two profile bucket pointers (the keyed mapping must round-trip)
    * a declarations mapping with one DeclaracionPointer
    * a tuple of WorkflowEvent entries (append-only audit log)

    The active-profile selector lives in the precedence chain
    (Settings override > plaintext pointer file) rather than on the
    record itself, so it is intentionally absent from the fixture.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    return WorkflowState(
        auth=AuthState(),
        declarations={
            "303:2025Q1": DeclaracionPointer(
                modelo="303",
                period="2025Q1",
                draft_id="d" * 64,
                status="BORRADOR",
                exported_path="exports/303-2025Q1.txt",
                verified=False,
                updated_at=now,
            ),
        },
        invoice_reviews={
            "invoice-2024-001": InvoiceReviewRecord(
                invoice_id="invoice-2024-001",
                fields={"note": "follow up VAT split"},
                updated_at=now,
            ),
        },
        ledger_reviews={
            "transaction-2024-abc": LedgerReviewRecord(
                transaction_id="transaction-2024-abc",
                updated_at=now,
            ),
        },
        bucket_events=(
            WorkflowEvent(
                action="profile.bucket.created",
                reason="initial provisioning",
                bucket_id="b" * 32,
                object_id="profile-a",
                at=now,
            ),
        ),
        updated_at=now,
    )


def test_workflow_state_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated WorkflowState saved through the repository loads back equal.

    Exercises the full encrypted-persistence boundary at FINANCIAL
    sensitivity:

        WorkflowState -> Envelope[WorkflowState] -> JSON bytes ->
            column encryption -> SQLite -> column decryption ->
            JSON bytes -> Envelope -> WorkflowState.

    Per-field witnesses pin the most fragile pieces:

    * the declarations mapping with its nested DeclaracionPointer,
    * the bucket_events tuple with a non-empty audit record.

    ``WorkflowState.profiles`` is no longer a persisted field; it is
    a filesystem-manifest computed property, so this roundtrip does
    not exercise it.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "workflow-state-roundtrip.db"
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_workflow_state()
            repo = WorkflowStateRepository()
            repo.save(original)
            loaded = repo.load()

            # The repository stamps a fresh ``updated_at`` on every save
            # (see ``WorkflowStateRepository.to_secure_object_write``).
            # Compare every field EXCEPT updated_at by re-projecting the
            # loaded state onto the original's timestamp; assert separately
            # that the stamped timestamp is >= the original.
            loaded_normalised = loaded.model_copy(update={"updated_at": original.updated_at})
            assert loaded_normalised == original
            assert loaded.updated_at >= original.updated_at
            assert "303:2025Q1" in loaded.declarations
            loaded_decl = loaded.declarations["303:2025Q1"]
            assert loaded_decl.draft_id == "d" * 64
            assert loaded_decl.exported_path == "exports/303-2025Q1.txt"
            assert len(loaded.bucket_events) == 1
            assert loaded.bucket_events[0].action == "profile.bucket.created"
            assert loaded.bucket_events[0].bucket_id == "b" * 32
            assert set(loaded.invoice_reviews) == {"invoice-2024-001"}
            loaded_invoice = loaded.invoice_reviews["invoice-2024-001"]
            assert isinstance(loaded_invoice, InvoiceReviewRecord)
            assert loaded_invoice.fields == {"note": "follow up VAT split"}
            assert set(loaded.ledger_reviews) == {"transaction-2024-abc"}
            loaded_ledger = loaded.ledger_reviews["transaction-2024-abc"]
            assert isinstance(loaded_ledger, LedgerReviewRecord)
            assert loaded_ledger.transaction_id == "transaction-2024-abc"
        finally:
            engine.dispose()


def test_workflow_state_absent_load_returns_empty_state(tmp_path: Path) -> None:
    """The repository's empty-state fallback survives the boundary.

    When no row exists, ``load()`` must return a default
    :class:`WorkflowState` rather than raising. This is a load-side
    contract not exercised by the round-trip test above.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "workflow-state-empty.db"
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            repo = WorkflowStateRepository()
            loaded = repo.load()

            # Empty-default identity: no declarations, empty event tuple.
            # (profiles is a computed property scanning tmp_path/buckets,
            # which has none provisioned in this test, so it also reads
            # as empty.)
            assert loaded.profiles == {}
            assert loaded.declarations == {}
            assert loaded.bucket_events == ()
        finally:
            engine.dispose()
