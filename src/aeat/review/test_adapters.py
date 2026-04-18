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
from pydantic import AnyHttpUrl

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
    save_invoices,
)
from ..financial.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    save_transactions,
)
from ..i18n import Translatable
from ..inbox import (
    Inbox,
    Notificacion,
    NotificacionKind,
    NotificacionPriority,
)
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
    InboxReviewItem,
    InvoiceReviewItem,
    ReviewSeverity,
    TransactionReviewItem,
    divergences_pending,
    drafts_pending,
    inbox_pending,
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
    classification: BusinessClassification = BusinessClassification.UNCLASSIFIED,
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
            _transaction(source_row_index=1),  # UNCLASSIFIED
            _transaction(source_row_index=2, classification=BusinessClassification.BUSINESS),
        )
    )
    save_transactions(catalogue, settings.aeat_financial_txs_dir / "transactions.json")
    items = transactions_pending(settings)
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, TransactionReviewItem)
    assert item.severity is ReviewSeverity.NORMAL
    assert item.modelo is None
    assert item.source.business_classification is BusinessClassification.UNCLASSIFIED


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
    save_invoices(catalogue, settings.aeat_invoices_dir / "invoices.json")
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
    save_invoices(catalogue, settings.aeat_invoices_dir / "invoices.json")
    assert invoices_pending(settings) == ()


def test_invoices_pending_emits_invoice_review_item(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))
    save_invoices(catalogue, settings.aeat_invoices_dir / "invoices.json")
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
    settings.aeat_drafts_dir.mkdir(parents=True, exist_ok=True)
    path = settings.aeat_drafts_dir / f"{draft.modelo}_{draft.period}_{draft.draft_id}.json"
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path


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
    )
    _write_draft(settings, _draft(draft_id="d1", findings=findings))
    items = drafts_pending(settings)
    assert len(items) == 2
    severities = {item.severity for item in items}
    assert severities == {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH}
    for item in items:
        assert isinstance(item, FindingReviewItem)
        assert item.draft_id == "d1"


def test_drafts_pending_emits_placeholder_when_no_findings_but_status_pending(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _write_draft(settings, _draft(draft_id="d2", status=FilingDraftStatus.VALIDATED))
    items = drafts_pending(settings)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL


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


# ── inbox adapter ─────────────────────────────────────────────────


def _notificacion(
    *,
    notificacion_id: str = "AEAT-0001",
    priority: NotificacionPriority = NotificacionPriority.CRITICAL,
    acknowledged: bool = False,
    appeal_deadline: date | None = None,
) -> Notificacion:
    received = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    return Notificacion(
        notificacion_id=notificacion_id,
        kind=NotificacionKind.REQUERIMIENTO,
        priority=priority,
        subject=_summary("subject"),
        body_excerpt=_summary("body"),
        received_at=received,
        effective_at=received,
        appeal_deadline=appeal_deadline,
        source_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/notif/x"),
        acknowledged_at=datetime(2026, 4, 5, 9, 0, tzinfo=UTC) if acknowledged else None,
        acknowledged_by="gw" if acknowledged else None,
    )


def _write_inbox(settings: Settings, notificaciones: tuple[Notificacion, ...]) -> Path:
    settings.aeat_inbox_dir.mkdir(parents=True, exist_ok=True)
    inbox = Inbox(entries={n.notificacion_id: n for n in notificaciones})
    path = settings.aeat_inbox_dir / "inbox.json"
    path.write_text(inbox.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_inbox_pending_returns_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert inbox_pending(settings) == ()


def test_inbox_pending_filters_acknowledged(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    _write_inbox(
        settings,
        (
            _notificacion(notificacion_id="AEAT-A"),
            _notificacion(notificacion_id="AEAT-B", acknowledged=True),
        ),
    )
    items = inbox_pending(settings)
    assert len(items) == 1
    assert isinstance(items[0], InboxReviewItem)
    assert items[0].source.notificacion_id == "AEAT-A"


@pytest.mark.parametrize(
    ("priority", "deadline_offset_days", "expected_severity"),
    [
        (NotificacionPriority.CRITICAL, None, ReviewSeverity.CRITICAL),
        (NotificacionPriority.HIGH, None, ReviewSeverity.HIGH),
        (NotificacionPriority.NORMAL, None, ReviewSeverity.NORMAL),
        (NotificacionPriority.INFO, None, ReviewSeverity.INFO),
        (NotificacionPriority.NORMAL, 3, ReviewSeverity.HIGH),  # inside lead window → upgraded
        (NotificacionPriority.NORMAL, 60, ReviewSeverity.NORMAL),  # outside lead window
    ],
)
def test_inbox_pending_severity_mapping(
    tmp_path: Path,
    priority: NotificacionPriority,
    deadline_offset_days: int | None,
    expected_severity: ReviewSeverity,
) -> None:
    from datetime import timedelta

    settings = _build_settings(tmp_path)
    today = date(2026, 4, 10)
    deadline = today + timedelta(days=deadline_offset_days) if deadline_offset_days is not None else None
    _write_inbox(
        settings,
        (
            _notificacion(
                priority=priority,
                appeal_deadline=deadline,
            ),
        ),
    )
    items = inbox_pending(settings, today=today)
    assert len(items) == 1
    assert items[0].severity is expected_severity
