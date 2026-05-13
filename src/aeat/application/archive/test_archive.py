"""Round-trip tests for the archive subsystem.

Exercises the storage layer end-to-end: save typed domain models via
their per-namespace repositories, archive everything, wipe the
backend, restore, and confirm every model loads back equal-by-value.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...domain.invoices._enums import InvoiceKind, IvaRate, PaymentStatus
from ...domain.invoices._models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices._repository import InvoiceCatalogueRepository
from ...domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ...domain.transactions._repository import TransactionCatalogueRepository
from . import (
    ArchiveBundle,
    ArchiveConflictError,
    ConflictPolicy,
    RestoreOutcome,
    all_archive_adapters,
    create_archive,
    restore_archive,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Per-test SQLite + ephemeral master key so list_records sees only fresh rows.

    The shared ``var/aeat.db`` carries rows encrypted under master keys
    from previous sessions; iterating those rows under a freshly minted
    ephemeral key fails the AEAD tag check. Every archive test isolates
    the backend at a tmp-path SQLite file and disposes the engine cache
    on entry and exit so :func:`get_engine` re-reads the env var.
    """
    previous_db = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()

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
        dispose_engine()
        if previous_db is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = previous_db


def _invoice(invoice_number: str = "INV-001") -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Service",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
        }
    )


def _transaction(provider_id: str = "row-1") -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="payment",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "payment"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.INCOMING},
    )


def _wipe_namespace(namespace: str) -> None:
    """Delete every secure object under a namespace via list+delete."""
    import json as _json

    repo = SecureObjectRepository()
    for adapter in all_archive_adapters():
        if adapter.namespace != namespace:
            continue
        for stored in tuple(
            repo.list_records(
                namespace,
                expected_class=adapter.classification,
                max_supported_version=adapter.schema_version,
            )
        ):
            extractor = adapter.extract_object_key
            if extractor is None:
                # Hashed-passthrough namespaces: the natural key is not
                # available; tests that wipe these should delete via
                # the SQL row's ``hashed_object_key`` directly.
                continue
            payload_dict = _json.loads(stored.payload.decode("utf-8")).get("payload", {})
            object_key = extractor(payload_dict)
            repo.delete(namespace, object_key)


class TestRegistry:
    """The default registry registers every namespace named in the spec."""

    def test_built_in_namespaces_are_registered(self) -> None:
        names = {adapter.namespace for adapter in all_archive_adapters()}
        # Domain user-data namespaces that ship with adapters today.
        assert {
            "aeat.domain.invoices",
            "aeat.domain.transactions",
            "aeat.domain.filing.drafts",
            "aeat.domain.filing.amendments",
            "aeat.domain.justificante.metadata",
            "aeat.domain.submission.records",
            "aeat.domain.usage_ratios",
            "aeat.domain.attachments.manifests",
            "aeat.application.filing.history",
            "aeat.application.profile.bucket",
        }.issubset(names)


class TestProfileBucketArchive:
    """Profile buckets round-trip through the archive subsystem."""

    def test_profile_bucket_round_trip(self) -> None:
        from ..profile._models import ProfileRecord
        from ..profile._repository import PROFILE_BUCKET_NAMESPACE, profile_bucket_repository

        repository = profile_bucket_repository()
        saved = repository.save(
            ProfileRecord(
                name="kent",
                values={"tax.id": "00000000T", "activity": "design", "iva.regime": "GENERAL"},
            )
        )

        bundle = create_archive(namespaces=(PROFILE_BUCKET_NAMESPACE,))
        assert len(bundle.records) == 1
        record = bundle.records[0]
        assert record.object_key == "profile-bucket:kent"
        assert record.hashed_object_key_b64 is None

        assert repository.delete("kent") is True
        assert repository.load("kent") is None

        report = restore_archive(bundle, conflict_policy=ConflictPolicy.OVERWRITE)
        assert all(entry.outcome is RestoreOutcome.WROTE for entry in report.entries)

        restored = repository.load("kent")
        assert restored is not None
        assert restored.name == saved.name
        assert restored.values == saved.values
        assert restored.updated_at.isoformat() == saved.updated_at.isoformat()


class TestFilingHistoryAdapter:
    """The filing-history adapter survives a save -> archive -> restore loop."""

    def test_filing_history_round_trip(self) -> None:
        from datetime import UTC
        from datetime import datetime as _dt

        from ...application.filing._history_models import FilingHistory, FilingHistoryEntry
        from ...application.filing._history_repository import FilingHistoryRepository
        from ...domain._identifiers import ModeloIdentifier

        original = FilingHistory(
            entries=(
                FilingHistoryEntry(
                    modelo=ModeloIdentifier("130"),
                    period="2026Q1",
                    submitted_at=_dt(2026, 4, 20, 12, 0, tzinfo=UTC),
                    status="submitted",
                ),
            )
        )
        FilingHistoryRepository().save("130", original)

        bundle = create_archive(namespaces=("aeat.application.filing.history",))
        assert len(bundle.records) == 1
        record = bundle.records[0]
        assert record.object_key == "130"

        SecureObjectRepository().delete("aeat.application.filing.history", "130")
        report = restore_archive(bundle, conflict_policy=ConflictPolicy.OVERWRITE)
        assert all(entry.outcome is RestoreOutcome.WROTE for entry in report.entries)

        reloaded = FilingHistoryRepository().load("130")
        assert reloaded == original


class TestArchiveExport:
    """Walking the live backend produces a bundle that mirrors saved state."""

    def test_empty_backend_produces_empty_bundle(self) -> None:
        bundle = create_archive()
        assert isinstance(bundle, ArchiveBundle)
        assert bundle.records == ()

    def test_export_captures_invoice_catalogue_after_save(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        bundle = create_archive()
        invoice_records = tuple(r for r in bundle.records if r.namespace == "aeat.domain.invoices")
        assert len(invoice_records) == 1
        record = invoice_records[0]
        assert record.object_key == "catalogue"
        # The decoded envelope's payload preserves invoice numbers.
        invoices_field = record.envelope_json["payload"]["invoices"]
        assert "INV-001" in {entry["invoice_number"] for entry in invoices_field.values()}

    def test_export_captures_multiple_namespaces_in_one_bundle(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        TransactionCatalogueRepository().save(TransactionCatalogue.from_transactions([_transaction()]))
        bundle = create_archive()
        namespaces = {record.namespace for record in bundle.records}
        assert {"aeat.domain.invoices", "aeat.domain.transactions"}.issubset(namespaces)

    def test_export_subset_filters_to_requested_namespaces(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        TransactionCatalogueRepository().save(TransactionCatalogue.from_transactions([_transaction()]))
        bundle = create_archive(namespaces=("aeat.domain.invoices",))
        assert {record.namespace for record in bundle.records} == {"aeat.domain.invoices"}


class TestArchiveRoundTrip:
    """Save -> archive -> wipe -> restore -> reload matches the original."""

    def test_invoice_catalogue_round_trip(self) -> None:
        original = InvoiceCatalogue.from_invoices([_invoice("INV-001"), _invoice("INV-002")])
        InvoiceCatalogueRepository().save(original)
        bundle = create_archive(namespaces=("aeat.domain.invoices",))

        _wipe_namespace("aeat.domain.invoices")
        assert InvoiceCatalogueRepository().exists() is False

        report = restore_archive(bundle, conflict_policy=ConflictPolicy.OVERWRITE)
        assert all(entry.outcome is RestoreOutcome.WROTE for entry in report.entries)
        reloaded = InvoiceCatalogueRepository().load()
        assert reloaded == original

    def test_transaction_catalogue_round_trip(self) -> None:
        original = TransactionCatalogue.from_transactions([_transaction("row-1"), _transaction("row-2")])
        TransactionCatalogueRepository().save(original)
        bundle = create_archive(namespaces=("aeat.domain.transactions",))

        _wipe_namespace("aeat.domain.transactions")
        report = restore_archive(bundle, conflict_policy=ConflictPolicy.OVERWRITE)
        assert all(entry.outcome is RestoreOutcome.WROTE for entry in report.entries)

        reloaded = TransactionCatalogueRepository().load()
        assert reloaded == original


class TestConflictPolicies:
    """Each conflict policy enforces its declared semantics."""

    def test_fail_policy_aborts_on_collision(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        bundle = create_archive(namespaces=("aeat.domain.invoices",))

        with pytest.raises(ArchiveConflictError, match=r"archive|conflict"):
            restore_archive(bundle, conflict_policy=ConflictPolicy.FAIL)

    def test_keep_policy_skips_existing_records(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice("INV-A")]))
        bundle = create_archive(namespaces=("aeat.domain.invoices",))
        # Mutate live state after exporting; KEEP must preserve the live state.
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice("INV-B")]))
        report = restore_archive(bundle, conflict_policy=ConflictPolicy.KEEP)

        assert all(entry.outcome is RestoreOutcome.SKIPPED_KEEP for entry in report.entries)
        reloaded = InvoiceCatalogueRepository().load()
        invoice_numbers = {invoice.invoice_number for invoice in reloaded.values()}
        assert invoice_numbers == {"INV-B"}

    def test_overwrite_policy_replaces_existing_records(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice("INV-A")]))
        bundle = create_archive(namespaces=("aeat.domain.invoices",))
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice("INV-B")]))
        report = restore_archive(bundle, conflict_policy=ConflictPolicy.OVERWRITE)

        assert all(entry.outcome is RestoreOutcome.OVERWROTE for entry in report.entries)
        reloaded = InvoiceCatalogueRepository().load()
        invoice_numbers = {invoice.invoice_number for invoice in reloaded.values()}
        assert invoice_numbers == {"INV-A"}


class TestBundleWireFormat:
    """The bundle JSON is portable and re-validates round-trip."""

    def test_bundle_round_trips_through_json(self) -> None:
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        bundle = create_archive(namespaces=("aeat.domain.invoices",))

        serialised = bundle.model_dump_json()
        reparsed = ArchiveBundle.model_validate_json(serialised)
        assert reparsed == bundle

    def test_bundle_records_are_sorted_for_diffability(self) -> None:
        TransactionCatalogueRepository().save(TransactionCatalogue.from_transactions([_transaction()]))
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_invoice()]))
        bundle = create_archive()

        ordering = [(record.namespace, record.object_key) for record in bundle.records]
        assert ordering == sorted(ordering)
