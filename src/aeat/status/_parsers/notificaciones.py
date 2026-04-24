"""Parser for the *Mis notificaciones* AEAT surface (#170).

Extracts every notification row from a server-rendered HTML snapshot
into a tuple of :class:`aeat.status.Notificacion`. Mirrors the
shape of :mod:`aeat.status._parsers.expedientes` — a pure function
with no I/O — so the same trimming/fixturing procedure applies.

Charter #116 (no-write mandate): this module is pure parsing; the
calling :class:`StatusReader` is the sole component allowed to touch
the browser, and only via ``page.goto(..., wait_until="domcontentloaded")``.
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl, ValidationError

from ...logging import get_logger
from .._errors import StatusParseError
from .._models import Notificacion

logger = get_logger(__name__)


_REQUIRED_HEADERS: tuple[str, ...] = (
    "identificador",
    "tipo",
    "asunto",
    "fecha puesta a disposicion",
)

_DATETIME_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)

_AEAT_TZ = ZoneInfo("Europe/Madrid")


def _normalise(text: str) -> str:
    """Return the NFKD-stripped, lowercased, whitespace-collapsed form."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _parse_aeat_datetime(raw: str) -> datetime:
    """Parse an AEAT timestamp into a UTC-aware datetime.

    Accepts ISO-8601 first (fixture shape), then falls back to the
    Spanish-locale formats AEAT actually renders. Naive results are
    localised to ``Europe/Madrid`` and converted to UTC so the
    returned timestamp is always tz-aware.

    Raises:
        StatusParseError: If none of the known formats match.
    """
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in _DATETIME_FORMATS:
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise StatusParseError(f"unparseable notificacion timestamp: {raw!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_AEAT_TZ)
    return parsed.astimezone(UTC)


def _direct_children(tag: Tag, name: str) -> list[Tag]:
    """Return direct child ``<name>`` tags, skipping nested tables."""
    return [child for child in tag.find_all(name, recursive=False) if isinstance(child, Tag)]


def _locate_header_row(table: Tag) -> Tag | None:
    """Return the first ``<tr>`` with ``<th>`` cells (prefer ``<thead>``)."""
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


def _find_table(soup: BeautifulSoup) -> Tag:
    """Locate the notificaciones table by header text."""
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        header_row = _locate_header_row(table)
        if header_row is None:
            continue
        header_texts = {_normalise(cell.get_text(" ", strip=True)) for cell in _direct_children(header_row, "th")}
        if all(required in header_texts for required in _REQUIRED_HEADERS):
            return table
    raise StatusParseError(f"could not locate 'Mis notificaciones' table — expected headers {_REQUIRED_HEADERS!r}")


def _header_index(table: Tag) -> tuple[Tag, dict[str, int]]:
    """Locate the header row and return ``(row, column_index)``.

    Raises:
        StatusParseError: If the table has no identifiable header row.
    """
    header_row = _locate_header_row(table)
    if header_row is None:
        raise StatusParseError("notificaciones table has no header row")
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


def parse_notificaciones(
    raw_html: str,
    *,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
) -> tuple[Notificacion, ...]:
    """Parse a *Mis notificaciones* HTML page into typed records.

    Args:
        raw_html: The raw HTML captured from ``page.content()``.
        source_url: The URL of the rendered page, stored on every
            produced :class:`Notificacion`.
        fetched_at: The UTC timestamp at which ``raw_html`` was
            captured.

    Returns:
        A tuple of :class:`Notificacion`, one per data row, in the
        order AEAT renders them.

    Raises:
        StatusParseError: If the table cannot be located, a row has
            the wrong shape (colspan/footer), or any row fails
            pydantic validation.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    table = _find_table(soup)
    header_row, columns = _header_index(table)
    expected_cells = (max(columns.values()) + 1) if columns else 0

    tbody = table.find("tbody")
    body: Tag = tbody if isinstance(tbody, Tag) else table
    records: list[Notificacion] = []
    for row in body.find_all("tr"):
        if not isinstance(row, Tag) or row is header_row:
            continue
        cells = _direct_children(row, "td")
        if not cells:
            continue
        if len(cells) < expected_cells:
            # Totals/footer row with colspan: skip silently.
            logger.debug("skipping short row (%d cells, expected %d)", len(cells), expected_cells)
            continue

        received_at = _parse_aeat_datetime(_cell_text(cells, columns, "fecha puesta a disposicion"))
        due_raw = _cell_text(cells, columns, "plazo")
        due_at = _parse_aeat_datetime(due_raw) if due_raw else None

        asunto = _cell_text(cells, columns, "asunto")
        try:
            record = Notificacion(
                notificacion_id=_cell_text(cells, columns, "identificador"),
                kind=_cell_text(cells, columns, "tipo"),
                title={"es": asunto},
                body_excerpt={"es": asunto},
                received_at=received_at,
                due_at=due_at,
                source_page_url=source_url,
                fetched_at=fetched_at,
            )
        except ValidationError as exc:
            raise StatusParseError(f"notificacion row failed validation: {exc}") from exc
        records.append(record)

    logger.info("parsed %d notificacion row(s)", len(records))
    return tuple(records)
