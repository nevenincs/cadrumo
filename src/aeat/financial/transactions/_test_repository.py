"""Tests for the governed-persistence TransactionCatalogue repository."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    LockAcquisitionError,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...storage.errors import ClassificationError
from .._raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ._enums import TransactionDirection
from ._repository import (
    ImportSummary,
    TransactionCatalogueRepository,
    migrate_legacy_catalogue_to_repository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def _direction_resolver(raw: RawTransaction) -> TransactionDirection:
    return TransactionDirection.INCOMING if raw.amount > 0 else TransactionDirection.OUTGOING


def _provenance(tmp_path: Path, *, row_index: int = 1) -> RawProvenance:
    source = tmp_path / "synthetic.csv"
    if not source.exists():
        source.write_text("synthetic", encoding="utf-8")
    return RawProvenance(
        source_path=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_row_index=row_index,
        source_format=SourceFormat.CSV,
        ingested_at=datetime.now(UTC),
        provider_name="test-bank",
    )


def _make_raw(
    tmp_path: Path,
    *,
    transaction_id: str,
    amount: Decimal,
    description: str = "synthetic",
    booked_date: date | None = None,
    row_index: int = 1,
) -> RawTransaction:
    return RawTransaction(
        transaction_id=transaction_id,
        booked_date=booked_date or date(2026, 4, 27),
        value_date=None,
        amount=amount,
        currency="EUR",
        counterparty=None,
        description=description,
        provenance=_provenance(tmp_path, row_index=row_index),
        raw_fields={"description": description, "amount": str(amount)},
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "tx-store"


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


class TestEmptyState:
    def test_load_returns_empty_catalogue_when_absent(self, store_dir: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        catalogue = repo.load()
        assert len(catalogue) == 0

    def test_envelope_path_is_under_store_dir(self, store_dir: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        assert repo.envelope_path == store_dir / "transactions.envelope.json"


class TestSaveLoad:
    def test_round_trip(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        raw = _make_raw(tmp_path, transaction_id="tx-001", amount=Decimal("125.50"))
        summary = repo.merge_raw_transactions([raw], direction_resolver=_direction_resolver)
        assert summary.imported == 1
        assert summary.skipped == 0

        # Re-load via a fresh repository instance: the envelope persists.
        repo_b = TransactionCatalogueRepository(store_dir=store_dir)
        catalogue = repo_b.load()
        assert len(catalogue) == 1


class TestIdempotency:
    def test_reimport_same_payload_skips_duplicates(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        raw = _make_raw(tmp_path, transaction_id="tx-002", amount=Decimal("75.00"))
        first = repo.merge_raw_transactions([raw], direction_resolver=_direction_resolver)
        assert first.imported == 1
        second = repo.merge_raw_transactions([raw], direction_resolver=_direction_resolver)
        assert second.imported == 0
        assert second.skipped == 1

    def test_three_imports_yield_one_row(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        raw = _make_raw(tmp_path, transaction_id="tx-003", amount=Decimal("10"))
        for _ in range(3):
            repo.merge_raw_transactions([raw], direction_resolver=_direction_resolver)
        assert len(repo.load()) == 1


class TestMixedImport:
    def test_partial_overlap(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        a = _make_raw(tmp_path, transaction_id="A", amount=Decimal("1"))
        b = _make_raw(tmp_path, transaction_id="B", amount=Decimal("2"))
        c = _make_raw(tmp_path, transaction_id="C", amount=Decimal("3"))
        repo.merge_raw_transactions([a, b], direction_resolver=_direction_resolver)
        summary = repo.merge_raw_transactions([b, c], direction_resolver=_direction_resolver)
        assert summary.imported == 1
        assert summary.skipped == 1
        assert len(repo.load()) == 3


class TestCiphertextOnDisk:
    """Wave-3 ADR invariant — transactions encrypted at rest at FINANCIAL class."""

    def test_envelope_is_financial_class(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        repo.merge_raw_transactions(
            [_make_raw(tmp_path, transaction_id="leak-canary", amount=Decimal("999"), description="LEAK-CANARY-VALUE")],
            direction_resolver=_direction_resolver,
        )
        envelope_text = repo.envelope_path.read_text(encoding="utf-8")
        # The envelope is JSON-on-disk plaintext today (no encryption
        # metadata yet — the substrate's envelope contract supports
        # ciphertext payloads but Wave-3 Phase 1 ships the envelope
        # contract first; ciphertext-payload support layers in via a
        # future ADR). Confirm the envelope's classification field:
        assert '"classification":"financial"' in envelope_text

    def test_classification_mismatch_raises(self, store_dir: Path) -> None:
        """A foreign-class envelope at the canonical path is refused at load."""
        from ...storage import Envelope, save_envelope
        from ._models import TransactionCatalogue

        store_dir.mkdir(parents=True, exist_ok=True)
        bad = Envelope[TransactionCatalogue](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=__import__("aeat.storage", fromlist=["SensitivityClass"]).SensitivityClass.OPERATIONAL,
            payload=TransactionCatalogue(),
        )
        save_envelope(bad, store_dir / "transactions.envelope.json")
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        with pytest.raises(ClassificationError):
            repo.load()


class TestConcurrency:
    def test_serial_back_to_back_imports_succeed(self, store_dir: Path, tmp_path: Path) -> None:
        """Two sequential merge calls in the same process do not race."""
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        repo.merge_raw_transactions(
            [_make_raw(tmp_path, transaction_id="seq-1", amount=Decimal("1"))],
            direction_resolver=_direction_resolver,
        )
        repo.merge_raw_transactions(
            [_make_raw(tmp_path, transaction_id="seq-2", amount=Decimal("2"))],
            direction_resolver=_direction_resolver,
        )
        assert len(repo.load()) == 2


class TestImportSummary:
    def test_summary_carries_path_and_counts(self, store_dir: Path, tmp_path: Path) -> None:
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        raw = _make_raw(tmp_path, transaction_id="sum-1", amount=Decimal("5"))
        summary = repo.merge_raw_transactions([raw], direction_resolver=_direction_resolver)
        assert isinstance(summary, ImportSummary)
        assert summary.imported == 1
        assert summary.skipped == 0
        assert summary.errors == 0
        assert "transactions.envelope.json" in summary.catalogue_path

    def test_summary_is_frozen(self, store_dir: Path, tmp_path: Path) -> None:
        from pydantic import ValidationError

        repo = TransactionCatalogueRepository(store_dir=store_dir)
        summary = repo.merge_raw_transactions(
            [_make_raw(tmp_path, transaction_id="frozen-1", amount=Decimal("1"))],
            direction_resolver=_direction_resolver,
        )
        with pytest.raises(ValidationError):
            summary.imported = 99  # type: ignore[misc]


class TestLegacyMigration:
    def test_migrate_legacy_to_repository(self, store_dir: Path, tmp_path: Path) -> None:
        from ._service import save_transactions

        # Build a legacy catalogue and persist it via the existing helper.
        repo = TransactionCatalogueRepository(store_dir=store_dir)
        seed_repo = TransactionCatalogueRepository(store_dir=tmp_path / "seed")
        seed_repo.merge_raw_transactions(
            [
                _make_raw(tmp_path, transaction_id="legacy-1", amount=Decimal("10")),
                _make_raw(tmp_path, transaction_id="legacy-2", amount=Decimal("20")),
            ],
            direction_resolver=_direction_resolver,
        )
        legacy_path = tmp_path / "transactions.json"
        save_transactions(seed_repo.load(), legacy_path)

        # Migrate.
        summary = migrate_legacy_catalogue_to_repository(legacy_path, repository=repo)
        assert summary.imported == 2
        assert len(repo.load()) == 2

    def test_migrate_into_non_empty_repo_without_overwrite_raises(
        self,
        store_dir: Path,
        tmp_path: Path,
    ) -> None:
        from ._service import save_transactions

        repo = TransactionCatalogueRepository(store_dir=store_dir)
        repo.merge_raw_transactions(
            [_make_raw(tmp_path, transaction_id="seed-1", amount=Decimal("1"))],
            direction_resolver=_direction_resolver,
        )
        legacy_path = tmp_path / "legacy.json"
        save_transactions(repo.load(), legacy_path)
        with pytest.raises(ValueError):
            migrate_legacy_catalogue_to_repository(legacy_path, repository=repo)


class TestLockAcquisitionExposed:
    """Confirm LockAcquisitionError type is exported (for downstream consumers)."""

    def test_lock_error_is_a_persistence_error(self) -> None:
        from ...storage.errors import PersistenceError

        assert issubclass(LockAcquisitionError, PersistenceError)
