"""Compute the presentation facets (styled ranges, widths, freezes, filters).

Pure functions that derive the workbook's visual layout from the resolved
:class:`SheetLayout` plus the already-computed structural facets (section
headers, anchors, provenance / evidence extents). The output is consumed
verbatim by both transports through the shared ``_theme`` palette, so the
offline xls and online Sheets present the same official-modelo look. Keeping
this computation in one place is what makes the design uniform across every
modelo and every transport.

Both data tabs use the column layout ``A=Sección B=Casilla C=Concepto D=Valor``
with an anchor column ``F``; the Procedencia / Evidencia / Detalle / Guía tabs
have their own widths declared below.
"""

from __future__ import annotations

from ._layout import SheetLayout
from ._records import (
    SheetAnchor,
    SheetAutoFilter,
    SheetColumnWidth,
    SheetFrozenView,
    SheetProvenanceRow,
    SheetSectionHeader,
    SheetStyledRange,
    TabName,
)
from ._theme import StyleRole

# Column indices shared by the two data tabs.
_COL_SECTION = 1
_COL_CASILLA = 2
_COL_CONCEPTO = 3
_COL_VALUE = 4
_COL_ANCHOR = 6

# Approximate character widths per column, per tab, sized so labels and legal
# references read without clipping.
_DATA_WIDTHS: tuple[tuple[int, int], ...] = (
    (_COL_SECTION, 30),
    (_COL_CASILLA, 9),
    (_COL_CONCEPTO, 52),
    (_COL_VALUE, 16),
    (5, 4),
    (_COL_ANCHOR, 22),
)
_PROVENANCE_WIDTHS: tuple[tuple[int, int], ...] = (
    (1, 14),
    (2, 6),
    (3, 44),
    (4, 18),
    (5, 11),
    (6, 26),
    (7, 26),
    (8, 18),
)
_TARIFFS_WIDTHS: tuple[tuple[int, int], ...] = (
    (1, 30),
    (2, 4),
    (3, 16),
    (4, 16),
    (5, 16),
    (6, 16),
)
_EVIDENCIA_WIDTHS: tuple[tuple[int, int], ...] = (
    (1, 10),
    (2, 10),
    (3, 18),
    (4, 14),
    (5, 8),
    (6, 14),
    (7, 10),
    (8, 12),
    (9, 22),
    (10, 16),
    (11, 12),
    (12, 30),
    (13, 18),
    (14, 18),
    (15, 24),
    (16, 24),
)
_GUIDE_WIDTHS: tuple[tuple[int, int], ...] = (
    (1, 90),
    (2, 40),
)

_EVIDENCIA_HEADER_ROW = 3
_EVIDENCIA_COLUMNS = 16
# Evidence is often attached to the plan after build time (the verify / export
# action bundles it), so the body styling covers a generous fixed window rather
# than gating on a body count the build pass does not yet know. Wrapping blank
# cells is harmless; the window keeps note / ref columns readable once rows land.
_EVIDENCIA_BODY_WINDOW = 250


def _widths(tab: TabName, pairs: tuple[tuple[int, int], ...]) -> list[SheetColumnWidth]:
    return [SheetColumnWidth(tab=tab, column=column, width=width) for column, width in pairs]


def _data_tab_ranges(
    *,
    tab: TabName,
    last_row: int,
    value_role: StyleRole,
    section_headers: tuple[SheetSectionHeader, ...],
) -> list[SheetStyledRange]:
    """Styled ranges shared by the Entradas / Cálculos tabs.

    Header band on row 1, a section banner per section change, the value column
    tinted by ``value_role`` (input vs computed), and a wrapped concepto column.
    """
    ranges: list[SheetStyledRange] = [
        SheetStyledRange(
            tab=tab,
            start_row=1,
            end_row=1,
            start_column=_COL_SECTION,
            end_column=_COL_VALUE,
            role=StyleRole.HEADER,
        ),
    ]
    if last_row >= 2:
        ranges.extend(
            (
                SheetStyledRange(
                    tab=tab,
                    start_row=2,
                    end_row=last_row,
                    start_column=_COL_CONCEPTO,
                    end_column=_COL_CONCEPTO,
                    role=StyleRole.BODY,
                    wrap=True,
                ),
                SheetStyledRange(
                    tab=tab,
                    start_row=2,
                    end_row=last_row,
                    start_column=_COL_VALUE,
                    end_column=_COL_VALUE,
                    role=value_role,
                ),
            )
        )
    for header in section_headers:
        if header.address.tab is not tab:
            continue
        ranges.append(
            SheetStyledRange(
                tab=tab,
                start_row=header.address.row,
                end_row=header.address.row,
                start_column=_COL_SECTION,
                end_column=_COL_SECTION,
                role=StyleRole.SECTION_BANNER,
                wrap=True,
            ),
        )
    return ranges


def _anchor_ranges(anchors: tuple[SheetAnchor, ...]) -> list[SheetStyledRange]:
    """Tint the start anchor as a banner and the final anchor as the result."""
    ranges: list[SheetStyledRange] = []
    for anchor in anchors:
        role = StyleRole.RESULT if anchor.kind == "final" else StyleRole.SECTION_BANNER
        ranges.append(
            SheetStyledRange(
                tab=anchor.address.tab,
                start_row=anchor.address.row,
                end_row=anchor.address.row,
                start_column=anchor.address.column,
                end_column=anchor.address.column,
                role=role,
            ),
        )
    return ranges


def compute_styling(
    *,
    layout: SheetLayout,
    section_headers: tuple[SheetSectionHeader, ...],
    anchors: tuple[SheetAnchor, ...],
    provenance: tuple[SheetProvenanceRow, ...],
    guide_paragraphs: int,
) -> tuple[
    tuple[SheetStyledRange, ...],
    tuple[SheetColumnWidth, ...],
    tuple[SheetFrozenView, ...],
    tuple[SheetAutoFilter, ...],
]:
    """Derive ``(styled_ranges, column_widths, frozen_views, auto_filters)``.

    Returns a four-tuple of (:class:`SheetStyledRange`, :class:`SheetColumnWidth`,
    :class:`SheetFrozenView`, :class:`SheetAutoFilter`) tuples.

    A pure function of the resolved layout and the structural facets: two runs
    over the same inputs produce the same facets, so the design is deterministic
    and the two transports stay in lock-step.
    """
    entradas_last = max(
        (row.row for row in layout.entradas_rows),
        default=1,
    )
    binding_last = max((row.row for row in layout.binding_rows), default=1)
    entradas_last = max(entradas_last, binding_last, 1)
    calculos_last = max((row.row for row in layout.calculos_rows), default=1)
    provenance_last = max(len(provenance) + 1, 1)
    evidencia_last = _EVIDENCIA_HEADER_ROW + _EVIDENCIA_BODY_WINDOW

    styled: list[SheetStyledRange] = []
    styled += _data_tab_ranges(
        tab=TabName.ENTRADAS,
        last_row=entradas_last,
        value_role=StyleRole.INPUT,
        section_headers=section_headers,
    )
    styled += _data_tab_ranges(
        tab=TabName.CALCULOS,
        last_row=calculos_last,
        value_role=StyleRole.COMPUTED,
        section_headers=section_headers,
    )
    # Provenance header band + wrapped concepto / legal / source columns.
    styled.append(
        SheetStyledRange(
            tab=TabName.PROVENANCE,
            start_row=1,
            end_row=1,
            start_column=1,
            end_column=8,
            role=StyleRole.HEADER,
        ),
    )
    if provenance_last >= 2:
        for wrap_col in (3, 6, 7):
            styled.append(
                SheetStyledRange(
                    tab=TabName.PROVENANCE,
                    start_row=2,
                    end_row=provenance_last,
                    start_column=wrap_col,
                    end_column=wrap_col,
                    role=StyleRole.BODY,
                    wrap=True,
                ),
            )
    # Evidencia: fingerprint title on A1, header band on row 3, wrapped note /
    # ref columns.
    styled.append(
        SheetStyledRange(
            tab=TabName.EVIDENCIA,
            start_row=1,
            end_row=1,
            start_column=1,
            end_column=1,
            role=StyleRole.TITLE,
        ),
    )
    styled.append(
        SheetStyledRange(
            tab=TabName.EVIDENCIA,
            start_row=_EVIDENCIA_HEADER_ROW,
            end_row=_EVIDENCIA_HEADER_ROW,
            start_column=1,
            end_column=_EVIDENCIA_COLUMNS,
            role=StyleRole.HEADER,
        ),
    )
    for wrap_col in (12, 15, 16):
        styled.append(
            SheetStyledRange(
                tab=TabName.EVIDENCIA,
                start_row=_EVIDENCIA_HEADER_ROW + 1,
                end_row=evidencia_last,
                start_column=wrap_col,
                end_column=wrap_col,
                role=StyleRole.BODY,
                wrap=True,
            ),
        )
    # Guía: title on A1, wrapped prose column.
    styled.append(
        SheetStyledRange(tab=TabName.GUIDE, start_row=1, end_row=1, start_column=1, end_column=1, role=StyleRole.TITLE),
    )
    if guide_paragraphs:
        styled.append(
            SheetStyledRange(
                tab=TabName.GUIDE,
                start_row=3,
                end_row=2 + guide_paragraphs,
                start_column=1,
                end_column=1,
                role=StyleRole.BODY,
                wrap=True,
            ),
        )
    # Anchors last so the result accent wins over the broad value column.
    styled += _anchor_ranges(anchors)

    widths: list[SheetColumnWidth] = []
    widths += _widths(TabName.ENTRADAS, _DATA_WIDTHS)
    widths += _widths(TabName.CALCULOS, _DATA_WIDTHS)
    widths += _widths(TabName.PROVENANCE, _PROVENANCE_WIDTHS)
    widths += _widths(TabName.TARIFFS, _TARIFFS_WIDTHS)
    widths += _widths(TabName.EVIDENCIA, _EVIDENCIA_WIDTHS)
    widths += _widths(TabName.GUIDE, _GUIDE_WIDTHS)

    frozen: list[SheetFrozenView] = [
        SheetFrozenView(tab=TabName.ENTRADAS, frozen_rows=1),
        SheetFrozenView(tab=TabName.CALCULOS, frozen_rows=1),
        SheetFrozenView(tab=TabName.PROVENANCE, frozen_rows=1),
        SheetFrozenView(tab=TabName.EVIDENCIA, frozen_rows=_EVIDENCIA_HEADER_ROW),
    ]

    filters: list[SheetAutoFilter] = [
        SheetAutoFilter(tab=TabName.ENTRADAS, start_row=1, end_row=entradas_last, start_column=1, end_column=4),
        SheetAutoFilter(tab=TabName.CALCULOS, start_row=1, end_row=calculos_last, start_column=1, end_column=4),
        SheetAutoFilter(tab=TabName.PROVENANCE, start_row=1, end_row=provenance_last, start_column=1, end_column=8),
    ]
    filters.append(
        SheetAutoFilter(
            tab=TabName.EVIDENCIA,
            start_row=_EVIDENCIA_HEADER_ROW,
            end_row=evidencia_last,
            start_column=1,
            end_column=_EVIDENCIA_COLUMNS,
        ),
    )

    return tuple(styled), tuple(widths), tuple(frozen), tuple(filters)


__all__ = ["compute_styling"]
