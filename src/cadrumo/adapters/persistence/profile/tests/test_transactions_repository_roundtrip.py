"""Strict roundtrip across the encrypted TransactionCatalogueRepository.

Persists :class:`TransactionCatalogue` under
``cadrumo.domain.transactions.bucket`` (per profile bucket) at
``SensitivityClass.FINANCIAL``.

Anti-tautology: builds a two-transaction catalogue with non-default
``business_classification`` (``MIXED`` with explicit ``business_pct``),
distinct categories, and provenance metadata, then loads it back.
Per-field witnesses pin business_pct, category_id, taxable_base and
the keying invariant (mapping keys equal transaction_id).

See Also:
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
        Encrypted per-transaction repository exercised by these roundtrips.
    :class:`~domain.transactions.TransactionCatalogue`
        Domain catalogue persisted under the bucket-scoped transaction namespace.
    :class:`~domain.iva.IvaCashAccountingPaymentEvidence`
        Cash-accounting payment evidence whose Decimal/date fields must survive
        JSON-shaped persistence roundtrips.

Transaction storage is bucket-scoped (never a cross-profile shared store) and
every persisted record stays encrypted at rest under the profile's
secure-object substrate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core import StorageCategory, storage_path
from .....domain.iva import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import StoredTransactionDriftError
from .....domain.transactions.models import Transaction, TransactionCatalogue, derive_transaction_id
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....tests.secure_sql import isolated_runtime_profile
from ...storage import SecureObjectRepository, SensitivityClass
from ...storage.bucket import bucket_paths
from ...storage.errors import ClassificationError, EnvelopeVersionError, SecureObjectRowIdentityError
from ...storage.sql import SecureObjectRawRow
from ..transactions import transaction_object_key
from ..transactions import TX_BUCKET_NAMESPACE, TransactionCatalogueRepository, _TX_CATALOGUE_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


def _raw(provider_id: str, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
        "source_jurisdiction": "ES",
        "group_label": None,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    if import_fingerprint is not None:
        payload["import_fingerprint"] = import_fingerprint
    return Transaction.model_validate(payload)


def _transaction_secure_row(
    repository: SecureObjectRepository,
    *,
    bucket_id: str,
    transaction_id: str,
) -> SecureObjectRawRow:
    from ...storage.crypto.encrypted_columns import secure_object_key_digest
    from ..transactions import TX_BUCKET_NAMESPACE, transaction_object_key

    object_digest = secure_object_key_digest(transaction_object_key(bucket_id, transaction_id))
    rows = [
        row
        for row in repository.iter_all_records_raw()
        if row.namespace == TX_BUCKET_NAMESPACE and row.object_key == object_digest
    ]
    assert len(rows) == 1
    return rows[0]


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
    assert (bucket_paths(tmp_path / "cadrumo-storage", _BUCKET_ID).database_file).is_file()


def test_transaction_catalogue_persists_only_to_the_secure_database_object(
    tmp_path: Path,
) -> None:
    """A saved catalogue never reaches the plaintext ``financial/transactions`` directory.

    :data:`StorageCategory.FINANCIAL_TRANSACTIONS` now declares
    no consumer at all. Its only one was the master-key rotation sweep,
    deleted with the shared-master model it belonged to, and even then that
    module only walked the directory looking for ``.envelope.json`` files to
    re-encrypt -- it was a sweep, never a writer. :class:`TransactionCatalogueRepository`'s own
    module docstring states "no plaintext transaction row, JSON catalogue,
    or envelope file lands on disk"; this proves it, mirroring
    ``test_put_file_reads_source_but_persists_only_secure_database_object``
    for the attachments store. The assertion routes through
    :func:`storage_path` rather than a literal so a future taxonomy subpath
    move is tracked automatically instead of silently passing vacuously
    against a stale path.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="provider-dormancy-check",
            amount=Decimal("42.00"),
            description="Dormancy-check transaction",
            classification=BusinessClassification.BUSINESS,
        )
        original = TransactionCatalogue.from_transactions([txn])
        repo.save(original)

        assert TransactionCatalogueRepository(bucket_id=profile.bucket_id).load() == original
        assert not storage_path(StorageCategory.FINANCIAL_TRANSACTIONS).exists()


def test_transaction_catalogue_refuses_foreign_payload_rekeyed_under_an_indexed_row(
    tmp_path: Path,
) -> None:
    """A valid foreign transaction re-filed under another indexed row is never projected."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        indexed = _transaction(
            provider_id="provider-row-indexed",
            amount=Decimal("100.00"),
            description="Indexed transaction",
            classification=BusinessClassification.BUSINESS,
        )
        foreign = _transaction(
            provider_id="provider-row-foreign",
            amount=Decimal("200.00"),
            description="Foreign transaction payload",
            classification=BusinessClassification.PERSONAL,
        )
        original = TransactionCatalogue.from_transactions([indexed, foreign])
        repo.save(original)

        # Baseline: full and date-indexed reads both faithfully project genuine
        # encrypted rows before the identity substitution below.
        assert TransactionCatalogueRepository(bucket_id=profile.bucket_id).load() == original
        assert (
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_for_date_range(
                date(2024, 4, 1),
                date(2024, 4, 30),
            )
            == original
        )

        indexed_key = transaction_object_key(profile.bucket_id, indexed.transaction_id)
        foreign_key = transaction_object_key(profile.bucket_id, foreign.transaction_id)
        indexed_record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            indexed_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        foreign_record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            foreign_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert indexed_record is not None
        assert foreign_record is not None

        # This is a real encrypted-store substitution, not a model double: the
        # foreign envelope remains valid for its own derived transaction ID but
        # is deliberately written under the indexed row's natural key.
        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=indexed_key,
            classification=indexed_record.classification,
            schema_version=indexed_record.schema_version,
            written_at=foreign_record.written_at,
            payload=foreign_record.payload,
            write_provenance="test.transactions_repository.foreign_payload_rekey",
        )

        expected_identifier = transaction_object_key(profile.bucket_id, indexed.transaction_id)
        with pytest.raises(SecureObjectRowIdentityError) as full_read:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert full_read.value.expected_identifier == expected_identifier

        with pytest.raises(SecureObjectRowIdentityError) as date_indexed_read:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_for_date_range(
                date(2024, 4, 1),
                date(2024, 4, 30),
            )
        assert date_indexed_read.value.expected_identifier == expected_identifier

        with pytest.raises(SecureObjectRowIdentityError) as partitioned_read:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(
                date(2024, 4, 1),
                date(2024, 4, 30),
            )
        assert partitioned_read.value.expected_identifier == expected_identifier


def test_transaction_catalogue_load_uses_json_mode_for_derived_id_roundtrip(
    tmp_path: Path,
) -> None:
    import json as _json

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    created = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
    modified = datetime(2024, 6, 1, 16, 45, tzinfo=UTC)
    transaction = Transaction.model_validate(
        {
            "raw": _raw("provider-json-mode", Decimal("121.00"), "Consulting invoice"),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.50"),
            "source_jurisdiction": "ES",
            "group_label": "Client A",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "created_at": created,
            "modified_at": modified,
        },
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repo.save(TransactionCatalogue.from_transactions([transaction]))

        object_key = transaction_object_key(profile.bucket_id, transaction.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        persisted = envelope["payload"]
        assert persisted["transaction_id"] == transaction.transaction_id
        assert isinstance(persisted["raw"]["booked_date"], str)
        assert isinstance(persisted["business_pct"], str)
        assert isinstance(persisted["created_at"], str)

        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    loaded_transaction = loaded.transactions[transaction.transaction_id]
    assert loaded_transaction == transaction
    assert loaded_transaction.transaction_id == derive_transaction_id(loaded_transaction.raw)
    assert loaded_transaction.business_pct == Decimal("0.50")
    assert loaded_transaction.iva_rate == Decimal("0.21")
    assert loaded_transaction.created_at == created
    assert loaded_transaction.modified_at == modified


def test_transaction_catalogue_save_skips_unchanged_secure_object_rows(
    tmp_path: Path,
) -> None:
    """Saving one changed transaction does not re-upsert unchanged transaction rows."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        changed = _transaction(
            provider_id="provider-row-changed",
            amount=Decimal("100.00"),
            description="Internet provider",
            classification=BusinessClassification.BUSINESS,
        )
        unchanged = _transaction(
            provider_id="provider-row-unchanged",
            amount=Decimal("25.50"),
            description="Personal lunch",
            classification=BusinessClassification.PERSONAL,
        )
        repo.save(TransactionCatalogue.from_transactions([changed, unchanged]))

        before_changed = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=changed.transaction_id,
        )
        before_unchanged = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=unchanged.transaction_id,
        )

        updated_changed = changed.model_copy(
            update={
                "group_label": "internet",
                "modified_at": datetime(2024, 4, 15, 12, 0, tzinfo=UTC),
            },
        )
        assert updated_changed.transaction_id == changed.transaction_id

        repo.save(TransactionCatalogue.from_transactions([updated_changed, unchanged]))

        after_changed = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=changed.transaction_id,
        )
        after_unchanged = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=unchanged.transaction_id,
        )

    assert after_unchanged.revision_id == before_unchanged.revision_id
    assert after_unchanged.payload_hash == before_unchanged.payload_hash
    assert after_unchanged.ciphertext_hash == before_unchanged.ciphertext_hash
    assert after_changed.revision_id != before_changed.revision_id
    assert after_changed.payload_hash != before_changed.payload_hash
    assert after_changed.previous_revision_id == before_changed.revision_id
    assert after_changed.previous_payload_hash == before_changed.payload_hash


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

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

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
        assert exc_info.value.context == {"bucket_id": profile.bucket_id}


def test_transaction_catalogue_inner_classification_mismatch_is_structured(
    tmp_path: Path,
) -> None:
    """Inner envelope classification drift must surface as structured storage integrity."""

    import json as _json

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

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

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

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
                "group_label": None,
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


def test_transaction_catalogue_rejects_missing_source_jurisdiction_key(
    tmp_path: Path,
) -> None:
    """A persisted envelope lacking source_jurisdiction is not current schema.

    Anti-tautology proof for the no-legacy contract: surgically delete
    the source_jurisdiction key from a previously-persisted envelope and
    reload. The load must refuse the malformed record instead of silently
    defaulting the regulatory source axis.
    """

    import json as _json

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        spanish_txn = Transaction.model_validate(
            {
                "raw": _raw("provider-row-es", Decimal("50.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
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
            "fixture must serialise source_jurisdiction into the envelope for the missing-key proof to be meaningful"
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

        with pytest.raises(StoredTransactionDriftError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert "source_jurisdiction" in str(exc_info.value.original_exception)


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
                "source_jurisdiction": "ES",
                "group_label": "Proyecto Acme",
            },
        )
        original = TransactionCatalogue.from_transactions([labelled])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_txn = loaded.transactions[labelled.transaction_id]
    assert loaded_txn.group_label == "Proyecto Acme"


def test_transaction_catalogue_rejects_missing_group_label_key(
    tmp_path: Path,
) -> None:
    """A persisted envelope lacking group_label is not current schema.

    Anti-tautology proof for the no-legacy contract: surgically delete the
    group_label key from a previously-persisted envelope and reload. The load
    must refuse the malformed record instead of silently defaulting the
    operator grouping axis.
    """

    import json as _json

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        labelled = Transaction.model_validate(
            {
                "raw": _raw("provider-row-grp", Decimal("90.00"), "Billete tren Proyecto Acme"),
                "direction": TransactionDirection.OUTGOING,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
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
            "fixture must serialise group_label into the envelope for the missing-key proof to be meaningful"
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

        with pytest.raises(StoredTransactionDriftError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()
        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert "group_label" in str(exc_info.value.original_exception)


def test_transaction_catalogue_preserves_nonnegative_amount_and_direction(
    tmp_path: Path,
) -> None:
    """A non-negative amount + authoritative direction round-trip through storage.

    The ledger-amount-direction convention stores ``raw.amount`` as a
    non-negative magnitude and carries the flow solely in
    :attr:`~domain.transactions.Transaction.direction`. This pins both halves through the encrypted
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
                "group_label": None,
                "business_classification": BusinessClassification.PERSONAL,
                "source_jurisdiction": "ES",
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
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
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

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        created = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
        modified = datetime(2024, 6, 1, 16, 45, tzinfo=UTC)
        stamped = Transaction.model_validate(
            {
                "raw": _raw("provider-row-ts", Decimal("77.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
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
            "fixture must serialise created_at into the envelope for the missing-key proof to be meaningful"
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


def test_transaction_timestamp_witness_rejects_missing_modified_at_from_decoded_row(
    tmp_path: Path,
) -> None:
    """The timestamp witness rejects decoded-row drift before legacy defaults can apply."""

    import json as _json

    from ..transactions import transaction_object_key
    from ..transactions import TX_BUCKET_NAMESPACE, _TX_CATALOGUE_VERSION, _decode_persisted_transaction_row, _validate_persisted_transaction_timestamps

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        created = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
        modified = datetime(2024, 6, 1, 16, 45, tzinfo=UTC)
        stamped = Transaction.model_validate(
            {
                "raw": _raw("provider-row-ts-modified", Decimal("77.00"), "Compra material oficina"),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "created_at": created,
                "modified_at": modified,
            },
        )
        repo.save(TransactionCatalogue.from_transactions([stamped]))

        object_key = transaction_object_key(profile.bucket_id, stamped.transaction_id)
        record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert record is not None
        decoded = _decode_persisted_transaction_row(record.payload)
        assert decoded is not None
        payload_value = decoded["payload"]
        assert isinstance(payload_value, dict)
        txn_dict = {str(key): value for key, value in payload_value.items()}
        assert txn_dict.get("modified_at") is not None, (
            "fixture must serialise modified_at into the envelope for the missing-key proof to be meaningful"
        )
        del txn_dict["modified_at"]
        decoded["payload"] = txn_dict

        with pytest.raises(ValidationError) as witness_exc:
            _validate_persisted_transaction_timestamps(decoded)
        assert "modified_at" in str(witness_exc.value)

        profile.repository.save(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(decoded).encode("utf-8"),
        )

        with pytest.raises(StoredTransactionDriftError) as exc_info:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

        assert isinstance(exc_info.value.original_exception, ValidationError)
        assert "modified_at" in str(exc_info.value.original_exception)


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

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

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


def test_load_then_save_reuses_the_memoized_hash_for_an_unchanged_row(
    tmp_path: Path,
) -> None:
    """The SAME repository instance's load-then-save skips re-serializing an untouched row.

    Proves the identity-keyed write-path hash cache is actually consulted, not
    merely present: after ``load()`` populates ``_serialized_hash_cache`` keyed
    by ``id(transaction)``, saving the exact catalogue that ``load()`` returned
    must reach the cache-hit branch in ``_reconcile`` -- proven by
    monkeypatching ``_serialise_transaction`` to raise if it is ever called for
    the untouched row and asserting the row's revision stays byte-identical.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        unchanged = _transaction(
            provider_id="provider-row-unchanged-cache",
            amount=Decimal("42.00"),
            description="Untouched row",
            classification=BusinessClassification.BUSINESS,
        )
        repo.save(TransactionCatalogue.from_transactions([unchanged]))

        before = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=unchanged.transaction_id,
        )

        reload_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        loaded = reload_repo.load()
        assert loaded.transactions[unchanged.transaction_id] is not unchanged

        reload_repo.save(loaded)

        after = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=unchanged.transaction_id,
        )

    assert after.revision_id == before.revision_id
    assert after.payload_hash == before.payload_hash


def test_cache_miss_on_content_edited_replacement_instance_still_detects_the_change(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: a content-edited row is NEVER served from a stale cache entry.

    ``Transaction`` is strict-frozen, so an edit (``model_copy(update=...)``)
    always produces a NEW object -- its ``id()`` is absent from
    ``_serialized_hash_cache`` (a genuine cache miss), so ``_reconcile`` must
    fall through to fresh serialize-and-hash and detect the real content
    change, even though the row shares the SAME repository instance that
    loaded the original.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        original = _transaction(
            provider_id="provider-row-edited",
            amount=Decimal("60.00"),
            description="Row that gets edited",
            classification=BusinessClassification.BUSINESS,
        )
        repo.save(TransactionCatalogue.from_transactions([original]))

        before = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=original.transaction_id,
        )

        reload_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        loaded = reload_repo.load()
        loaded_transaction = loaded.transactions[original.transaction_id]
        edited = loaded_transaction.model_copy(
            update={
                "group_label": "edited-after-load",
                "modified_at": datetime(2024, 5, 1, 8, 0, tzinfo=UTC),
            },
        )
        assert edited is not loaded_transaction
        assert edited.transaction_id == loaded_transaction.transaction_id

        reload_repo.save(TransactionCatalogue.from_transactions([edited]))

        after = _transaction_secure_row(
            profile.repository,
            bucket_id=profile.bucket_id,
            transaction_id=original.transaction_id,
        )

    assert after.revision_id != before.revision_id
    assert after.payload_hash != before.payload_hash
    assert after.previous_revision_id == before.revision_id


def test_loaded_envelope_bytes_equal_fresh_serialization_of_the_same_instance(
    tmp_path: Path,
) -> None:
    """Pins the write-path cache's equivalence assumption: stored bytes == fresh re-serialization.

    The cache is only sound if the plaintext envelope bytes ``load()``
    persisted at write time are byte-identical to what
    ``_serialise_transaction`` would recompute for the SAME loaded instance.
    This directly proves that equality, not just the cache's observable
    skip-behaviour.
    """

    from ..transactions import _TX_CATALOGUE_VERSION, TX_BUCKET_NAMESPACE, transaction_object_key

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="provider-row-equivalence",
            amount=Decimal("77.00"),
            description="Equivalence pin",
            classification=BusinessClassification.BUSINESS,
        )
        repo.save(TransactionCatalogue.from_transactions([txn]))

        object_key = transaction_object_key(profile.bucket_id, txn.transaction_id)
        stored_record = profile.repository.load(
            TX_BUCKET_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        assert stored_record is not None

        reload_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        loaded = reload_repo.load()
        loaded_transaction = loaded.transactions[txn.transaction_id]

        fresh_bytes = reload_repo._serialise_transaction(loaded_transaction)

    assert fresh_bytes == stored_record.payload


def test_transaction_catalogue_preserves_populated_cash_accounting_evidence_through_encrypted_storage(
    tmp_path: Path,
) -> None:
    """A populated ``cash_accounting_payment_evidence`` tuple survives the encrypted roundtrip.

    The prior gap: every roundtrip in this suite exercised only the
    empty-tuple default for the criterio-de-caja axis, so the exact shape
    that broke (a save/load cycle over a NON-EMPTY payment-evidence tuple,
    ``246ba49ae4``, fixed by ``f514824d18``) was untested. Builds a
    TAXPAYER_REGIME row satisfying every ``_enforce_cash_accounting_axis``
    invariant (a real operation date, a payment-evidence tuple whose totals
    stay within taxable_base/iva_amount/recargo_amount, and a payment_date at
    or before the statutory 31 December fallback), saves it, reloads through a
    FRESH repository instance, and asserts strict equality plus per-entry
    witnesses on the reconstituted evidence tuple.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        cash_sale = Transaction.model_validate(
            {
                "raw": _raw("provider-cash-accounting", Decimal("1210.00"), "Venta criterio de caja"),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "iva_category": IvaCategory.DOMESTIC_GENERAL,
                "cash_accounting_treatment": IvaCashAccountingTreatment.TAXPAYER_REGIME,
                "operation_date": date(2026, 3, 20),
                "cash_accounting_payment_evidence": (
                    IvaCashAccountingPaymentEvidence(
                        payment_date=date(2026, 4, 15),
                        taxable_base=Decimal("600.00"),
                        iva_amount=Decimal("126.00"),
                    ),
                    IvaCashAccountingPaymentEvidence(
                        payment_date=date(2026, 6, 10),
                        taxable_base=Decimal("400.00"),
                        iva_amount=Decimal("84.00"),
                    ),
                ),
            },
        )
        original = TransactionCatalogue.from_transactions([cash_sale])
        repo.save(original)
        loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert loaded == original
    loaded_txn = loaded.transactions[cash_sale.transaction_id]
    assert loaded_txn.cash_accounting_treatment is IvaCashAccountingTreatment.TAXPAYER_REGIME
    assert loaded_txn.operation_date == date(2026, 3, 20)
    assert len(loaded_txn.cash_accounting_payment_evidence) == 2
    first, second = loaded_txn.cash_accounting_payment_evidence
    assert isinstance(first, IvaCashAccountingPaymentEvidence)
    assert first.payment_date == date(2026, 4, 15)
    assert first.taxable_base == Decimal("600.00")
    assert first.iva_amount == Decimal("126.00")
    assert first.recargo_amount == Decimal("0")
    assert second.payment_date == date(2026, 6, 10)
    assert second.taxable_base == Decimal("400.00")
    assert second.iva_amount == Decimal("84.00")
    total_base = sum((evidence.taxable_base for evidence in loaded_txn.cash_accounting_payment_evidence), Decimal("0"))
    total_iva = sum((evidence.iva_amount for evidence in loaded_txn.cash_accounting_payment_evidence), Decimal("0"))
    assert total_base == Decimal("1000.00")
    assert total_iva == Decimal("210.00")
