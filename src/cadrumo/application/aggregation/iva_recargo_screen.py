"""Screen a charged recargo de equivalencia against the rate the law pairs with its IVA rate.

Arts. 160 and 161 of Ley 37/1992 fix the recargo: its base is the IVA base and
its cuota that base times the rate published for the applied IVA rate on the
devengo date. A charged line whose recargo departs from that by more than a
cent is refused; within the cent the recorded figure is the invoice's own
rounding and is the one declared, as the IVA cuota screen treats its cuota.
Only the charged side is screened: a recargo borne on a purchase reaches no IVA
casilla, and the buyer's cost is what the supplier charged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.i18n.render import tr
from ...core.money.rounding import CENT, round_to_cents
from ...domain.calculations.registry.iva_flow_catalogue import resolve_iva_flow_direction_catalogue
from ...domain.iva.recargo_equivalencia import (
    IVA_RECARGO_TOBACCO_FACT_ID,
    RecargoRateRecord,
    recargo_rate_record_for_applied_rate,
)
from .iva_cuota_disagreement import eur_figure, percent_figure
from .iva_ledger import IvaLedgerAggregationIssue, IvaLedgerAggregationIssueReason

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.iva.flow import IvaFlowDirection
    from ...domain.transactions.models import Transaction

#: The precision a recargo is compared at before the one-cent rounding allowance.
_COMPARISON_QUANTUM = Decimal("0.0001")


class ChargedRecargoVerdict(StrEnum):
    """Why a charged recargo cannot reach a casilla as recorded."""

    #: The recorded recargo is more than a cent from base times the published rate.
    DEPARTS_FROM_PUBLISHED_RATE = "departs_from_published_rate"
    #: The registry publishes no recargo rate for this IVA rate on this date.
    RATE_UNMODELLED = "rate_unmodelled"
    #: The recorded recargo is the labores del tabaco rate, a rung no casilla is bound for.
    TOBACCO_RUNG_UNSUPPORTED = "tobacco_rung_unsupported"


@dataclass(frozen=True, slots=True)
class ChargedRecargoFinding:
    """One charged line whose recorded recargo cannot be declared as it stands.

    Attributes:
        verdict: Why the recorded figure cannot be declared.
        base: The line's taxable base, which is also the recargo's base.
        applied_rate: The IVA rate charged on the line, as a fraction.
        declared: The recargo recorded on the line.
        devengo_date: The date the rate was resolved for.
        recargo_rate: The published recargo rate the figure was weighed against,
            or ``None`` when the registry publishes none for the line.
        expected: Base times that rate, to the cent, or ``None`` without a rate.
        legal_refs: The registry legal references grounding the rate.
    """

    verdict: ChargedRecargoVerdict
    base: Decimal
    applied_rate: Decimal
    declared: Decimal
    devengo_date: date
    recargo_rate: Decimal | None
    expected: Decimal | None
    legal_refs: tuple[str, ...]


def charged_recargo_finding(
    *,
    base: Decimal,
    applied_rate: Decimal,
    declared: Decimal,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> ChargedRecargoFinding | None:
    """Return why a charged line's recorded recargo cannot be declared, or ``None`` when it can.

    A line that records no recargo charged none and has nothing to screen.
    """
    if declared == Decimal("0"):
        return None
    record = recargo_rate_record_for_applied_rate(applied_rate, devengo_date, operation=operation)
    if record is not None and _within_rounding(declared, base, record):
        return None
    tobacco = recargo_rate_record_for_applied_rate(
        applied_rate,
        devengo_date,
        operation=operation,
        fact_id=IVA_RECARGO_TOBACCO_FACT_ID,
    )
    if tobacco is not None and _within_rounding(declared, base, tobacco):
        return _finding(
            ChargedRecargoVerdict.TOBACCO_RUNG_UNSUPPORTED, tobacco, base, applied_rate, declared, devengo_date
        )
    if record is None:
        return ChargedRecargoFinding(
            verdict=ChargedRecargoVerdict.RATE_UNMODELLED,
            base=base,
            applied_rate=applied_rate,
            declared=declared,
            devengo_date=devengo_date,
            recargo_rate=None,
            expected=None,
            legal_refs=(),
        )
    return _finding(
        ChargedRecargoVerdict.DEPARTS_FROM_PUBLISHED_RATE, record, base, applied_rate, declared, devengo_date
    )


def _within_rounding(declared: Decimal, base: Decimal, record: RecargoRateRecord) -> bool:
    return abs(declared - (base * record.recargo_rate).quantize(_COMPARISON_QUANTUM)) <= CENT


def _finding(
    verdict: ChargedRecargoVerdict,
    record: RecargoRateRecord,
    base: Decimal,
    applied_rate: Decimal,
    declared: Decimal,
    devengo_date: date,
) -> ChargedRecargoFinding:
    return ChargedRecargoFinding(
        verdict=verdict,
        base=base,
        applied_rate=applied_rate,
        declared=declared,
        devengo_date=devengo_date,
        recargo_rate=record.recargo_rate,
        expected=round_to_cents(base * record.recargo_rate),
        legal_refs=record.legal_refs,
    )


_VERDICT_LOCALE_KEYS: dict[ChargedRecargoVerdict, str] = {
    ChargedRecargoVerdict.DEPARTS_FROM_PUBLISHED_RATE: (
        "aggregation.iva_ledger.errors.recargo_departs_from_published_rate"
    ),
    ChargedRecargoVerdict.RATE_UNMODELLED: "aggregation.iva_ledger.errors.recargo_rate_unmodelled",
    ChargedRecargoVerdict.TOBACCO_RUNG_UNSUPPORTED: "aggregation.iva_ledger.errors.recargo_tobacco_rung_unsupported",
}

_ISSUE_REASONS: dict[ChargedRecargoVerdict, IvaLedgerAggregationIssueReason] = {
    ChargedRecargoVerdict.DEPARTS_FROM_PUBLISHED_RATE: (
        IvaLedgerAggregationIssueReason.RECARGO_DEPARTS_FROM_PUBLISHED_RATE
    ),
    ChargedRecargoVerdict.RATE_UNMODELLED: IvaLedgerAggregationIssueReason.RECARGO_RATE_UNMODELLED,
    ChargedRecargoVerdict.TOBACCO_RUNG_UNSUPPORTED: IvaLedgerAggregationIssueReason.RECARGO_TOBACCO_RUNG_UNSUPPORTED,
}


def charged_recargo_issue(
    transaction: Transaction,
    *,
    operation_date: date,
    flow_direction: IvaFlowDirection,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Refuse a charged row whose recorded recargo cannot reach the recargo casilla as it stands.

    Runs after the IVA cuota screen, so a row whose own cuota is wrong names that
    fault first. A received row is never screened.
    """
    base = transaction.taxable_base
    applied_rate = transaction.iva_rate
    declared = transaction.recargo_amount
    if base is None or applied_rate is None or declared is None:
        return None
    flows = resolve_iva_flow_direction_catalogue(effective_date=operation_date, authority=operation)
    if flow_direction != flows.issued_token:
        return None
    finding = charged_recargo_finding(
        base=base,
        applied_rate=applied_rate,
        declared=declared,
        devengo_date=operation_date,
        operation=operation,
    )
    if finding is None:
        return None
    return IvaLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=_ISSUE_REASONS[finding.verdict],
        detail=charged_recargo_words(finding, operation=operation),
    )


def charged_recargo_words(finding: ChargedRecargoFinding, *, operation: PinnedAuthorityOperation) -> str:
    """The sentence explaining a charged recargo finding, in the filer's language."""
    figures = {
        "declared": eur_figure(finding.declared),
        "base": eur_figure(finding.base),
        "rate": percent_figure(finding.applied_rate),
        "date": finding.devengo_date.isoformat(),
    }
    if finding.recargo_rate is None or finding.expected is None:
        return tr(_VERDICT_LOCALE_KEYS[finding.verdict], **figures)
    provisions = ", ".join(
        f"art. {article}"
        for article in (operation.legal_reference(ref).article for ref in finding.legal_refs)
        if article is not None
    )
    return tr(
        _VERDICT_LOCALE_KEYS[finding.verdict],
        **figures,
        recargo_rate=percent_figure(finding.recargo_rate),
        expected=eur_figure(finding.expected),
        provision=provisions or ", ".join(finding.legal_refs),
    )


__all__ = [
    "ChargedRecargoFinding",
    "ChargedRecargoVerdict",
    "charged_recargo_finding",
    "charged_recargo_issue",
    "charged_recargo_words",
]
