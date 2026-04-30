"""Per-adapter unit tests for the review-queue source adapters.

Each adapter is exercised through its public single-source path:
the happy path with a synthetic source, the missing-source path,
and the severity-mapping invariants.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ..config import Settings
from ..filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
)
from ..financial import RawProvenance, RawTransaction, SourceFormat
from ..financial.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ..financial.invoices._repository import InvoiceCatalogueRepository
from ..financial.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ..financial.transactions._repository import TransactionCatalogueRepository
from ..i18n import Translatable
from ..sync import (
    CasillaAddedWithDefault,
    CasillaRemoved,
    DivergenceClassification,
    DivergenceRecord,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
)
from . import (
    DivergenceReviewItem,
    FindingReviewItem,
    InvoiceReviewItem,
    ReviewSeverity,
    TransactionReviewItem,
    divergences_pending,
    drafts_pending,
    invoices_pending,
    transactions_pending,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


# ── shared helpers ────────────────────────────────────────────────


def _build_settings(tmp_path: Path) -> Settings:
    """Build a Settings instance with every disk root anchored at tmp_path."""
    return Settings(
        aeat_financial_txs_dir=tmp_path / "transactions",
        aeat_invoices_dir=tmp_path / "invoices",
        aeat_attachments_dir=tmp_path / "attachments",
        aeat_sync_divergence_file_dir=tmp_path / "divergences",
        aeat_inbox_dir=tmp_path / "inbox",
        aeat_inbox_pdf_dir=tmp_path / "inbox-pdfs",
        aeat_drafts_dir=tmp_path / "drafts",
    )


def _summary(text: str = "demo") -> Translatable:
    return {"es": text, "en": text, "hu": text}


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
    assert transactions_pending(settings) == ()


def test_transactions_pending_filters_unclassified(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(source_row_index=1),  # NOT_YET_PROCESSED
            _transaction(source_row_index=2, classification=BusinessClassification.BUSINESS),
        )
    )
    TransactionCatalogueRepository(store_dir=settings.aeat_financial_txs_dir).save(catalogue)
    items = transactions_pending(settings)
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, TransactionReviewItem)
    assert item.severity is ReviewSeverity.NORMAL
    assert item.modelo is None
    assert item.source.business_classification is BusinessClassification.NOT_YET_PROCESSED


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
    TransactionCatalogueRepository(store_dir=settings.aeat_financial_txs_dir).save(catalogue)
    items = transactions_pending(settings)
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
    TransactionCatalogueRepository(store_dir=settings.aeat_financial_txs_dir).save(catalogue)
    assert transactions_pending(settings) == ()


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
    InvoiceCatalogueRepository(store_dir=settings.aeat_invoices_dir).save(catalogue)
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
    InvoiceCatalogueRepository(store_dir=settings.aeat_invoices_dir).save(catalogue)
    assert invoices_pending(settings) == ()


def test_invoices_pending_emits_invoice_review_item(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))
    InvoiceCatalogueRepository(store_dir=settings.aeat_invoices_dir).save(catalogue)
    items = invoices_pending(settings)
    assert len(items) == 1
    assert isinstance(items[0], InvoiceReviewItem)


# ── divergences adapter ───────────────────────────────────────────


def _divergence_record(
    *,
    classification: DivergenceClassification = DivergenceClassification.BREAKING,
    casilla_id: str = "C9",
    modelo: ModeloIdentifier | None = None,
) -> DivergenceRecord:
    modelo_value = modelo if modelo is not None else ModeloIdentifier("130")
    if classification is DivergenceClassification.BREAKING:
        payload: CasillaRemoved | CasillaAddedWithDefault = CasillaRemoved(
            modelo=modelo_value,
            casilla_id=casilla_id,
        )
    else:
        payload = CasillaAddedWithDefault(
            modelo=modelo_value,
            casilla_id=casilla_id,
            default="0",
            label=_summary("label"),
        )
    return DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime(2026, 4, 12, tzinfo=UTC),
        modelo=modelo_value,
        classification=classification,
        payload=payload,
    )


def test_divergences_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    items = divergences_pending(settings)
    assert items == ()


@pytest.mark.parametrize(
    ("classification", "expected_severity"),
    [
        (DivergenceClassification.BREAKING, ReviewSeverity.CRITICAL),
        (DivergenceClassification.SUSPICIOUS, ReviewSeverity.CRITICAL),
        (DivergenceClassification.ADDITIVE, ReviewSeverity.NORMAL),
        (DivergenceClassification.BENIGN, ReviewSeverity.NORMAL),
    ],
)
def test_divergences_pending_severity_mapping(
    tmp_path: Path,
    classification: DivergenceClassification,
    expected_severity: ReviewSeverity,
) -> None:
    settings = _build_settings(tmp_path)
    repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
    repo.save(_divergence_record(classification=classification))
    items = divergences_pending(settings)
    assert len(items) == 1
    assert items[0].severity is expected_severity
    assert isinstance(items[0], DivergenceReviewItem)


def test_divergences_pending_skips_non_pending_records(tmp_path: Path) -> None:
    """Records that already transitioned out of PENDING must not appear in the queue."""
    from ..sync import ResolutionState

    settings = _build_settings(tmp_path)
    repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
    pending = _divergence_record(classification=DivergenceClassification.BREAKING)
    repo.save(pending)
    resolved = pending.model_copy(
        update={
            "record_id": uuid.uuid4().hex,
            "resolution_state": ResolutionState.HUMAN_APPROVED,
        }
    )
    repo.save(resolved)
    items = divergences_pending(settings)
    assert len(items) == 1
    assert items[0].source.record_id == pending.record_id


# ── drafts adapter ────────────────────────────────────────────────


def _draft(
    *,
    draft_id: str,
    modelo: str = "130",
    period: str = "2026Q1",
    status: FilingDraftStatus = FilingDraftStatus.READY_TO_SUBMIT,
    findings: tuple[FilingValidationFinding, ...] = (),
) -> FilingDraft:
    values = (
        FilingValue(
            casilla_id="03",
            value=Decimal("0"),
            kind=FilingValueKind.LITERAL,
            source="test",
        ),
    )
    return FilingDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=status,
        values=values,
        findings=findings,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        schema_version="filing-schema-0.1.0",
    )


def _write_draft(settings: Settings, draft: FilingDraft) -> Path:
    """Persist ``draft`` through the FilingDraftRepository (ciphertext-at-rest)."""
    from ..filing._repository import FilingDraftRepository

    settings.aeat_drafts_dir.mkdir(parents=True, exist_ok=True)
    repository = FilingDraftRepository(store_dir=settings.aeat_drafts_dir)
    repository.save(draft)
    return repository.envelope_path_for(draft.draft_id)


def test_drafts_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert drafts_pending(settings) == ()


def test_drafts_pending_emits_one_finding_per_finding(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    findings = (
        FilingValidationFinding(
            casilla_id="03",
            severity=FilingFindingSeverity.ERROR,
            code="casilla-out-of-range",
            message=_summary("range"),
        ),
        FilingValidationFinding(
            casilla_id="04",
            severity=FilingFindingSeverity.WARNING,
            code="casilla-required-missing",
            message=_summary("missing"),
        ),
        FilingValidationFinding(
            casilla_id="05",
            severity=FilingFindingSeverity.INFO,
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
    _write_draft(settings, _draft(draft_id="d_draft", status=FilingDraftStatus.DRAFT))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL
    summary_en = items[0].summary.get("en", "")
    assert "DRAFT" in summary_en


def test_drafts_pending_emits_placeholder_when_no_findings_but_status_pending(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _write_draft(settings, _draft(draft_id="d2", status=FilingDraftStatus.VALIDATED))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL


def test_drafts_pending_emits_high_severity_for_approval_stale(tmp_path: Path) -> None:
    """`status=APPROVAL_STALE` (#230) must surface as a HIGH-severity finding row."""
    settings = _build_settings(tmp_path)
    _write_draft(settings, _draft(draft_id="d_stale", status=FilingDraftStatus.APPROVAL_STALE))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.HIGH
    assert items[0].draft_id == "d_stale"
    summary_en = items[0].summary.get("en", "")
    assert "APPROVAL_STALE" in summary_en
    assert items[0].drill_command.startswith("aeat review show ")


def test_drafts_pending_skips_ready_drafts_with_no_findings(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _write_draft(settings, _draft(draft_id="d3", status=FilingDraftStatus.READY_TO_SUBMIT))
    assert drafts_pending(settings) == ()


def test_drafts_pending_dedups_identical_finding_triples(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    finding = FilingValidationFinding(
        casilla_id="03",
        severity=FilingFindingSeverity.ERROR,
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
