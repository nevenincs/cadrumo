"""Ordinary catalogue reads decode rows as authenticated; every other path validates in full.

A row the store decrypts under its AEAD binding skips only the derived-id
re-hash. These tests run the real encrypted store: the authenticated read equals
the fully validated read, a row that no longer derives its id still loads but is
refused by the explicit re-validation read and by the write path, the field-level
refusals still fire on stored rows, and a row of another inner schema version is
validated in full.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.transactions.errors import StoredTransactionDriftError
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.repository import transaction_object_key
from .....domain.transactions.tests.varied_ledger_seed import varied_transactions
from ...storage.envelope.contract import Envelope
from ...storage.errors import EnvelopeVersionError
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "17171717-1717-4171-8171-171717171717"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _shape(transaction: Transaction) -> tuple[str, str, frozenset[str]]:
    return (
        transaction.model_dump_json(),
        repr(sorted((name, str(value)) for name, value in transaction.model_dump(mode="python").items())),
        frozenset(transaction.model_fields_set),
    )


def _rewrite_row(
    objects: SecureObjectRepository,
    bucket_id: str,
    transaction_id: str,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    """Re-encrypt one stored row with an edited envelope, as only a key holder could."""
    object_key = transaction_object_key(bucket_id, transaction_id)
    record = objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key,
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    mutate(envelope)
    objects.save(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=object_key,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )


def _stored_payload(objects: SecureObjectRepository, bucket_id: str, transaction_id: str) -> bytes:
    record = objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        transaction_object_key(bucket_id, transaction_id),
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    return record.payload


def _rehome_raw(envelope: dict[str, object]) -> None:
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    raw = payload["raw"]
    assert isinstance(raw, dict)
    raw["description"] = "rewritten after the id was derived"


@contextmanager
def _seeded(tmp_path: Path, count: int = 96) -> Generator[tuple[SecureObjectRepository, TransactionCatalogue]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        saved = TransactionCatalogue.from_transactions(varied_transactions(count))
        TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository).save(saved)
        yield profile.repository, saved


def test_an_authenticated_load_equals_a_fully_validated_load(tmp_path: Path) -> None:
    with _seeded(tmp_path) as (objects, saved):
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        authenticated = repository.load()
        full = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_fully_validated()
        by_ids = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_by_ids(
            saved.transactions,
        )

        assert list(authenticated.transactions) == list(full.transactions)
        assert set(authenticated.transactions) == set(saved.transactions)
        for transaction_id, row in saved.transactions.items():
            assert authenticated.transactions[transaction_id] == full.transactions[transaction_id] == row
            assert _shape(authenticated.transactions[transaction_id]) == _shape(full.transactions[transaction_id])
            assert _shape(by_ids.transactions[transaction_id]) == _shape(full.transactions[transaction_id])


def test_a_row_that_no_longer_derives_its_id_is_refused_off_the_authenticated_read(tmp_path: Path) -> None:
    """The authenticated read skips the re-hash; re-validation, the write path and imports do not."""
    with _seeded(tmp_path, count=4) as (objects, saved):
        target = next(iter(saved.values()))
        _rewrite_row(objects, _BUCKET_ID, target.transaction_id, _rehome_raw)
        stored = _stored_payload(objects, _BUCKET_ID, target.transaction_id)

        loaded = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()
        targeted = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_by_ids(
            [target.transaction_id],
        )
        opened = loaded.transactions[target.transaction_id]
        assert opened.raw.description == "rewritten after the id was derived"
        assert targeted.transactions[target.transaction_id] == opened

        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_fully_validated()
        with pytest.raises(ValidationError):
            TransactionCatalogueRepository(
                bucket_id=_BUCKET_ID, objects=objects
            ).replace_if_current_with_secure_object_writes(opened, opened.model_copy(update={"notes": "edited"}), ())
        with pytest.raises(ValidationError):
            Envelope[Transaction].model_validate_json(stored)
        with pytest.raises(ValidationError):
            Transaction.model_validate(opened.model_dump())


def _mutate_payload(field: str, value: object) -> Callable[[dict[str, object]], None]:
    def mutate(envelope: dict[str, object]) -> None:
        payload = envelope["payload"]
        assert isinstance(payload, dict)
        if field.startswith("raw."):
            raw = payload["raw"]
            assert isinstance(raw, dict)
            raw[field.removeprefix("raw.")] = value
        else:
            payload[field] = value

    return mutate


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw.amount", "-1.00"),
        ("direction", "sideways"),
        ("modified_at", "2026-01-01T00:00:00"),
        ("concepto_ingreso", "bogus_concepto"),
        ("cash_accounting_treatment", "deferred"),
        ("unexpected", "value"),
    ],
)
def test_a_stored_row_still_meets_every_kept_refusal(tmp_path: Path, field: str, value: object) -> None:
    """Amount direction, enum membership, UTC typing, registry vocabulary and shape refuse a stored row."""
    with _seeded(tmp_path, count=4) as (objects, saved):
        target = next(row for row in saved.values() if row.cash_accounting_treatment == "none")
        _rewrite_row(objects, _BUCKET_ID, target.transaction_id, _mutate_payload(field, value))

        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()
        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_by_ids(
                [target.transaction_id],
            )


def _older_inner_version(envelope: dict[str, object]) -> None:
    envelope["schema_version"] = TRANSACTION_CATALOGUE_NAMESPACE.schema_version - 1


def _current_inner_version(envelope: dict[str, object]) -> None:
    envelope["schema_version"] = TRANSACTION_CATALOGUE_NAMESPACE.schema_version


def test_a_row_of_another_inner_schema_version_is_validated_in_full(tmp_path: Path) -> None:
    """The authenticated-row exemption covers only the current schema version."""
    with _seeded(tmp_path, count=4) as (objects, saved):
        intact, rehomed = list(saved.values())[:2]
        _rewrite_row(objects, _BUCKET_ID, intact.transaction_id, _older_inner_version)

        with pytest.raises(EnvelopeVersionError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()

        def older_and_rehomed(envelope: dict[str, object]) -> None:
            _older_inner_version(envelope)
            _rehome_raw(envelope)

        _rewrite_row(objects, _BUCKET_ID, intact.transaction_id, _current_inner_version)
        _rewrite_row(objects, _BUCKET_ID, rehomed.transaction_id, older_and_rehomed)
        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()
        with pytest.raises(StoredTransactionDriftError):
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_by_ids(
                [rehomed.transaction_id],
            )
