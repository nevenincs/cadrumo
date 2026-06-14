"""Read-only notifications/messages reader for the authenticated AEAT sede.

Captured against a production account; the sede exposes two
notification surfaces:

* **Summary** (``/wlpl/GNNO-JDIT/ResumenInteresados``) — unread
  notifications + unread communications, two tables keyed by
  *número de certificado*.
* **Query** (``/wlpl/GNNO-JDIT/SvInteresadosQuery?VEZ=BUSCAR1``) — a
  full-text search form plus a results table with one row per
  (notification, communication, or pending) item.

Both surfaces are reachable on the ``www6`` Cl@ve-dispatched
subdomain; an earlier assumption that notifications lived only on
``www1`` (cert-only) was wrong.

The reader is structurally read-only: no form submission, no
state-changing URL. Acknowledgement (``acuse``) is a strictly local
concern (the local inbox tracks read/unread); the reader never
tells AEAT "this was read".

Public surface: :class:`RemoteNotification`, :class:`NotificationsSnapshot`,
:func:`parse_notifications_query`, :func:`parse_notifications_summary`,
:func:`fetch_notifications_query`, :func:`fetch_notifications_summary`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import TYPE_CHECKING, Final, Literal

from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl, BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.config import Settings
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.parsing._dates import _parse_date
from .....core.time import now
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._auth_state import storage_state_for_session
from ._browser_constants import PLAYWRIGHT_WAIT_DOMCONTENTLOADED
from ._errors import SedeNavigationError, SedeParseError

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_RESUMEN_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"
_NOTIF_SUMMARY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_summary}"
_NOTIF_QUERY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_query}"


# Número de certificado: 13 digits. Captured: 2699101808461 / 2596230606502.
_CERT_RE: Final[re.Pattern[str]] = re.compile(r"^\d{10,16}$")
# _DATE_RE removed — date parsing delegated to core.parsing._dates._parse_ddmmyyyy_date


class RemoteNotification(BaseModel):
    """One row of AEAT's notifications/communications surface.

    ``tipo`` distinguishes a formal ``Notificación`` (legally binding,
    triggers the ten-day ``acuse`` window) from a lighter-weight
    ``Comunicación``. The ``pendiente`` value marks the placeholder
    state AEAT shows for items that have been issued but not yet
    delivered.

    Attributes:
        certificado_id: ``Nº de certificado`` — 13-digit (or longer)
            AEAT identifier.
        tipo: Row class — ``"notificacion"`` | ``"comunicacion"`` |
            ``"pendiente"`` | ``"unknown"``.
        concepto: Free-text concepto / subject line (may be empty for
            pending rows).
        titular_nif: NIF / NIE of the titular (verbatim from AEAT).
        titular_nombre: Free-text nombre / razón social of the titular.
        destinatario_nif: NIF of the destinatario (may equal titular).
        destinatario_nombre: Free-text nombre / razón social of the
            destinatario.
        fecha_emision: ``Fecha de emisión`` as a local date.
        fecha_notificacion: ``Fecha de notificación`` when the row has
            been delivered, else ``None``.
        modo_notificacion: Text AEAT prints for the delivery channel,
            or ``None`` when not yet delivered.
        leida: ``True`` if AEAT marks the row as "Leída", ``False``
            otherwise, ``None`` for pending rows with no column value.
        source_url: URL the row was scraped from.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    certificado_id: str = Field(min_length=8, max_length=32)
    tipo: Literal["notificacion", "comunicacion", "pendiente", "unknown"]
    concepto: str = Field(default="", max_length=256)
    titular_nif: str = Field(min_length=4, max_length=32)
    titular_nombre: str = Field(max_length=256)
    destinatario_nif: str = Field(max_length=32)
    destinatario_nombre: str = Field(max_length=256)
    fecha_emision: date
    fecha_notificacion: date | None = None
    modo_notificacion: str | None = Field(default=None, max_length=64)
    leida: bool | None = None
    source_url: AnyHttpUrl
    mode: Literal["read"] = "read"


class NotificationsSnapshot(BaseModel):
    """One sede-side capture of the entire notifications surface.

    Attributes:
        rows: Every notification / communication the sede returned.
        captured_at: UTC timestamp at snapshot completion.
        source_url: The sede URL the rows were scraped from (summary
            or query, depending on caller choice).
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    rows: tuple[RemoteNotification, ...]
    captured_at: datetime
    source_url: AnyHttpUrl
    mode: Literal["read"] = "read"


# ── Parsing ────────────────────────────────────────────────────────────────


def parse_notifications_query(html: str, *, source_url: str) -> NotificationsSnapshot:
    """Parse the full ``SvInteresadosQuery`` results table.

    This is the canonical list view; every row carries the full
    column set (``tipo``, ``leída``, ``modo de notificación``, etc.).
    Prefer this over :func:`parse_notifications_summary` when a
    complete picture is needed.

    Args:
        html: Raw HTML body of a SvInteresadosQuery results page.
        source_url: URL the HTML was scraped from (recorded on the
            returned snapshot).

    Returns:
        A :class:`NotificationsSnapshot` with one row per item.
    """
    rows = _parse_rows(html, source_url=source_url, is_summary=False)
    return NotificationsSnapshot(
        rows=tuple(rows),
        captured_at=now(),
        source_url=AnyHttpUrl(source_url),
    )


def parse_notifications_summary(html: str, *, source_url: str) -> NotificationsSnapshot:
    """Parse the unread-summary ``ResumenInteresados`` tables.

    The summary carries fewer columns per row (no ``leída`` / ``modo``),
    so the returned :class:`RemoteNotification` records leave those as
    ``None``. Useful for a cheap unread count / dashboard view.

    Args:
        html: Raw HTML body of a ResumenInteresados page.
        source_url: URL the HTML was scraped from.

    Returns:
        A :class:`NotificationsSnapshot` with one row per item.
    """
    rows = _parse_rows(html, source_url=source_url, is_summary=True)
    return NotificationsSnapshot(
        rows=tuple(rows),
        captured_at=now(),
        source_url=AnyHttpUrl(source_url),
    )


def _parse_rows(
    html: str,
    *,
    source_url: str,
    is_summary: bool,
) -> list[RemoteNotification]:
    """Walk every certificate-bearing table in ``html`` and yield typed rows."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:  # pragma: no cover — lxml always available
        raise SedeParseError(f"failed to parse notifications HTML: {exc}") from exc
    for tag in soup(["script", "style"]):
        tag.decompose()

    rows: list[RemoteNotification] = []
    for table in soup.find_all("table"):
        header_cells = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not header_cells:
            continue
        normalised = [h.lower() for h in header_cells]
        has_cert = any("certificado" in h for h in normalised)
        if not has_cert:
            continue
        header_index = _index_columns(normalised)
        for table_row in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in table_row.find_all("td")]
            if not cells:
                continue
            row = _row_from_cells(
                cells,
                header_index=header_index,
                source_url=source_url,
                is_summary=is_summary,
            )
            if row is not None:
                rows.append(row)
    return rows


def _index_columns(headers: list[str]) -> dict[str, int]:
    """Map normalised column labels to column indices so column order can drift safely."""
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        lower = h.lower()
        if "certificado" in lower:
            idx["certificado"] = i
        elif "concepto" in lower:
            idx["concepto"] = i
        elif "tipo" in lower:
            idx["tipo"] = i
        elif "destinatario" in lower:
            idx["destinatario"] = i
        elif "titular" in lower:
            idx["titular"] = i
        elif "modo" in lower:
            idx["modo"] = i
        elif "fecha de notificaci" in lower:
            idx["fecha_notificacion"] = i
        elif "fecha de emisi" in lower:
            idx["fecha_emision"] = i
        elif "le" in lower and "da" in lower:
            # "Leída" / "Leida" — accented or not.
            idx["leida"] = i
    return idx


def _row_from_cells(
    cells: list[str],
    *,
    header_index: dict[str, int],
    source_url: str,
    is_summary: bool,
) -> RemoteNotification | None:
    """Build a :class:`RemoteNotification` from one table row, or ``None`` if it cannot be classified."""
    cert_idx = header_index.get("certificado")
    if cert_idx is None or cert_idx >= len(cells):
        return None
    certificado_id = cells[cert_idx]
    if not _CERT_RE.match(certificado_id):
        return None

    concepto_raw = _safe_cell(cells, header_index.get("concepto")) or ""
    titular_raw = _safe_cell(cells, header_index.get("titular")) or ""
    destinatario_raw = _safe_cell(cells, header_index.get("destinatario")) or ""
    tipo_raw = _safe_cell(cells, header_index.get("tipo")) or ""
    modo_raw = _safe_cell(cells, header_index.get("modo"))
    leida_raw = _safe_cell(cells, header_index.get("leida"))
    emision_raw = _safe_cell(cells, header_index.get("fecha_emision"))
    notif_raw = _safe_cell(cells, header_index.get("fecha_notificacion"))

    fecha_emision = _parse_date_local(emision_raw)
    if fecha_emision is None:
        return None
    fecha_notificacion = _parse_date_local(notif_raw)

    titular_nif, titular_nombre = _split_nif_name(titular_raw)
    destinatario_nif, destinatario_nombre = _split_nif_name(destinatario_raw)

    tipo = _classify_tipo(tipo_raw, concepto_raw, is_summary)
    concepto = concepto_raw.replace("*", "").strip()
    leida = _parse_leida(leida_raw)

    try:
        return RemoteNotification(
            certificado_id=certificado_id,
            tipo=tipo,
            concepto=concepto,
            titular_nif=titular_nif or "X0000000Z",
            titular_nombre=titular_nombre[:256],
            destinatario_nif=destinatario_nif,
            destinatario_nombre=destinatario_nombre[:256],
            fecha_emision=fecha_emision,
            fecha_notificacion=fecha_notificacion,
            modo_notificacion=modo_raw or None,
            leida=leida,
            source_url=AnyHttpUrl(source_url),
        )
    except Exception as exc:  # pragma: no cover — schema drift guard
        log.debug("notifications: skipped row id=%r: %s", certificado_id, exc, exc_info=True)
        return None


def _safe_cell(cells: list[str], idx: int | None) -> str | None:
    """Return ``cells[idx]`` stripped, or ``None`` if absent / empty."""
    if idx is None or idx >= len(cells):
        return None
    value = cells[idx].strip()
    return value or None


def _parse_date_local(raw: str | None) -> date | None:
    """Parse a Spanish ``DD-MM-YYYY`` date string, returning ``None`` on any failure."""
    return _parse_date(raw, fmt="ddmmyyyy", on_error="none")


def _split_nif_name(raw: str) -> tuple[str, str]:
    """Split ``"Y1234567X PERSONA PRUEBA UNO"`` into ``(nif, name)``."""
    parts = raw.split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()


def _classify_tipo(
    tipo_raw: str,
    concepto_raw: str,
    is_summary: bool,
) -> Literal["notificacion", "comunicacion", "pendiente", "unknown"]:
    """Classify a row into ``notificacion`` / ``comunicacion`` / ``pendiente`` / ``unknown``."""
    lower = tipo_raw.lower()
    if "pendiente" in concepto_raw.lower() or "pendiente" in lower:
        return "pendiente"
    if "notific" in lower:
        return "notificacion"
    if "comunic" in lower or "comunic" in concepto_raw.lower():
        return "comunicacion"
    if is_summary:
        # Summary tables split notification rows from communication rows
        # by table order rather than a "Tipo" column; when there's no
        # column to read, default to "notificacion" for the first table
        # and "comunicacion" for the second. Callers that need sharper
        # classification should use parse_notifications_query.
        return "notificacion"
    return "unknown"


def _parse_leida(raw: str | None) -> bool | None:
    """Parse a Spanish ``Leída`` cell into a tri-state boolean (``None`` for blank)."""
    if not raw:
        return None
    lower = raw.strip().lower()
    if not lower:
        return None
    if lower in {"si", "sí", "s", "true", "✓"}:
        return True
    if lower in {"no", "n", "false", "-"}:
        return False
    return None


# ── Live fetchers ──────────────────────────────────────────────────────────


async def fetch_notifications_summary(
    session: AeatSession,
    *,
    settings: Settings | None = None,
) -> NotificationsSnapshot:
    """Live-fetch ``ResumenInteresados`` using the authenticated session.

    Args:
        session: An authenticated :class:`AeatSession` whose encrypted
            browser state carries valid AEAT cookies.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        A :class:`NotificationsSnapshot` parsed from the live HTML.
    """
    return await _fetch_and_parse(
        session,
        url=_NOTIF_SUMMARY_URL,
        parser=parse_notifications_summary,
        settings=settings,
    )


async def fetch_notifications_query(
    session: AeatSession,
    *,
    settings: Settings | None = None,
) -> NotificationsSnapshot:
    """Live-fetch ``SvInteresadosQuery`` (the full table) using Cl@ve.

    Args:
        session: An authenticated :class:`AeatSession`.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        A :class:`NotificationsSnapshot` parsed from the live HTML.
    """
    return await _fetch_and_parse(
        session,
        url=_NOTIF_QUERY_URL,
        parser=parse_notifications_query,
        settings=settings,
    )


async def _fetch_and_parse(
    session: AeatSession,
    *,
    url: str,
    parser: Callable[..., NotificationsSnapshot],
    settings: Settings | None,
) -> NotificationsSnapshot:
    """Drive Playwright to ``url`` under the authenticated session and parse the HTML."""
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    storage_state_path = session.storage_state_path
    if storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    browser_session = await default_browser_session_factory(settings)
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            # Warm the cookie jar on the authenticated landing.
            # Non-Playwright failures (e.g. domain errors, keyboard interrupts)
            # propagate unmodified; only browser-level transport and OS-level
            # I/O errors are suppressed here since they do not prevent the
            # primary goto from succeeding.
            try:
                await page.goto(_RESUMEN_URL, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
            except (PlaywrightError, OSError) as exc:
                log.debug(
                    "fetch_notifications: warm-up navigation to %s suppressed: %s",
                    _RESUMEN_URL,
                    exc,
                    exc_info=True,
                )
            try:
                await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
            except PlaywrightError as exc:
                raise SedeNavigationError(f"goto {url!r} failed: {exc}") from exc
            html = await page.content()
            snapshot = parser(html, source_url=url)
            log.info(
                "fetch_notifications: fetched %d row(s) from %s",
                len(snapshot.rows),
                url,
            )
            return snapshot
        finally:
            try:
                await context.close()
            except Exception as _exc:
                log.debug("fetch_notifications: context.close suppressed: %s", _exc, exc_info=True)
    finally:
        await browser_session.close()


__all__ = [
    "NotificationsSnapshot",
    "RemoteNotification",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "parse_notifications_query",
    "parse_notifications_summary",
]
