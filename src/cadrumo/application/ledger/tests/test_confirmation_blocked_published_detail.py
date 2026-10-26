"""A blocked confirm records its blockers for other processes by id and reason, never by their explanation.

A blocker's explanation names the figures or readings the document prints. The
in-process envelope still shows it to the person at the terminal; the detail an
operation records for a frontend in another process carries only each
blocker's id and reason. The refusal is raised by the real confirmation gate
and projected by the real error-envelope and operation-detail builders.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.errors.error_codes import build_error_envelope
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ...operations.error_detail import build_operation_error_detail
from ..confirmation_gate import ConfirmationBlockedError, confirmation_blockers, resolved_blockers
from ..invoice_draft_records import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A value the document prints, which the blocker's explanation repeats.
_PRINTED_VALUE = "Talleres Berrocal prints 4.528,32"


def _blocked_draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="ESB12345674",
            ),
        ),
        discrepancies=(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                field="grand_total",
                detail=f"the total does not close: {_PRINTED_VALUE}",
                expected=Decimal("121.00"),
                observed=Decimal("126.20"),
            ),
        ),
    )


def _refusal() -> ConfirmationBlockedError:
    with pytest.raises(ConfirmationBlockedError) as raised:
        resolved_blockers(draft=_blocked_draft(), resolutions=())
    return raised.value


def test_the_blocker_explanation_repeats_the_printed_value() -> None:
    """Control: without it, the absence asserted below would prove nothing."""
    (blocker,) = confirmation_blockers(_blocked_draft())

    assert _PRINTED_VALUE in blocker.detail


def test_the_terminal_envelope_still_shows_the_blocker_explanation() -> None:
    context = build_error_envelope(_refusal()).context

    assert context is not None
    assert _PRINTED_VALUE in context["unresolved_blockers"]


def test_the_recorded_detail_names_each_blocker_by_id_and_reason_only() -> None:
    (blocker,) = confirmation_blockers(_blocked_draft())

    detail = build_operation_error_detail(_refusal())

    assert detail is not None
    context = detail.context_mapping()
    assert context["unresolved_blocker_ids"] == blocker.blocker_id
    assert context["unresolved_blocker_reasons"] == ConfirmationBlockReason.CLOSURE_DISCREPANCY.value
    assert "unresolved_blockers" not in context
    assert _PRINTED_VALUE not in detail.model_dump_json(), "the recorded detail repeats the document"
