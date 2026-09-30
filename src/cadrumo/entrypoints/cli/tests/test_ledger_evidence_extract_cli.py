"""Pure public-payload checks for the registered invoice extract CLI surface."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

import pytest
import typer

from ....application.ledger.invoice_draft_payloads import EvidenceExtractResult
from ....application.ledger.invoice_draft_records import (
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
)
from ....application.ledger.invoice_evidence_operation import LedgerEvidenceExtractProjection
from ....application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from ....application.ledger.structured_invoice_ports import (
    StructuredInvoiceClassification,
    StructuredInvoiceClassificationKind,
)
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.operations import OperationEffect
from .._ledger_evidence_cli import (
    _evidence_extract_lines,
    _evidence_extract_payload,
    _require_exact_evidence_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_EVIDENCE_ID = "e" * 16
_ATTACHMENT_ID = "a" * 64
_SOURCE_SHA256 = "b" * 64
_DRAFT_SHA256 = "c" * 64


def _projection() -> LedgerEvidenceExtractProjection:
    """Return a source-complete structured draft through its public DTO."""
    draft = InvoiceDraft(
        supplier_name="Mayorista Ejemplo SL",
        invoice_number="FAC-2024-0007",
        invoice_date="2024-11-20",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21.00"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("126.20"),
        currency="EUR",
        recargo_amount=Decimal("5.20"),
        lines=(
            InvoiceDraftLine(
                description="Genero para reventa",
                quantity=Decimal("10"),
                unit_price=Decimal("10.00"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21.00"),
                iva_amount=Decimal("21.00"),
                recargo_rate=Decimal("5.20"),
                recargo_amount=Decimal("5.20"),
            ),
        ),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21.00"),
                taxable_base=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
                recargo_rate=Decimal("5.20"),
                recargo_amount=Decimal("5.20"),
            ),
        ),
        provenance=(
            FieldProvenance(
                field="invoice_number",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="FAC-2024-0007",
            ),
        ),
        raw_text_length=1_024,
    )
    draft.set_facturae_invoice_class(
        StructuredInvoiceClassification("OO", StructuredInvoiceClassificationKind.ORDINARY),
    )
    return LedgerEvidenceExtractProjection(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE_ID,
        attachment_id=_ATTACHMENT_ID,
        source_sha256=_SOURCE_SHA256,
        draft_review_sha256=_DRAFT_SHA256,
        consent_audit_effect=OperationEffect.NONE,
        draft=InvoiceDraftProjectionV1.from_draft(draft),
    )


@pytest.mark.parametrize(("evidence_id", "attachment_id"), [(None, None), (_EVIDENCE_ID, _ATTACHMENT_ID)])
def test_extract_preflight_requires_exactly_one_reference(
    evidence_id: str | None,
    attachment_id: str | None,
) -> None:
    with pytest.raises(typer.BadParameter):
        _require_exact_evidence_reference(evidence_id, attachment_id)


def test_extract_payload_keeps_full_structured_draft_and_both_review_addresses() -> None:
    projection = _projection()

    result = EvidenceExtractResult.model_validate_json(
        json.dumps(_evidence_extract_payload(bucket_id=str(_PROFILE), projection=projection)),
    )

    assert result.evidence_id == _EVIDENCE_ID
    assert result.attachment_id == _ATTACHMENT_ID
    assert result.source_sha256 == _SOURCE_SHA256
    assert result.draft_review_sha256 == _DRAFT_SHA256
    assert result.consent_audit_effect is OperationEffect.NONE
    assert result.supplier_name == "Mayorista Ejemplo SL"
    assert result.invoice_number == "FAC-2024-0007"
    assert result.taxable_base == "100.00"
    assert result.grand_total == "126.20"
    assert result.lines[0].quantity == "10"
    assert result.lines[0].iva_amount == "21.00"
    assert result.iva_breakdown[0].recargo_amount == "5.20"
    assert result.provenance[0].origin == FieldOrigin.EXACT_STRUCTURED.value
    assert result.facturae_invoice_class is not None
    assert result.facturae_invoice_class.source_code == "OO"

    lines = _evidence_extract_lines(str(_PROFILE), projection)
    assert f"source_sha256\t{_SOURCE_SHA256}" in lines
    assert f"draft_review_sha256\t{_DRAFT_SHA256}" in lines
    assert "consent_audit_effect\tnone" in lines
