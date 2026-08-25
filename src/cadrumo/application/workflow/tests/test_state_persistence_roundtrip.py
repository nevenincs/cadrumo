"""Strict roundtrip across the WorkflowStateRepository encrypted boundary.

:class:`WorkflowStateRepository` persists the operator-facing
:class:`WorkflowState` through :class:`SecureObjectRepository` at
``SensitivityClass.FINANCIAL``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Period
from ....tests.secure_sql import isolated_runtime_profile
from ...review import (
    InvoiceReviewRecord,
    LedgerReviewRecord,
)
from cadrumo.application.auth.models import AuthState
from ..persistence import WorkflowStateRepository
from ..profile_bucket_scan import list_profile_buckets
from ..state_models import (
    DeclaracionPointer,
    WorkflowEvent,
    WorkflowState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKFLOW_TIMESTAMP = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)


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

    return WorkflowState(
        auth=AuthState(),
        declarations={
            "303:2025:1T": DeclaracionPointer(
                modelo="303",
                period=Period.from_year_and_code(2025, "1T"),
                draft_id="d" * 64,
                status="BORRADOR",
                exported_path="exports/303-2025-1T.txt",
                verified=False,
                updated_at=_WORKFLOW_TIMESTAMP,
            ),
        },
        invoice_reviews={
            "a" * 64: InvoiceReviewRecord(
                invoice_id="a" * 64,
                fields={"note": "follow up IVA split"},
                updated_at=_WORKFLOW_TIMESTAMP,
            ),
        },
        ledger_reviews={
            "b" * 64: LedgerReviewRecord(
                transaction_id="b" * 64,
                updated_at=_WORKFLOW_TIMESTAMP,
            ),
        },
        bucket_events=(
            WorkflowEvent(
                action="profile.bucket.created",
                reason="initial provisioning",
                bucket_id="b" * 32,
                object_id="profile-a",
                at=_WORKFLOW_TIMESTAMP,
            ),
        ),
        updated_at=_WORKFLOW_TIMESTAMP,
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

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_workflow_state()
        repo = WorkflowStateRepository()
        repo.save(original)
        loaded = repo.load()

        loaded_normalised = loaded.model_copy(update={"updated_at": original.updated_at})
        assert loaded_normalised == original
        assert loaded.updated_at >= original.updated_at
        assert "303:2025:1T" in loaded.declarations
        loaded_decl = loaded.declarations["303:2025:1T"]
        assert loaded_decl.period == Period.from_year_and_code(2025, "1T")
        assert loaded_decl.draft_id == "d" * 64
        assert loaded_decl.exported_path == "exports/303-2025-1T.txt"
        assert len(loaded.bucket_events) == 1
        assert loaded.bucket_events[0].action == "profile.bucket.created"
        assert loaded.bucket_events[0].bucket_id == "b" * 32
        assert set(loaded.invoice_reviews) == {"a" * 64}
        loaded_invoice = loaded.invoice_reviews["a" * 64]
        assert isinstance(loaded_invoice, InvoiceReviewRecord)
        assert loaded_invoice.fields == {"note": "follow up IVA split"}
        assert set(loaded.ledger_reviews) == {"b" * 64}
        loaded_ledger = loaded.ledger_reviews["b" * 64]
        assert isinstance(loaded_ledger, LedgerReviewRecord)
        assert loaded_ledger.transaction_id == "b" * 64


def test_workflow_state_absent_load_returns_empty_state(
    tmp_path: Path,
) -> None:
    """The repository's empty-state fallback survives the boundary.

    When no row exists, ``load()`` must return a default
    :class:`WorkflowState` rather than raising. This is a load-side
    contract not exercised by the round-trip test above.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = WorkflowStateRepository()
        loaded = repo.load()

        assert set(list_profile_buckets(root=profile.storage_root)) == {profile.bucket_id}
        assert loaded.declarations == {}
        assert loaded.bucket_events == ()
