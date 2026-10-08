"""Export saved reconciliation history and differences through the shared workbook plan."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from uuid import UUID

from ...core.hashing import canonical_json_bytes, sha256_hex
from ..storage.calc_sheets.records import (
    SheetCellAddress,
    SheetColumnWidth,
    SheetExportPlan,
    SheetFrozenView,
    SheetGuideContent,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetStyledRange,
    SheetValueCell,
    TabName,
)
from ..storage.calc_sheets.theme import StyleRole
from .reconciliation_list_operation import ModeloReconciliationListProjection


def build_modelo_reconciliation_export_plan(
    projection: ModeloReconciliationListProjection,
    *,
    publication_id: UUID,
    exported_at: datetime,
    label: Callable[[str], str],
) -> SheetExportPlan[SheetReviewMetadata]:
    """Render only persisted differences, references and advisories, with literal values.

    The caller obtains this exact-profile projection through the registered read
    operation and owns destination admission. No evidence file, present-day
    registry, ledger or remote service is consulted to rebuild old comparisons.
    Empty value strings remain missing rather than being translated to zero.
    """
    # Revalidate even when a caller used model_copy to construct a result.
    projection = ModeloReconciliationListProjection.model_validate_json(projection.model_dump_json())
    cells: list[SheetValueCell] = []
    styles: list[SheetStyledRange] = []
    widths: list[SheetColumnWidth] = []
    freezes: list[SheetFrozenView] = []
    protections: list[SheetProtectedRange] = []

    def table(
        tab: TabName, headers: Sequence[str], rows: Sequence[Sequence[str]], column_widths: Sequence[int]
    ) -> None:
        if len(rows) > 10_000 or len(cells) + (len(rows) + 1) * len(headers) > 250_000:
            raise ValueError("reconciliation exceeds workbook limits; select one work unit")
        for row_index, values in enumerate((tuple(label(header) for header in headers), *rows), 1):
            for column, value in enumerate(values, 1):
                if len(value) > 40_000:
                    raise ValueError("reconciliation text exceeds workbook cell limit")
                cells.append(
                    SheetValueCell(
                        address=SheetCellAddress.at(tab, row_index, column),
                        value=value,
                        role="source_value",
                    )
                )
        styles.append(
            SheetStyledRange(
                tab=tab,
                start_row=1,
                end_row=1,
                start_column=1,
                end_column=len(headers),
                role=StyleRole.HEADER,
                wrap=True,
            )
        )
        widths.extend(
            SheetColumnWidth(tab=tab, column=column, width=width) for column, width in enumerate(column_widths, 1)
        )
        freezes.append(SheetFrozenView(tab=tab, frozen_rows=1, frozen_columns=1))
        protections.append(
            SheetProtectedRange(
                tab=tab,
                start_row=1,
                end_row=len(rows) + 1,
                start_column=1,
                end_column=len(headers),
                description=label("saved_comparison_notice"),
            )
        )

    records: list[tuple[str, ...]] = []
    references: list[tuple[str, ...]] = []
    differences: list[tuple[str, ...]] = []
    advisories: list[tuple[str, ...]] = []
    for entry in projection.reconciliations:
        if entry.diff_count != len(entry.diffs) or entry.advisory_count != len(entry.advisories):
            raise ValueError("reconciliation detail is incomplete; export cannot discard findings")
        snapshot = entry.registry_snapshot_ref
        # A collision-free short reference joins the human rows to the full
        # persisted identity retained in the supporting reference sheet.
        prefix_length = 8
        while any(
            other.event_id != entry.event_id and other.event_id[:prefix_length] == entry.event_id[:prefix_length]
            for other in projection.reconciliations
        ):
            prefix_length += 1
        record_ref = f"R-{entry.event_id[:prefix_length]}"
        records.append(
            (
                f"{label('record')} {record_ref}",
                entry.reconciled_at.strftime("%Y-%m-%d %H:%M UTC"),
                snapshot.modelo if snapshot else "",
                str(snapshot.modelo_year) if snapshot else "",
                snapshot.period if snapshot else "",
                label(f"verdict_{entry.verdict.value}"),
                label(f"evidence_kind_{entry.source_kind.value}"),
                str(entry.diff_count),
                str(entry.advisory_count),
            )
        )
        references.append(
            (
                record_ref,
                entry.event_id,
                entry.reconciled_at.isoformat(),
                entry.verdict.value,
                snapshot.modelo if snapshot else "",
                str(snapshot.modelo_year) if snapshot else "",
                snapshot.period if snapshot else "",
                snapshot.revision_id if snapshot else "",
                entry.work_unit_id,
                entry.calculation_revision_id or "",
                entry.source_kind.value,
                entry.source_path,
                entry.actor,
            )
        )
        differences.extend(
            (
                record_ref,
                label(f"difference_kind_{diff.diff_kind.value}"),
                diff.field_name,
                diff.work_unit_value,
                diff.evidence_value,
                diff.kind,
                "\n".join(diff.legal_refs),
                "\n".join(diff.source_refs),
            )
            for diff in entry.diffs
        )
        advisories.extend(
            (
                record_ref,
                advisory.code,
                advisory.message,
                "\n".join(f"{key}: {value}" for key, value in advisory.context),
            )
            for advisory in entry.advisories
        )
    table(
        TabName.FORM,
        (
            "record",
            "date",
            "modelo",
            "year",
            "period",
            "verdict",
            "evidence_kind",
            "difference_count",
            "advisory_count",
        ),
        records,
        (32, 25, 12, 12, 12, 24, 24, 18, 18),
    )
    table(
        TabName.PROVENANCE,
        (
            "record",
            "record_identity",
            "date",
            "verdict",
            "modelo",
            "year",
            "period",
            "registry_revision",
            "work_unit",
            "calculation_revision",
            "evidence_kind",
            "evidence_reference",
            "actor",
        ),
        references,
        (18, 72, 28, 24, 12, 12, 12, 36, 72, 72, 24, 60, 28),
    )
    table(
        TabName.DETALLE,
        (
            "record",
            "difference_kind",
            "field",
            "saved_value",
            "evidence_value",
            "difference_reason",
            "legal_refs",
            "source_refs",
        ),
        differences,
        (18, 24, 30, 24, 24, 36, 45, 45),
    )
    table(TabName.EVIDENCIA, ("record", "advisory_code", "advisory", "context"), advisories, (18, 36, 70, 60))
    return SheetExportPlan[SheetReviewMetadata](
        metadata=SheetReviewMetadata(
            kind="reconciliation",
            snapshot_digest=sha256_hex(canonical_json_bytes(projection.model_dump(mode="json"))),
            publication_id=publication_id,
            title=label("title"),
            exported_at=exported_at,
        ),
        human_presentation=True,
        tabs=(TabName.FORM, TabName.DETALLE, TabName.EVIDENCIA, TabName.PROVENANCE, TabName.GUIDE),
        value_cells=tuple(cells),
        styled_ranges=tuple(styles),
        column_widths=tuple(widths),
        frozen_views=tuple(freezes),
        protected_ranges=tuple(protections),
        guide=SheetGuideContent(title=label("title"), paragraphs=(label("saved_comparison_notice"),)),
    )
