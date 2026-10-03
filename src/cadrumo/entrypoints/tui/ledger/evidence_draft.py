"""Operator-facing wording for the safe invoice evidence draft projection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, assert_never

from ....application.ledger.invoice_draft_records import LabelReadingFallback, LabelReadingFallbackCause
from ....application.ledger.invoice_evidence_operation_dtos import (
    FieldProvenanceProjectionV1,
    InvoiceDraftProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.i18n.render import tr
from ....domain.iva.classification import InvoiceKind
from .models import LedgerEvidenceDraftV1

_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}


def draft_lines(draft: LedgerEvidenceDraftV1) -> tuple[str, ...]:
    """Show what the reader found; unread fields never imply a zero value.

    When the full projection is unavailable, a final line names the model
    reader's fallback and which fields were left unread.
    """
    unread = tr("tui.ledger.evidence.draft.unread")

    def shown(value: str | None) -> str:
        return unread if value is None else value

    if draft.full_projection is None:
        lines: tuple[str, ...] = (
            tr(
                "tui.ledger.evidence.draft.supplier",
                name=shown(draft.supplier_name),
                nif=shown(draft.supplier_tax_id),
            ),
            tr(
                "tui.ledger.evidence.draft.identity",
                number=shown(draft.invoice_number),
                date=shown(draft.invoice_date),
            ),
            tr(
                "tui.ledger.evidence.draft.amounts",
                base=shown(draft.taxable_base),
                rate=shown(draft.iva_rate),
                iva=shown(draft.iva_amount),
                total=shown(draft.grand_total),
                currency=shown(draft.currency),
            ),
            tr("tui.ledger.evidence.draft.discrepancies", count=draft.discrepancies),
        )
    else:
        lines = tuple(_full_draft_lines(draft.full_projection, shown=shown))
    fallback = draft.label_reading_fallback
    if fallback is None:
        return lines
    return (*lines, _label_reading_line(fallback))


def _full_draft_lines(
    projection: InvoiceDraftProjectionV1,
    *,
    shown: Callable[[str | None], str],
) -> list[str]:
    """Render every canonical draft fact with field labels and repeated evidence rows."""
    unread = tr("tui.ledger.evidence.draft.unread")

    def amount(value: PublicDecimal | None) -> str:
        return unread if value is None else value.decimal

    def invoice_kind(value: InvoiceKind | None) -> str:
        return unread if value is None else tr(_KIND_LOCALE_KEYS[value])

    supply_nature = unread if projection.proposed_supply_nature is None else projection.proposed_supply_nature.value
    lines = [
        tr(
            "tui.ledger.evidence.draft.party",
            role=tr("tui.ledger.evidence.draft.supplier_role"),
            name=shown(projection.supplier_name),
            tax_id=shown(projection.supplier_tax_id),
            postal_code=shown(projection.supplier_postal_code),
            country=shown(projection.supplier_country),
            country_code=shown(projection.supplier_country_code),
            stated_country_code=shown(projection.supplier_stated_country_code),
        ),
        tr(
            "tui.ledger.evidence.draft.party",
            role=tr("tui.ledger.evidence.draft.customer_role"),
            name=shown(projection.customer_name),
            tax_id=shown(projection.customer_tax_id),
            postal_code=shown(projection.customer_postal_code),
            country=shown(projection.customer_country),
            country_code=shown(projection.customer_country_code),
            stated_country_code=shown(projection.customer_stated_country_code),
        ),
        tr(
            "tui.ledger.evidence.draft.document",
            number=shown(projection.invoice_number),
            series=shown(projection.invoice_series),
            date=shown(projection.invoice_date),
            rectifies=shown(projection.rectifies_invoice_number),
            supply_nature=supply_nature,
            iva_category=shown(projection.iva_category),
            suggested_kind=invoice_kind(projection.suggested_kind),
        ),
        tr(
            "tui.ledger.evidence.draft.amounts",
            base=amount(projection.taxable_base),
            rate=amount(projection.iva_rate),
            iva=amount(projection.iva_amount),
            total=amount(projection.grand_total),
            currency=shown(projection.currency),
        ),
        tr("tui.ledger.evidence.draft.regime", value=shown(projection.regime_legend)),
        tr(
            "tui.ledger.evidence.draft.adjustments",
            recargo=amount(projection.recargo_amount),
            retention_rate=amount(projection.retencion_rate),
            retention=amount(projection.retencion_amount),
            suplidos=amount(projection.suplidos_amount),
        ),
    ]

    lines.extend(_line_rows(projection, amount=amount, shown=shown))
    lines.extend(_breakdown_rows(projection, amount=amount))
    lines.extend(_discrepancy_rows(projection, amount=amount, shown=shown))
    lines.extend(_provenance_rows(projection, unread=unread, shown=shown))

    structured_class = projection.facturae_invoice_class
    lines.append(
        tr(
            "tui.ledger.evidence.draft.structured_class",
            source_code=unread if structured_class is None else structured_class.source_code,
            kind=unread if structured_class is None else structured_class.kind.value,
        )
    )
    lines.append(
        tr(
            "tui.ledger.evidence.draft.source_metadata",
            transcription_sha256=shown(projection.transcription_sha256),
            raw_text_length=projection.raw_text_length,
        )
    )
    return lines


def _line_rows(
    projection: InvoiceDraftProjectionV1,
    *,
    amount: Callable[[PublicDecimal | None], str],
    shown: Callable[[str | None], str],
) -> list[str]:
    lines = [tr("tui.ledger.evidence.draft.lines_heading")]
    if not projection.lines:
        lines.append(tr("tui.ledger.evidence.draft.lines_empty"))
    for index, row in enumerate(projection.lines, start=1):
        lines.append(
            tr(
                "tui.ledger.evidence.draft.line",
                index=index,
                description=shown(row.description),
                quantity=amount(row.quantity),
                unit_price=amount(row.unit_price),
                base=amount(row.taxable_base),
                rate=amount(row.iva_rate),
                iva=amount(row.iva_amount),
                recargo_rate=amount(row.recargo_rate),
                recargo=amount(row.recargo_amount),
            )
        )
    return lines


def _breakdown_rows(
    projection: InvoiceDraftProjectionV1,
    *,
    amount: Callable[[PublicDecimal | None], str],
) -> list[str]:
    lines = [tr("tui.ledger.evidence.draft.breakdown_heading")]
    if not projection.iva_breakdown:
        lines.append(tr("tui.ledger.evidence.draft.breakdown_empty"))
    for index, row in enumerate(projection.iva_breakdown, start=1):
        lines.append(
            tr(
                "tui.ledger.evidence.draft.breakdown",
                index=index,
                rate=amount(row.iva_rate),
                base=amount(row.taxable_base),
                iva=amount(row.iva_amount),
                recargo_rate=amount(row.recargo_rate),
                recargo=amount(row.recargo_amount),
            )
        )
    return lines


def _discrepancy_rows(
    projection: InvoiceDraftProjectionV1,
    *,
    amount: Callable[[PublicDecimal | None], str],
    shown: Callable[[str | None], str],
) -> list[str]:
    lines = [tr("tui.ledger.evidence.draft.findings_heading")]
    if not projection.discrepancies:
        lines.append(tr("tui.ledger.evidence.draft.findings_empty"))
    for row in projection.discrepancies:
        lines.append(
            tr(
                "tui.ledger.evidence.draft.finding",
                kind=row.kind.value,
                field=shown(row.field),
                detail=shown(row.detail),
                expected=amount(row.expected),
                observed=amount(row.observed),
            )
        )
    return lines


def _provenance_rows(
    projection: InvoiceDraftProjectionV1,
    *,
    unread: str,
    shown: Callable[[str | None], str],
) -> list[str]:
    lines = [tr("tui.ledger.evidence.draft.provenance_heading")]
    if not projection.provenance:
        lines.append(tr("tui.ledger.evidence.draft.provenance_empty"))
    for row in projection.provenance:
        lines.extend(_provenance_lines(row, unread=unread, shown=shown))
    return lines


def _provenance_lines(
    row: FieldProvenanceProjectionV1,
    *,
    unread: str,
    shown: Callable[[str | None], str],
) -> tuple[str, ...]:
    """Preserve every provenance axis and each ambiguity candidate in the review."""
    values = [
        tr(
            "tui.ledger.evidence.draft.provenance",
            field=row.field,
            origin=row.origin.value,
            grounding=row.grounding.value,
            anchor=shown(row.anchor),
            refused_anchor=shown(row.refused_anchor),
            self_reported=tr(
                "tui.ledger.evidence.draft.yes" if row.anchor_self_reported else "tui.ledger.evidence.draft.no"
            ),
            derived_from=", ".join(row.derived_from) if row.derived_from else unread,
            role_evidence=shown(row.role_evidence),
            unverified=tr(
                "tui.ledger.evidence.draft.yes" if row.attribution_unverified else "tui.ledger.evidence.draft.no"
            ),
            note=row.note or unread,
        )
    ]
    values.extend(
        tr(
            "tui.ledger.evidence.draft.candidate",
            field=row.field,
            value=candidate.value,
            anchor=shown(candidate.anchor),
            note=candidate.note or unread,
        )
        for candidate in row.candidates
    )
    return tuple(values)


def _label_reading_line(fallback: LabelReadingFallback) -> str:
    """Name what stopped model fill and list every unread field."""
    match fallback.cause:
        case LabelReadingFallbackCause.READER_UNAVAILABLE:
            key = "tui.ledger.evidence.draft.label_reading.reader_unavailable"
        case LabelReadingFallbackCause.LOAD_HEADROOM_REFUSED:
            key = "tui.ledger.evidence.draft.label_reading.headroom_refused"
        case LabelReadingFallbackCause.INFERENCE_SLOT_BUSY:
            key = "tui.ledger.evidence.draft.label_reading.busy_refused"
        case unhandled:
            assert_never(unhandled)
    return tr(key, count=len(fallback.unread_fields), fields=", ".join(fallback.unread_fields))


__all__ = ["draft_lines"]
