"""Pure-function HTML parsers for the authenticated AEAT sede.

All parsers take raw HTML strings and return strict pydantic records.
No Playwright, no I/O. This makes them trivially unit-testable
against captured fixtures and keeps the navigation (side-effect)
concerns isolated in :mod:`adapters.outbound.aeat.sede._walker`.

Public surface: :func:`parse_resumen_tree` (top-level expediente
listing), :func:`parse_expediente_detail` (per-expediente CSV
extraction).
"""

from __future__ import annotations

import re
from html import unescape
from typing import Final
from urllib.parse import urljoin, urlparse

from bs4 import Tag
from pydantic import AnyHttpUrl

from .....core.config import Settings
from .....core.logging import get_logger
from .._html import parse_html
from ._declarations_remote import extract_csv_from_url
from .errors import SedeParseError
from ._schema import Expediente, JustificanteRef

_SEDE_PATHS = Settings.external_constants().aeat.sede_paths

_log = get_logger(__name__)

# onclick on a Modelo 100 expediente row, captured 2026-04-24:
#   javascript:lanzarTewvForm(this,12);return false;
# The ``href`` carries the real per-year endpoint we must GET directly
# (lanzarTewvForm rewrites it into a hidden form submit when clicked,
# but the ``href`` is already valid as a GET with session cookies).
_EXPEDIENTE_LINK_HANDLERS: Final[tuple[str, ...]] = ("lanzarTewvForm",)

# Modelo-code pattern inside a category label.
_MODELO_IN_LABEL: Final[re.Pattern[str]] = re.compile(r"\bModelo\s+(?P<modelo>\d{2,4})\b")

_IRPF_ENDPOINT: Final[re.Pattern[str]] = re.compile(
    rf"{re.escape(_SEDE_PATHS.irpf_expediente_detail_year_prefix)}(?P<year>\d{{4}})"
    rf"{re.escape(_SEDE_PATHS.irpf_expediente_detail_year_suffix)}",
)

# Locate the cotejo link by its PATH and capture the whole query string; the
# CSV parameter is then read by the canonical query-aware extractor. Matching
# the literal ``?CSV=`` sequence instead would refuse a link that merely
# carries another parameter first, or orders its parameters differently --
# neither of which changes what AEAT served.
_COTEJO_HREF: Final[re.Pattern[str]] = re.compile(
    rf"{re.escape(_SEDE_PATHS.cotejo_query)}\?(?P<query>[^\"'\s>]+)",
)


def parse_resumen_tree(html: str, *, base_url: str) -> tuple[Expediente, ...]:
    """Extract every expediente leaf from a ResumenVlt page.

    The sede renders an AJAX-expanded category tree. After every
    relevant category has been expanded (by the walker), every
    expediente shows up as an ``<a>`` whose ``href`` points at one
    of AEAT's per-filing-family endpoints and whose text is the
    expediente id.

    Args:
        html: Full HTML body of the ResumenVlt page (post-expansion).
        base_url: The sede base URL (for resolving relative hrefs);
            typically ``"https://www6.agenciatributaria.gob.es"``.

    Returns:
        Tuple of :class:`Expediente` records, one per discovered
        leaf. Order matches document order.

    Raises:
        SedeParseError: If the page has no category tree at all (the
            authenticated session likely expired).
    """
    try:
        soup = parse_html(html)
    except Exception as exc:
        raise SedeParseError(f"failed to parse ResumenVlt HTML: {exc}") from exc

    # Strip script/style so text traversal is clean.
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Sanity check: every ResumenVlt page has the "Mis Expedientes"
    # page title as an <h1>/<h2>. Missing → page drift or bad session.
    heading_regex = re.compile(r"Mis\s+Expedientes", re.I)
    heading = None
    for candidate in soup.find_all(["h1", "h2"]):
        if heading_regex.search(candidate.get_text(" ", strip=True)):
            heading = candidate
            break
    if heading is None:
        raise SedeParseError("ResumenVlt page missing 'Mis Expedientes' heading")

    results: list[Expediente] = []
    for anchor in soup.find_all("a"):
        onclick = str(anchor.get("onclick") or "").strip()
        if not any(h in onclick for h in _EXPEDIENTE_LINK_HANDLERS):
            continue
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        expediente_id = anchor.get_text(" ", strip=True)
        if not expediente_id or " " in expediente_id:
            continue
        category_path = _collect_category_path(anchor)
        modelo = _infer_modelo_from_category(category_path)
        ejercicio = _infer_ejercicio(expediente_id, href)
        absolute_url = urljoin(base_url, href) if not urlparse(href).netloc else href
        try:
            expediente = Expediente(
                expediente_id=expediente_id,
                modelo=modelo,
                ejercicio=ejercicio,
                category_path=category_path,
                detail_url=AnyHttpUrl(absolute_url),
            )
        except Exception as exc:  # pragma: no cover — schema drift guard
            _log.debug(
                "parse_resumen_tree: skipping malformed expediente row id=%r href=%r: %s",
                expediente_id,
                href,
                exc,
                exc_info=True,
            )
            continue
        results.append(expediente)
    return tuple(results)


def parse_expediente_detail(
    html: str,
    *,
    expediente_id: str,
    base_url: str,
) -> JustificanteRef:
    """Extract the CSV-keyed justificante handle from a detail page.

    Captured live: every IRPF detail page (``/wlpl/DASR-CORE/
    AccesoDR<YYYY>RVlt``) exposes the filed declaration via a
    ``Grabación de la declaración ... (Consulta / Copia)`` link that
    points at ``/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=<csv>``.

    Args:
        html: Full HTML body of the expediente detail page.
        expediente_id: AEAT-assigned identifier (copied through onto
            the returned :class:`JustificanteRef`).
        base_url: The sede base URL for absolutising the cotejo and
            PDF endpoints.

    Returns:
        A :class:`JustificanteRef` ready for
        :func:`capture_justificante`.

    Raises:
        SedeParseError: If no CSV-carrying anchor is present.
    """
    match = _COTEJO_HREF.search(html)
    if match is None:
        raise SedeParseError(
            f"expediente {expediente_id!r}: no /CotejoIdSv?CSV= link on detail page; "
            "session may have expired or the modelo exposes a different verifier",
        )
    # Anchors carry HTML-escaped ampersands; unescape before parsing the query
    # so a second parameter does not swallow the CSV key.
    query = unescape(match.group("query"))
    try:
        csv = extract_csv_from_url(f"{_SEDE_PATHS.cotejo_query}?{query}")
    except SedeParseError as exc:
        raise SedeParseError(
            f"expediente {expediente_id!r}: cotejo CSV does not match the AEAT shape: {exc}",
        ) from exc
    cotejo_url = urljoin(base_url, f"{_SEDE_PATHS.cotejo_query}?CSV={csv}")
    pdf_url = urljoin(base_url, f"{_SEDE_PATHS.cotejo_document}?CSV={csv}")
    return JustificanteRef(
        csv=csv,
        expediente_id=expediente_id,
        cotejo_url=AnyHttpUrl(cotejo_url),
        pdf_url=AnyHttpUrl(pdf_url),
    )


def _collect_category_path(anchor: Tag) -> tuple[str, ...]:
    """Walk up from a leaf ``<a>`` collecting parent category labels.

    The sede tree uses nested ``<ul>/<li>`` where each ``<li>`` begins
    with a label anchor (``<a onclick="javascript:desplegar(...)"``)
    identifying the category. We collect those labels from innermost
    to root, then reverse for a root-to-leaf breadcrumb.
    """
    labels: list[str] = []
    current = anchor.parent
    while current is not None:
        if isinstance(current, Tag) and current.name == "li":
            label = _li_header_label(current, leaf=anchor)
            if label is not None:
                labels.append(label)
        current = current.parent
    return tuple(reversed(labels))


def _li_header_label(li: Tag, *, leaf: Tag) -> str | None:
    """Return the header-anchor text for a sede ``<li>`` node, or ``None``.

    The header anchor is normally the first direct ``<a>`` child of the
    ``<li>`` (``recursive=False``); when the theme wraps the header in a
    ``<span>`` the first ``<a>`` is nested instead. In both cases the
    header anchor is distinct from ``leaf`` — that's what tells the
    walker the current ``<li>`` is an ancestor category rather than the
    leaf row itself.
    """
    header_anchor = li.find("a", recursive=False)
    if header_anchor is None:
        first_anchor = li.find("a")
        if first_anchor is not None and first_anchor is not leaf:
            header_anchor = first_anchor
    if header_anchor is None or header_anchor is leaf:
        return None
    text = header_anchor.get_text(" ", strip=True)
    return text or None


def _infer_modelo_from_category(category_path: tuple[str, ...]) -> str | None:
    """Pull the modelo code out of the deepest category label, if any."""
    for label in reversed(category_path):
        match = _MODELO_IN_LABEL.search(label)
        if match is not None:
            modelo = match.group("modelo")
            if isinstance(modelo, str):
                return modelo
    return None


def _infer_ejercicio(expediente_id: str, href: str) -> int | None:
    """Derive the tax year from the URL or expediente id."""
    url_match = _IRPF_ENDPOINT.search(href)
    if url_match is not None:
        try:
            return int(url_match.group("year"))
        except ValueError:  # pragma: no cover — regex guarantees digits
            return None
    # Expediente IDs lead with the tax year for most modelos.
    try:
        candidate = int(expediente_id[:4])
    except ValueError:
        return None
    if 2000 <= candidate <= 2099:
        return candidate
    return None


__all__ = [
    "parse_expediente_detail",
    "parse_resumen_tree",
]
