"""What a structured record states as withheld and could not be read as a retencion.

A retencion is read only where the format names the withheld tax as IRPF. These
findings keep everything else visible: a withheld figure left unread is still money
that does not reach the bank, so the operator answers it rather than meeting the
shortfall later against a bank movement.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.draft_discrepancy import DraftDiscrepancyKind, DraftFindingWording
from ...core.percentage import fraction_of_percentage
from .closure_findings import retention_figures_disagree, within_rounding_allowance
from .invoice_draft_records import DraftDiscrepancyFinding, FindingWords
from .structured_invoice_ports import StructuredInvoiceRecord, StructuredWithheldTax

__all__ = ["withheld_tax_findings"]


def _unread_finding(stated_type: str | None, amount: Decimal | None) -> DraftDiscrepancyFinding:
    words = (
        FindingWords.of(DraftFindingWording.WITHHELD_UNNAMED_TAX, amount=amount)
        if stated_type is None
        else FindingWords.of(DraftFindingWording.WITHHELD_NAMED_TAX, amount=amount, tax=stated_type)
    )
    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        field="retencion_amount",
        words=words,
        observed=amount,
    )


def _total_finding(taxes: tuple[StructuredWithheldTax, ...], stated: Decimal) -> DraftDiscrepancyFinding | None:
    amounts = [row.amount for row in taxes if row.amount is not None]
    if len(amounts) != len(taxes):
        return None
    summed = sum(amounts, Decimal("0"))
    if within_rounding_allowance(stated - summed, term_count=len(amounts)):
        return None
    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        field="retencion_amount",
        words=FindingWords.of(DraftFindingWording.WITHHELD_TOTAL_DISAGREES, stated=stated, summed=summed),
        expected=summed,
        observed=stated,
    )


def _band_finding(row: StructuredWithheldTax) -> DraftDiscrepancyFinding | None:
    if row.rate is None or row.base is None or row.amount is None:
        return None
    if not retention_figures_disagree(rate_points=row.rate, amount=row.amount, base=row.base):
        return None
    expected = row.base * fraction_of_percentage(row.rate)
    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
        field="retencion_amount",
        words=FindingWords.of(
            DraftFindingWording.WITHHELD_NOT_RATE_OF_BASE,
            amount=row.amount,
            rate=row.rate,
            base=row.base,
            expected=expected,
        ),
        expected=expected,
        observed=row.amount,
    )


def _unread_findings(taxes: tuple[StructuredWithheldTax, ...], stated: Decimal | None) -> list[DraftDiscrepancyFinding]:
    findings: list[DraftDiscrepancyFinding] = []
    if not taxes and stated is not None and stated != 0:
        findings.append(_unread_finding(None, stated))
    findings.extend(
        _unread_finding(row.stated_type, row.amount)
        for row in taxes
        if not row.is_irpf and row.amount is not None and row.amount != 0
    )
    return findings


def _band_findings(taxes: tuple[StructuredWithheldTax, ...]) -> list[DraftDiscrepancyFinding]:
    return [finding for row in taxes if row.is_irpf and (finding := _band_finding(row)) is not None]


def withheld_tax_findings(record: StructuredInvoiceRecord) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return the findings a record's withheld figures raise, in a stable order.

    The per-tax rate check runs only where the record yielded no single rate. A single
    rate reaches the draft, where the shared closure check asks the same question, and
    asking twice would give the operator two blockers for one figure.
    """
    taxes = record.withheld_taxes
    stated = record.withheld_total
    findings = _unread_findings(taxes, stated)
    if taxes and stated is not None and (total := _total_finding(taxes, stated)) is not None:
        findings.append(total)
    if record.retencion_rate is None:
        findings.extend(_band_findings(taxes))
    return tuple(findings)
