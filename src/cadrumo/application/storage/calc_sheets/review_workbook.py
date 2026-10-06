"""Project a sealed local review baseline through the canonical workbook plan."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from ...export.review_snapshot import CalculationReviewSelection, ReviewSnapshot, ReviewSourceKind
from .records import (
    SheetAutoFilter,
    SheetCellAddress,
    SheetColumnWidth,
    SheetExportPlan,
    SheetFrozenView,
    SheetGuideContent,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetStyledRange,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole
from .workbook_cells import SheetCellValue

_MAX_ROWS = 10_000
_MAX_CELLS = 250_000
_MAX_TEXT = 40_000
_HEADER_ROW = 4
_FIRST_ROW = 5
_REVIEW_ROWS = 30

type ReviewLabelResolver = Callable[[str], str]


def _column_width(header: str) -> int:
    if header in {"casilla", "currency", "unit", "byte_length"}:
        return 14
    if header in {"booked_date", "value_date", "review_date"}:
        return 18
    if header in {"detail", "finding", "scenario", "description", "reason"}:
        return 60
    if header in {"value", "digest", "registry_digest", "source_refs", "legal_refs"}:
        return 48
    if header in {"sources", "results", "evidence", "attachments", "document_links", "reference"}:
        return 38
    return 26


def _exact(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


class _ReviewLayout:
    """Collect typed presentation facets, with no source reads or calculations."""

    def __init__(self, label: ReviewLabelResolver) -> None:
        self.label = label
        self.cells: list[SheetValueCell] = []
        self.styles: list[SheetStyledRange] = []
        self.widths: list[SheetColumnWidth] = []
        self.freezes: list[SheetFrozenView] = []
        self.filters: list[SheetAutoFilter] = []
        self.formats: list[SheetNumberFormat] = []
        self.tabs: list[TabName] = []

    def row(self, tab: TabName, row: int, values: Sequence[SheetCellValue]) -> None:
        if row > _MAX_ROWS or len(self.cells) + len(values) > _MAX_CELLS:
            raise ValueError("review exceeds workbook output limits; select a smaller snapshot")
        for column, value in enumerate(values, 1):
            if value is None and tab is not TabName.ENTRADAS:
                value = self.label("not_captured")
            if isinstance(value, str) and len(value) > _MAX_TEXT:
                raise ValueError("review text exceeds workbook cell limit")
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError("review numeric value must be finite")
            self.cells.append(
                SheetValueCell(address=SheetCellAddress.at(tab, row, column), value=value, role="metadata")
            )

    def style(
        self, tab: TabName, first: int, last: int, columns: int, role: StyleRole, *, start_column: int = 1
    ) -> None:
        self.styles.append(
            SheetStyledRange(
                tab=tab,
                start_row=first,
                end_row=last,
                start_column=start_column,
                end_column=columns,
                role=role,
                wrap=True,
            )
        )

    def table(
        self,
        tab: TabName,
        title: str,
        notice: str,
        headers: tuple[str, ...],
        rows: Sequence[Sequence[SheetCellValue]],
    ) -> None:
        projected_cells = len(self.cells) + 4 + len(headers) + len(rows) * len(headers)
        if _HEADER_ROW + len(rows) > _MAX_ROWS or projected_cells > _MAX_CELLS:
            raise ValueError("review exceeds workbook output limits; select a smaller snapshot")
        self.tabs.append(tab)
        self.row(tab, 1, (self.label(title),))
        notice_text = self.label(notice)
        if not rows:
            notice_text += "\n" + self.label("no_captured_rows")
        self.row(tab, 2, (notice_text,))
        self.row(tab, 3, (self.label("overview"), "'Guía'!A1"))
        self.row(tab, _HEADER_ROW, tuple(self.label(header) for header in headers))
        for index, values in enumerate(rows, _FIRST_ROW):
            if len(values) != len(headers):
                raise ValueError("review table row does not match its header")
            self.row(tab, index, values)
        end = max(_HEADER_ROW, _HEADER_ROW + len(rows))
        self.style(tab, 1, 1, len(headers), StyleRole.TITLE)
        self.style(tab, 2, 3, len(headers), StyleRole.BODY)
        self.style(tab, _HEADER_ROW, _HEADER_ROW, len(headers), StyleRole.HEADER)
        if rows:
            self.style(tab, _FIRST_ROW, end, len(headers), StyleRole.BODY)
        self.widths.extend(
            SheetColumnWidth(tab=tab, column=column, width=_column_width(header))
            for column, header in enumerate(headers, 1)
        )
        self.freezes.append(SheetFrozenView(tab=tab, frozen_rows=_HEADER_ROW, frozen_columns=1))
        self.filters.append(
            SheetAutoFilter(tab=tab, start_row=_HEADER_ROW, end_row=end, start_column=1, end_column=len(headers))
        )

    def numeric(self, tab: TabName, row: int, column: int, value: Decimal | None) -> None:
        if value is not None:
            self.formats.append(
                SheetNumberFormat(
                    address=SheetCellAddress.at(tab, row, column),
                    data_type="decimal",
                    pattern="#,##0.00##########",
                )
            )


def build_review_workbook(
    snapshot: ReviewSnapshot,
    *,
    publication_id: UUID,
    exported_at: datetime,
    label: ReviewLabelResolver,
) -> SheetExportPlan[SheetReviewMetadata]:
    """Render captured facts only; labels are supplied by the localized caller.

    Calculation rows retain snapshot order. A ledger review carries no calculation
    identity or casilla claim. Cross-references use explicit contribution identities,
    never period proximity. No live formulas or external acquisition are generated.
    """
    if (
        max(
            len(snapshot.amounts),
            len(snapshot.ledger_rows),
            len(snapshot.contributions),
            len(snapshot.evidence),
            len(snapshot.findings),
        )
        > _MAX_ROWS - _HEADER_ROW
    ):
        raise ValueError("review exceeds workbook output limits; select a smaller snapshot")
    layout = _ReviewLayout(label)
    selection = snapshot.selection
    amount_addresses = {
        item.amount_id: f"'Cálculos'!A{index}" for index, item in enumerate(snapshot.amounts, _FIRST_ROW)
    }
    source_addresses = {
        item.contribution_id: f"'Procedencia'!A{index}" for index, item in enumerate(snapshot.contributions, _FIRST_ROW)
    }
    ledger_addresses = {
        item.transaction_id: f"'Detalle'!A{index}" for index, item in enumerate(snapshot.ledger_rows, _FIRST_ROW)
    }
    evidence_addresses = {
        item.evidence_id: f"'Evidencia'!A{index}" for index, item in enumerate(snapshot.evidence, _FIRST_ROW)
    }
    source_amounts: dict[str, list[str]] = {item.contribution_id: [] for item in snapshot.contributions}
    for amount in snapshot.amounts:
        for source_id in amount.contribution_ids:
            source_amounts[source_id].append(amount_addresses[amount.amount_id])

    overview: list[tuple[SheetCellValue, ...]] = [
        (label("status"), snapshot.status.value),
        (label("review_quality"), label("status_" + snapshot.status.value)),
        (label("snapshot"), snapshot.snapshot_digest),
        (label("publication"), str(publication_id)),
        (label("exported_at"), exported_at.isoformat()),
        (label("evidence_scope"), label("index_only_notice")),
        (label("numeric_notice"), label("exact_decimal_notice")),
        (label("missing_data"), label("not_captured_notice")),
    ]
    if isinstance(selection, CalculationReviewSelection):
        overview.extend(
            (
                (label("modelo"), selection.modelo),
                (label("period"), f"{selection.filing_year} / {selection.period}"),
                (label("work_unit"), selection.work_unit_id),
                (label("calculation_revision"), selection.calculation_revision_id),
                (label("registry_revision"), selection.registry_snapshot_ref.revision_id),
                (label("authority"), selection.authority_generation),
                (label("registry_digest"), selection.registry_digest),
            )
        )
    else:
        overview.extend(
            ((label("ledger_snapshot"), selection.ledger_snapshot_id), (label("scope"), label("ledger_scope_notice")))
        )
    overview.extend(
        (label("finding") + ": " + item.code, item.detail + "\n" + ", ".join(item.related_ids))
        for item in snapshot.findings
    )
    overview.extend(
        (label(key), Decimal(count))
        for key, count in (
            ("result_count", len(snapshot.amounts)),
            ("ledger_row_count", len(snapshot.ledger_rows)),
            ("contribution_count", len(snapshot.contributions)),
            ("evidence_count", len(snapshot.evidence)),
            ("finding_count", len(snapshot.findings)),
        )
    )
    overview.extend(
        (label(key), target)
        for key, target in (
            ("ledger", "'Detalle'!A1"),
            ("sources", "'Procedencia'!A1"),
            ("evidence", "'Evidencia'!A1"),
            ("review", "'Entradas'!A1"),
        )
    )
    if isinstance(selection, CalculationReviewSelection):
        overview.append((label("results"), "'Cálculos'!A1"))
    layout.table(TabName.GUIDE, "overview", "baseline_notice", ("field", "value"), overview)
    layout.widths[-1] = SheetColumnWidth(tab=TabName.GUIDE, column=2, width=90)
    layout.style(TabName.GUIDE, _FIRST_ROW, _FIRST_ROW + 1, 2, StyleRole.SECTION_BANNER)

    if isinstance(selection, CalculationReviewSelection):
        layout.table(
            TabName.CALCULOS,
            "results",
            "baseline_notice",
            (
                "amount_id",
                "casilla",
                "row_id",
                "value",
                "exact_value",
                "unit",
                "currency",
                "rounding",
                "sources",
                "formula",
                "legal_refs",
                "source_refs",
            ),
            [
                (
                    item.amount_id,
                    item.casilla_id,
                    item.row_id,
                    item.value,
                    str(item.value),
                    item.unit,
                    item.currency,
                    item.rounding,
                    "\n".join(source_addresses[key] for key in item.contribution_ids),
                    item.formula_reference,
                    "\n".join(item.legal_refs),
                    "\n".join(item.source_refs),
                )
                for item in snapshot.amounts
            ],
        )
        for index, amount in enumerate(snapshot.amounts, _FIRST_ROW):
            layout.numeric(TabName.CALCULOS, index, 4, amount.value)
        if snapshot.amounts:
            layout.style(
                TabName.CALCULOS, _FIRST_ROW, _HEADER_ROW + len(snapshot.amounts), 4, StyleRole.COMPUTED, start_column=4
            )

    ledger_sources: dict[str, list[str]] = {}
    ledger_results: dict[str, list[str]] = {}
    ledger_evidence: dict[str, list[str]] = {}
    invoice_evidence: dict[str, list[str]] = {}
    evidence_sources: dict[str, list[str]] = {item.evidence_id: [] for item in snapshot.evidence}
    for source in snapshot.contributions:
        for evidence_id in source.evidence_ids:
            evidence_sources[evidence_id].append(source_addresses[source.contribution_id])
        if source.kind is ReviewSourceKind.LEDGER_ROW:
            ledger_sources.setdefault(source.source_id, []).append(source_addresses[source.contribution_id])
            ledger_results.setdefault(source.source_id, []).extend(source_amounts[source.contribution_id])
            ledger_evidence.setdefault(source.source_id, []).extend(source.evidence_ids)
        elif source.kind is ReviewSourceKind.INVOICE:
            invoice_evidence.setdefault(source.source_id, []).extend(source.evidence_ids)
    ledger_rows: list[tuple[SheetCellValue, ...]] = []
    for index, row in enumerate(snapshot.ledger_rows, _FIRST_ROW):
        booked = date.fromisoformat(row.booked_date)
        linked_results = tuple(dict.fromkeys(ledger_results.get(row.transaction_id, ())))
        captured_evidence_ids = tuple(
            dict.fromkeys(
                (
                    *ledger_evidence.get(row.transaction_id, ()),
                    *(invoice_evidence.get(row.invoice_id, ()) if row.invoice_id is not None else ()),
                    *row.attachment_ids,
                    *row.document_link_ids,
                    row.purchase_invoice_evidence_id,
                )
            )
        )
        evidence_links = tuple(
            evidence_addresses[key] for key in captured_evidence_ids if key is not None and key in evidence_addresses
        )
        ledger_rows.append(
            (
                row.transaction_id,
                Decimal((booked - date(1899, 12, 30)).days),
                row.value_date,
                row.direction,
                row.amount,
                row.currency,
                row.value_in_eur,
                row.business_classification,
                row.taxable_base,
                row.iva_amount,
                row.counterparty,
                row.invoice_id,
                row.fingerprint,
                "\n".join(ledger_sources.get(row.transaction_id, ())) or label("unattributed"),
                "\n".join(row.attachment_ids),
                "\n".join(row.document_link_ids),
                row.fx_rate,
                row.business_pct,
                row.iva_rate,
                row.recargo_amount,
                row.iva_category,
                row.irpf_category,
                row.purchase_invoice_evidence_id,
                str(row.amount),
                "\n".join(row.legal_refs),
                "\n".join(row.source_refs),
                "\n".join(linked_results) or label("unattributed"),
                "\n".join(evidence_links) or label("no_inventory_reference"),
                row.lifecycle_state,
                row.description,
                row.usage_ratio_id,
                row.deduction_fact_kind,
                row.art_104_tres_exclusion,
                row.input_classification,
                row.prorrata_sector_id,
                row.prorrata_reference,
                row.category_id,
                row.source_jurisdiction,
                row.m210_official_tipo_renta_code,
                row.m210_gross_income_amount,
                row.m210_applicable_rate,
                row.m210_payer_mode,
                row.m210_payer_id,
                row.m210_asset_or_right_id,
                row.counterparty_country,
                _exact(row.value_in_eur),
                _exact(row.taxable_base),
                _exact(row.iva_amount),
                _exact(row.fx_rate),
                _exact(row.business_pct),
                _exact(row.iva_rate),
                _exact(row.recargo_amount),
                _exact(row.m210_gross_income_amount),
                _exact(row.m210_applicable_rate),
            )
        )
        layout.formats.append(
            SheetNumberFormat(
                address=SheetCellAddress.at(TabName.DETALLE, index, 2), data_type="date", pattern="yyyy-mm-dd"
            )
        )
        for column, value in (
            (5, row.amount),
            (7, row.value_in_eur),
            (9, row.taxable_base),
            (10, row.iva_amount),
            (17, row.fx_rate),
            (18, row.business_pct),
            (19, row.iva_rate),
            (20, row.recargo_amount),
            (40, row.m210_gross_income_amount),
            (41, row.m210_applicable_rate),
        ):
            layout.numeric(TabName.DETALLE, index, column, value)
    layout.table(
        TabName.DETALLE,
        "ledger",
        "ledger_notice",
        (
            "transaction",
            "booked_date",
            "value_date",
            "direction",
            "amount",
            "currency",
            "eur_value",
            "classification",
            "taxable_base",
            "iva_amount",
            "counterparty",
            "invoice",
            "digest",
            "sources",
            "attachments",
            "document_links",
            "fx_rate",
            "business_pct",
            "iva_rate",
            "recargo_amount",
            "iva_category",
            "irpf_category",
            "purchase_invoice_evidence",
            "exact_amount",
            "legal_refs",
            "source_refs",
            "results",
            "evidence",
            "lifecycle_state",
            "description",
            "usage_ratio_id",
            "deduction_fact_kind",
            "art_104_tres_exclusion",
            "input_classification",
            "prorrata_sector_id",
            "prorrata_reference",
            "category_id",
            "source_jurisdiction",
            "m210_official_tipo_renta_code",
            "m210_gross_income_amount",
            "m210_applicable_rate",
            "m210_payer_mode",
            "m210_payer_id",
            "m210_asset_or_right_id",
            "counterparty_country",
            "exact_eur_value",
            "exact_taxable_base",
            "exact_iva_amount",
            "exact_fx_rate",
            "exact_business_pct",
            "exact_iva_rate",
            "exact_recargo_amount",
            "exact_m210_gross_income_amount",
            "exact_m210_applicable_rate",
        ),
        ledger_rows,
    )
    layout.table(
        TabName.PROVENANCE,
        "sources",
        "attribution_notice",
        (
            "contribution",
            "kind",
            "source_id",
            "source_revision",
            "digest",
            "ledger",
            "results",
            "evidence",
            "detail",
            "source_kind",
        ),
        [
            (
                item.contribution_id,
                item.kind.value,
                item.source_id,
                item.source_revision,
                item.source_digest,
                ledger_addresses.get(item.source_id)
                if item.kind is ReviewSourceKind.LEDGER_ROW
                else label("not_ledger_source"),
                "\n".join(source_amounts[item.contribution_id]) or label("unattributed"),
                "\n".join(evidence_addresses[key] for key in item.evidence_ids),
                item.detail,
                label("source_kind_" + item.kind.value),
            )
            for item in snapshot.contributions
        ],
    )
    layout.table(
        TabName.EVIDENCIA,
        "evidence",
        "index_only_notice",
        (
            "evidence_id",
            "source_revision",
            "disposition",
            "digest",
            "media_type",
            "byte_length",
            "reason",
            "availability",
            "sources",
        ),
        [
            (
                item.evidence_id,
                item.source_revision,
                item.disposition.value,
                item.digest,
                item.media_type,
                Decimal(item.byte_length) if item.byte_length is not None else None,
                item.reason,
                label("evidence_" + item.disposition.value),
                "\n".join(evidence_sources[item.evidence_id]) or label("unattributed"),
            )
            for item in snapshot.evidence
        ],
    )
    layout.table(
        TabName.ENTRADAS,
        "review",
        "external_notes_notice",
        (
            "reference",
            "finding",
            "scenario",
            "reviewer",
            "review_date",
            "review_status",
        ),
        [(None,) * 6 for _ in range(_REVIEW_ROWS)],
    )
    layout.style(TabName.ENTRADAS, _FIRST_ROW, _HEADER_ROW + _REVIEW_ROWS, 6, StyleRole.INPUT)
    return SheetExportPlan[SheetReviewMetadata](
        metadata=SheetReviewMetadata(
            kind=selection.kind,
            snapshot_digest=snapshot.snapshot_digest,
            publication_id=publication_id,
            title=label("overview"),
            exported_at=exported_at,
        ),
        tabs=tuple(layout.tabs),
        value_cells=tuple(layout.cells),
        number_formats=tuple(layout.formats),
        styled_ranges=tuple(layout.styles),
        column_widths=tuple(layout.widths),
        frozen_views=tuple(layout.freezes),
        auto_filters=tuple(layout.filters),
        guide=SheetGuideContent(title=label("overview"), paragraphs=(label("baseline_notice"),)),
    )
