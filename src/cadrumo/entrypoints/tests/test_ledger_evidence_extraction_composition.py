"""The composed text-layer reader refuses an unreadable PDF with its typed refusal."""

from __future__ import annotations

import pytest

from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ...application.ledger.preconditions import LedgerPreconditionCondition
from ..ledger_evidence_extraction_composition import evidence_text_layer_ports

pytestmark = [pytest.mark.unit]


def test_an_unreadable_pdf_is_a_typed_text_layer_refusal() -> None:
    ports = evidence_text_layer_ports()

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        ports.extract_pages_text(b"%PDF-1.7\nthis is not a readable document")

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE.value
    assert verdict.evidence[0].values["pdf_layer_present"] is False
