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
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final, Literal
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.parsing import parse_date
from .....core.time import now
from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._auth_state import storage_state_for_session
from ._browser_constants import PLAYWRIGHT_WAIT_DOMCONTENTLOADED
from ._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ._walker import assert_landed_url_readable

if TYPE_CHECKING:
    from ..auth import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_SEDE_HOST = urlsplit(_SEDE_BASE).netloc
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_RESUMEN_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"
_NOTIF_SUMMARY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_summary}"
_NOTIF_QUERY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_query}"

# AEAT dispatches the authenticated sede across a ``www{n}`` load-balancer pool;
# the read guard admits any subdomain under the AEAT apex (host-suffix widened)
# so a sibling-host landing is tolerated, while success detection keys on the
# notifications PATH plus a positive page marker (below).
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-notifications-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_SEDE_HOST,),
    allowed_host_suffixes=(_AEAT_HOST_SUFFIX,),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)

BrowserSessionFactory = Callable[[Settings], Awaitable[Any]]
"""Async factory returning an object exposing ``create_context(storage_state=...)`` + ``close()``.

Production passes :func:`default_browser_session_factory`. The callable seam
keeps browser-session construction owned by the outbound adapter composition
boundary.
"""

# Page-level marker present on BOTH the summary (``Resumen de notificaciones y
# comunicaciones no leídas``) and the query (``Consulta de notificaciones y
# comunicaciones``) page headings and titles. It is row-count INDEPENDENT — the
# heading renders on a genuinely-empty notifications page — so a zero-row parse
# with the marker present is a legitimate "no pending items", while a zero-row
# parse with the marker ABSENT is a wrong-service / auth-gate / maintenance
# landing. Grounded against the real captures in ``test_notifications.py``
# (fixtures ``notifications-summary-resumen.html`` / ``notifications-query-results.html``);
# absent from the maintenance interstitial fixture.
_NOTIFICATIONS_PAGE_MARKER: Final = "notificaciones y comunicaciones"


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
        summary_table_tipo = _summary_table_tipo(table) if is_summary else None
        for table_row in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in table_row.find_all("td")]
            if not cells:
                continue
            row = _row_from_cells(
                cells,
                header_index=header_index,
                source_url=source_url,
                is_summary=is_summary,
                summary_table_tipo=summary_table_tipo,
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
    summary_table_tipo: Literal["notificacion", "comunicacion"] | None,
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

    tipo = _classify_tipo(
        tipo_raw,
        concepto_raw,
        is_summary=is_summary,
        summary_table_tipo=summary_table_tipo,
    )
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
    return parse_date(raw, fmt="ddmmyyyy", on_error="none")


def _split_nif_name(raw: str) -> tuple[str, str]:
    """Split ``"Y1234567X PERSONA PRUEBA UNO"`` into ``(nif, name)``."""
    parts = raw.split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()


# ADAPTER-INTERNAL-ALIAS-RATIONALE-BS4-TAG: table is a bs4 Tag/NavigableString,
# a third-party type this module intentionally does not import for typing.
def _summary_table_tipo(table: Any) -> Literal["notificacion", "comunicacion"] | None:
    """Return the summary category declared by the table's preceding section heading."""
    heading = table.find_previous(["h2", "h3"])
    if heading is None:
        return None
    label = heading.get_text(" ", strip=True).lower()
    if "comunic" in label:
        return "comunicacion"
    if "notific" in label:
        return "notificacion"
    return None


def _classify_tipo(
    tipo_raw: str,
    concepto_raw: str,
    *,
    is_summary: bool,
    summary_table_tipo: Literal["notificacion", "comunicacion"] | None,
) -> Literal["notificacion", "comunicacion", "pendiente", "unknown"]:
    """Classify a row into ``notificacion`` / ``comunicacion`` / ``pendiente`` / ``unknown``."""
    lower = tipo_raw.lower()
    if "pendiente" in concepto_raw.lower() or "pendiente" in lower:
        return "pendiente"
    if "notific" in lower:
        return "notificacion"
    if "comunic" in lower or "comunic" in concepto_raw.lower():
        return "comunicacion"
    if summary_table_tipo is not None:
        return summary_table_tipo
    if is_summary:
        # A malformed summary lacking its section heading retains the historic
        # conservative default instead of silently becoming an unknown row.
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
        settings: Optional :class:`core.config.Settings` override.

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
        settings: Optional :class:`core.config.Settings` override.

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
    """Resolve the session's storage state, then drive Playwright to ``url`` and parse."""
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    return await _navigate_and_parse(
        storage_state,
        url=url,
        parser=parser,
        settings=settings,
        browser_session_factory=default_browser_session_factory,
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-PLAYWRIGHT-PAGE: page is a Playwright
# Page-like object; typed loosely so both sync and async Playwright pages
# satisfy this shared helper without importing either concrete type here.
def _notifications_landing_url(page: Any, *, requested_url: str) -> str:
    """Return the URL AEAT actually served, refusing an unreadable landing.

    Mirrors :func:`_walker.assert_landed_url_readable`: an empty or otherwise
    unreadable ``page.url`` must not be silently substituted with the
    originally-requested URL -- see that function's own docstring for the
    fail-open bug this shape used to reproduce (the re-assertion after a
    ``goto`` skipped entirely when the landed URL was empty).
    """
    return assert_landed_url_readable(getattr(page, "url", "") or "", requested_url=requested_url)


async def _navigate_and_parse(
    storage_state: Mapping[str, object],
    *,
    url: str,
    parser: Callable[..., NotificationsSnapshot],
    settings: Settings,
    browser_session_factory: BrowserSessionFactory,
) -> NotificationsSnapshot:
    """Storage-state-driven core of :func:`_fetch_and_parse`.

    Split out so storage-state navigation and the landing/marker guard remain
    one explicit adapter boundary shared by the authenticated fetch paths.
    """
    browser_session = await browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state=storage_state)
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
        _assert_read_http("GET", url)
        try:
            await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto {url!r} failed: {exc}") from exc
        # Follow the redirect chain rather than assuming the request host:
        # capture where AEAT actually landed and re-assert that host through
        # the host-suffix read guard so an off-AEAT redirect fails closed
        # while a ``www{n}`` load-balancer dispatch is tolerated.
        landing_url = _notifications_landing_url(page, requested_url=url)
        landing = urlsplit(landing_url)
        _assert_read_http("GET", f"{landing.scheme}://{landing.netloc}{landing.path}")
        html = await page.content()
        snapshot = parser(html, source_url=_recorded_landing_url(landing_url, fallback_url=url))
        if not snapshot.rows and not _notifications_marker_present(html):
            # A zero-row parse with NO notifications page marker is a
            # wrong-service / auth-gate / maintenance landing, not a genuine
            # "no pending items" — surface the page signal instead of a
            # silent empty snapshot. A genuine empty page still renders the
            # marker and returns normally above.
            raise SedeNavigationError(
                "AEAT notifications navigation returned a page with no notifications marker and no "
                "rows; this is a wrong-service / auth-gate / maintenance landing, not an empty inbox. "
                f"landing_host={landing.netloc!r} landing_path={landing.path!r} "
                f"marker_present=False row_count=0",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                translated_message=tr("adapters.sede.errors.notifications_bad_landing"),
                context={
                    "requested_url": url,
                    "landing_host": landing.netloc,
                    "landing_path": landing.path,
                    "marker_present": False,
                    "row_count": 0,
                },
                suggestion=(
                    "Re-authenticate (run `aeat config auth status`) and retry; if AEAT is serving a "
                    "maintenance interstitial, retry later. Do not treat this as an empty inbox."
                ),
            )
        log.info(
            "fetch_notifications: fetched %d row(s) from %s",
            len(snapshot.rows),
            url,
        )
        return snapshot
    finally:
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-notifications-close",
        )


def _assert_read_http(method: str, url: str) -> None:
    """Fail-closed guard: refuse any non-read-only or off-AEAT notifications navigation."""
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


def _recorded_landing_url(landing_url: str, *, fallback_url: str) -> str:
    """Return the usable landing origin/path for evidence provenance."""
    landing = urlsplit(landing_url)
    if landing.scheme and landing.netloc and landing.path:
        return urlunsplit((landing.scheme, landing.netloc, landing.path, landing.query, ""))
    return fallback_url


def _notifications_marker_present(html: str) -> bool:
    """Return whether the raw HTML carries the row-count-independent notifications page marker.

    Used only to distinguish a genuine empty inbox (marker present, zero rows)
    from a wrong-service / auth-gate / maintenance landing (marker absent).
    """
    return _NOTIFICATIONS_PAGE_MARKER in html.lower()


__all__ = [
    "NotificationsSnapshot",
    "RemoteNotification",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "parse_notifications_query",
    "parse_notifications_summary",
]
