"""Projection of the figures owner's answers into the invoice figures preview contract."""

from __future__ import annotations

from decimal import Decimal

from ...domain.invoices.figures import (
    DatedRateSlot,
    FigureFinding,
    InvoiceFigures,
    LineFigures,
    StatedFigure,
)
from ...domain.invoices.rule_findings import rule_finding_words_key
from ..operations.public_scalar import PublicDecimal, project_facts
from .figures_preview_contracts import (
    INVOICE_FIGURES_PREVIEW_LABEL_PREFIX,
    InvoiceFiguresPreviewFigure,
    InvoiceFiguresPreviewFinding,
    InvoiceFiguresPreviewLineResult,
    InvoiceFiguresPreviewRateSlot,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewRetention,
    InvoiceFiguresPreviewRuleFinding,
    InvoiceFiguresPreviewTotals,
    InvoiceFiguresPreviewVerdict,
)
from .figures_preview_rule_findings import LocatedRuleFinding


def project_figure(figure: StatedFigure) -> InvoiceFiguresPreviewFigure:
    """Project one stated figure with its computed counterpart and verdict."""
    return InvoiceFiguresPreviewFigure(
        computed=_public(figure.computed),
        stated=_public(figure.stated),
        verdict=figure.verdict,
        submitted=_public(figure.submitted),
    )


def _rate_slot_label_key(slot: str) -> str:
    token = slot.lower().replace(".", "_")
    return f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}rate_slot.{token}"


def project_slot(slot: DatedRateSlot) -> InvoiceFiguresPreviewRateSlot:
    """Project one dated rate slot with its served label key."""
    return InvoiceFiguresPreviewRateSlot(
        slot=str(slot.slot),
        fraction=_public(slot.fraction),
        in_force=slot.in_force,
        coverage_gap=slot.coverage_gap,
        label_key=_rate_slot_label_key(str(slot.slot)),
    )


def project_finding(finding: FigureFinding, line_key: str | None = None) -> InvoiceFiguresPreviewFinding:
    """Project one figure finding, located on a line when it concerns one."""
    return InvoiceFiguresPreviewFinding(
        code=finding.code,
        severity=finding.severity,
        fields=finding.fields,
        line_key=line_key,
        values=project_facts(finding.values),
        label_key=f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}finding.{finding.code.value}",
    )


def project_rule_finding(located: LocatedRuleFinding) -> InvoiceFiguresPreviewRuleFinding:
    """Project one located document-rule finding."""
    finding = located.finding
    return InvoiceFiguresPreviewRuleFinding(
        code=finding.code,
        fields=finding.fields,
        line_key=located.line_key,
        values=project_facts(finding.values),
        label_key=rule_finding_words_key(finding.code),
    )


def project_totals(figures: InvoiceFigures) -> InvoiceFiguresPreviewTotals:
    """Project the invoice totals."""
    return InvoiceFiguresPreviewTotals(
        base=_public(figures.base_total),
        iva=_public(figures.iva_total),
        recargo=_public(figures.recargo_amount),
        total=_public(figures.total),
        net_of_retention=_public(figures.net_of_retention),
    )


def project_retention(figures: InvoiceFigures) -> InvoiceFiguresPreviewRetention:
    """Project the stated and implied retention."""
    return InvoiceFiguresPreviewRetention(
        rate=_public(figures.retention_rate),
        amount=_public(figures.retention_amount),
        implied=_public(figures.retention_implied),
    )


def project_lines(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
) -> tuple[InvoiceFiguresPreviewLineResult, ...]:
    """Project each line's subtotal and cuota in request order."""
    return tuple(
        InvoiceFiguresPreviewLineResult(
            key=line.key,
            subtotal=project_figure(figures.subtotal),
            iva_amount=project_figure(figures.iva_amount),
        )
        for line, figures in zip(request.lines, lines, strict=True)
    )


def project_findings(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
    date_findings: tuple[FigureFinding, ...],
    invoice: InvoiceFigures,
) -> tuple[InvoiceFiguresPreviewFinding, ...]:
    """Project the date, line and invoice figure findings in that order."""
    return (
        *(project_finding(finding) for finding in date_findings),
        *(
            project_finding(finding, line.key)
            for line, figures in zip(request.lines, lines, strict=True)
            for finding in figures.findings
        ),
        *(project_finding(finding) for finding in invoice.findings),
    )


def verdict_label(missing: tuple[str, ...], invoice_id: str | None) -> InvoiceFiguresPreviewVerdict:
    """Name how the draft was answered: incomplete, or what acceptance would do."""
    if missing:
        return "incomplete"
    return "would_accept" if invoice_id is not None else "would_refuse"


def _public(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))
