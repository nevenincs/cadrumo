"""Per-adapter unit tests for the review-queue source adapters.

Each adapter is exercised through its public single-source path:
the happy path with a synthetic source, the missing-source path,
and the severity-mapping invariants.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import (
    _INVOICE_CATALOGUE_VERSION,
    _INVOICE_NAMESPACE,
    _INVOICE_OBJECT_KEY,
    InvoiceCatalogueRepository,
)
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....core import CasillaId, Period, validated_casilla_id
from ....core.classification import SensitivityClass
from ....core.config import Settings
from ....core.errors.severity import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.schema import ModeloDraft, ModeloValidationFinding, ModeloValue, ModeloValueKind, compute_modelo_draft_id, registry_schema_version
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from .._adapters import drafts_pending, invoices_pending, transactions_pending
from ..enums import ReviewSeverity
from ..errors import ReviewSourceLoadError
from ..models import FindingReviewItem, InvoiceReviewItem, TransactionReviewItem

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_REVIEW_FINDING_CASILLA: CasillaId = validated_casilla_id("03", surface="_REVIEW_FINDING_CASILLA")
_REVIEW_MISSING_CASILLA: CasillaId = validated_casilla_id("04", surface="_REVIEW_MISSING_CASILLA")
_REVIEW_INFO_CASILLA: CasillaId = validated_casilla_id("05", surface="_REVIEW_INFO_CASILLA")
_PROFILE_ID = "23232323-2323-4232-8232-232323232323"
_OTHER_PROFILE_ID = "44444444-4444-4444-8444-444444444444"
_ACTIVE_PROFILE_ID = "45454545-4545-4454-8454-454545454545"
_CORRUPT_ROW_WRITTEN_AT = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)


# ── shared helpers ────────────────────────────────────────────────


def _build_settings(tmp_path: Path) -> Settings:
    """Build a Settings instance with every disk root anchored at tmp_path."""
    return Settings(
        cadrumo_financial_txs_dir=tmp_path / "transactions",
        cadrumo_invoices_dir=tmp_path / "invoices",
        cadrumo_attachments_dir=tmp_path / "attachments",
        cadrumo_drafts_dir=tmp_path / "probe-drafts",
    )


def _seed_active_profile(bucket_id: str = _PROFILE_ID) -> None:
    """Register the minimal placeholder profile so drafts match the active tax id.

    Seeded through a detached WorkflowState, never a repository read: the
    capsule publishes by an atomic no-replace rename onto
    ``buckets/<profile-id>``, which a workflow-state repository construction
    would otherwise materialise first and collide with.
    """
    register_minimal_profile(
        profile_id=bucket_id,
        overrides={"identity.tax_id": "00000000T"},
    )


def _summary(text: str = "demo") -> tr:
    return tr("translation")


_TEST_REVISION_ID = "test-revision"


def _schema_version(modelo: str = "130") -> str:
    return registry_schema_version(modelo=modelo, revision_id=_TEST_REVISION_ID)


def _case_profile_id(index: int) -> str:
    return f"23232323-2323-4232-8232-232323232{index:03d}"


def test_adapters_return_empty_when_source_missing(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    for adapter in (transactions_pending, invoices_pending, drafts_pending):
        with open_test_profile_session(_PROFILE_ID):
            _seed_active_profile(_PROFILE_ID)
            assert adapter(settings, bucket_id=_PROFILE_ID) == ()


# ── transactions adapter ──────────────────────────────────────────


def _raw(*, source_row_index: int = 1, description: str = "Office") -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=f"prov-{source_row_index}",
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
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": classification,
        },
    )


def test_transactions_pending_filters_unclassified(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(source_row_index=1),  # NOT_YET_PROCESSED
            _transaction(source_row_index=2, classification=BusinessClassification.BUSINESS),
        ),
    )
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        items = transactions_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, TransactionReviewItem)
    assert item.severity is ReviewSeverity.NORMAL
    assert item.modelo is None
    assert item.source.business_classification is BusinessClassification.NOT_YET_PROCESSED


def test_transactions_pending_drills_into_ledger_owned_review_command(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions((_transaction(source_row_index=1),))
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        items = transactions_pending(settings, bucket_id=_PROFILE_ID)

    assert len(items) == 1
    assert items[0].drill_command == f"aeat app ledger review {items[0].source.transaction_id}"
    assert " edit " not in items[0].drill_command
    assert "--set" not in items[0].drill_command


def test_transactions_pending_reads_only_requested_bucket(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    other_bucket_catalogue = TransactionCatalogue.from_transactions((_transaction(source_row_index=1),))
    with open_test_profile_session(_OTHER_PROFILE_ID):
        _seed_active_profile(_OTHER_PROFILE_ID)
        TransactionCatalogueRepository(bucket_id=_OTHER_PROFILE_ID).save(other_bucket_catalogue)

    with open_test_profile_session(_ACTIVE_PROFILE_ID):
        _seed_active_profile(_ACTIVE_PROFILE_ID)
        assert transactions_pending(settings, bucket_id=_ACTIVE_PROFILE_ID) == ()
    with open_test_profile_session(_OTHER_PROFILE_ID):
        _seed_active_profile(_OTHER_PROFILE_ID)
        assert len(transactions_pending(settings, bucket_id=_OTHER_PROFILE_ID)) == 1


def test_transactions_pending_severity_mapping(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    cases = (
        (BusinessClassification.NOT_YET_PROCESSED, ReviewSeverity.NORMAL),
        (BusinessClassification.PROCESSED_UNCLASSIFIED, ReviewSeverity.HIGH),
        (BusinessClassification.FAILED_VALIDATION, ReviewSeverity.CRITICAL),
    )
    for index, (state, expected_severity) in enumerate(cases, start=1):
        bucket_id = _case_profile_id(index)
        catalogue = TransactionCatalogue.from_transactions(
            (_transaction(source_row_index=index, classification=state),),
        )
        with open_test_profile_session(bucket_id):
            _seed_active_profile(bucket_id)
            TransactionCatalogueRepository(bucket_id=bucket_id).save(catalogue)
            items = transactions_pending(settings, bucket_id=bucket_id)
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
        ),
    )
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        assert transactions_pending(settings, bucket_id=_PROFILE_ID) == ()


def test_transactions_pending_skips_reviewed_excluded(tmp_path: Path) -> None:
    """``REVIEWED_EXCLUDED`` rows are a final disposition and must not resurface.

    The operator reviewed the row and deliberately excluded it from filing, so
    the review queue must drop it.
    """
    settings = _build_settings(tmp_path)
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(
                source_row_index=1,
                classification=BusinessClassification.REVIEWED_EXCLUDED,
            ),
            _transaction(
                source_row_index=2,
                classification=BusinessClassification.NOT_YET_PROCESSED,
            ),
        ),
    )
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        pending = transactions_pending(settings, bucket_id=_PROFILE_ID)
    assert [item.source.business_classification for item in pending] == [
        BusinessClassification.NOT_YET_PROCESSED,
    ]


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
        },
    )


def test_invoices_pending_severity_mapping(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    cases = (
        (PaymentStatus.PENDING, (), ReviewSeverity.HIGH),  # unmatched dominates
        (PaymentStatus.OVERDUE, ("a" * 64,), ReviewSeverity.HIGH),
        (PaymentStatus.PENDING, ("a" * 64,), ReviewSeverity.NORMAL),
        (PaymentStatus.PARTIALLY_PAID, ("a" * 64,), ReviewSeverity.NORMAL),
    )
    for index, (payment_status, linked, expected_severity) in enumerate(cases, start=10):
        bucket_id = _case_profile_id(index)
        catalogue = InvoiceCatalogue.from_invoices(
            (
                _invoice(
                    invoice_number=f"INV-SEVERITY-{index}",
                    payment_status=payment_status,
                    linked_transaction_ids=linked,
                ),
            ),
        )
        with open_test_profile_session(bucket_id):
            _seed_active_profile(bucket_id)
            InvoiceCatalogueRepository(bucket_id=bucket_id).save(catalogue)
            items = invoices_pending(settings, bucket_id=bucket_id)
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
        ),
    )
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        InvoiceCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        assert invoices_pending(settings, bucket_id=_PROFILE_ID) == ()


def test_invoices_pending_emits_invoice_review_item(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    catalogue = InvoiceCatalogue.from_invoices((_invoice(),))
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        InvoiceCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
        items = invoices_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
    assert isinstance(items[0], InvoiceReviewItem)


def test_invoices_pending_reads_only_requested_bucket(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    other_catalogue = InvoiceCatalogue.from_invoices((_invoice(invoice_number="INV-OTHER"),))
    with open_test_profile_session(_OTHER_PROFILE_ID):
        _seed_active_profile(_OTHER_PROFILE_ID)
        InvoiceCatalogueRepository(bucket_id=_OTHER_PROFILE_ID).save(other_catalogue)

    with open_test_profile_session(_ACTIVE_PROFILE_ID):
        _seed_active_profile(_ACTIVE_PROFILE_ID)
        assert invoices_pending(settings, bucket_id=_ACTIVE_PROFILE_ID) == ()
    with open_test_profile_session(_OTHER_PROFILE_ID):
        _seed_active_profile(_OTHER_PROFILE_ID)
        assert len(invoices_pending(settings, bucket_id=_OTHER_PROFILE_ID)) == 1


def test_invoices_pending_load_failure_context_omits_raw_storage_error(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile(_PROFILE_ID)
        secure_object_repository_for_active_bucket().save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=_CORRUPT_ROW_WRITTEN_AT,
            payload=b"{not-json",
        )
        with pytest.raises(ReviewSourceLoadError) as exc_info:
            invoices_pending(settings, bucket_id=_PROFILE_ID)

    assert exc_info.value.translated_message == "review.adapters.errors.invoices_load_failed"
    assert exc_info.value.context == {"error_type": "ValidationError"}
    assert "not-json" not in str(exc_info.value)


# ── drafts adapter ────────────────────────────────────────────────


def _draft(
    *,
    modelo: str = "130",
    period: Period = _PERIOD,
    status: ModeloDraftStatus = ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    findings: tuple[ModeloValidationFinding, ...] = (),
) -> ModeloDraft:
    values = (
        ModeloValue(
            casilla_id=_REVIEW_FINDING_CASILLA,
            value=Decimal("0"),
            kind=ModeloValueKind.LITERAL,
            source="test",
        ),
    )
    snapshot_ref = RegistrySnapshotRef(
        modelo=modelo,
        revision_id=_TEST_REVISION_ID,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )
    return ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo=modelo,
            period=period,
            profile_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=status,
        values=values,
        findings=findings,
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        schema_version=_schema_version(modelo),
    )


def _write_draft(settings: Settings, draft: ModeloDraft, *, bucket_id: str = _PROFILE_ID) -> Path:
    """Persist ``draft`` through the ModeloDraftRepository (ciphertext-at-rest)."""
    from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository

    del settings
    repository = ModeloDraftRepository(bucket_id=bucket_id)
    repository.save(draft)
    return repository.envelope_path_for(draft.draft_id)


def test_drafts_pending_load_failure_context_omits_raw_storage_error(tmp_path: Path) -> None:
    from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository

    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        repository = ModeloDraftRepository(bucket_id=_PROFILE_ID)
        repository.secure_object_repository.save(
            namespace=repository.namespace,
            object_key="corrupt-draft",
            classification=repository.sensitivity,
            schema_version=repository.schema_version,
            written_at=_CORRUPT_ROW_WRITTEN_AT,
            payload=b"{not-json",
        )
        with pytest.raises(ReviewSourceLoadError) as exc_info:
            drafts_pending(settings, bucket_id=_PROFILE_ID)

    assert exc_info.value.translated_message == "review.adapters.errors.drafts_load_failed"
    assert exc_info.value.context == {"error_type": "ValidationError"}
    assert "corrupt-draft" not in str(exc_info.value)
    assert "not-json" not in str(exc_info.value)


def test_drafts_pending_emits_one_finding_per_finding(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    findings = (
        ModeloValidationFinding(
            casilla_id=_REVIEW_FINDING_CASILLA,
            severity=BaseSeverity.ERROR,
            code="casilla-out-of-range",
            message=_summary("range"),
        ),
        ModeloValidationFinding(
            casilla_id=_REVIEW_MISSING_CASILLA,
            severity=BaseSeverity.WARNING,
            code="casilla-required-missing",
            message=_summary("missing"),
        ),
        ModeloValidationFinding(
            casilla_id=_REVIEW_INFO_CASILLA,
            severity=BaseSeverity.INFO,
            code="casilla-info-note",
            message=_summary("info"),
        ),
    )
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        draft = _draft(findings=findings)
        _write_draft(settings, draft)
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 3
    severities = {item.severity for item in items}
    assert severities == {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH, ReviewSeverity.INFO}
    for item in items:
        assert isinstance(item, FindingReviewItem)
        assert item.draft_id == draft.draft_id


def test_drafts_pending_emits_placeholder_for_draft_status(tmp_path: Path) -> None:
    """`status=DRAFT` with no findings must emit the same placeholder as VALIDATED."""
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(settings, _draft(status=ModeloDraftStatus.BORRADOR))
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL
    summary_key = items[0].summary
    assert summary_key == "review.filing.draft_placeholder_summary"


def test_drafts_pending_emits_placeholder_when_no_findings_but_status_pending(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(settings, _draft(status=ModeloDraftStatus.VALIDADO))
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.NORMAL


def test_drafts_pending_emits_high_severity_for_approval_stale(tmp_path: Path) -> None:
    """`status=APPROVAL_STALE` must surface as a HIGH-severity finding row."""
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        draft = _draft(status=ModeloDraftStatus.APROBACION_CADUCADA)
        _write_draft(settings, draft)
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
    assert items[0].source is None
    assert items[0].severity is ReviewSeverity.HIGH
    assert items[0].draft_id == draft.draft_id
    summary_key = items[0].summary
    assert summary_key == "review.filing.stale_approval_summary"
    assert items[0].drill_command.startswith("aeat app review view ")


def test_drafts_pending_skips_ready_drafts_with_no_findings(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(settings, _draft(status=ModeloDraftStatus.LISTO_PARA_PRESENTAR))
        assert drafts_pending(settings, bucket_id=_PROFILE_ID) == ()


def test_drafts_pending_dedups_identical_finding_triples(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    finding = ModeloValidationFinding(
        casilla_id=_REVIEW_FINDING_CASILLA,
        severity=BaseSeverity.ERROR,
        code="casilla-out-of-range",
        message=_summary("dup"),
    )
    # Same finding repeated twice — dedup should collapse to one.
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(
            settings,
            _draft(findings=(finding, finding)),
        )
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
    assert len(items) == 1
