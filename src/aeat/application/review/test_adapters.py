"""Per-adapter unit tests for the review-queue source adapters.

Each adapter is exercised through its public single-source path:
the happy path with a synthetic source, the missing-source path,
and the severity-mapping invariants.
"""

from __future__ import annotations

from ...core.errors import BaseSeverity
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.sql import dispose_engine
from ...application.user_profile._testing import register_minimal_profile
from ...application.workflow._persistence import workflow_state_repository
from ...core.config import Settings
from ...core.i18n import Translatable as tr
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ...domain.invoices._repository import InvoiceCatalogueRepository
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ...domain.transactions._repository import TransactionCatalogueRepository
from ..filing import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValidationFinding,
    ModeloValue,
    ModeloValueKind,
)
from . import (
    FindingReviewItem,
    InvoiceReviewItem,
    ReviewSeverity,
    TransactionReviewItem,
    drafts_pending,
    invoices_pending,
    transactions_pending,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ── shared helpers ────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _secure_object_backend(tmp_path: Path):
    old_database_url = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()
    try:
        yield
    finally:
        if old_database_url is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = old_database_url
        dispose_engine()


def _build_settings(tmp_path: Path) -> Settings:
    """Build a Settings instance with every disk root anchored at tmp_path."""
    return Settings(
        aeat_financial_txs_dir=tmp_path / "transactions",
        aeat_invoices_dir=tmp_path / "invoices",
        aeat_attachments_dir=tmp_path / "attachments",
        aeat_inbox_dir=tmp_path / "inbox",
        aeat_inbox_pdf_dir=tmp_path / "inbox-pdfs",
        aeat_drafts_dir=tmp_path / "drafts",
    )


def _seed_active_profile() -> None:
    """Register the minimal placeholder profile so drafts match the active tax id."""
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "00000000T"},
        )
    )


def _summary(text: str = "demo") -> tr:
    return tr("translation")


def _schema_version(modelo: str = "130") -> str:
    return f"test-schema-{modelo}"


# ── transactions adapter ──────────────────────────────────────────


def _raw(*, source_row_index: int = 1, description: str = "Office") -> RawTransaction:
    return RawTransaction(
        transaction_id=f"prov-{source_row_index}",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.34"),
        currency="EUR",
        counterparty=None,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=source_row_index,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"Concepto": description},
    )


def _transaction(
    *,
    source_row_index: int = 1,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    description: str = "Office supplies",
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(source_row_index=source_row_index, description=description),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
        }
    )


def test_transactions_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert transactions_pending(settings, bucket_id="test") == ()


def test_transactions_pending_filters_unclassified(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(source_row_index=1),  # NOT_YET_PROCESSED
            _transaction(source_row_index=2, classification=BusinessClassification.BUSINESS),
        )
    )
    TransactionCatalogueRepository(bucket_id="test").save(catalogue)
    items = transactions_pending(settings, bucket_id="test")
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, TransactionReviewItem)
    assert item.severity is ReviewSeverity.NORMAL
    assert item.modelo is None
    assert item.source.business_classification is BusinessClassification.NOT_YET_PROCESSED


def test_transactions_pending_drills_into_ledger_owned_review_command(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions((_transaction(source_row_index=1),))
    TransactionCatalogueRepository(bucket_id="test").save(catalogue)

    items = transactions_pending(settings, bucket_id="test")

    assert len(items) == 1
    assert items[0].drill_command == f"aeat app ledger review --id {items[0].source.transaction_id}"
    assert " edit " not in items[0].drill_command
    assert "--set" not in items[0].drill_command


def test_transactions_pending_reads_only_requested_bucket(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    other_bucket_catalogue = TransactionCatalogue.from_transactions((_transaction(source_row_index=1),))
    TransactionCatalogueRepository(bucket_id="other-profile").save(other_bucket_catalogue)

    assert transactions_pending(settings, bucket_id="active-profile") == ()
    assert len(transactions_pending(settings, bucket_id="other-profile")) == 1


@pytest.mark.parametrize(
    ("state", "expected_severity"),
    [
        (BusinessClassification.NOT_YET_PROCESSED, ReviewSeverity.NORMAL),
        (BusinessClassification.PROCESSED_UNCLASSIFIED, ReviewSeverity.HIGH),
        (BusinessClassification.FAILED_VALIDATION, ReviewSeverity.CRITICAL),
    ],
)
def test_transactions_pending_severity_mapping(
    tmp_path: Path,
    state: BusinessClassification,
    expected_severity: ReviewSeverity,
) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions((_transaction(source_row_index=1, classification=state),))
    TransactionCatalogueRepository(bucket_id="test").save(catalogue)
    items = transactions_pending(settings, bucket_id="test")
    assert len(items) == 1
    assert items[0].severity is expected_severity


def test_transactions_pending_skips_skipped_by_rule(tmp_path: Path) -> None:
    """``SKIPPED_BY_RULE`` rows have a final disposition and must not appear."""
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(
                source_row_index=1,
                classification=BusinessClassification.SKIPPED_BY_RULE,
            ),
            _transaction(
                source_row_index=2,
                classification=BusinessClassification.BUSINESS,
            ),
        )
    )
    TransactionCatalogueRepository(bucket_id="test").save(catalogue)
    assert transactions_pending(settings, bucket_id="test") == ()


# ── invoices adapter ──────────────────────────────────────────────


def _invoice_line() -> InvoiceLine:
    return InvoiceLine(
        description="Consultoría",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )


def _invoice(
    *,
    invoice_number: str = "INV-001",
    payment_status: PaymentStatus = PaymentStatus.PENDING,
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    line = _invoice_line()
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
            "payment_status": payment_status,
            "linked_transaction_ids": linked_transaction_ids,
        }
    )


def test_invoices_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert invoices_pending(settings) == ()


@pytest.mark.parametrize(
    ("payment_status", "linked", "expected_severity"),
    [
        (PaymentStatus.PENDING, (), ReviewSeverity.HIGH),  # unmatched dominates
        (PaymentStatus.OVERDUE, ("a" * 64,), ReviewSeverity.HIGH),
        (PaymentStatus.PENDING, ("a" * 64,), ReviewSeverity.NORMAL),
        (PaymentStatus.PARTIALLY_PAID, ("a" * 64,), ReviewSeverity.NORMAL),
    ],
)
def test_invoices_pending_severity_mapping(
    tmp_path: Path,
    payment_status: PaymentStatus,
    linked: tuple[str, ...],
    expected_severity: ReviewSeverity,
) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices(
        (_invoice(payment_status=payment_status, linked_transaction_ids=linked),)
    )
    InvoiceCatalogueRepository().save(catalogue)
    items = invoices_pending(settings)
    assert len(items) == 1
    assert items[0].severity is expected_severity


def test_invoices_pending_skips_paid_and_cancelled(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices(
        (
            _invoice(
                invoice_number="INV-A",
                payment_status=PaymentStatus.PAID,
                linked_transaction_ids=("a" * 64,),
            ),
            _invoice(
                invoice_number="INV-B",
                payment_status=PaymentStatus.CANCELLED,
                linked_transaction_ids=("b" * 64,),
            ),
        )
    )
    InvoiceCatalogueRepository().save(catalogue)
    assert invoices_pending(settings) == ()


def test_invoices_pending_emits_invoice_review_item(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))
    InvoiceCatalogueRepository().save(catalogue)
    items = invoices_pending(settings)
    assert len(items) == 1
    assert isinstance(items[0], InvoiceReviewItem)


# ── drafts adapter ────────────────────────────────────────────────


def _draft(
    *,
    draft_id: str,
    modelo: str = "130",
    period: str = "2026Q1",
    status: ModeloDraftStatus = ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    findings: tuple[ModeloValidationFinding, ...] = (),
) -> ModeloDraft:
    values = (
        ModeloValue(
            casilla_id="03",
            value=Decimal("0"),
            kind=ModeloValueKind.LITERAL,
            source="test",
        ),
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=status,
        values=values,
        findings=findings,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        schema_version=_schema_version(modelo),
    )


def _write_draft(settings: Settings, draft: ModeloDraft) -> Path:
    """Persist ``draft`` through the ModeloDraftRepository (ciphertext-at-rest)."""
    from ...domain.filing import ModeloDraftRepository

    del settings
    repository = ModeloDraftRepository()
    repository.save(draft)
    return repository.envelope_path_for(draft.draft_id)


def test_drafts_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert drafts_pending(settings) == ()


def test_drafts_pending_emits_one_finding_per_finding(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    findings = (
        ModeloValidationFinding(
            casilla_id="03",
            severity=BaseSeverity.ERROR,
            code="casilla-out-of-range",
            message=_summary("range"),
        ),
        ModeloValidationFinding(
            casilla_id="04",
            severity=BaseSeverity.WARNING,
            code="casilla-required-missing",
            message=_summary("missing"),
        ),
        ModeloValidationFinding(
            casilla_id="05",
            severity=BaseSeverity.INFO,
            code="casilla-info-note",
            message=_summary("info"),
        ),
    )
    _write_draft(settings, _draft(draft_id="d1", findings=findings))
    items = drafts_pending(settings)
    assert len(items) == 3
    severities = {item.severity for item in items}
    assert severities == {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH, ReviewSeverity.INFO}
    for item in items:
        assert isinstance(item, FindingReviewItem)
        assert item.draft_id == "d1"


def test_drafts_pending_emits_placeholder_for_draft_status(tmp_path: Path) -> None:
    """`status=DRAFT` with no findings must emit the same placeholder as VALIDATED."""
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    _write_draft(settings, _draft(draft_id="d_draft", status=ModeloDraftStatus.BORRADOR))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL
    summary_key = items[0].summary
    assert summary_key == "review.filing.draft_placeholder_summary"


def test_drafts_pending_emits_placeholder_when_no_findings_but_status_pending(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    _write_draft(settings, _draft(draft_id="d2", status=ModeloDraftStatus.VALIDADO))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL


def test_drafts_pending_emits_high_severity_for_approval_stale(tmp_path: Path) -> None:
    """`status=APPROVAL_STALE` must surface as a HIGH-severity finding row."""
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    _write_draft(settings, _draft(draft_id="d_stale", status=ModeloDraftStatus.APROBACION_CADUCADA))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.HIGH
    assert items[0].draft_id == "d_stale"
    summary_key = items[0].summary
    assert summary_key == "review.filing.stale_approval_summary"
    assert items[0].drill_command.startswith("aeat app review show ")


def test_drafts_pending_skips_ready_drafts_with_no_findings(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    _write_draft(settings, _draft(draft_id="d3", status=ModeloDraftStatus.LISTO_PARA_PRESENTAR))
    assert drafts_pending(settings) == ()


def test_drafts_pending_dedups_identical_finding_triples(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _seed_active_profile()
    finding = ModeloValidationFinding(
        casilla_id="03",
        severity=BaseSeverity.ERROR,
        code="casilla-out-of-range",
        message=_summary("dup"),
    )
    # Same finding repeated twice — dedup should collapse to one.
    _write_draft(
        settings,
        _draft(draft_id="d4", findings=(finding, finding)),
    )
    items = drafts_pending(settings)
    assert len(items) == 1