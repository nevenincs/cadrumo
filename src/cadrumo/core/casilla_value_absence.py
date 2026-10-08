"""Named grounds for reading a casilla a casilla-value mapping omits as zero.

A casilla missing from a ``Mapping[CasillaId, Decimal]`` and a casilla holding
zero are different facts: missing, unsupported, deferred and proven-zero states
must stay distinguishable through calculation and filing. A reader may fold an
absence into zero only on a ground that makes the fold correct for that reader,
and it names the ground at the read. Every such fold is therefore classified,
reviewable and searchable by its ground; a reader that has no ground handles the
absence itself, as a refusal or a disclosed diagnostic.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from .casilla_id import CasillaId
from .decimal.constants import ZERO


class AbsentCasillaReading(StrEnum):
    """The ground on which one reader reads an omitted casilla as zero."""

    UNSUPPLIED_INPUT = "unsupplied_input"
    """A calculation input the caller did not supply evaluates as zero.

    Calculation reads it so; whether a required manual input was ever supplied
    is refused by verification's required-casilla check, which reads the
    supplied inputs rather than the arithmetic that consumed them.
    """

    SPARSE_FOLD_TOTAL = "sparse_fold_total"
    """The mapping holds an aggregation fold's totals.

    A fold names only the casillas some admitted observation reached; a casilla
    no observation reached folded nothing. Excluded, deferred and out-of-window
    sources travel beside the fold as their own diagnostics.
    """

    RESULT_CASILLA_ALTERNATIVE = "result_casilla_alternative"
    """The reader sums a modelo's declared alternative final-result casillas.

    A revision states only the alternatives that apply to it. Filing-time
    consumers that require an observed result enforce its presence before they
    derive a disposition from the sum.
    """

    OMITTED_BOX_DECLARES_ZERO = "omitted_box_declares_zero"
    """The reader checks box arithmetic as the return declares it.

    A box the return leaves out declares zero, so the arithmetic reads it as
    the return does.
    """

    ADVISORY_TRIGGER_OPERAND = "advisory_trigger_operand"
    """An advisory that fires only on a stated, non-zero amount.

    An unstated amount gives it nothing to advise on. Whether that absence is
    itself a defect is decided by completeness verification, not by the
    advisory.
    """

    ADVISORY_GAP_OPERAND = "advisory_gap_operand"
    """An advisory that fires when nothing is declared in the casilla.

    An absent value fires it exactly as zero does, so the absence is disclosed
    to the operator rather than suppressed.
    """

    def read(self, values: Mapping[CasillaId, Decimal], casilla_id: CasillaId) -> Decimal:
        """Return the stated value of ``casilla_id``, or zero on this ground when it is absent."""
        value = values.get(casilla_id)
        return ZERO if value is None else value


__all__ = ["AbsentCasillaReading"]
