"""Shared helpers for per-modelo detail-page parsers (#168).

Each public ``parse_<modelo>_detail`` function under this package
consumes the same form shape: a server-rendered HTML table whose
``<tr>`` rows carry ``(casilla_id, value, label)`` tuples. The
helpers here extract that shape generically so each modelo parser
can focus on the headline totals and the modelo-specific quirks.

Parsers are pure (ADR D5): no I/O, no browser, no network.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl, ValidationError

from ...logging import get_logger
from ...status import Expediente
from .._decimal import parse_decimal
from .._errors import HistoryParseError
from .._models import FiledModelo, FiledModeloMetadata, RawCalculationPayload

logger = get_logger(__name__)

_CASILLA_ID_RE = re.compile(r"^[0-9A-Z]{2,8}$")

_TOTAL_INGRESAR_RE = re.compile(
    r"Total\s+a\s+ingresar\s*[:\-]?\s*([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
_TOTAL_DEVOLVER_RE = re.compile(
    r"Total\s+a\s+devolver\s*[:\-]?\s*([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
_RESULTADO_COMPENSAR_RE = re.compile(
    r"(?:Resultado\s+a\s+compensar|A\s+compensar)\s*[:\-]?\s*"
    r"([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
_NIF_RE = re.compile(r"\b([0-9A-Z]{8,12})\b")
_COMPLEMENTARIA_RE = re.compile(
    r"(?:complementaria\s+de|amends)\s*[:\-]?\s*([0-9A-Z]{1,64})",
    re.IGNORECASE,
)


def normalise(text: str) -> str:
    """Return the NFKD-stripped, lowercased, whitespace-collapsed form."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def soup_of(raw_html: str) -> BeautifulSoup:
    """Return a :class:`BeautifulSoup` parsed with the stdlib parser."""
    return BeautifulSoup(raw_html, "html.parser")


def _direct_children(tag: Tag, name: str) -> list[Tag]:
    return [c for c in tag.find_all(name, recursive=False) if isinstance(c, Tag)]


def find_casillas_table(soup: BeautifulSoup) -> Tag:
    """Locate the casillas table by ``class="casillas"`` or header match.

    The canonical fixture shape is ``<table class="casillas">`` with
    columns ``Casilla``, ``Valor``, optionally ``Descripción``. The
    helper falls back to selecting by header-text match so minor
    class-name drift between campaigns does not break the parser.

    Raises:
        HistoryParseError: If no table is found.
    """
    # Fast path — look for the canonical class marker.
    table = soup.find("table", class_=re.compile(r"casill", re.IGNORECASE))
    if isinstance(table, Tag):
        return table
    # Fallback — header-text match.
    for candidate in soup.find_all("table"):
        if not isinstance(candidate, Tag):
            continue
        header_cells = [normalise(th.get_text(" ", strip=True)) for th in candidate.find_all("th")]
        if "casilla" in header_cells and "valor" in header_cells:
            return candidate
    raise HistoryParseError("could not locate casillas table in detail page")


def extract_casillas(table: Tag) -> tuple[dict[str, str], tuple[str, ...]]:
    """Extract the ``{casilla_id: raw_value}`` mapping from ``table``.

    Returns:
        A tuple ``(casillas, warnings)``. ``warnings`` carries
        non-fatal observations (empty table, dropped rows) for the
        caller to attach to :attr:`FiledModelo.parse_warnings`.
    """
    warnings: list[str] = []
    casillas: dict[str, str] = {}
    tbody = table.find("tbody")
    body: Tag = tbody if isinstance(tbody, Tag) else table
    rows_seen = 0
    for row in body.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = _direct_children(row, "td")
        if len(cells) < 2:
            continue
        rows_seen += 1
        casilla_id = cells[0].get_text(" ", strip=True)
        value = cells[1].get_text(" ", strip=True)
        if not casilla_id:
            warnings.append("row with empty casilla id skipped")
            continue
        if not _CASILLA_ID_RE.match(casilla_id):
            warnings.append(f"casilla id {casilla_id!r} skipped (invalid format)")
            continue
        if casilla_id in casillas:
            warnings.append(f"duplicate casilla id {casilla_id!r}; last value wins")
        casillas[casilla_id] = value
    if rows_seen == 0:
        warnings.append("casillas table had no data rows")
    return casillas, tuple(warnings)


def extract_optional_decimal(
    text: str,
    pattern: re.Pattern[str],
    *,
    label: str,
    warnings: list[str],
) -> Decimal | None:
    """Apply ``pattern`` over ``text`` and parse the first group as Decimal.

    Collects a warning on ``warnings`` if no match is found and
    returns ``None`` — headline totals are optional.
    """
    match = pattern.search(text)
    if match is None:
        warnings.append(f"{label} label absent")
        return None
    try:
        return parse_decimal(match.group(1))
    except HistoryParseError as exc:
        warnings.append(f"{label} value could not be parsed: {exc}")
        return None


def extract_tax_id(text: str, expediente: Expediente) -> str:
    """Return the best-effort tax id visible on the detail page.

    Falls back to extracting the NIF embedded in ``expediente_id``
    (AEAT expediente ids are typically prefixed with the year and the
    taxpayer's NIF). If nothing matches, raises
    :class:`HistoryParseError`.
    """
    # A labelled NIF in the form body is the authoritative source.
    nif_match = re.search(
        r"(?:NIF|DNI|CIF)\s*[:\-]?\s*([0-9A-Z]{8,12})",
        text,
        re.IGNORECASE,
    )
    if nif_match is not None:
        return nif_match.group(1)
    # Fallback — try to find a bare NIF-shaped token.
    bare_match = _NIF_RE.search(expediente.expediente_id)
    if bare_match is not None:
        return bare_match.group(1)
    raise HistoryParseError(f"could not locate tax id in detail page for expediente {expediente.expediente_id!r}")


def extract_complementaria_of(text: str) -> str | None:
    """Return the ``expediente_id`` this filing amends, or ``None``."""
    match = _COMPLEMENTARIA_RE.search(text)
    if match is None:
        return None
    return match.group(1)


def build_filed_modelo(
    *,
    expediente: Expediente,
    soup: BeautifulSoup,
    source_url: AnyHttpUrl,
    fetched_at: datetime,
    resultado_a_compensar_pattern: re.Pattern[str] | None = None,
) -> FiledModelo:
    """Compose a :class:`FiledModelo` from a parsed detail-page soup.

    This helper is the shared backbone of every ``parse_<modelo>_detail``
    function: it runs the generic casilla extraction, extracts the
    three headline totals via regex, accumulates parse warnings, and
    validates through the pydantic models.

    Args:
        expediente: Upstream :class:`aeat.status.Expediente`.
        soup: Parsed :class:`BeautifulSoup` tree of the detail page.
        source_url: Detail-page URL.
        fetched_at: UTC timestamp the HTML was captured.
        resultado_a_compensar_pattern: Optional override for modelos
            that expose this total (303, 390). ``None`` means the
            parser does not look for it.

    Raises:
        HistoryParseError: If the casillas table is missing or a
            produced pydantic model fails validation.
    """
    warnings: list[str] = []
    table = find_casillas_table(soup)
    casillas, table_warnings = extract_casillas(table)
    warnings.extend(table_warnings)

    body_text = soup.get_text(" ", strip=True)
    total_ingresar = extract_optional_decimal(
        body_text,
        _TOTAL_INGRESAR_RE,
        label="total_a_ingresar",
        warnings=warnings,
    )
    total_devolver = extract_optional_decimal(
        body_text,
        _TOTAL_DEVOLVER_RE,
        label="total_a_devolver",
        warnings=warnings,
    )
    resultado_compensar: Decimal | None = None
    if resultado_a_compensar_pattern is not None:
        resultado_compensar = extract_optional_decimal(
            body_text,
            resultado_a_compensar_pattern,
            label="resultado_a_compensar",
            warnings=warnings,
        )

    tax_id = extract_tax_id(body_text, expediente)
    complementaria_of = extract_complementaria_of(body_text)

    try:
        metadata = FiledModeloMetadata(
            expediente_id=expediente.expediente_id,
            modelo=expediente.modelo,
            period=expediente.period,
            status=expediente.status,
            presented_at=expediente.presented_at,
            tax_id=tax_id,
            csv=expediente.csv,
            justificante_url=expediente.justificante_url,
            complementaria_of=complementaria_of,
            source_page_url=source_url,
            fetched_at=fetched_at,
        )
        calculations = RawCalculationPayload(
            casillas=casillas,
            total_a_ingresar=total_ingresar,
            total_a_devolver=total_devolver,
            resultado_a_compensar=resultado_compensar,
            source_page_url=source_url,
            fetched_at=fetched_at,
        )
        return FiledModelo(
            metadata=metadata,
            calculations=calculations,
            parse_warnings=tuple(warnings),
        )
    except ValidationError as exc:
        raise HistoryParseError(
            f"detail-page validation failed for expediente {expediente.expediente_id!r}: {exc}"
        ) from exc


__all__ = [
    "build_filed_modelo",
    "extract_casillas",
    "extract_complementaria_of",
    "extract_optional_decimal",
    "extract_tax_id",
    "find_casillas_table",
    "normalise",
    "soup_of",
]
