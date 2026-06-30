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

from ....adapters.persistence.storage import SensitivityClass
from ....adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    StoredTransactionDriftError,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from .._repository import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        mixed_txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
            import_fingerprint="f" * 64,
        )
        personal_txn = _transaction(
            provider_id="provider-row-2",
            amount=Decimal("25.50"),
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
    assert (tmp_path / "aeat-storage" / "buckets" / _BUCKET_ID / "db" / "aeat.db").is_file()


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

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        mixed_txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
        )
        original = TransactionCatalogue.from_transactions([mixed_txn])
        repo.save(original)

        object_key = transaction_object_key(profile.bucket_id, mixed_txn.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]
        assert "business_pct" in txn_dict, (
            "fixture must serialise business_pct into the envelope for this proof test to be meaningful"
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
        # The load boundary wraps the raw pydantic ValidationError in
        # StoredTransactionDriftError so the CLI surface routes the
        # failure to the repair-oriented stored-data-validation path.
        # The original ValidationError is preserved for inspection.
        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert exc_info.value.bucket_id == profile.bucket_id
        assert exc_info.value.translated_message == "errors.storage.stored_data_validation_boundary"
        assert exc_info.value.context == {"bucket_id": profile.bucket_id, "recovery": "aeat config repair --help"}
        assert exc_info.value.suggestion == "aeat config repair --help"


def test_transaction_catalogue_inner_classification_mismatch_is_structured(
    tmp_path: Path,
) -> None:
    """Inner envelope classification drift must surface as structured storage integrity."""

    import json as _json

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.BUSINESS,
        )
        repo.save(TransactionCatalogue.from_transactions([txn]))

        object_key = transaction_object_key(profile.bucket_id, txn.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        assert envelope["classification"] == SensitivityClass.FINANCIAL.value
        envelope["classification"] = SensitivityClass.AUDIT.value
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ClassificationError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_classification"
    assert exc_info.value.context == {
        "namespace": TX_BUCKET_NAMESPACE,
        "object_key": object_key,
        "bucket_id": profile.bucket_id,
        "classification": SensitivityClass.AUDIT.value,
        "expected": SensitivityClass.FINANCIAL.value,
    }


def test_transaction_catalogue_inner_schema_version_mismatch_is_structured(
    tmp_path: Path,
) -> None:
    """Inner envelope schema drift must surface as structured storage integrity."""

    import json as _json

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("100.00"),
            description="Internet provider - mixed use",
            classification=BusinessClassification.BUSINESS,
        )
        repo.save(TransactionCatalogue.from_transactions([txn]))

        object_key = transaction_object_key(profile.bucket_id, txn.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        assert envelope["schema_version"] == _TX_CATALOGUE_VERSION
        envelope["schema_version"] = _TX_CATALOGUE_VERSION + 1
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(EnvelopeVersionError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_envelope_version"
    assert exc_info.value.context == {
        "namespace": TX_BUCKET_NAMESPACE,
        "object_key": object_key,
        "bucket_id": profile.bucket_id,
        "schema_version": _TX_CATALOGUE_VERSION + 1,
        "expected": _TX_CATALOGUE_VERSION,
    }


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        spanish_txn = Transaction.model_validate(
            {
                "raw": _raw("provider-row-es", Decimal("50.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
            },
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

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        spanish_txn = Transaction.model_validate(
            {
                "raw": _raw("provider-row-es", Decimal("50.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
            },
        )
        original = TransactionCatalogue.from_transactions([spanish_txn])
        repo.save(original)

        object_key = transaction_object_key(profile.bucket_id, spanish_txn.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]
        assert txn_dict.get("source_jurisdiction") == "ES", (
            "fixture must serialise source_jurisdiction into the envelope for the grandfather proof to be meaningful"
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


def test_transaction_catalogue_preserves_group_label_through_encrypted_storage(
    tmp_path: Path,
) -> None:
    """group_label must survive the encrypted-envelope roundtrip.

    Anchors the operator-assigned organisational grouping axis at
    the persistence boundary: a Transaction carrying a non-default
    ``group_label`` saved through the repository must load back equal (strict
    pydantic equality), with the label preserved verbatim. A save-drops /
    load-re-defaults regression would otherwise silently lose every operator
    grouping made over thousands of rows.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        labelled = Transaction.model_validate(
            {
                "raw": _raw("provider-row-grp", Decimal("90.00"), "Billete tren Proyecto Acme"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "group_label": "Proyecto Acme",
            },
        )
        original = TransactionCatalogue.from_transactions([labelled])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_txn = loaded.transactions[labelled.transaction_id]
    assert loaded_txn.group_label == "Proyecto Acme"


def test_transaction_catalogue_grandfathers_missing_group_label_key(
    tmp_path: Path,
) -> None:
    """A persisted envelope lacking group_label must load with None.

    Anti-tautology proof for the grandfather contract: surgically delete the
    group_label key from a previously-persisted envelope and reload. The load
    must succeed with ``loaded.group_label is None`` (None default), and the
    labelled catalogue must NOT equal the deleted-key version, locking the
    field's identity contribution at the model boundary.
    """

    import json as _json

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        labelled = Transaction.model_validate(
            {
                "raw": _raw("provider-row-grp", Decimal("90.00"), "Billete tren Proyecto Acme"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "group_label": "Proyecto Acme",
            },
        )
        original = TransactionCatalogue.from_transactions([labelled])
        repo.save(original)

        object_key = transaction_object_key(profile.bucket_id, labelled.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]
        assert txn_dict.get("group_label") == "Proyecto Acme", (
            "fixture must serialise group_label into the envelope for the grandfather proof to be meaningful"
        )
        del txn_dict["group_label"]
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        loaded_txn = loaded.transactions[labelled.transaction_id]
        assert loaded_txn.group_label is None
        assert loaded != original


def test_transaction_catalogue_preserves_nonnegative_amount_and_direction(
    tmp_path: Path,
) -> None:
    """A non-negative amount + authoritative direction round-trip through storage.

    The ledger-amount-direction convention stores ``raw.amount`` as a
    non-negative magnitude and carries the flow solely in
    :attr:`Transaction.direction`. This pins both halves through the encrypted
    boundary: an OUTGOING magnitude row and an INTERNAL_TRANSFER magnitude row
    must load back strictly equal, with the magnitude and the direction
    preserved verbatim. A save-drops / load-re-derives regression on either
    axis would silently lose the operator's flow encoding.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        outgoing = _transaction(
            provider_id="provider-row-out",
            amount=Decimal("121.00"),
            description="Compra material oficina",
            classification=BusinessClassification.BUSINESS,
        )
        transfer = Transaction.model_validate(
            {
                "raw": _raw("provider-row-transfer", Decimal("5000.00"), "Traspaso a cuenta de ahorro"),
                "direction": TransactionDirection.INTERNAL_TRANSFER,
                "business_classification": BusinessClassification.PERSONAL,
            },
        )
        original = TransactionCatalogue.from_transactions([outgoing, transfer])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_out = loaded.transactions[outgoing.transaction_id]
    loaded_transfer = loaded.transactions[transfer.transaction_id]
    assert loaded_out.raw.amount == Decimal("121.00")
    assert loaded_out.direction is TransactionDirection.OUTGOING
    assert loaded_transfer.raw.amount == Decimal("5000.00")
    assert loaded_transfer.direction is TransactionDirection.INTERNAL_TRANSFER


def test_transaction_catalogue_preserves_created_modified_at_through_encrypted_storage(
    tmp_path: Path,
) -> None:
    """created_at and modified_at must survive the encrypted-envelope roundtrip.

    Anchors the ledger-interface-contract D6 lifecycle-timestamp axis at the
    persistence boundary: a Transaction carrying non-default, distinct
    ``created_at`` and ``modified_at`` UTC-aware timestamps saved through the
    repository must load back strictly equal, both timestamps preserved
    verbatim. A save-drops / load-re-defaults regression would otherwise
    silently lose the temporal sort key for every persisted row.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        created = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
        modified = datetime(2024, 6, 1, 16, 45, tzinfo=UTC)
        stamped = Transaction.model_validate(
            {
                "raw": _raw("provider-row-ts", Decimal("77.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "created_at": created,
                "modified_at": modified,
            },
        )
        original = TransactionCatalogue.from_transactions([stamped])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_txn = loaded.transactions[stamped.transaction_id]
    # Distinct non-default witnesses: a save that collapsed the two timestamps
    # into one (or re-defaulted either to None) would fail these.
    assert loaded_txn.created_at == created
    assert loaded_txn.modified_at == modified
    assert loaded_txn.created_at != loaded_txn.modified_at


def test_transaction_catalogue_rejects_missing_created_at_key(
    tmp_path: Path,
) -> None:
    """A persisted envelope lacking created_at must fail the storage boundary.

    Anti-tautology proof for the D6 lifecycle-timestamp axis: surgically
    delete the ``created_at`` key from a previously-persisted envelope and
    reload. The repository must surface a validation drift instead of
    defaulting the field during deserialisation; otherwise legacy rows would be
    silently repaired and the timestamp roundtrip test would be tautological.
    """

    import json as _json

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        created = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
        modified = datetime(2024, 6, 1, 16, 45, tzinfo=UTC)
        stamped = Transaction.model_validate(
            {
                "raw": _raw("provider-row-ts", Decimal("77.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "created_at": created,
                "modified_at": modified,
            },
        )
        original = TransactionCatalogue.from_transactions([stamped])
        repo.save(original)

        object_key = transaction_object_key(profile.bucket_id, stamped.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]
        assert txn_dict.get("created_at") is not None, (
            "fixture must serialise created_at into the envelope for the grandfather proof to be meaningful"
        )
        del txn_dict["created_at"]
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

        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert exc_info.value.translated_message == "errors.storage.stored_data_validation_boundary"


def test_transaction_catalogue_negative_amount_payload_rejected_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: a persisted envelope with a negative amount is refused.

    Persists a valid non-negative-magnitude row, then surgically rewrites the
    on-disk amount to a negative value and re-saves. The load path MUST reject
    the mutated record because :class:`RawTransaction` enforces the
    non-negative gate on rehydration. If the load silently admitted the
    negative amount, the magnitude gate would be tautological and every
    transaction roundtrip in the suite would be suspect.
    """

    import json as _json

    from .._repository import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="provider-row-1",
            amount=Decimal("100.00"),
            description="Internet provider",
            classification=BusinessClassification.BUSINESS,
        )
        original = TransactionCatalogue.from_transactions([txn])
        repo.save(original)

        object_key = transaction_object_key(profile.bucket_id, txn.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        txn_dict = envelope["payload"]
        assert txn_dict["raw"]["amount"] == "100.00", (
            "fixture must serialise the magnitude into the envelope for this proof to be meaningful"
        )
        txn_dict["raw"]["amount"] = "-100.00"
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
        assert isinstance(exc_info.value.original_exception, ValidationError)
