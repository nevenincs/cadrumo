"""Lay a calculation summary's pages out and draw them, recording a tag plan.

Layout runs to completion before anything is drawn, so every footer knows the
page total. Drawing then records, for every piece of text it sets, where that
text sits in the document's logical structure -- a path from the ``Document``
element down to a heading, paragraph or table cell -- or that it is an artifact:
the brand line, a repeated table header, a footer. The tagging pass pairs each
text object in the page content with the next entry of that plan, so this module
never writes marked-content operators itself, and the page writer never needs to
know what tagging is.

The pairing rests on one property of the page writer: it emits exactly one text
object per string drawn. :func:`draw_summary_pages` draws only through its
single-string calls, and the tagging pass refuses a page whose text objects and
plan entries do not pair one to one.

Every visible string comes from the presentation; this module chooses faces,
colours and positions and adds no words of its own. Colours are the brand's light
palette with inks that clear WCAG AA (4.5:1) on every ground they are set on.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, NamedTuple

from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from ....application.modelo.calculation_report import CalculationReportRowRole, CalculationReportValueState
from ....application.modelo.calculation_summary_presentation import (
    CalculationSummaryFact,
    CalculationSummaryPresentation,
    CalculationSummaryRow,
    CalculationSummarySection,
)
from .structure_tagging import StructNode, StructPath
from .summary_fonts import SummaryFace, register_summary_fonts

type Colour = tuple[float, float, float]


def _hex_colour(value: str) -> Colour:
    digits = value.removeprefix("#")
    red, green, blue = (int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4))
    return (red, green, blue)


INK: Final[Colour] = _hex_colour("#1c1a17")
MUTED_INK: Final[Colour] = _hex_colour("#6b655c")
RUST: Final[Colour] = _hex_colour("#c4553b")
RUST_INK: Final[Colour] = _hex_colour("#9e4029")
PANEL: Final[Colour] = _hex_colour("#f1eee7")
RULE: Final[Colour] = _hex_colour("#d8cec0")
SUCCESS_INK: Final[Colour] = _hex_colour("#3a6249")
SUCCESS_WASH: Final[Colour] = _hex_colour("#e7efe9")
WARNING_INK: Final[Colour] = _hex_colour("#7a4f0f")

PAGE_WIDTH, PAGE_HEIGHT = A4
_MARGIN_X: Final[float] = 50.0
_MARGIN_TOP: Final[float] = 56.0
_MARGIN_BOTTOM: Final[float] = 58.0
_CONTENT_WIDTH: Final[float] = PAGE_WIDTH - 2 * _MARGIN_X
_FOOTER_Y: Final[float] = 30.0
_FOOTER_RULE_Y: Final[float] = 42.0
_COLUMN_NUMBER_X: Final[float] = _MARGIN_X + 4
_COLUMN_LABEL_X: Final[float] = _MARGIN_X + 66
_NUMBER_WIDTH: Final[float] = _COLUMN_LABEL_X - _COLUMN_NUMBER_X - 8
_COLUMN_VALUE_RIGHT: Final[float] = PAGE_WIDTH - _MARGIN_X - 4
_VALUE_COLUMN_WIDTH: Final[float] = 132.0
_LABEL_WIDTH: Final[float] = _COLUMN_VALUE_RIGHT - _VALUE_COLUMN_WIDTH - 10 - _COLUMN_LABEL_X
_FACT_VALUE_X: Final[float] = _MARGIN_X + 150
_LINE: Final[float] = 11.0

_DOCUMENT: Final[StructNode] = ("Document", "document", ())
_ROW_SCOPE: Final[tuple[tuple[str, str], ...]] = (("Scope", "Row"),)
_COLUMN_SCOPE: Final[tuple[tuple[str, str], ...]] = (("Scope", "Column"),)


@dataclass(frozen=True, slots=True)
class DrawText:
    """One string set at one position, and where it sits in the structure."""

    x: float
    y: float
    text: str
    face: SummaryFace
    size: float
    colour: Colour
    align_right: bool
    tag: StructPath | None


@dataclass(frozen=True, slots=True)
class DrawRect:
    """One filled rectangle; always decoration."""

    x: float
    y: float
    width: float
    height: float
    colour: Colour


@dataclass(frozen=True, slots=True)
class DrawRule:
    """One stroked line; always decoration."""

    x1: float
    y1: float
    x2: float
    y2: float
    colour: Colour
    width: float


type DrawOperation = DrawText | DrawRect | DrawRule


@dataclass(slots=True)
class SummaryPage:
    """The operations one page draws, in drawing order."""

    operations: list[DrawOperation] = field(default_factory=list)


class DrawnSummary(NamedTuple):
    """Untagged page bytes and the per-page tag plan for their text objects."""

    payload: bytes
    plans: tuple[tuple[StructPath | None, ...], ...]


def wrap_text(text: str, face: SummaryFace, size: float, width: float) -> tuple[str, ...]:
    """Break ``text`` into lines no wider than ``width``, on spaces where possible.

    A single word wider than the line -- a long identifier, a token without
    spaces -- is broken between characters rather than allowed to run into the
    next column.
    """
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = word if not current else f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, face.value, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ""
        for character in word:
            if current and pdfmetrics.stringWidth(current + character, face.value, size) > width:
                lines.append(current)
                current = ""
            current += character
    if current or not lines:
        lines.append(current)
    return tuple(lines)


def _leaf(key: str, role: str, *parents: StructNode, attributes: tuple[tuple[str, str], ...] = ()) -> StructPath:
    return (_DOCUMENT, *parents, (role, key, attributes))


class _Layout:
    """A single flowing column with page breaks and repeated table headers."""

    def __init__(self) -> None:
        self.pages: list[SummaryPage] = [SummaryPage()]
        self.y = PAGE_HEIGHT - _MARGIN_TOP
        self._table_header: Callable[[bool], None] | None = None

    @property
    def page(self) -> SummaryPage:
        return self.pages[-1]

    def ensure(self, height: float) -> None:
        if self.y - height >= _MARGIN_BOTTOM:
            return
        self.pages.append(SummaryPage())
        self.y = PAGE_HEIGHT - _MARGIN_TOP
        if self._table_header is not None:
            self._table_header(True)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        face: SummaryFace,
        size: float,
        colour: Colour,
        *,
        tag: StructPath | None,
        align_right: bool = False,
    ) -> None:
        self.page.operations.append(DrawText(x, y, text, face, size, colour, align_right, tag))

    def rect(self, x: float, y: float, width: float, height: float, colour: Colour) -> None:
        self.page.operations.append(DrawRect(x, y, width, height, colour))

    def rule(self, x1: float, y1: float, x2: float, y2: float, colour: Colour, width: float) -> None:
        self.page.operations.append(DrawRule(x1, y1, x2, y2, colour, width))

    def start_table(self, header: Callable[[bool], None]) -> None:
        self._table_header = header
        header(False)

    def end_table(self) -> None:
        self._table_header = None


def _lay_title(layout: _Layout, presentation: CalculationSummaryPresentation) -> None:
    layout.text(_MARGIN_X, layout.y, presentation.brand, SummaryFace.TEXT_BOLD, 8.5, RUST_INK, tag=None)
    layout.rule(_MARGIN_X, layout.y - 6, PAGE_WIDTH - _MARGIN_X, layout.y - 6, RUST, 1.2)
    layout.y -= 34
    for line in wrap_text(presentation.title, SummaryFace.TEXT_BOLD, 18, _CONTENT_WIDTH):
        layout.text(_MARGIN_X, layout.y, line, SummaryFace.TEXT_BOLD, 18, INK, tag=_leaf("title", "H1"))
        layout.y -= 22
    layout.y += 4
    for line in wrap_text(presentation.subtitle, SummaryFace.TEXT, 9.5, _CONTENT_WIDTH):
        layout.text(_MARGIN_X, layout.y, line, SummaryFace.TEXT, 9.5, MUTED_INK, tag=_leaf("subtitle", "P"))
        layout.y -= 13
    layout.y -= 9


def _lay_notice(layout: _Layout, presentation: CalculationSummaryPresentation) -> None:
    notice: StructNode = ("Div", "notice", ())
    inner = _CONTENT_WIDTH - 28
    title_lines = wrap_text(presentation.notice_title, SummaryFace.TEXT_BOLD, 10, inner)
    body_lines = wrap_text(presentation.notice_body, SummaryFace.TEXT, 8.5, inner)
    identity_lines = wrap_text(presentation.software_identity_notice, SummaryFace.TEXT, 8.5, inner)
    height = 12 + 13 * len(title_lines) + 3 + _LINE * len(body_lines) + 5 + _LINE * len(identity_lines) + 6
    layout.ensure(height + 8)
    top = layout.y
    layout.rect(_MARGIN_X, top - height, _CONTENT_WIDTH, height, PANEL)
    layout.rect(_MARGIN_X, top - height, 3, height, RUST)
    y = top - 16
    for line in title_lines:
        tag = (_DOCUMENT, notice, ("P", "notice-title", ()))
        layout.text(_MARGIN_X + 14, y, line, SummaryFace.TEXT_BOLD, 10, RUST_INK, tag=tag)
        y -= 13
    y -= 3
    for line in body_lines:
        layout.text(
            _MARGIN_X + 14, y, line, SummaryFace.TEXT, 8.5, INK, tag=(_DOCUMENT, notice, ("P", "notice-body", ()))
        )
        y -= _LINE
    y -= 5
    for line in identity_lines:
        tag = (_DOCUMENT, notice, ("P", "notice-identity", ()))
        layout.text(_MARGIN_X + 14, y, line, SummaryFace.TEXT, 8.5, WARNING_INK, tag=tag)
        y -= _LINE
    layout.y = top - height - 18


def _lay_fact_rows(
    layout: _Layout,
    facts: tuple[CalculationSummaryFact, ...],
    *,
    table_key: str,
    value_face: SummaryFace,
    value_size: float,
    value_below: bool,
) -> None:
    """Lay a two-column label/value table, each label a row header."""
    table: StructNode = ("Table", table_key, ())
    value_x = _MARGIN_X if value_below else _FACT_VALUE_X
    value_width = _CONTENT_WIDTH if value_below else PAGE_WIDTH - _MARGIN_X - _FACT_VALUE_X
    for index, fact in enumerate(facts):
        row: StructNode = ("TR", f"{table_key}-r{index}", ())
        value_lines = wrap_text(fact.value, value_face, value_size, value_width)
        height = (_LINE + 3 if value_below else 0) + _LINE * len(value_lines) + 3
        layout.ensure(height)
        header_tag = (_DOCUMENT, table, row, ("TH", f"{table_key}-r{index}-h", _ROW_SCOPE))
        layout.text(_MARGIN_X, layout.y, fact.label, SummaryFace.TEXT, 8.5, MUTED_INK, tag=header_tag)
        y = layout.y - (_LINE + 1 if value_below else 0)
        for line in value_lines:
            cell_tag = (_DOCUMENT, table, row, ("TD", f"{table_key}-r{index}-v", ()))
            layout.text(value_x, y, line, value_face, value_size, INK, tag=cell_tag)
            y -= _LINE
        layout.y -= height + (4 if value_below else 0)


def _lay_paragraph(layout: _Layout, text: str, *, key: str, size: float, colour: Colour) -> None:
    """Lay one paragraph, kept on one page whenever it fits on one."""
    lines = wrap_text(text, SummaryFace.TEXT, size, _CONTENT_WIDTH)
    layout.ensure(min(_LINE * len(lines), PAGE_HEIGHT - _MARGIN_TOP - _MARGIN_BOTTOM))
    for line in lines:
        layout.ensure(_LINE)
        layout.text(_MARGIN_X, layout.y, line, SummaryFace.TEXT, size, colour, tag=_leaf(key, "P"))
        layout.y -= _LINE


def _lay_heading(layout: _Layout, text: str, *, key: str, reserve: float) -> None:
    lines = wrap_text(text, SummaryFace.TEXT_BOLD, 12, _CONTENT_WIDTH)
    layout.ensure(15 * len(lines) + reserve)
    for line in lines:
        layout.text(_MARGIN_X, layout.y, line, SummaryFace.TEXT_BOLD, 12, INK, tag=_leaf(key, "H2"))
        layout.y -= 15
    layout.rule(_MARGIN_X, layout.y + 10, PAGE_WIDTH - _MARGIN_X, layout.y + 10, RUST, 0.8)
    layout.y -= 5


def _value_style(row: CalculationSummaryRow) -> tuple[SummaryFace, Colour]:
    if row.value_state is CalculationReportValueState.ABSENT:
        return SummaryFace.TEXT, WARNING_INK
    if row.value_state is CalculationReportValueState.NOT_APPLICABLE:
        return SummaryFace.TEXT, MUTED_INK
    emphasised = row.row_role in (CalculationReportRowRole.SUBTOTAL, CalculationReportRowRole.RESULT)
    colour = SUCCESS_INK if row.row_role is CalculationReportRowRole.RESULT else INK
    return (SummaryFace.FIGURE_BOLD if emphasised else SummaryFace.FIGURE), colour


def _lay_section(
    layout: _Layout,
    presentation: CalculationSummaryPresentation,
    section: CalculationSummarySection,
    *,
    index: int,
) -> None:
    _lay_heading(layout, section.heading, key=f"section-{index}-heading", reserve=18 + 18)
    table: StructNode = ("Table", f"section-{index}", ())

    def header(repeated: bool) -> None:
        row: StructNode = ("TR", f"section-{index}-header", ())

        def tag(column: str) -> StructPath | None:
            if repeated:
                return None
            return (_DOCUMENT, table, row, ("TH", f"section-{index}-header-{column}", _COLUMN_SCOPE))

        layout.rect(_MARGIN_X, layout.y - 4, _CONTENT_WIDTH, 15, PANEL)
        face = SummaryFace.TEXT_SEMIBOLD
        layout.text(_COLUMN_NUMBER_X, layout.y, presentation.column_casilla, face, 8, MUTED_INK, tag=tag("number"))
        layout.text(_COLUMN_LABEL_X, layout.y, presentation.column_concept, face, 8, MUTED_INK, tag=tag("concept"))
        layout.text(
            _COLUMN_VALUE_RIGHT,
            layout.y,
            presentation.column_amount,
            face,
            8,
            MUTED_INK,
            tag=tag("amount"),
            align_right=True,
        )
        layout.y -= 17

    layout.start_table(header)
    for row_index, row in enumerate(section.rows):
        emphasised = row.row_role in (CalculationReportRowRole.SUBTOTAL, CalculationReportRowRole.RESULT)
        label_face = SummaryFace.TEXT_BOLD if emphasised else SummaryFace.TEXT
        value_face, value_colour = _value_style(row)
        number_lines = wrap_text(row.casilla_number, SummaryFace.FIGURE, 9, _NUMBER_WIDTH)
        label_lines = wrap_text(row.label, label_face, 9, _LABEL_WIDTH) if row.label else ()
        value_lines = wrap_text(row.value_text, value_face, 9, _VALUE_COLUMN_WIDTH)
        height = 5 + _LINE * max(len(number_lines), len(label_lines), len(value_lines))
        layout.ensure(height + 2)
        tr: StructNode = ("TR", f"section-{index}-r{row_index}", ())
        if row.row_role is CalculationReportRowRole.RESULT:
            layout.rect(_MARGIN_X, layout.y - height + 7, _CONTENT_WIDTH, height + 2, SUCCESS_WASH)
        number_tag = (_DOCUMENT, table, tr, ("TD", f"section-{index}-r{row_index}-number", ()))
        for line_index, line in enumerate(number_lines):
            layout.text(
                _COLUMN_NUMBER_X, layout.y - _LINE * line_index, line, SummaryFace.FIGURE, 9, INK, tag=number_tag
            )
        label_tag = (_DOCUMENT, table, tr, ("TD", f"section-{index}-r{row_index}-concept", ()))
        for line_index, line in enumerate(label_lines):
            layout.text(_COLUMN_LABEL_X, layout.y - _LINE * line_index, line, label_face, 9, INK, tag=label_tag)
        value_tag = (_DOCUMENT, table, tr, ("TD", f"section-{index}-r{row_index}-amount", ()))
        for line_index, line in enumerate(value_lines):
            layout.text(
                _COLUMN_VALUE_RIGHT,
                layout.y - _LINE * line_index,
                line,
                value_face,
                9,
                value_colour,
                tag=value_tag,
                align_right=True,
            )
        layout.y -= height
        layout.rule(_MARGIN_X, layout.y + 7, PAGE_WIDTH - _MARGIN_X, layout.y + 7, RULE, 0.4)
        layout.y -= 2
    layout.end_table()
    layout.y -= 12


def _lay_footers(layout: _Layout, presentation: CalculationSummaryPresentation) -> None:
    total = len(layout.pages)
    for number, page in enumerate(layout.pages, start=1):
        page.operations.append(DrawRule(_MARGIN_X, _FOOTER_RULE_Y, PAGE_WIDTH - _MARGIN_X, _FOOTER_RULE_Y, RULE, 0.5))
        page.operations.append(
            DrawText(_MARGIN_X, _FOOTER_Y, presentation.footer_notice, SummaryFace.TEXT, 7.5, MUTED_INK, False, None),
        )
        page.operations.append(
            DrawText(
                PAGE_WIDTH - _MARGIN_X,
                _FOOTER_Y,
                f"{presentation.page_counter(number, total)} \u00b7 {presentation.revision_prefix}",
                SummaryFace.TEXT,
                7.5,
                MUTED_INK,
                True,
                None,
            ),
        )


def lay_out_summary(presentation: CalculationSummaryPresentation) -> tuple[SummaryPage, ...]:
    """Lay every page of the summary out, footers included."""
    register_summary_fonts()
    layout = _Layout()
    _lay_title(layout, presentation)
    _lay_notice(layout, presentation)
    _lay_fact_rows(
        layout,
        presentation.facts,
        table_key="facts",
        value_face=SummaryFace.TEXT,
        value_size=9,
        value_below=False,
    )
    layout.y -= 6
    _lay_paragraph(layout, presentation.legend, key="legend", size=8, colour=MUTED_INK)
    layout.y -= 10
    for index, section in enumerate(presentation.sections):
        _lay_section(layout, presentation, section, index=index)
    _lay_heading(layout, presentation.trace_heading, key="trace-heading", reserve=2 * _LINE + 8)
    _lay_fact_rows(
        layout,
        presentation.trace,
        table_key="trace",
        value_face=SummaryFace.FIGURE,
        value_size=7.5,
        value_below=True,
    )
    layout.y -= 4
    _lay_paragraph(layout, presentation.signature_meaning, key="signature-meaning", size=8.5, colour=INK)
    _lay_footers(layout, presentation)
    return tuple(layout.pages)


def _summary_canvas(buffer: io.BytesIO, *, language: str) -> canvas.Canvas:
    """Open a page canvas whose initial font is the summary's text face.

    The initial font matters for archival conformance: the page writer's built-in
    default is a standard font it references on every page without embedding,
    while an embedded TrueType initial face is referenced by nothing until text is
    set in it. The face is chosen through the writer's own default for the one
    construction, and the default is restored before anything else can read it.
    """
    previous = rl_config.canvas_basefontname
    rl_config.canvas_basefontname = SummaryFace.TEXT.value
    try:
        return canvas.Canvas(buffer, pagesize=A4, pageCompression=0, invariant=1, lang=language)
    finally:
        rl_config.canvas_basefontname = previous


def draw_summary_pages(pages: tuple[SummaryPage, ...], *, language: str) -> DrawnSummary:
    """Draw laid-out pages; return the untagged bytes and the per-page tag plan.

    Drawn uncompressed and in the page writer's invariant mode, so the output is a
    function of the pages alone: no creation clock and no random document id.
    """
    register_summary_fonts()
    buffer = io.BytesIO()
    page_canvas = _summary_canvas(buffer, language=language)
    plans: list[tuple[StructPath | None, ...]] = []
    for page in pages:
        plan: list[StructPath | None] = []
        for operation in page.operations:
            if isinstance(operation, DrawRect):
                page_canvas.setFillColorRGB(*operation.colour)
                page_canvas.rect(operation.x, operation.y, operation.width, operation.height, stroke=0, fill=1)
            elif isinstance(operation, DrawRule):
                page_canvas.setStrokeColorRGB(*operation.colour)
                page_canvas.setLineWidth(operation.width)
                page_canvas.line(operation.x1, operation.y1, operation.x2, operation.y2)
            else:
                page_canvas.setFont(operation.face.value, operation.size)
                page_canvas.setFillColorRGB(*operation.colour)
                if operation.align_right:
                    page_canvas.drawRightString(operation.x, operation.y, operation.text)
                else:
                    page_canvas.drawString(operation.x, operation.y, operation.text)
                plan.append(operation.tag)
        plans.append(tuple(plan))
        page_canvas.showPage()
    page_canvas.save()
    return DrawnSummary(payload=buffer.getvalue(), plans=tuple(plans))


__all__ = [
    "INK",
    "MUTED_INK",
    "PAGE_HEIGHT",
    "PAGE_WIDTH",
    "PANEL",
    "RULE",
    "RUST",
    "RUST_INK",
    "SUCCESS_INK",
    "SUCCESS_WASH",
    "WARNING_INK",
    "DrawRect",
    "DrawRule",
    "DrawText",
    "DrawnSummary",
    "SummaryPage",
    "draw_summary_pages",
    "lay_out_summary",
    "wrap_text",
]
