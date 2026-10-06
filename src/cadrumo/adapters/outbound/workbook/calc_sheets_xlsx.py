"""Offline XLSX materializer for a :class:`SheetExportPlan`.

This is the offline half of the one-builder / two-transport export contract: the
engine produces one plan, the Google Sheets apply adapter writes it to the
operator's Drive, and this module writes the same plan to an ``.xlsx`` payload
the operator can open without an account. The plan is the only input, so the two
transports cannot disagree about what the workbook says: every tab, cell,
formula, format, style, width, freeze, filter, protected region, note, input
validation and identity stamp here comes from a facet the plan declares, and this
module adds none of its own.

Three places the offline carrier differs from the online one, each a carrier
difference rather than a content difference:

- **Protection.** Sheets protects a rectangle; Excel protects a sheet and marks
  individual cells locked. So a tab the plan declares a protected range for gets
  sheet protection with the cells inside those rectangles locked and the written
  cells outside them unlocked, which leaves the same set editable on both
  transports. Sorting and filtering stay permitted, because the online
  protection restricts editing values rather than navigating them. No password is
  set: the online protection carries no shared secret either, and a password
  stored in a filing artefact would be a secret written to disk.
- **Identity.** Online, the registry and engine identity is spreadsheet
  developer metadata; offline it is workbook custom document properties, keyed by
  the same shared stamps, so a reader validating compatibility reads one
  vocabulary.
- **Numbers.** The online transport is sent ``USER_ENTERED`` text so Sheets
  parses the figure; here a ``Decimal`` is written as the number itself, which is
  exact and needs no parse.

Output is deterministic: the workbook's created/modified properties come from the
plan's export timestamp rather than the clock, and the archive is rebuilt with
one fixed entry timestamp, so materializing the same plan twice yields identical
bytes and a digest can identify the artefact.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC
from io import BytesIO
from typing import TYPE_CHECKING, Final, Literal, Protocol, cast
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.comments import Comment
from openpyxl.packaging.custom import StringProperty
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.writer.excel import ExcelWriter

from ....application.storage.calc_sheets.export_tables import export_identity_stamps
from ....application.storage.calc_sheets.records import (
    AnySheetExportPlan,
    SheetCellConstraint,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetStyledRange,
    SheetTemplatePreviewMetadata,
    TabName,
    column_index_to_letters,
)
from ....application.storage.calc_sheets.theme import (
    ROLE_STYLES,
    STYLED_RANGE_VERTICAL_ALIGN,
    WORKBOOK_FONT_FAMILY,
)
from ....application.storage.calc_sheets.workbook_cells import (
    formula_cell_blocks,
    plan_value_blocks,
    validate_merged_content,
)
from ....core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

_COMMENT_AUTHOR: Final[str] = "Cadrumo"
_DOCUMENT_CREATOR: Final[str] = "Cadrumo"
#: Alpha channel openpyxl expects ahead of the shared palette's ``RRGGBB``.
_OPAQUE_ALPHA: Final[str] = "FF"
#: The zip format cannot represent a timestamp before 1980.
_ARCHIVE_EPOCH: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
_LANDSCAPE: Final[Literal["landscape"]] = "landscape"

#: Every :class:`SheetExportPlan` field this materializer renders. ``tariffs`` and
#: ``provenance`` are rendered through the value cells the engine derives from
#: them, ``metadata`` and ``relation_provenance`` through the identity stamps and
#: the Guía surface, ``font_family`` as the base font of every written cell.
_RENDERED_PLAN_FACETS: Final[frozenset[str]] = frozenset(
    {
        "anchors",
        "auto_filters",
        "cell_constraints",
        "column_widths",
        "evidence",
        "font_family",
        "formula_cells",
        "frozen_views",
        "guide",
        "human_presentation",
        "metadata",
        "number_formats",
        "protected_ranges",
        "provenance",
        "relation_provenance",
        "row_sets",
        "section_headers",
        "styled_ranges",
        "tariffs",
        "tabs",
        "value_cells",
        "merged_ranges",
        "row_heights",
    },
)


class _CustomDocumentProperties(Protocol):
    """The one custom-property operation this materializer performs."""

    def append(self, prop: StringProperty) -> None:
        """Add one custom document property to the workbook."""
        ...


class _WorkbookCustomProperties(Protocol):
    """A workbook carrying custom document properties.

    ``openpyxl`` 3.1 exposes ``Workbook.custom_doc_props`` as public API, but the
    installed type stubs omit it. Naming the one attribute used keeps the access
    typed at this boundary instead of untyped everywhere it is reached.
    """

    @property
    def custom_doc_props(self) -> _CustomDocumentProperties:
        """The workbook's custom document properties."""
        ...


def unrendered_plan_facets(facet_names: Iterable[str]) -> tuple[str, ...]:
    """Return the named plan facets this materializer does not render.

    Args:
        facet_names: Field names declared by an export plan.

    Returns:
        tuple[str, ...]: The unrendered names, sorted. Empty when every named
        facet reaches the workbook.
    """
    return tuple(sorted(set(facet_names) - _RENDERED_PLAN_FACETS))


def _require_rendered_facets(plan: AnySheetExportPlan) -> None:
    """Refuse a plan carrying a facet this materializer would silently drop.

    A workbook missing a declared facet is not a lesser workbook; it is a
    workbook that says something the plan did not authorise it to say -- an
    unprotected computed region, or an operator input with no validation. The
    plan's schema is the inventory, so a facet added to the plan without being
    rendered here fails loudly at the first export instead of shipping.
    """
    unrendered = unrendered_plan_facets(type(plan).model_fields)
    if unrendered:
        raise InternalInvariantError(
            "offline workbook materializer does not render every declared plan facet",
            context={"unrendered_facets": ", ".join(unrendered)},
        )


def materialize_export_plan(plan: AnySheetExportPlan) -> bytes:
    """Materialise ``plan`` as the bytes of one offline ``.xlsx`` workbook.

    Args:
        plan: The :class:`~application.storage.calc_sheets.records.SheetExportPlan`
            produced by
            :func:`~application.storage.calc_sheets.engine.build_export_plan`.

    Returns:
        bytes: A complete workbook payload. The same plan always yields the same
        bytes, so a caller may content-address the artefact.

    Raises:
        :exc:`~core.errors.hierarchy.InternalInvariantError`: When the plan
            declares a facet this materializer does not render.
    """
    _require_rendered_facets(plan)
    validate_merged_content(plan)

    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    sheets: dict[TabName, Worksheet] = {tab: workbook.create_sheet(title=tab.value) for tab in plan.tabs}

    written = _write_cells(sheets, plan)
    family = plan.font_family or WORKBOOK_FONT_FAMILY
    _apply_base_font(written, family=family)
    _apply_styled_ranges(sheets, plan.styled_ranges, family=family)
    _apply_number_formats(sheets, plan)
    _apply_emphasis(sheets, plan)
    _apply_notes(sheets, plan)
    _apply_cell_constraints(sheets, plan)
    _apply_column_widths(sheets, plan)
    _apply_views(sheets, plan)
    _apply_auto_filters(sheets, plan)
    _apply_protection(sheets, plan, written=written)
    for region in plan.merged_ranges:
        sheets[region.tab].merge_cells(
            start_row=region.start_row,
            end_row=region.end_row,
            start_column=region.start_column,
            end_column=region.end_column,
        )
    for height in plan.row_heights:
        sheets[height.tab].row_dimensions[height.row].height = height.height_pixels * 0.75
    _stamp_identity(workbook, plan)

    return _deterministic_payload(workbook, plan)


def _cell(sheet: Worksheet, *, row: int, column: int) -> Cell:
    """Return one writable cell of ``sheet``.

    A worksheet answers with a merged placeholder where a merge covers the
    address, and such a cell holds no value of its own. This materializer merges
    nothing, so a placeholder here would mean the workbook no longer matches the
    plan rather than something to write around.

    Raises:
        :exc:`~core.errors.hierarchy.InternalInvariantError`: When the address is
            covered by a merge.
    """
    cell = sheet.cell(row=row, column=column)
    if not isinstance(cell, Cell):
        raise InternalInvariantError(
            "offline workbook cell is a merged placeholder",
            context={"tab": sheet.title, "row": row, "column": column},
        )
    return cell


def _write_cells(
    sheets: Mapping[TabName, Worksheet],
    plan: AnySheetExportPlan,
) -> Mapping[TabName, tuple[Cell, ...]]:
    """Write every value and formula the shared cell stream addresses.

    A blank operator-input cell is created without a value rather than skipped:
    it is a cell the plan declares, so it must carry the input styling that tells
    the operator to fill it in.
    """
    written: dict[TabName, list[Cell]] = {tab: [] for tab in plan.tabs}
    for block in plan_value_blocks(plan):
        for address, value in block.addressed_values():
            cell = _cell(sheets[address.tab], row=address.row, column=address.column)
            if value is not None:
                cell.value = value
                if isinstance(value, str):
                    cell.data_type = "s"
            written[address.tab].append(cell)
    for block in formula_cell_blocks(plan.formula_cells):
        for address, value in block.addressed_values():
            cell = _cell(sheets[address.tab], row=address.row, column=address.column)
            cell.value = value
            written[address.tab].append(cell)
    return {tab: tuple(cells) for tab, cells in written.items()}


def _apply_base_font(written: Mapping[TabName, tuple[Cell, ...]], *, family: str) -> None:
    """Set the declared family on every written cell, before role styling lands."""
    base = Font(name=family)
    for cells in written.values():
        for cell in cells:
            cell.font = base


def _apply_styled_ranges(
    sheets: Mapping[TabName, Worksheet],
    styled_ranges: Sequence[SheetStyledRange],
    *,
    family: str,
) -> None:
    """Resolve each role-tagged range through the shared palette and paint it.

    Ranges are painted in declaration order so a later narrow accent (the green
    result) wins over the broad column it refines, matching the order the online
    transport's requests are applied in.
    """
    for styled in styled_ranges:
        style = ROLE_STYLES[styled.role]
        font = Font(
            name=family,
            bold=style.bold,
            color=_argb(style.font_hex) if style.font_hex is not None else None,
        )
        fill = (
            PatternFill(fill_type="solid", start_color=_argb(style.fill_hex), end_color=_argb(style.fill_hex))
            if style.fill_hex is not None
            else None
        )
        alignment = Alignment(
            horizontal=style.align,
            vertical=STYLED_RANGE_VERTICAL_ALIGN,
            wrap_text=styled.wrap,
        )
        sheet = sheets[styled.tab]
        for row in range(styled.start_row, styled.end_row + 1):
            for column in range(styled.start_column, styled.end_column + 1):
                cell = _cell(sheet, row=row, column=column)
                cell.font = font
                cell.alignment = alignment
                if fill is not None:
                    cell.fill = fill
                if styled.boxed:
                    side = Side(style="thin")
                    cell.border = Border(top=side, bottom=side, left=side, right=side)


def _apply_number_formats(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Give each numeric casilla cell the display pattern the plan declares."""
    for number_format in plan.number_formats:
        address = number_format.address
        cell = _cell(sheets[address.tab], row=address.row, column=address.column)
        cell.number_format = number_format.pattern


def _apply_emphasis(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Bold the section-header cells and the start / final anchor labels.

    The weight is added to whatever font the cell already carries, so the role
    styling's family and colour survive.
    """
    addresses = [header.address for header in plan.section_headers] + [anchor.address for anchor in plan.anchors]
    for address in addresses:
        cell = _cell(sheets[address.tab], row=address.row, column=address.column)
        cell.font = cell.font + Font(bold=True)


def _apply_notes(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Attach each value cell's note as a workbook comment."""
    for value_cell in plan.value_cells:
        if value_cell.note is None:
            continue
        address = value_cell.address
        cell = _cell(sheets[address.tab], row=address.row, column=address.column)
        cell.comment = Comment(value_cell.note, _COMMENT_AUTHOR)


def _apply_cell_constraints(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Install each constrained cell's input validation and its grounding note.

    The note is attached after :func:`_apply_notes` for the same reason the
    online transport orders its requests this way: where a cell carries both, the
    legal grounding of the constraint is the more specific thing to say about it.
    """
    for constraint in plan.cell_constraints:
        validation = _validation_for(constraint)
        address = constraint.address
        sheet = sheets[address.tab]
        cell = _cell(sheet, row=address.row, column=address.column)
        cell.comment = Comment(constraint.grounding_message(), _COMMENT_AUTHOR)
        if validation is None:
            continue
        sheet.add_data_validation(validation)
        validation.add(cell)


def _validation_for(constraint: SheetCellConstraint) -> DataValidation | None:
    """Build the cell validation for a constraint, or ``None`` when it bounds nothing."""
    choices = constraint.text_validation_formula()
    if choices is not None:
        message = constraint.grounding_message()
        return DataValidation(
            type="custom",
            formula1=choices,
            allow_blank=True,
            showInputMessage=True,
            showErrorMessage=True,
            errorStyle="stop",
            prompt=message,
            error=message,
        )
    lower, upper = constraint.resolved_bounds()
    message = constraint.grounding_message()
    if lower is not None and upper is not None:
        operator, formula1, formula2 = "between", format(lower, "f"), format(upper, "f")
    elif lower is not None:
        operator, formula1, formula2 = "greaterThanOrEqual", format(lower, "f"), None
    elif upper is not None:
        operator, formula1, formula2 = "lessThanOrEqual", format(upper, "f"), None
    else:
        return None
    return DataValidation(
        type="decimal",
        operator=operator,
        formula1=formula1,
        formula2=formula2,
        allow_blank=True,
        showInputMessage=True,
        showErrorMessage=True,
        prompt=message,
        error=message,
    )


def _apply_column_widths(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Size each declared column so labels and legal references do not clip.

    The plan states widths in character units, which is the unit a spreadsheet
    column width already uses here; the online transport is the one that has to
    convert, into pixels.
    """
    for width in plan.column_widths:
        letters = column_index_to_letters(width.column)
        sheets[width.tab].column_dimensions[letters].width = width.width


def _apply_views(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Freeze each declared header band and repeat it on every printed page.

    The repeated print rows are the frozen rows: one declared header band, shown
    on screen while scrolling and again at the top of each printed page.
    """
    for sheet in sheets.values():
        sheet.page_setup.orientation = _LANDSCAPE
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    for frozen in plan.frozen_views:
        sheet = sheets[frozen.tab]
        sheet.freeze_panes = _cell(sheet, row=frozen.frozen_rows + 1, column=frozen.frozen_columns + 1)
        if frozen.frozen_rows:
            sheet.print_title_rows = f"1:{frozen.frozen_rows}"


def _apply_auto_filters(sheets: Mapping[TabName, Worksheet], plan: AnySheetExportPlan) -> None:
    """Install the declared filter over each tab's header and data rows."""
    for auto_filter in plan.auto_filters:
        start = f"{column_index_to_letters(auto_filter.start_column)}{auto_filter.start_row}"
        end = f"{column_index_to_letters(auto_filter.end_column)}{auto_filter.end_row}"
        sheets[auto_filter.tab].auto_filter.ref = f"{start}:{end}"


def _apply_protection(
    sheets: Mapping[TabName, Worksheet],
    plan: AnySheetExportPlan,
    *,
    written: Mapping[TabName, tuple[Cell, ...]],
) -> None:
    """Protect every tab the plan declares a protected range for.

    Sheet protection locks the cells inside the declared rectangles; the written
    cells outside them are unlocked so the editable set matches the online
    transport, where only the declared rectangles are protected.
    """
    ranges_by_tab: dict[TabName, list[SheetProtectedRange]] = {}
    for region in plan.protected_ranges:
        ranges_by_tab.setdefault(region.tab, []).append(region)
    unlocked = Protection(locked=False)
    for tab, regions in ranges_by_tab.items():
        sheet = sheets[tab]
        sheet.protection.sheet = True
        sheet.protection.sort = False
        sheet.protection.autoFilter = False
        for cell in written[tab]:
            if not _within_any(regions, row=cell.row, column=cell.column):
                cell.protection = unlocked


def _within_any(regions: Iterable[SheetProtectedRange], *, row: int, column: int) -> bool:
    """Whether a cell falls inside any of the declared protected rectangles."""
    return any(
        region.start_row <= row <= region.end_row and region.start_column <= column <= region.end_column
        for region in regions
    )


def _stamp_identity(workbook: Workbook, plan: AnySheetExportPlan) -> None:
    """Carry the export's identity in the workbook's own document properties.

    The shared stamps become custom document properties, the machine-readable
    offline counterpart of the online transport's developer metadata. The core
    properties carry the human-readable title and the plan's export timestamp;
    taking the timestamp from the plan rather than the clock is what makes two
    runs of one plan identical.
    """
    metadata = plan.metadata
    exported_at = metadata.exported_at.astimezone(UTC).replace(tzinfo=None)
    workbook.properties.creator = _DOCUMENT_CREATOR
    workbook.properties.lastModifiedBy = _DOCUMENT_CREATOR
    workbook.properties.title = (
        metadata.title
        if isinstance(metadata, (SheetReviewMetadata, SheetTemplatePreviewMetadata))
        else f"AEAT {metadata.modelo_id} {metadata.period.registry_token} {metadata.filing_year}"
    )
    workbook.properties.created = exported_at
    workbook.properties.modified = exported_at
    # The workbook ships live formulas with no cached results, so a reader must
    # compute them on open exactly as the online workbook does.
    workbook.calculation.fullCalcOnLoad = True
    properties = cast("_WorkbookCustomProperties", workbook).custom_doc_props
    for key, value in export_identity_stamps(plan):
        properties.append(StringProperty(name=key, value=value))


def _deterministic_payload(workbook: Workbook, plan: AnySheetExportPlan) -> bytes:
    """Serialize ``workbook`` into bytes that depend only on the plan.

    ``Workbook.save`` stamps the modification property with the wall clock and
    every archive entry with the current time, so the same plan would otherwise
    produce different bytes on every run. Writing through the archive writer
    keeps the plan's timestamp, and the archive is then rebuilt with one fixed
    entry timestamp.
    """
    raw = BytesIO()
    archive = ZipFile(raw, "w", ZIP_DEFLATED, allowZip64=True)
    ExcelWriter(workbook, archive).save()
    return _normalized_archive(raw.getvalue(), timestamp=_archive_timestamp(plan))


def _archive_timestamp(plan: AnySheetExportPlan) -> tuple[int, int, int, int, int, int]:
    """Return the plan's export instant as a zip entry timestamp."""
    exported_at = plan.metadata.exported_at.astimezone(UTC)
    stamp = (
        exported_at.year,
        exported_at.month,
        exported_at.day,
        exported_at.hour,
        exported_at.minute,
        exported_at.second,
    )
    return _ARCHIVE_EPOCH if exported_at.year < _ARCHIVE_EPOCH[0] else stamp


def _normalized_archive(raw: bytes, *, timestamp: tuple[int, int, int, int, int, int]) -> bytes:
    """Rewrite an archive so every entry carries one fixed timestamp.

    Entry order, names, contents and compression are preserved exactly; only the
    per-entry clock reading is replaced, because it is the one part of the
    payload that is not a function of the plan.
    """
    normalized = BytesIO()
    with (
        ZipFile(BytesIO(raw)) as source,
        ZipFile(normalized, "w", ZIP_DEFLATED, allowZip64=True) as target,
    ):
        for entry in source.infolist():
            fixed = ZipInfo(filename=entry.filename, date_time=timestamp)
            fixed.compress_type = entry.compress_type
            fixed.external_attr = entry.external_attr
            fixed.internal_attr = entry.internal_attr
            fixed.create_system = entry.create_system
            target.writestr(fixed, source.read(entry.filename))
    return normalized.getvalue()


def _argb(hex_value: str) -> str:
    """Convert a shared-palette ``RRGGBB`` colour to the opaque ``AARRGGBB`` form."""
    return f"{_OPAQUE_ALPHA}{hex_value.lstrip('#')}"


__all__ = [
    "materialize_export_plan",
    "unrendered_plan_facets",
]
