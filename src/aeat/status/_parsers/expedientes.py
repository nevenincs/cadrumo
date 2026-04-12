"""Parser for the *Mis expedientes* AEAT surface.

Extracts every expediente row from a server-rendered HTML snapshot
into a tuple of :class:`aeat.status.Expediente`. The parser selects
the canonical ``<table>`` by its ``<th>`` header text, which survives
the minor layout drift AEAT ships between campaigns.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from urllib.parse import urljoin

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

# Date/datetime formats the AEAT portal is known to emit. ISO is the
# fixture shape; the two Spanish formats are the live-page shapes.
_DATETIME_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def _normalise(text: str) -> str:
    """Return the NFKD-stripped, lowercased, whitespace-collapsed form."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _parse_aeat_datetime(raw: str) -> datetime:
    """Parse an AEAT presented_at field.

    Accepts ISO-8601 first (fixture shape), then falls back to the
    Spanish-locale shapes AEAT actually renders.

    Raises:
        StatusParseError: If none of the known formats match.
    """
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise StatusParseError(f"unparseable presented_at timestamp: {raw!r}")


def _direct_children(tag: Tag, name: str) -> list[Tag]:
    """Return direct child ``<name>`` tags of ``tag``, skipping nested tables."""
    return [child for child in tag.find_all(name, recursive=False) if isinstance(child, Tag)]


def _find_table(soup: BeautifulSoup) -> Tag:
    """Locate the expedientes table by header text.

    The match is tolerant: it looks for tables whose *own* ``<th>``
    cells (not cells of nested sub-tables) cover every required
    header. Nested tables are skipped to avoid polluting the header
    heuristic.

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
        # Walk the table's own tr/th cells, ignoring any inner nested
        # tables' headers.
        header_row = _locate_header_row(table)
        if header_row is None:
            continue
        header_texts = {_normalise(cell.get_text(" ", strip=True)) for cell in _direct_children(header_row, "th")}
        if all(required in header_texts for required in _REQUIRED_HEADERS):
            return table
    raise StatusParseError(f"could not locate 'Mis expedientes' table — expected headers {_REQUIRED_HEADERS!r}")


def _locate_header_row(table: Tag) -> Tag | None:
    """Return the first ``<tr>`` that carries any ``<th>`` cells.

    Prefers a ``<thead>`` if present, otherwise scans the table body
    for the first row whose direct children include a ``<th>``.
    """
    thead = table.find("thead")
    if isinstance(thead, Tag):
        for row in _direct_children(thead, "tr"):
            if _direct_children(row, "th"):
                return row
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        if _direct_children(row, "th"):
            return row
    return None


def _header_index(table: Tag) -> tuple[Tag, dict[str, int]]:
    """Locate the header row and return ``(row, column_index)``.

    Raises:
        StatusParseError: If the table has no identifiable header row.
    """
    header_row = _locate_header_row(table)
    if header_row is None:
        raise StatusParseError("expedientes table has no header row")
    columns: dict[str, int] = {}
    for i, cell in enumerate(_direct_children(header_row, "th")):
        columns[_normalise(cell.get_text(" ", strip=True))] = i
    return header_row, columns


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


def _resolve_url(href: str, base: str) -> AnyHttpUrl:
    """Resolve ``href`` against ``base`` and validate as ``AnyHttpUrl``.

    AEAT ships many justificante links as relative paths (``/wlpl/...``);
    this helper absolutises them via :func:`urllib.parse.urljoin` before
    pydantic strict-validates the result.

    Raises:
        StatusParseError: If the resolved URL fails validation.
    """
    absolute = urljoin(base, href)
    try:
        return _URL_ADAPTER.validate_python(absolute)
    except ValidationError as exc:
        raise StatusParseError(f"invalid justificante url on expediente row: {href!r}") from exc


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
            produced :class:`Expediente` and used as the base for
            resolving relative justificante links.
        fetched_at: The UTC timestamp at which ``raw_html`` was
            captured, stored on every produced record.

    Returns:
        A tuple of :class:`Expediente`, one per data row.

    Raises:
        StatusParseError: If the table cannot be located, a row has
            the wrong shape (colspan/footer), or any row fails
            pydantic validation.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    table = _find_table(soup)
    header_row, columns = _header_index(table)
    source_url_str = str(source_url)
    expected_cells = (max(columns.values()) + 1) if columns else 0

    # Prefer the tbody rows; fall back to the whole table but
    # *always* skip the header row explicitly.
    tbody = table.find("tbody")
    body: Tag = tbody if isinstance(tbody, Tag) else table
    records: list[Expediente] = []
    for row in body.find_all("tr"):
        if not isinstance(row, Tag) or row is header_row:
            continue
        cells = _direct_children(row, "td")
        if not cells:
            # Header or separator row — skip silently.
            continue
        if len(cells) < expected_cells:
            # Footer / totals row with colspan: not an expediente.
            logger.debug("skipping short row (%d cells, expected %d)", len(cells), expected_cells)
            continue

        presented_at = _parse_aeat_datetime(_cell_text(cells, columns, "fecha presentacion"))

        csv_text = _cell_text(cells, columns, "csv") or None
        href = _cell_anchor_href(cells, columns, "justificante")
        justificante_url = _resolve_url(href, source_url_str) if href else None

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
