"""Tests for active-profile transaction catalogue resolution."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions import (
    LedgerNoActiveBucketError,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from cadrumo.application.workflow.state_models import WorkflowState, active_transaction_catalogue_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUNTIME_BUCKET_ID = "f8dbdb29-a1ff-45d2-b63a-ed066d5f2f0c"
_FIRST_BUCKET_ID = "db6f2ed3-93cd-407d-b683-73e57933e783"
_SECOND_BUCKET_ID = "45a7579d-5ba0-41f0-ae45-cb45d48bd015"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_RUNTIME_BUCKET_ID,
    ) as profile:
        yield profile.repository


def _state(*, profile: str, bucket_id: str) -> WorkflowState:
    """Build a WorkflowState — the state is a passthrough here.

    ``active_transaction_catalogue_repository`` resolves the active
    bucket via the precedence chain (``Settings.cadrumo_active_profile``
    override or pointer file), not via any field on the state record.
    Callers set ``override_settings(cadrumo_active_profile=...)`` per
    assertion. The ``profile`` and ``bucket_id`` arguments are kept
    for call-site readability.
    """

    del profile, bucket_id
    return WorkflowState()


def _transaction(provider_id: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("42.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description=f"bucket scoped row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )


def test_active_transaction_catalogue_repository_routes_by_active_profile_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    from ....core.config import override_settings

    first_state = _state(profile="alpha", bucket_id=_FIRST_BUCKET_ID)
    second_state = _state(profile="beta", bucket_id=_SECOND_BUCKET_ID)
    first_transaction = _transaction("same-provider-row")

    with override_settings(cadrumo_active_profile=_FIRST_BUCKET_ID):
        active_transaction_catalogue_repository(first_state, objects=secure_objects).save(
            TransactionCatalogue.from_transactions((first_transaction,)),
        )
        first_catalogue = active_transaction_catalogue_repository(first_state, objects=secure_objects).load()
    with override_settings(cadrumo_active_profile=_SECOND_BUCKET_ID):
        second_catalogue = active_transaction_catalogue_repository(second_state, objects=secure_objects).load()

    assert tuple(first_catalogue.transactions) == (first_transaction.transaction_id,)
    assert second_catalogue.transactions == {}


def test_active_transaction_catalogue_repository_rejects_missing_active_bucket() -> None:
    with pytest.raises(LedgerNoActiveBucketError) as raised:
        active_transaction_catalogue_repository(WorkflowState())
    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
