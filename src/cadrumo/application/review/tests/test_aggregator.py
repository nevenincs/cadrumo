"""End-to-end tests for the cross-source review-queue aggregator."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.config import Settings
from ....core.errors import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.filing import (
    ModeloDraft,
    ModeloValidationFinding,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from .. import (
    ReviewItemKind,
    ReviewQueue,
    ReviewSeverity,
    ReviewState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_REVIEW_FINDING_CASILLA: CasillaId = validated_casilla_id("03", surface="_REVIEW_FINDING_CASILLA")
_PROFILE_ID = "23232323-2323-4232-8232-232323232323"


def _summary(text: str = "demo") -> tr:
    return tr("translation")


_TEST_REVISION_ID = "test-revision"


def _schema_version(modelo: str = "130") -> str:
    return registry_schema_version(modelo=modelo, revision_id=_TEST_REVISION_ID)


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        cadrumo_financial_txs_dir=tmp_path / "transactions",
        cadrumo_invoices_dir=tmp_path / "invoices",
        cadrumo_attachments_dir=tmp_path / "attachments",
        cadrumo_drafts_dir=tmp_path / "probe-drafts",
    )


def _seed_all_sources(tmp_path: Path) -> Settings:
    """Materialise one pending item in every source under tmp_path."""
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id=_PROFILE_ID,
            overrides={"identity.tax_id": "00000000T"},
        )

        raw = RawTransaction(
            provider_transaction_id="prov-1",
            booked_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            amount=Decimal("12.34"),
            currency="EUR",
            counterparty=None,
            description="Bank fee",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="a" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
                provider_name="csv",
            ),
            raw_fields={"Concepto": "Bank fee"},
        )
        transaction = Transaction.model_validate(
            {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
        )
        catalogue = TransactionCatalogue.from_transactions((transaction,))
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)

        line = InvoiceLine(
            description="Consultoría",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            subtotal=Decimal("100.00"),
            iva_rate=IvaRate.RATE_21,
            iva_amount=Decimal("21.00"),
        )
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
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
            },
        )
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((invoice,)))

        finding = ModeloValidationFinding(
            casilla_id=_REVIEW_FINDING_CASILLA,
            severity=BaseSeverity.ERROR,
            code="casilla-out-of-range",
            message=_summary("range"),
        )
        period = Period.from_year_and_code(2026, "1T")
        snapshot_ref = RegistrySnapshotRef(
            modelo="130",
            revision_id=_TEST_REVISION_ID,
            modelo_year=period.filing_year,
            period=period.registry_token,
        )
        values = (
            ModeloValue(
                casilla_id=_REVIEW_FINDING_CASILLA,
                value=Decimal("0"),
                kind=ModeloValueKind.LITERAL,
                source="test",
            ),
        )
        draft = ModeloDraft(
            draft_id=compute_modelo_draft_id(
                modelo="130",
                period=period,
                profile_tax_id="00000000T",
                snapshot_ref=snapshot_ref,
                values=values,
            ),
            modelo="130",
            period=period,
            profile_tax_id="00000000T",
            subject_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            status=ModeloDraftStatus.BORRADOR,
            values=values,
            findings=(finding,),
            created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            schema_version=_schema_version(),
        )
        from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository

        ModeloDraftRepository().save(draft)

    return settings


def _collect(settings: Settings, **kwargs: Any) -> tuple[Any, ...]:
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        return ReviewQueue.collect(settings, bucket_id=_PROFILE_ID, **kwargs)


def test_collect_returns_one_item_per_source(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings)
    kinds = {item.kind for item in items}
    assert kinds == {
        ReviewItemKind.TRANSACTION,
        ReviewItemKind.INVOICE,
        ReviewItemKind.FINDING,
    }
    assert len(items) == 3


def test_collect_sorts_critical_before_normal(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings)
    severities = [item.severity for item in items]
    # CRITICAL comes first; NORMAL last; the seeded items are CRITICAL x1, HIGH x1, NORMAL x1.
    assert severities[0] is ReviewSeverity.CRITICAL
    assert severities[-1] is ReviewSeverity.NORMAL


def test_collect_filters_by_kind(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings, kinds=frozenset({ReviewItemKind.FINDING}))
    kinds = {item.kind for item in items}
    assert kinds == {ReviewItemKind.FINDING}
    assert len(items) == 1


def test_collect_filters_by_modelo(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings, modelo="130")
    # Transaction and invoice carry no modelo so they are excluded.
    assert {item.kind for item in items} == {ReviewItemKind.FINDING}


def test_collect_state_all_matches_pending_today(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    pending = _collect(settings, state=ReviewState.PENDING)
    every = _collect(settings, state=ReviewState.ALL)
    assert pending == every


def test_collect_returns_empty_tuple_when_no_sources_present(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        assert ReviewQueue.collect(settings, bucket_id=_PROFILE_ID) == ()
