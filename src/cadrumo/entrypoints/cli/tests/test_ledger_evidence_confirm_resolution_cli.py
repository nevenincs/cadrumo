"""Pure operator presentation checks over the closed confirmation projection."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from ....application.ledger.invoice_evidence_operation import LedgerEvidenceConfirmProjection
from ....application.ledger.invoice_evidence_operation_dtos import (
    ClassificationAssemblyProjectionV1,
    ConfirmationBlockerProjectionV1,
    ConfirmedEstablishmentProjectionV1,
    CounterpartyEstablishmentProjectionV1,
    DeclaredFactsProjectionV1,
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
    IvaCategoryResolutionProjectionV1,
    RegistryFactProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.classifier_input_source import ClassifierInputSource
from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.iva_category_resolution import IvaCategoryOutcome
from ....core.json_contract import NoticeSeverity
from ....domain.invoices.enums import PaymentStatus
from ....domain.iva.classification import InvoiceKind
from .._ledger_evidence_cli import (
    _confirm_resolution_lines,
    _evidence_confirm_notices,
    _evidence_confirm_payload,
    _resolution_notices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_EVIDENCE_ID = "e" * 16
_ATTACHMENT_ID = "a" * 64
_SOURCE_SHA256 = "b" * 64
_DRAFT_SHA256 = "c" * 64
_INVOICE_ID = "d" * 64
_FINDING_ID = "f" * 16
_REDACTED_PARTY = "sha256:deadbeef"


def _invoice() -> CatalogueInvoiceSnapshot:
    """Build a complete public invoice snapshot for the CLI projector."""
    return CatalogueInvoiceSnapshot(
        invoice_id=_INVOICE_ID,
        bucket_id=str(_PROFILE_ID),
        kind=InvoiceKind.RECEIVED,
        invoice_number="ES-2026-000019",
        issued_at=date(2026, 3, 11),
        counterparty_name="Acme Suministros SL",
        counterparty_tax_id=None,
        counterparty_country="ES",
        base_total=PublicDecimal(decimal="100.00"),
        iva_total=PublicDecimal(decimal="21.00"),
        grand_total=PublicDecimal(decimal="121.00"),
        currency="EUR",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
        source_filename="factura.xml",
        source_sha256=_SOURCE_SHA256,
        source_row_index=None,
        notes="",
        retention_rate=None,
        retention_amount=None,
        recargo_amount=None,
        operation_type=None,
        lines=(
            InvoiceLineSnapshot(
                description="Komponenter",
                quantity=PublicDecimal(decimal="1"),
                unit_price=PublicDecimal(decimal="100.00"),
                subtotal=PublicDecimal(decimal="100.00"),
                iva_rate="21",
                iva_amount=PublicDecimal(decimal="21.00"),
            ),
        ),
        invoice_class="ORDINARIA",
        series=None,
        operation_date=None,
        operation_date_role=None,
        iva_category=None,
        rectifies_invoice_number=None,
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_source=None,
        base_total_eur=None,
        iva_total_eur=None,
        grand_total_eur=None,
    )


def _establishment(
    *,
    outcome: IvaCategoryOutcome,
    category: str | None,
    note: str,
    declared: str | None = None,
    include_review_item: bool = True,
) -> ConfirmedEstablishmentProjectionV1:
    resolution = IvaCategoryResolutionProjectionV1(
        outcome=outcome,
        category=category,
        classified=None,
        declared=(
            None
            if declared is None
            else RegistryFactProjectionV1(
                value=declared,
                source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            )
        ),
        note=note,
    )
    review_items = (
        (
            ConfirmationBlockerProjectionV1(
                blocker_id=_FINDING_ID,
                reason=ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT,
                field="supplier_tax_id",
                detail=f"Establishment is unknown for {_REDACTED_PARTY}.",
            ),
        )
        if include_review_item
        else ()
    )
    return ConfirmedEstablishmentProjectionV1(
        counterparty=CounterpartyEstablishmentProjectionV1(),
        filer_scope=None,
        declared=DeclaredFactsProjectionV1(),
        assembly=ClassificationAssemblyProjectionV1(),
        category=resolution,
        review_items=review_items,
        resolved=not include_review_item,
    )


def _confirmation(
    establishment: ConfirmedEstablishmentProjectionV1,
) -> InvoiceConfirmationProjectionV1:
    return InvoiceConfirmationProjectionV1(
        invoice=_invoice(),
        draft=InvoiceDraftProjectionV1(),
        created=True,
        confirmation_id="1" * 16,
        establishment=establishment,
    )


def _operation_projection(
    confirmation: InvoiceConfirmationProjectionV1,
) -> LedgerEvidenceConfirmProjection:
    return LedgerEvidenceConfirmProjection(
        profile_id=_PROFILE_ID,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_ATTACHMENT_ID,
        source_sha256=_SOURCE_SHA256,
        reviewed_draft_sha256=_DRAFT_SHA256,
        confirmation=confirmation,
    )


def test_withheld_relief_and_unresolved_party_reach_the_closed_cli_projection() -> None:
    establishment = _establishment(
        outcome=IvaCategoryOutcome.UNSUPPORTED_RELIEF,
        category=None,
        note="The declared exemption cannot be placed without territory evidence.",
        declared="intra_community_supply",
    )
    confirmation = _confirmation(establishment)

    payload = _evidence_confirm_payload(
        bucket_id=str(_PROFILE_ID),
        projection=_operation_projection(confirmation),
    )
    notices = {notice.code: notice for notice in _resolution_notices(establishment)}
    lines = _confirm_resolution_lines(establishment)

    assert payload["iva_category"] is None
    assert payload["iva_category_outcome"] == IvaCategoryOutcome.UNSUPPORTED_RELIEF.value
    assert "advisory" not in payload
    relief = notices["ledger.evidence.confirm.category_unsupported_relief"]
    assert relief.severity is NoticeSeverity.WARNING
    assert relief.context == {
        "outcome": IvaCategoryOutcome.UNSUPPORTED_RELIEF.value,
        "declared_category": "intra_community_supply",
        "note": "The declared exemption cannot be placed without territory evidence.",
    }
    establishment_notice = notices["ledger.evidence.confirm.review_undetermined_establishment"]
    assert establishment_notice.severity is NoticeSeverity.WARNING
    assert establishment_notice.context == {
        "finding_id": _FINDING_ID,
        "reason": ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT.value,
        "field": "supplier_tax_id",
        "detail": f"Establishment is unknown for {_REDACTED_PARTY}.",
    }
    assert "iva_category\t-\tunsupported_relief" in lines
    assert (
        f"review_item\tundetermined_establishment\tsupplier_tax_id\tEstablishment is unknown for {_REDACTED_PARTY}."
        in lines
    )


def test_inferred_category_makes_review_notices_informational() -> None:
    establishment = _establishment(
        outcome=IvaCategoryOutcome.RATE_INFERRED,
        category="domestic_general",
        note="The rate implies the standard domestic category.",
    )
    confirmation = _confirmation(establishment)

    payload = _evidence_confirm_payload(
        bucket_id=str(_PROFILE_ID),
        projection=_operation_projection(confirmation),
    )
    notices = {notice.code: notice for notice in _evidence_confirm_notices(confirmation)}

    assert payload["iva_category"] == "domestic_general"
    assert payload["iva_category_outcome"] == IvaCategoryOutcome.RATE_INFERRED.value
    inferred = notices["ledger.evidence.confirm.category_rate_inferred"]
    assert inferred.severity is NoticeSeverity.INFO
    assert inferred.context == {
        "outcome": IvaCategoryOutcome.RATE_INFERRED.value,
        "iva_category": "domestic_general",
        "note": "The rate implies the standard domestic category.",
    }
    assert notices["ledger.evidence.confirm.review_undetermined_establishment"].severity is NoticeSeverity.INFO


def test_placed_category_without_open_review_has_no_resolution_notice() -> None:
    establishment = _establishment(
        outcome=IvaCategoryOutcome.CLASSIFIED,
        category="domestic_general",
        note="The rule table placed the category from the available facts.",
        include_review_item=False,
    )

    assert _resolution_notices(establishment) == []
