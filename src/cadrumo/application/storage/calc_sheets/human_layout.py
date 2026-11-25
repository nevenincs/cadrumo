"""Assemble the presentation layout for human workbooks."""

from __future__ import annotations

from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .records import (
    SheetAutoFilter,
    SheetCellConstraint,
    SheetColumnWidth,
    SheetEvidenceFacet,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFrozenView,
    SheetHiddenRow,
    SheetMergedRange,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetRowHeight,
    SheetRowSet,
    SheetStyledRange,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .theme import StyleRole


def guide_paragraph_height(text: str) -> int:
    """Fit wrapped prose in the shared guide's 110-character-wide column."""
    return max(44, 20 * ((len(text) + 99) // 100 + 1))


def assemble_human_layout[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    rows: dict[tuple[TabName, int], CasillaDefinition],
    values: list[SheetValueCell],
    constraints: list[SheetCellConstraint],
    row_sets: tuple[SheetRowSet, ...],
    evidence_formats: list[SheetNumberFormat],
) -> SheetExportPlan[M]:
    """Replace support-tab layout while retaining calculation addressing."""
    replaced_tabs = (TabName.GUIDE, TabName.PROVENANCE, TabName.EVIDENCIA)
    sizes = {
        tab: (
            max(cell.address.row for cell in values if cell.address.tab is tab),
            max(cell.address.column for cell in values if cell.address.tab is tab),
        )
        for tab in replaced_tabs
    }
    widths: dict[TabName, tuple[int, ...]] = {
        TabName.GUIDE: (110,),
        TabName.PROVENANCE: (65, 80, 80),
        TabName.EVIDENCIA: (60, 15, 10, 15, 12, 15, 35, 15, 18, 20, 70, 70, 30, 60),
    }
    styles = tuple(
        style
        for tab, (last_row, last_column) in sizes.items()
        for style in (
            SheetStyledRange(
                tab=tab,
                start_row=1,
                end_row=last_row,
                start_column=1,
                end_column=last_column,
                role=StyleRole.FORM_LABEL,
                wrap=True,
            ),
            SheetStyledRange(
                tab=tab,
                start_row=1,
                end_row=1,
                start_column=1,
                end_column=last_column,
                role=StyleRole.FORM_SECTION,
                wrap=True,
            ),
        )
    )
    return type(plan).model_validate(
        {
            **dict(plan),
            "human_presentation": True,
            **_base_fields(plan, rows, values, constraints, row_sets, replaced_tabs),
            **_protection_fields(plan, sizes, replaced_tabs),
            **_view_fields(plan, widths, styles, replaced_tabs),
            **_format_fields(plan, values, evidence_formats, replaced_tabs),
        }
    )


def _base_fields[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    rows: dict[tuple[TabName, int], CasillaDefinition],
    values: list[SheetValueCell],
    constraints: list[SheetCellConstraint],
    row_sets: tuple[SheetRowSet, ...],
    replaced_tabs: tuple[TabName, ...],
) -> dict[str, object]:
    return {
        "hidden_rows": tuple(
            SheetHiddenRow(tab=tab, row=row)
            for tab, row in sorted(
                {(hidden.tab, hidden.row) for hidden in plan.hidden_rows if hidden.tab not in replaced_tabs}
                | {address for address, owner in rows.items() if owner.internal_only}
            )
        ),
        "value_cells": tuple(values),
        "cell_constraints": tuple(constraints),
        "row_sets": row_sets,
        "anchors": (),
        "section_headers": (),
        "evidence": SheetEvidenceFacet(),
    }


def _protection_fields[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M], sizes: dict[TabName, tuple[int, int]], replaced_tabs: tuple[TabName, ...]
) -> dict[str, object]:
    return {
        "protected_ranges": (
            *(
                region.model_copy(update={"description": "Datos calculados y referencias de consulta"})
                for region in plan.protected_ranges
                if region.tab not in replaced_tabs
            ),
            *(
                SheetProtectedRange(
                    tab=tab,
                    start_row=1,
                    end_row=last_row,
                    start_column=1,
                    end_column=last_column,
                    description="Datos y referencias de consulta",
                )
                for tab, (last_row, last_column) in sizes.items()
            ),
        ),
        "auto_filters": (
            *(region for region in plan.auto_filters if region.tab not in replaced_tabs),
            *(
                SheetAutoFilter(tab=tab, start_row=1, end_row=last_row, start_column=1, end_column=last_column)
                for tab, (last_row, last_column) in sizes.items()
                if tab is not TabName.GUIDE
            ),
        ),
    }


def _retained_merges[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M], replaced_tabs: tuple[TabName, ...]
) -> tuple[SheetMergedRange, ...]:
    return tuple(region for region in plan.merged_ranges if region.tab not in replaced_tabs)


def _view_fields[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    widths: dict[TabName, tuple[int, ...]],
    styles: tuple[SheetStyledRange, ...],
    replaced_tabs: tuple[TabName, ...],
) -> dict[str, object]:
    return {
        "frozen_views": (
            *(view for view in plan.frozen_views if view.tab not in replaced_tabs),
            *(SheetFrozenView(tab=tab, frozen_rows=1) for tab in replaced_tabs),
        ),
        "column_widths": (
            *(width for width in plan.column_widths if width.tab not in replaced_tabs),
            *(
                SheetColumnWidth(tab=tab, column=column, width=width)
                for tab, columns in widths.items()
                for column, width in enumerate(columns, 1)
            ),
        ),
        "styled_ranges": (*(style for style in plan.styled_ranges if style.tab not in replaced_tabs), *styles),
        "merged_ranges": _retained_merges(plan, replaced_tabs),
    }


def _format_fields[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    values: list[SheetValueCell],
    evidence_formats: list[SheetNumberFormat],
    replaced_tabs: tuple[TabName, ...],
) -> dict[str, object]:
    return {
        "row_heights": (
            *(height for height in plan.row_heights if height.tab not in replaced_tabs),
            *(
                SheetRowHeight(
                    tab=TabName.GUIDE,
                    row=cell.address.row,
                    height_pixels=guide_paragraph_height(str(cell.value)),
                )
                for cell in values
                if cell.address.tab is TabName.GUIDE
            ),
        ),
        "number_formats": (
            *(fmt for fmt in plan.number_formats if fmt.address.tab not in replaced_tabs),
            *evidence_formats,
        ),
    }
