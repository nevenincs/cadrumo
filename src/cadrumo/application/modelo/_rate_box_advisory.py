"""Calculate-time advisory when rate boxes account for less than their total.

A rate-specific official box may assert only a rate the evidence determines, so
a ledger row that records a cuota without recording the rate charged reaches the
rate-blind total and no box. The return stays whole and the breakdown stays
truthful, and the price is that the boxes sum to less than the total by exactly
that amount.

The operator has to be told, and told HERE rather than only at export. The
repair is a ledger edit -- record the rate on the rows that lack one -- and the
information the repair needs is the amount and the tier, which is what this
advisory carries. Refusing the calculation instead would withhold the number the
operator needs in order to act, which is why this gate is non-blocking while the
export gate on the same condition is not.

Both gates read
:func:`~domain.calculations.registry.rate_box_coverage_shortfalls` over the same
derived partitions, so an operator cannot meet a refusal at export that no
advisory preceded at calculate.

See Also:
    :mod:`domain.calculations.registry._rate_box_partition`
        Derives the two layers and owns the one subtraction both gates read.
    :mod:`application.filing._export_parity`
        The export-side refusal on the same condition.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import CasillaId
from ...domain.calculations.registry.rate_box_partition import (
    derive_rate_box_partitions,
    rate_box_coverage_shortfalls,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation import CalculationSourceDiagnostic

__all__ = ["collect_rate_box_coverage_diagnostics"]

_LEDGER_IVA_SOURCE_KIND = "ledger_iva_aggregation"


def collect_rate_box_coverage_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per rate partition whose boxes underaccount its total.

    Args:
        revision: The :class:`ModeloRevision` whose ledger-IVA bindings are read
            for the two-layer rate partitions. A revision declaring no
            rate-specific binding yields no advisory.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.

    Returns:
        Tuple of non-blocking
        :class:`~application.aggregation.CalculationSourceDiagnostic` rows, each
        naming the unaccounted amount, the tier holding it, and the boxes that
        do not reach it.
    """
    shortfalls = rate_box_coverage_shortfalls(
        derive_rate_box_partitions(revision),
        casilla_values,
    )
    return tuple(
        CalculationSourceDiagnostic(
            reason="rate_boxes_underaccount_total",
            source_kind=_LEDGER_IVA_SOURCE_KIND,
            message=(
                f"{shortfall.shortfall} of the {'/'.join(shortfall.partition.rate_kinds)} "
                f"{shortfall.partition.fact} declared in {shortfall.partition.total_casilla_id!r} "
                f"({shortfall.total}) reaches no rate box: boxes "
                f"{list(shortfall.partition.box_casilla_ids)!r} account for {shortfall.boxes_total}. "
                f"Those rows record a cuota without recording the rate charged, so no official box may "
                f"assert a rate for them. The return still declares the full amount"
            ),
            remedy=(
                "Record the IVA rate on the ledger rows that lack one, then recalculate; "
                "export refuses while the rate boxes do not account for the declared total."
            ),
            casilla_id=shortfall.partition.total_casilla_id,
        )
        for shortfall in shortfalls
    )
