"""A source advisory retains typed diagnostic facts without an inferred action."""

from __future__ import annotations

import pytest

from ....application.aggregation import CalculationSourceDiagnostic
from .._modelo_rendering import source_diagnostic_notice
from .._modelo_work_calculate_cli import _work_calculate_source_advisory_output

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
    assert context["remedy"] == _REMEDY


def test_the_advisory_text_projection_carries_the_non_command_remedy() -> None:
    notices, lines = _work_calculate_source_advisory_output((_rate_box_diagnostic(),))

    assert notices[0].message == _MESSAGE
    assert notices[0].action is None
    assert len(lines) == 1
    assert _MESSAGE in lines[0]
    assert _REMEDY in lines[0]


def test_a_calculation_with_no_advisory_emits_no_notice() -> None:
    """The negative control: a projector that always emitted one would pass above."""
    assert _work_calculate_source_advisory_output(()) == ([], [])


def test_same_message_is_presented_once_without_discarding_distinct_contexts() -> None:
    first = _rate_box_diagnostic()
    same_message = first.model_copy(update={"source_kind": "ledger_renta_gastos_aggregation"})
    distinct = first.model_copy(update={"message": f"{_MESSAGE} for a different source row"})

    notices, lines = _work_calculate_source_advisory_output((first, same_message, distinct))

    assert [notice.message for notice in notices] == [_MESSAGE, _MESSAGE, distinct.message]
    assert notices[0].context is not None
    assert notices[0].context["source_kind"] == first.source_kind
    assert notices[1].context is not None
    assert notices[1].context["source_kind"] == same_message.source_kind
    assert len(lines) == 2
