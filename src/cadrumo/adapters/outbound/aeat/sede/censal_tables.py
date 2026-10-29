"""Header-driven parsing of census activities, premises and obligations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl

from .....application.user_profile.censal_observation import (
    CensalCell,
    CensalConsultation,
    CensalRow,
    CensalSection,
)
from .....core.text_fold import fold_diacritics
from .._html import parse_html
from .errors import SedeFailureMode, SedeParseError


def census_text(element: Tag) -> str | None:
    """Read rendered text without executable source or nonbreaking padding."""
    text = " ".join(element.get_text(" ", strip=True).split())
    return text or None


def census_key(text: str) -> str:
    """Normalize presentation punctuation without changing the source label."""
    return re.sub(r"[^\w]+", "", fold_diacritics(text).casefold())


def census_document(html: str) -> BeautifulSoup:
    """Remove executable source before reading the rendered document."""
    soup = parse_html(html)
    for element in soup.select("script, style, noscript"):
        element.decompose()
    return soup


def census_source_url(url: str) -> AnyHttpUrl:
    """Keep the public route, excluding query parameters and fragments."""
    parts = urlsplit(url)
    return AnyHttpUrl(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


def census_shape_error(reason: str) -> SedeParseError:
    """Report a structural refusal without including private page content."""
    # Error messages describe the shape, never untrusted cell values.
    return SedeParseError(
        f"Census consultation shape is unsupported: {reason}",
        failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
    )


_HEADINGS = {
    "actividades": "relaciondeactividades",
    "locales": "relaciondelocalesdeunaactividad",
    "obligaciones": "obligacionestributarias",
}
_REQUIRED_COLUMNS = {
    "actividades": frozenset({"epigrafe", "denominacion", "estado"}),
    "locales": frozenset({"domicilio", "estado", "referenciacatastral"}),
    "obligaciones": frozenset({"descripciondelaobligacion", "periodicidad", "estado"}),
}
_EMPTY_MARKERS = frozenset({"noexistenregistros", "nohayregistros", "nosehanencontradoregistros"})


def _owned_cells(row: Tag, table: Tag) -> tuple[Tag, ...]:
    if row.find_parent("tfoot") is not None:
        return ()
    owner = row.find_parent(lambda tag: tag.name == "table" or tag.get("role") in {"table", "grid"})
    if owner is not table:
        return ()
    return tuple(child for child in row.children if isinstance(child, Tag) and _is_cell(child))


def _is_cell(element: Tag) -> bool:
    return element.name in {"th", "td"} or element.get("role") in {"columnheader", "cell", "gridcell"}


def _header_cells(cells: tuple[Tag, ...]) -> bool:
    return all(cell.name == "th" or cell.get("role") == "columnheader" for cell in cells)


def _incoming_header(cells: tuple[Tag, ...]) -> tuple[str, ...]:
    if any(cell.get("colspan", "1") != "1" for cell in cells):
        return ()
    incoming = tuple(census_text(cell) or "" for cell in cells)
    return incoming if any(incoming) else ()


def _check_header(columns: tuple[str, ...]) -> None:
    keys = tuple(census_key(column) for column in columns)
    if not all(keys) or len(set(keys)) != len(keys):
        raise census_shape_error("empty or duplicate table headers")


def _empty_marker(cells: tuple[Tag, ...]) -> bool:
    return len(cells) == 1 and census_key(census_text(cells[0]) or "") in _EMPTY_MARKERS


def _check_geometry(cells: tuple[Tag, ...], columns: tuple[str, ...]) -> None:
    if len(cells) != len(columns) or any(
        cell.get("colspan", "1") != "1" or cell.get("rowspan", "1") != "1" for cell in cells
    ):
        raise census_shape_error("table cell/header cardinality changed")


@dataclass
class _TableRows:
    columns: tuple[str, ...] = ()
    records: list[CensalRow] = field(default_factory=list)
    explicitly_empty: bool = False

    def header(self, cells: tuple[Tag, ...]) -> None:
        incoming = _incoming_header(cells)
        if not incoming:
            return
        if self.columns and incoming != self.columns:
            raise census_shape_error("conflicting table headers")
        self.columns = incoming
        _check_header(self.columns)

    def values(self, cells: tuple[Tag, ...]) -> None:
        if not self.columns:
            raise census_shape_error("table values precede their headers")
        if _empty_marker(cells):
            if self.records:
                raise census_shape_error("empty marker contradicts table records")
            self.explicitly_empty = True
            return
        if self.explicitly_empty:
            raise census_shape_error("table records contradict empty marker")
        _check_geometry(cells, self.columns)
        self.records.append(
            CensalRow(
                columns=self.columns,
                cells=tuple(
                    CensalCell(role="value", text=census_text(cell), column=column)
                    for column, cell in zip(self.columns, cells, strict=True)
                ),
            )
        )


def _table_rows(table: Tag) -> tuple[tuple[str, ...], tuple[CensalRow, ...]]:
    state = _TableRows()
    for row in table.select("tr, [role=row]"):
        cells = _owned_cells(row, table)
        if not cells:
            continue
        if _header_cells(cells):
            state.header(cells)
        else:
            state.values(cells)
    if not state.records and not state.explicitly_empty:
        raise census_shape_error("table is empty without an explicit empty-result marker")
    return state.columns, tuple(state.records)


def _consultation_heading(soup: BeautifulSoup, expected: str) -> Tag:
    for node in soup.select("h1, h2, [role=heading]"):
        if census_key(census_text(node) or "") == expected:
            return node
    raise census_shape_error("consultation heading missing")


def _consultation_sections(
    soup: BeautifulSoup,
    heading: Tag,
    required: frozenset[str],
    kind: str,
) -> tuple[CensalSection, ...]:
    sections: list[CensalSection] = []
    for table in soup.select("table, [role=table], [role=grid]"):
        headers = {census_key(census_text(cell) or "") for cell in table.select("th, [role=columnheader]")}
        if not required.issubset(headers):
            continue
        _, rows = _table_rows(table)
        caption = table.find("caption")
        title = census_text(caption) if isinstance(caption, Tag) else census_text(heading)
        sections.append(CensalSection(title=title or kind, rows=rows))
    if not sections:
        raise census_shape_error("recognizable consultation table missing")
    return tuple(sections)


def _check_pagination(soup: BeautifulSoup, sections: tuple[CensalSection, ...]) -> None:
    for match in re.finditer(
        r"mostrados\s+los\s+registros\s+(\d+)\s+a\s+(\d+)\s+de\s+un\s+total\s+de\s+(\d+)",
        soup.get_text(" ", strip=True),
        re.IGNORECASE,
    ):
        first, last, total = map(int, match.groups())
        if first != 1 or last != total or total != sum(len(section.rows) for section in sections):
            raise census_shape_error("consultation is paginated or its record count is inconsistent")


def parse_censal_table(
    html: str,
    *,
    kind: Literal["actividades", "locales", "obligaciones"],
    source_url: str,
) -> CensalConsultation:
    """Recognize a consultation and associate every value with its own header.

    New columns survive verbatim. A missing or ambiguous header is a shape
    change, never permission to shift values or report an empty census.
    """
    soup = census_document(html)
    heading = _consultation_heading(soup, _HEADINGS[kind])
    sections = _consultation_sections(soup, heading, _REQUIRED_COLUMNS[kind], kind)
    _check_pagination(soup, sections)
    return CensalConsultation(kind=kind, source_url=census_source_url(source_url), sections=sections)
