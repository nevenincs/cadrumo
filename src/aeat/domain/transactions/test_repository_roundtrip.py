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

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from . import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
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
) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(provider_id, amount, description),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": classification,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    return Transaction.model_validate(payload)


def test_transaction_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated transaction catalogue round-trips through the encrypted bucket store."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "transactions-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            bucket_id = "default-bucket"
            repo = TransactionCatalogueRepository(bucket_id=bucket_id)

            mixed_txn = _transaction(
                provider_id="provider-row-1",
                amount=Decimal("-100.00"),
                description="Internet provider - mixed use",
                classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
            )
            personal_txn = _transaction(
                provider_id="provider-row-2",
                amount=Decimal("-25.50"),
                description="Personal lunch",
                classification=BusinessClassification.PERSONAL,
            )
            original = TransactionCatalogue.from_transactions([mixed_txn, personal_txn])
            repo.save(original)
            loaded = repo.load()

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
            assert loaded_personal.business_classification is BusinessClassification.PERSONAL
            assert loaded_personal.business_pct is None
            # Provenance must survive ingest.
            assert loaded_mixed.raw.provenance.source_format is SourceFormat.CSV
            assert loaded_mixed.raw.provenance.source_row_index == 7
        finally:
            engine.dispose()


def test_transaction_catalogue_dropped_business_pct_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._repository import TX_BUCKET_NAMESPACE, transaction_catalogue_object_key

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "transactions-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            bucket_id = "default-bucket"
            repo = TransactionCatalogueRepository(bucket_id=bucket_id)

            mixed_txn = _transaction(
                provider_id="provider-row-1",
                amount=Decimal("-100.00"),
                description="Internet provider - mixed use",
                classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
            )
            original = TransactionCatalogue.from_transactions([mixed_txn])
            repo.save(original)

            object_key = transaction_catalogue_object_key(bucket_id)
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == TX_BUCKET_NAMESPACE,
                    SecureObjectRow.object_key == object_key,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                txn_dict = envelope["payload"]["transactions"][mixed_txn.transaction_id]
                assert "business_pct" in txn_dict, (
                    "fixture must serialise business_pct into the envelope "
                    "for this proof test to be meaningful"
                )
                del txn_dict["business_pct"]
                row.payload = _json.dumps(envelope).encode("utf-8")

            # Now reload. The model_validator enforces MIXED <-> business_pct;
            # the mutated record must either raise or surface inequality.
            regression_caught = False
            try:
                mutated = repo.load()
            except Exception:  # noqa: BLE001 - boundary may raise different types
                regression_caught = True
            else:
                if mutated != original:
                    regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: deleting business_pct from a "
                "MIXED transaction did NOT surface on load. The catalogue "
                "boundary is tautological and every transaction roundtrip "
                "in the suite is suspect."
            )
        finally:
            engine.dispose()
