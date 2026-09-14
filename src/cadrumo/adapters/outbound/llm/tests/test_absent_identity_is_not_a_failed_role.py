"""Invoice-field grounding records rejected identifiers at the LLM adapter seam.

The application identity resolver is tested separately with application-owned
identity candidates. These cases assert the outbound grounder preserves the
distinction between an absent identifier and one printed but unverifiable.
"""

from __future__ import annotations

import json

import pytest

from cadrumo.adapters.outbound.llm.invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.core.field_origin import FieldOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: The filer's own identifier, and a real third party's. Both verify.
_FILER_CIF = "B17283946"
_COUNTERPARTY_CIF = "B12345674"
#: Correct shape, wrong control character -- the misread that hides a real
#: supplier from a validating read.
_BAD_CHECKSUM_CIF = "B1234567X"


def _grounded(payload: dict[str, str]):
    return ground_extracted_fields(
        parse_invoice_extraction_response(json.dumps(payload)),
        raw_text_length=256,
        origin=FieldOrigin.TEXT_LAYER,
    )


def test_the_reading_stage_records_an_identifier_it_rejected() -> None:
    """Dropping the VALUE is right; dropping the FACT is not.

    The grounder drops a checksum-failing identifier to ``None`` and builds no
    envelope for it, so by the time the resolver reads the draft the document
    looks like it printed nothing. This is the only stage that still knows
    otherwise.
    """
    draft = _grounded(
        {
            "supplier_tax_id": _BAD_CHECKSUM_CIF,
            "supplier_tax_id_anchor": _BAD_CHECKSUM_CIF,
            "supplier_tax_id_role_evidence": "Proveedor:",
        },
    )

    assert draft.supplier_tax_id is None, "the unverifiable value must still be dropped"
    assert [f.kind for f in draft.discrepancies] == [DraftDiscrepancyKind.IDENTITY_UNVERIFIED]
    assert _BAD_CHECKSUM_CIF in draft.discrepancies[0].detail, (
        "the operator must be told which printed identifier failed, not merely that one did"
    )


def test_the_reading_stage_records_nothing_when_the_document_printed_nothing() -> None:
    """The bound on the case above: silence must not become a rejection.

    Without this, "record a rejection" could be implemented as "record one
    whenever the slot is empty", which re-creates the blocker across the
    legitimate population from the other side.
    """
    draft = _grounded({"invoice_number": "2026-0142", "invoice_number_anchor": "2026-0142"})

    assert draft.discrepancies == ()


def test_the_reading_stage_records_nothing_for_an_identifier_that_verifies() -> None:
    """A good identifier is not a rejection, on either party's slot."""
    draft = _grounded(
        {
            "supplier_tax_id": _COUNTERPARTY_CIF,
            "supplier_tax_id_anchor": _COUNTERPARTY_CIF,
            "customer_tax_id": _FILER_CIF,
            "customer_tax_id_anchor": _FILER_CIF,
        },
    )

    assert draft.supplier_tax_id == _COUNTERPARTY_CIF
    assert draft.discrepancies == ()

