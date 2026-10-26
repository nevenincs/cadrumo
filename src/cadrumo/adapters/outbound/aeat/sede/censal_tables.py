"""Header-driven parsing of census activities, premises and obligations."""

from __future__ import annotations

import re
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


def _table_rows(table: Tag) -> tuple[tuple[str, ...], tuple[CensalRow, ...]]:
    columns: tuple[str, ...] = ()
    result: list[CensalRow] = []
    explicitly_empty = False
    for row in table.select("tr, [role=row]"):
        if row.find_parent("tfoot") is not None:
            continue
        owner = row.find_parent(lambda tag: tag.name == "table" or tag.get("role") in {"table", "grid"})
        if owner is not table:
            continue
        cells = tuple(
            child
            for child in row.children
            if isinstance(child, Tag)
            and (child.name in {"th", "td"} or child.get("role") in {"columnheader", "cell", "gridcell"})
        )
        if not cells:
            continue
        if all(cell.name == "th" or cell.get("role") == "columnheader" for cell in cells):
            if any(cell.get("colspan", "1") != "1" for cell in cells):
                continue
            incoming = tuple(census_text(cell) or "" for cell in cells)
            if not any(incoming):
                continue
            if columns and incoming != columns:
                raise census_shape_error("conflicting table headers")
            columns = incoming
            keys = tuple(census_key(column) for column in columns)
            if not all(keys) or len(set(keys)) != len(keys):
                raise census_shape_error("empty or duplicate table headers")
            continue
        if not columns:
            raise census_shape_error("table values precede their headers")
        if len(cells) == 1 and census_key(census_text(cells[0]) or "") in _EMPTY_MARKERS:
            if result:
                raise census_shape_error("empty marker contradicts table records")
            explicitly_empty = True
            continue
        if explicitly_empty:
            raise census_shape_error("table records contradict empty marker")
        if len(cells) != len(columns) or any(
            cell.get("colspan", "1") != "1" or cell.get("rowspan", "1") != "1" for cell in cells
        ):
            raise census_shape_error("table cell/header cardinality changed")
        result.append(
            CensalRow(
                columns=columns,
                cells=tuple(
                    CensalCell(role="value", text=census_text(cell), column=column)
                    for column, cell in zip(columns, cells, strict=True)
                ),
            )
        )
    if not result and not explicitly_empty:
        raise census_shape_error("table is empty without an explicit empty-result marker")
    return columns, tuple(result)


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
    heading = next(
        (
            node
            for node in soup.select("h1, h2, [role=heading]")
            if census_key(census_text(node) or "") == _HEADINGS[kind]
        ),
        None,
    )
    if heading is None:
        raise census_shape_error("consultation heading missing")
    sections: list[CensalSection] = []
    for table in soup.select("table, [role=table], [role=grid]"):
        headers = {census_key(census_text(cell) or "") for cell in table.select("th, [role=columnheader]")}
        if not _REQUIRED_COLUMNS[kind].issubset(headers):
            continue
        _, rows = _table_rows(table)
        caption = table.find("caption")
        title = census_text(caption) if isinstance(caption, Tag) else census_text(heading)
        sections.append(CensalSection(title=title or kind, rows=rows))
    if not sections:
        raise census_shape_error("recognizable consultation table missing")
    for match in re.finditer(
        r"mostrados\s+los\s+registros\s+(\d+)\s+a\s+(\d+)\s+de\s+un\s+total\s+de\s+(\d+)",
        soup.get_text(" ", strip=True),
        re.IGNORECASE,
    ):
        first, last, total = map(int, match.groups())
        if first != 1 or last != total or total != sum(len(section.rows) for section in sections):
            raise census_shape_error("consultation is paginated or its record count is inconsistent")
    return CensalConsultation(kind=kind, source_url=census_source_url(source_url), sections=tuple(sections))
