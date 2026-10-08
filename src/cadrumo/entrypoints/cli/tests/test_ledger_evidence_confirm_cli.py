"""Pure public-payload checks for the registered invoice confirm CLI surface."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
import typer

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from ....application.ledger.invoice_evidence_confirm_operation import LedgerEvidenceConfirmProjection
from ....application.ledger.invoice_evidence_operation_dtos import (
    FieldProvenanceProjectionV1,
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....domain.invoices.enums import PaymentStatus
from ....domain.iva.classification import InvoiceKind
from .._ledger_evidence_cli import _evidence_confirm_payload, _require_exact_evidence_reference
from ..ledger_business_payloads import EvidenceConfirmResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_EVIDENCE_ID = "e" * 16
_ATTACHMENT_ID = "a" * 64
_SOURCE_SHA256 = "b" * 64
_DRAFT_SHA256 = "c" * 64
_INVOICE_ID = "d" * 64


def _public_decimal(value: str) -> PublicDecimal:
    return PublicDecimal(decimal=value)


def _projection() -> LedgerEvidenceConfirmProjection:
    """Build a strict canonical read projection with both provenance views."""
    extracted = FieldProvenanceProjectionV1(
        field="invoice_number",
        origin=FieldOrigin.EXACT_STRUCTURED,
        grounding=FieldGroundingOutcome.ANCHORED,
        anchor="FAC-2024-0007",
    )
    confirmed = FieldProvenanceProjectionV1(
        field="invoice_number",
        origin=FieldOrigin.OPERATOR,
        grounding=FieldGroundingOutcome.UNANCHORED,
    )
    draft = InvoiceDraftProjectionV1(
        invoice_number="FAC-2024-0007",
        taxable_base=_public_decimal("100.00"),
        provenance=(extracted,),
    )
    snapshot = CatalogueInvoiceSnapshot(
        invoice_id=_INVOICE_ID,
        bucket_id=str(_PROFILE),
        kind=InvoiceKind.RECEIVED,
        invoice_number="FAC-2024-0007",
        issued_at=date(2024, 11, 20),
        counterparty_name="Mayorista Ejemplo SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        base_total=_public_decimal("100.00"),
        iva_total=_public_decimal("21.00"),
        grand_total=_public_decimal("121.00"),
        currency="EUR",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
        source_filename="factura.xml",
        source_sha256=_SOURCE_SHA256,
        source_row_index=None,
        notes="",
        retention_rate=None,
        retention_amount=None,
        recargo_amount=_public_decimal("5.20"),
        operation_type=None,
        lines=(
            InvoiceLineSnapshot(
                description="Genero para reventa",
                quantity=_public_decimal("10"),
                unit_price=_public_decimal("10.00"),
                subtotal=_public_decimal("100.00"),
                iva_rate="21",
                iva_amount=_public_decimal("21.00"),
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
    return LedgerEvidenceConfirmProjection(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_ATTACHMENT_ID,
        source_sha256=_SOURCE_SHA256,
        reviewed_draft_sha256=_DRAFT_SHA256,
        confirmation=InvoiceConfirmationProjectionV1(
            invoice=snapshot,
            draft=draft,
            created=True,
            confirmation_id="f" * 16,
            confirmed_provenance=(confirmed,),
        ),
    )


@pytest.mark.parametrize(("evidence_id", "attachment_id"), [(None, None), (_EVIDENCE_ID, _ATTACHMENT_ID)])
def test_confirm_preflight_requires_exactly_one_reference(
    evidence_id: str | None,
    attachment_id: str | None,
) -> None:
    with pytest.raises(typer.BadParameter):
        _require_exact_evidence_reference(evidence_id, attachment_id)


def test_confirm_payload_keeps_canonical_invoice_review_digests_and_provenance() -> None:
    projection = _projection()

    result = EvidenceConfirmResult.model_validate(
        _evidence_confirm_payload(bucket_id=str(_PROFILE), projection=projection),
    )

    assert result.evidence_id == _EVIDENCE_ID
    assert result.attachment_id == _ATTACHMENT_ID
    assert result.source_sha256 == _SOURCE_SHA256
    assert result.reviewed_draft_sha256 == _DRAFT_SHA256
    assert result.invoice_id == _INVOICE_ID
    assert result.invoice_number == "FAC-2024-0007"
    assert result.counterparty_name == "Mayorista Ejemplo SL"
    assert result.base_total == "100.00"
    assert result.iva_total == "21.00"
    assert result.grand_total == "121.00"
    assert result.recargo_amount == "5.20"
    assert result.provenance[0].origin == FieldOrigin.EXACT_STRUCTURED.value
    assert result.confirmed_provenance[0].origin == FieldOrigin.OPERATOR.value
    assert result.confirmation_id == "f" * 16
