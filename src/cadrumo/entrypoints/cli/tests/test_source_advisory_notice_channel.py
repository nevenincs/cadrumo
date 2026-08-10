"""A source advisory retains typed diagnostic facts without an inferred action."""

from __future__ import annotations

import pytest

from ....application.aggregation import CalculationSourceDiagnostic
from .._modelo_rendering import source_diagnostic_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REASON = "rate_boxes_underaccount_total"
_MESSAGE = (
    "120.00 of the super_reduced iva_amount_sum declared in "
    "'iva.anual.repercutido.super-reducido' (420.00) reaches no rate box"
)
_REMEDY = "Record the IVA rate on the ledger rows that lack one, then recalculate"

def _rate_box_diagnostic() -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=_REASON,
        source_kind="ledger_iva_aggregation",
        message=_MESSAGE,
        remedy=_REMEDY,
    )


def test_the_advisory_becomes_a_non_action_notice_carrying_reason_and_message() -> None:
    notice = source_diagnostic_notice(_rate_box_diagnostic(), code="modelo.work.calculate.source_advisory")

    context = notice.context
    assert context is not None, "the advisory reached the operator with no structured provenance"
    assert context["reason"] == _REASON
    assert context["source_kind"] == "ledger_iva_aggregation"
    assert notice.action is None
    assert notice.message == _MESSAGE
