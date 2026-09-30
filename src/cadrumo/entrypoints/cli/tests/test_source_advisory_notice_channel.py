"""A source advisory reads as the editor's findings list words it, and keeps its typed facts without an inferred action."""

from __future__ import annotations

import pytest

from ....application.aggregation.source_mesh import CalculationSourceDiagnostic
from ....core.config import override_settings
from ....core.json_contract import NoticeSeverity
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


def test_the_advisory_becomes_a_non_action_notice_worded_by_its_reason_with_its_account_in_context() -> None:
    with override_settings(cadrumo_output_language="en"):
        notice = source_diagnostic_notice(_rate_box_diagnostic(), code="modelo.work.calculate.source_advisory")

    context = notice.context
    assert context is not None, "the advisory reached the operator with no structured provenance"
    assert context["reason"] == _REASON
    assert context["source_kind"] == "ledger_iva_aggregation"
    assert context["level"] == "blocks"
    assert context["detail"] == _MESSAGE
    assert context["remedy"] == _REMEDY
    assert notice.action is None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.message == "Part of the VAT total in box without a number is not placed in any rate box."


def test_the_text_line_names_the_level_what_happened_and_what_to_do_without_the_account() -> None:
    with override_settings(cadrumo_output_language="en"):
        notices, lines = _work_calculate_source_advisory_output((_rate_box_diagnostic(),))

    assert notices[0].action is None
    assert lines == [
        "Blocks filing: Part of the VAT total in box without a number is not placed in any rate box. "
        "Check the VAT rate on your invoices and records, then calculate again. "
        "The declaration cannot be exported until this is fixed."
    ]
    assert _MESSAGE not in lines[0]
    assert _REMEDY not in lines[0]


def test_a_note_for_the_filers_information_is_not_a_warning() -> None:
    information = CalculationSourceDiagnostic(reason="oss_no_live_source", source_kind="oss", message="no OSS invoice")
    with override_settings(cadrumo_output_language="en"):
        notice = source_diagnostic_notice(information, code="modelo.work.calculate.source_advisory")

    assert notice.severity is NoticeSeverity.INFO
    assert notice.context is not None
    assert notice.context["level"] == "info"


def test_a_calculation_with_no_advisory_emits_no_notice() -> None:
    """The negative control: a projector that always emitted one would pass above."""
    assert _work_calculate_source_advisory_output(()) == ([], [])


def test_the_same_sentence_is_presented_once_without_discarding_distinct_contexts() -> None:
    first = _rate_box_diagnostic()
    same_reason = first.model_copy(update={"source_kind": "ledger_renta_gastos_aggregation"})
    distinct = first.model_copy(update={"message": f"{_MESSAGE} for a different source row"})

    with override_settings(cadrumo_output_language="en"):
        notices, lines = _work_calculate_source_advisory_output((first, same_reason, distinct))

    assert [notice.context["detail"] for notice in notices if notice.context is not None] == [
        _MESSAGE,
        _MESSAGE,
        distinct.message,
    ]
    assert notices[1].context is not None
    assert notices[1].context["source_kind"] == same_reason.source_kind
    assert len(lines) == 1
