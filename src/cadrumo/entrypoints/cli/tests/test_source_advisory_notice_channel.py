"""A source advisory reaches the operator through the typed notice channel.

Non-blocking diagnostics reach an operator only as envelope ``Notice`` rows;
anything the projector drops is invisible to every surface that has to show it.
The rate-box coverage advisory is the case under test because its remedy is the
whole basis of the two-gate split -- the export refusal on the same condition is
fair only if the operator was told, in time, what to repair.

Three parts of the diagnostic must survive the hop, and each is dropped by a
different plausible edit: the ``reason`` (the machine-queryable kind, on
``context``), the ``remedy`` (the repair instruction, on ``suggestion``), and
the ``message`` itself, which must reach the terminal line as well as the JSON.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....application.aggregation import CalculationSourceDiagnostic
from .._modelo_work_calculate_cli import _work_calculate_source_advisory_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REASON = "rate_boxes_underaccount_total"
_MESSAGE = (
    "120.00 of the super_reduced iva_amount_sum declared in "
    "'iva.anual.repercutido.super-reducido' (420.00) reaches no rate box"
)
_REMEDY = "Record the IVA rate on the ledger rows that lack one, then recalculate"


@dataclass(frozen=True)
class _DiagnosticsOnly:
    """The one attribute the projector reads off a calculation result.

    Not a stand-in for the calculation: the diagnostic below is a real
    :class:`~application.aggregation.CalculationSourceDiagnostic`. The projector
    accepts the whole result envelope while reading only ``source_diagnostics``,
    and persisting a revision to hand it one would exercise the persistence path
    instead of the hop under test.
    """

    source_diagnostics: tuple[CalculationSourceDiagnostic, ...]


def _rate_box_diagnostic() -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason=_REASON,
        source_kind="ledger_iva_aggregation",
        message=_MESSAGE,
        remedy=_REMEDY,
    )


def test_the_advisory_becomes_a_notice_carrying_reason_remedy_and_message() -> None:
    notices, lines = _work_calculate_source_advisory_output(_DiagnosticsOnly((_rate_box_diagnostic(),)))

    assert len(notices) == 1
    assert notices[0].context["reason"] == _REASON
    assert notices[0].context["source_kind"] == "ledger_iva_aggregation"
    assert notices[0].suggestion == _REMEDY
    assert notices[0].message == _MESSAGE
    assert len(lines) == 1
    assert _MESSAGE in lines[0]
    assert _REMEDY in lines[0]


def test_a_calculation_with_no_advisory_emits_no_notice() -> None:
    """The negative control: a projector that always emitted one would pass above."""
    assert _work_calculate_source_advisory_output(_DiagnosticsOnly(())) == ([], [])
