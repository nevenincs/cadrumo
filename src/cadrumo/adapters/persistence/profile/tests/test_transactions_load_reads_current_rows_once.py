"""An ordinary catalogue read is one addressed snapshot, never a migration pass."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import update

from ...storage.tests.secure_sql import isolated_runtime_profile
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.transactions import models as transaction_models
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import LedgerStorageError, StoredTransactionDriftError
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....domain.transactions.repository import transaction_object_key
from ...storage.crypto.encrypted_columns import secure_object_key_digest
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql import orm as _orm
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.sql.session import session_scope
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "34343434-3434-4343-8343-343434343434"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Transactions resolve their IVA vocabulary inside a caller-held operation."""
    with bundled_indexed_authority().operation():
        yield


def _transaction(provider_id: str) -> Transaction:
    booked = date(2025, 2, 3)
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=booked,
                value_date=booked,
                amount=Decimal("42.00"),
                currency="EUR",
                counterparty="Snapshot Read SL",
                description=f"snapshot read {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2025, 2, 4, 9, 0, tzinfo=UTC),
                    provider_name="snapshot read provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def _count(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
    calls: list[str] = []
    original: Callable[..., Any] = getattr(SecureObjectRepository, name)

    def counting(self: SecureObjectRepository, *args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(SecureObjectRepository, name, counting)
    return calls


def test_loading_current_rows_runs_no_migration_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        saved = TransactionCatalogue.from_transactions([_transaction("row-1"), _transaction("row-2")])
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(saved)
        migrations = _count(monkeypatch, "migrate_many_atomically")
        version_scans = _count(monkeypatch, "peek_many_schema_versions")

        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert migrations == []
    assert version_scans == []
    assert sorted(loaded.transactions) == sorted(saved.transactions)


def test_one_stale_row_still_refuses_the_whole_read(tmp_path: Path) -> None:
    """TEETH: a row below the current schema is never read as if it were current."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        stale = _transaction("row-stale")
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions([_transaction("row-current"), stale]),
        )
        stored_key = secure_object_key_digest(transaction_object_key(profile.bucket_id, stale.transaction_id))
        with session_scope(profile.repository.engine) as session:
            session.execute(
                update(_orm.SecureObjectRow)
                .where(
                    _orm.SecureObjectRow.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                    _orm.SecureObjectRow.object_key == stored_key,
                )
                .values(schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version - 1),
            )

        with pytest.raises(LedgerStorageError, match="explicit IVA authority migration before read"):
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()


def test_a_load_still_proves_every_stored_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A read from storage re-derives each row's id; appends trusting members never reach here."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions([_transaction(f"row-{index}") for index in range(3)]),
        )
        derivations: list[str] = []
        derive = transaction_models.derive_transaction_id

        def counting(*args: Any, **kwargs: Any) -> str:
            derivations.append("derived")
            return derive(*args, **kwargs)

        monkeypatch.setattr(transaction_models, "derive_transaction_id", counting)
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert len(derivations) >= 3


def test_a_tampered_stored_row_is_refused_on_load(tmp_path: Path) -> None:
    """TEETH: a stored row whose body no longer derives its id does not load."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        target = _transaction("row-tampered")
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions([_transaction("row-intact"), target]),
        )
        object_key = transaction_object_key(profile.bucket_id, target.transaction_id)
        record = profile.repository.load(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key,
            expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        )
        assert record is not None
        envelope = json.loads(record.payload.decode("utf-8"))
        envelope["payload"]["raw"]["description"] = "rewritten after the id was derived"
        profile.repository.save(
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
