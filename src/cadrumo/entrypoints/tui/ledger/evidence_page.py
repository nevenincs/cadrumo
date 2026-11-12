"""Operator-facing wording for what the page read serves of one stored document."""

from __future__ import annotations

from ....application.ledger.evidence_page_contracts import (
    EvidencePageMediaType,
    EvidenceStructuredFactV1,
    EvidenceStructuredInvoiceV1,
    LedgerEvidencePageProjection,
)
from ....core.i18n.render import tr


def _fact_value(fact: EvidenceStructuredFactV1) -> str:
    """The value as served: the record's text as it stands, or its figure as the backend wrote it."""
    if fact.text is not None:
        return fact.text
    return "" if fact.number is None else fact.number.decimal


def _fact_line(fact: EvidenceStructuredFactV1) -> str:
    return tr("tui.ledger.evidence.page.fact", label=tr(fact.label_key), value=_fact_value(fact))


def _structured_lines(invoice: EvidenceStructuredInvoiceV1) -> tuple[str, ...]:
    """Word a structured e-invoice: its served title, facts and lines, each under its served label."""
    if not invoice.facts and not invoice.lines:
        return (tr(invoice.title_key), tr("tui.ledger.evidence.page.empty"))
    return (
        tr(invoice.title_key),
        *(_fact_line(fact) for fact in invoice.facts),
        *(
            tr(
                "tui.ledger.evidence.page.line",
                position=position,
                facts="; ".join(_fact_line(fact) for fact in line.facts),
            )
            for position, line in enumerate(invoice.lines, start=1)
        ),
    )


def page_lines(page: LedgerEvidencePageProjection) -> tuple[str, ...]:
    """Show what the read served: a structured invoice's facts and lines, or a drawn page's place in its document.

    The terminal does not draw an image, so a PDF or an image states which
    page of which document the runtime drew, and says that it is not drawn here.
    """
    if page.structured_invoice is not None:
        return _structured_lines(page.structured_invoice)
    if page.media_type is EvidencePageMediaType.XML:
        return (tr("tui.ledger.evidence.page.empty"),)
    return (
        tr(
            "tui.ledger.evidence.page.document",
            file=page.file_name or "-",
            media=page.media_type.value,
            page=page.page,
            count=page.page_count,
        ),
        tr("tui.ledger.evidence.page.not_drawn"),
    )


__all__ = ["page_lines"]
