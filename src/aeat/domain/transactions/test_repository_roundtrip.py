"""Strict roundtrip across the encrypted TransactionCatalogueRepository.

Persists :class:`TransactionCatalogue` under
``aeat.domain.transactions.bucket`` (per profile bucket) at
``SensitivityClass.FINANCIAL``.

Anti-tautology: builds a two-transaction catalogue with non-default
``business_classification`` (``MIXED`` with explicit ``business_pct``),
distinct categories, and provenance metadata, then loads it back.
Per-field witnesses pin business_pct, category_id, taxable_base and
the keying invariant (mapping keys equal transaction_id).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...adapters.persistence.storage import SensitivityClass
from ...tests.secure_sql import isolated_runtime_profile
from . import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    StoredTransactionDriftError,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ._repository import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _raw(provider_id: str, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    description: str,
    classification: BusinessClassification,
    business_pct: Decimal | None = None,
    import_fingerprint: str | None = None,
) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(provider_id, amount, description),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": classification,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    if import_fingerprint is not None:
        payload["import_fingerprint"] = import_fingerprint
    return Transaction.model_validate(payload)


def test_transaction_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated transaction catalogue round-trips through the encrypted bucket store."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default-bucket") as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        mixed_txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("-100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
            import_fingerprint="f" * 64,
        )
        personal_txn = _transaction(
            provider_id="provider-row-2",
            amount=Decimal("-25.50"),
            description="Personal lunch",
            classification=BusinessClassification.PERSONAL,
        )
        original = TransactionCatalogue.from_transactions([mixed_txn, personal_txn])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    assert set(loaded.transactions.keys()) == {
        mixed_txn.transaction_id,
        personal_txn.transaction_id,
    }
    loaded_mixed = loaded.transactions[mixed_txn.transaction_id]
    loaded_personal = loaded.transactions[personal_txn.transaction_id]
    # Per-field witnesses on non-default identity-bearing axes.
    assert loaded_mixed.business_classification is BusinessClassification.MIXED
    assert loaded_mixed.business_pct == Decimal("0.60")
    assert loaded_mixed.import_fingerprint == "f" * 64
    assert loaded_personal.business_classification is BusinessClassification.PERSONAL
    assert loaded_personal.business_pct is None
    assert loaded_personal.import_fingerprint is None
    # Provenance must survive ingest.
    assert loaded_mixed.raw.provenance.source_format is SourceFormat.CSV
    assert loaded_mixed.raw.provenance.source_row_index == 7
    assert (tmp_path / "aeat-storage" / "buckets" / "default-bucket" / "db" / "aeat.db").is_file()


def test_transaction_catalogue_dropped_business_pct_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: deleting ``business_pct`` on a MIXED row must surface.

    Persists a MIXED transaction (which requires a non-None
    ``business_pct`` per the model_validator), then surgically deletes
    the ``business_pct`` key from the encrypted JSON envelope and re-
    saves. The load path must reject the mutated record: the
    invariant ``business_classification == MIXED <-> business_pct
    is not None`` is enforced on the rehydrated model. If the load
    silently succeeds with ``business_pct=None``, the catalogue
    boundary is tautological and every transaction roundtrip in the
    suite is suspect.
    """

    import json as _json

    from ._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_catalogue_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default-bucket") as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        mixed_txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("-100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
        )
        original = TransactionCatalogue.from_transactions([mixed_txn])
        repo.save(original)

        object_key = transaction_catalogue_object_key(profile.bucket_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]["transactions"][mixed_txn.transaction_id]
        assert "business_pct" in txn_dict, (
            "fixture must serialise business_pct into the envelope "
            "for this proof test to be meaningful"
        )
        del txn_dict["business_pct"]
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(StoredTransactionDriftError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        # Wave-3 W09.P41.S214: the load boundary now wraps the raw pydantic
        # ValidationError in StoredTransactionDriftError so the CLI surface
        # routes the failure to the repair-oriented stored-data-validation
        # path. The original ValidationError is preserved for inspection.
        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert exc_info.value.bucket_id == profile.bucket_id


def test_transaction_catalogue_preserves_source_jurisdiction_through_encrypted_storage(
    tmp_path: Path,
) -> None:
    """source_jurisdiction must survive the encrypted-envelope roundtrip.

    Anchors the source-jurisdiction axis at the persistence boundary: a
    Transaction carrying ``source_jurisdiction="ES"`` saved through the
    repository must load back equal (strict pydantic equality), with the
    field preserved verbatim. Foundational for the IRNR scope filter and
    the Art. 93 LIRPF Beckham base filter.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default-bucket") as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        spanish_txn = Transaction.model_validate(
            {
                "raw": _raw("provider-row-es", Decimal("-50.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
            }
        )
        original = TransactionCatalogue.from_transactions([spanish_txn])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_txn = loaded.transactions[spanish_txn.transaction_id]
    assert loaded_txn.source_jurisdiction == "ES"


def test_transaction_catalogue_grandfathers_missing_source_jurisdiction_key(
    tmp_path: Path,
) -> None:
    """A persisted envelope lacking source_jurisdiction must load with None.

    Anti-tautology proof for the grandfather contract: surgically delete
    the source_jurisdiction key from a previously-persisted envelope and
    reload. The load must succeed with ``loaded.source_jurisdiction is
    None`` because the field carries a None default — operator catalogues
    written before the axis was introduced must continue to deserialise
    cleanly. The original-with-ES catalogue must NOT equal the deleted-key
    version, locking the field's identity contribution.
    """

    import json as _json

    from ._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_catalogue_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default-bucket") as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        spanish_txn = Transaction.model_validate(
            {
                "raw": _raw("provider-row-es", Decimal("-50.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
            }
        )
        original = TransactionCatalogue.from_transactions([spanish_txn])
        repo.save(original)

        object_key = transaction_catalogue_object_key(profile.bucket_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]["transactions"][spanish_txn.transaction_id]
        assert txn_dict.get("source_jurisdiction") == "ES", (
            "fixture must serialise source_jurisdiction into the envelope "
            "for the grandfather proof to be meaningful"
        )
        del txn_dict["source_jurisdiction"]
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        loaded_txn = loaded.transactions[spanish_txn.transaction_id]
        assert loaded_txn.source_jurisdiction is None
        # Strict-inequality witness: the field carries identity weight at
        # the model boundary, so the grandfathered catalogue must NOT
        # equal the original ES-bearing catalogue.
        assert loaded != original
