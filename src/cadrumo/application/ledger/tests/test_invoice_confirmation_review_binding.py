"""A confirmation re-read must still be the document and draft an operator reviewed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ....domain.invoices.errors import InvoiceValidationError
from ....domain.iva.classification import InvoiceKind
from .. import invoice_confirmation as confirmation
from ..invoice_draft_records import InvoiceDraft
from ..structured_invoice_ports import StructuredInvoiceClassification, StructuredInvoiceClassificationKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="A58818501",
        invoice_number="F-1",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
    )


def test_review_digest_covers_values_and_the_structured_invoice_class() -> None:
    draft = _draft()
    original = confirmation.invoice_draft_review_sha256(draft)
    assert original != confirmation.invoice_draft_review_sha256(draft.model_copy(update={"invoice_number": "F-2"}))

    draft.set_facturae_invoice_class(
        StructuredInvoiceClassification(source_code="R1", kind=StructuredInvoiceClassificationKind.CORRECTIVE)
    )
    assert original != confirmation.invoice_draft_review_sha256(draft)


@pytest.mark.parametrize("stale_part", ["source", "draft"])
def test_stale_review_refuses_before_candidate_or_persistence(monkeypatch: pytest.MonkeyPatch, stale_part: str) -> None:
    draft = _draft()
    source_sha256 = "a" * 64
    preparation = type("Preparation", (), {"attachment_id": source_sha256, "draft": draft})()
    candidate_calls: list[str] = []

    monkeypatch.setattr(confirmation, "_prepare_invoice_confirmation", lambda **_kwargs: preparation)
    monkeypatch.setattr(
        confirmation,
        "_build_confirmed_invoice_candidate",
        lambda **_kwargs: candidate_calls.append("built"),
    )
    expected_source = "b" * 64 if stale_part == "source" else source_sha256
    expected_draft = "b" * 64 if stale_part == "draft" else confirmation.invoice_draft_review_sha256(draft)
    kwargs: dict[str, Any] = {
        "bucket_id": "test-bucket",
        "kind": InvoiceKind.RECEIVED,
        "counterparty_country": "ES",
        "evidence_id": "test-evidence",
        "catalogue_creation_ports": object(),
        "counterparty_establishment_repository": object(),
        "evidence_ports": object(),
        "extraction_ports": object(),
        "operation": object(),
        "legends": (),
        "expected_source_sha256": expected_source,
        "expected_draft_review_sha256": expected_draft,
    }
    with pytest.raises(InvoiceValidationError, match="changed since review"):
        confirmation.prepare_invoice_confirmation_from_evidence(**kwargs)
    assert candidate_calls == []
