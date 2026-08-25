"""Tests for active-profile transaction catalogue resolution."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
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
from ....tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ..active_profile import active_transaction_catalogue_repository

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
    tmp_path: Path,
) -> None:
    """The ACTIVE PROFILE decides which bucket the catalogue resolves to.

    Two REAL committed capsules, switched through the active-profile setting,
    because the resolution chain now runs setting -> active selector ->
    committed bucket pointer -> bucket id. That last hop is why a synthetic id
    no longer routes: ``resolve_profile_bucket`` returns nothing for a bucket
    no capsule was ever published for, so the seam needs provisioned buckets
    rather than invented identifiers.

    An earlier version patched ``require_active_profile_bucket_id`` into this
    function's ``__globals__`` with an iterator of three ids. That proved only
    that the function consumed whatever the lambda returned, in the order it
    happened to call it: the active profile was not involved anywhere, so the
    test no longer tested its own name, and caching the lookup would have broken
    it while the behaviour stayed correct.
    """
    first_transaction = _transaction("same-provider-row")

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:

        def factory(bucket_id: str) -> TransactionCatalogueRepository:
            objects = (
                runtime.primary.repository if bucket_id == runtime.primary.bucket_id else runtime.secondary.repository
            )
            return TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)

        active_transaction_catalogue_repository(repository_factory=factory).save(
            TransactionCatalogue.from_transactions((first_transaction,)),
        )
        first_catalogue = active_transaction_catalogue_repository(repository_factory=factory).load()
        with runtime.switch_to_secondary():
            second_catalogue = active_transaction_catalogue_repository(repository_factory=factory).load()

    assert tuple(first_catalogue.transactions) == (first_transaction.transaction_id,)
    assert second_catalogue.transactions == {}


def test_active_transaction_catalogue_repository_rejects_missing_active_bucket() -> None:
    with pytest.raises(LedgerNoActiveBucketError) as raised:
        active_transaction_catalogue_repository(
            repository_factory=lambda bucket_id: TransactionCatalogueRepository(bucket_id=bucket_id),
        )
    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
