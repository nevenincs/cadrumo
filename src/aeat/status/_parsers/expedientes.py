"""Parser for the *Mis expedientes* AEAT surface.

Extracts every expediente row from a server-rendered HTML snapshot
into a tuple of :class:`aeat.status.Expediente`. The parser selects
the canonical ``<table>`` by its ``<th>`` header text, which survives
the minor layout drift AEAT ships between campaigns.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from aeat.logging import get_logger

from .._errors import StatusParseError
from .._models import Expediente

logger = get_logger(__name__)

_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)

_REQUIRED_HEADERS: tuple[str, ...] = (
    "expediente",
    "modelo",
    "periodo",
    "estado",
    "fecha presentacion",
)


def _normalise(text: str) -> str:
    """Return the NFKD-stripped, lowercased, whitespace-collapsed form."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _find_table(soup: BeautifulSoup) -> Tag:
    """Locate the expedientes table by header text.

    Args:
        soup: The parsed document.

    Returns:
        The ``<table>`` whose header row contains every required
        column label.

    Raises:
        StatusParseError: If no matching table is found.
    """
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        header_cells = table.find_all("th")
        header_texts = {_normalise(cell.get_text(" ", strip=True)) for cell in header_cells}
        if all(required in header_texts for required in _REQUIRED_HEADERS):
            return table
    raise StatusParseError(f"could not locate 'Mis expedientes' table — expected headers {_REQUIRED_HEADERS!r}")


def _header_index(table: Tag) -> dict[str, int]:
    """Map normalised header text → column index for the given table."""
    index: dict[str, int] = {}
    header_row = table.find("tr")
    if not isinstance(header_row, Tag):
        raise StatusParseError("expedientes table has no header row")
    for i, cell in enumerate(header_row.find_all("th")):
        index[_normalise(cell.get_text(" ", strip=True))] = i
    return index


def _cell_text(cells: list[Tag], columns: dict[str, int], key: str) -> str:
    """Return the stripped text of the column identified by ``key``."""
    if key not in columns:
        return ""
    i = columns[key]
    if i >= len(cells):
        return ""
    return cells[i].get_text(" ", strip=True)


def _cell_anchor_href(cells: list[Tag], columns: dict[str, int], key: str) -> str | None:
    """Return the first ``<a href="...">`` under the column, or ``None``."""
    if key not in columns:
        return None
    i = columns[key]
    if i >= len(cells):
        return None
    anchor = cells[i].find("a")
    if not isinstance(anchor, Tag):
        return None
    href = anchor.get("href")
    if not isinstance(href, str) or not href:
        return None
    return href


def parse_expedientes(
    raw_html: str,
    *,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> tuple[Expediente, ...]:
    """Parse a *Mis expedientes* HTML page into typed records.

    Args:
        raw_html: The raw HTML captured from ``page.content()``.
        source_url: The URL of the rendered page, stored on every
            produced :class:`Expediente`.
        fetched_at: The UTC timestamp at which ``raw_html`` was
            captured, stored on every produced record.

    Returns:
        A tuple of :class:`Expediente`, one per data row.

    Raises:
        StatusParseError: If the table cannot be located or any row
            fails pydantic validation.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    table = _find_table(soup)
    columns = _header_index(table)

    body = table.find("tbody") or table
    records: list[Expediente] = []
    for row in body.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [cell for cell in row.find_all("td") if isinstance(cell, Tag)]
        if not cells:
            continue

        presented_raw = _cell_text(cells, columns, "fecha presentacion")
        try:
            presented_at = datetime.fromisoformat(presented_raw)
        except ValueError as exc:
            raise StatusParseError(f"unparseable presented_at timestamp: {presented_raw!r}") from exc

        csv_text = _cell_text(cells, columns, "csv") or None
        href = _cell_anchor_href(cells, columns, "justificante")
        justificante_url: AnyHttpUrl | None
        if href is None:
            justificante_url = None
        else:
            try:
                justificante_url = _URL_ADAPTER.validate_python(href)
            except ValidationError as exc:
                raise StatusParseError(f"invalid justificante url on expediente row: {href!r}") from exc

        try:
            record = Expediente(
                expediente_id=_cell_text(cells, columns, "expediente"),
                modelo=_cell_text(cells, columns, "modelo"),
                period=_cell_text(cells, columns, "periodo"),
                status=_cell_text(cells, columns, "estado"),
                presented_at=presented_at,
                csv=csv_text,
                justificante_url=justificante_url,
                source_page_url=source_url,
                fetched_at=fetched_at,
            )
        except ValidationError as exc:
            raise StatusParseError(f"expediente row failed validation: {exc}") from exc
        records.append(record)

    logger.info("parsed %d expediente row(s)", len(records))
    return tuple(records)
