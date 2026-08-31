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
:func:`fetch_notifications_query`, :func:`fetch_notifications_summary`,
:func:`notifications_query_url`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final, Literal
from urllib.parse import urlencode, urlsplit, urlunsplit

from bs4 import Tag
from pydantic import AnyHttpUrl, BaseModel, Field

from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....core.hashing import sha256_hex
from .....core.i18n import tr
from .....core.identity import AeatCertificadoId, ContentDigest
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.parsing import parse_date
from .....core.time.clock import now
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from .._html import parse_html
from .._playwright import PlaywrightError
from ..browser._factory import default_browser_session_factory
from ._adapter_utils import assert_pdf_response, assert_read_http_for, assert_read_landing, cell_text
from ._auth_state import storage_state_for_session
from ._browser_constants import PLAYWRIGHT_WAIT_DOMCONTENTLOADED
from .errors import SedeFailureMode, SedeNavigationError, SedeParseError
from .walker import assert_landed_url_readable

if TYPE_CHECKING:
    from .....application.auth.session_types import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_SEDE_HOST = urlsplit(_SEDE_BASE).netloc
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_NOTIF_SUMMARY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_summary}"
_NOTIF_QUERY_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_query}"
_NOTIFICATIONS_READ_PATHS: tuple[str, ...] = tuple(
    urlsplit(path).path
    for path in (
        _EXTERNAL.aeat.sede_paths.notifications_summary,
        _EXTERNAL.aeat.sede_paths.notifications_query,
        _EXTERNAL.aeat.sede_paths.notifications_detail,
    )
)

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
    allowed_read_paths=_NOTIFICATIONS_READ_PATHS,
    # The detail endpoint serves the notification PDF only on a POST. Scoped to
    # that one path: the allowance is a transport fact, and the LEGAL gate is
    # ``assert_notification_content_readable``, which refuses every row AEAT
    # does not already report as read.
    allowed_read_post_paths=(_NOTIFICATIONS_READ_PATHS[2],),
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
        certificado_id: ``Nº de certificado`` — AEAT's per-notification
            identifier, typed :data:`~core.identity.AeatCertificadoId`.
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

    certificado_id: AeatCertificadoId
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
        soup = parse_html(html)
    except Exception as exc:  # pragma: no cover — lxml always available
        raise SedeParseError(f"failed to parse notifications HTML: {exc}") from exc
    for tag in soup(["script", "style"]):
        tag.decompose()

    rows: list[RemoteNotification] = []
    for table in soup.find_all("table"):
        rows.extend(_certificate_table_rows(table, source_url=source_url, is_summary=is_summary))
    return rows


def _certificate_table_rows(
    table: Tag,
    *,
    source_url: str,
    is_summary: bool,
) -> list[RemoteNotification]:
    """Yield typed rows from one table, or nothing when it bears no certificate column."""
    header_cells = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    if not header_cells:
        return []
    normalised = [h.lower() for h in header_cells]
    if not any("certificado" in h for h in normalised):
        return []
    return _rows_from_table_body(
        table,
        header_index=_index_columns(normalised),
        source_url=source_url,
        is_summary=is_summary,
        summary_table_tipo=_summary_table_tipo(table) if is_summary else None,
    )


def _rows_from_table_body(
    table: Tag,
    *,
    header_index: dict[str, int],
    source_url: str,
    is_summary: bool,
    summary_table_tipo: Literal["notificacion", "comunicacion"] | None,
) -> list[RemoteNotification]:
    """Project every populated body row of one certificate-bearing table."""
    rows: list[RemoteNotification] = []
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


_NOTIFICATION_COLUMN_MATCHERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("certificado",), "certificado"),
    (("concepto",), "concepto"),
    (("tipo",), "tipo"),
    (("destinatario",), "destinatario"),
    (("titular",), "titular"),
    (("modo",), "modo"),
    # The summary renders "Fecha de emisión"; the query renders "Fecha
    # emisión". Article-free stems keep both AEAT surfaces addressable.
    (("fecha", "notificaci"), "fecha_notificacion"),
    (("fecha", "emisi"), "fecha_emision"),
    # "Leída" / "Leida" — accented or not.
    (("le", "da"), "leida"),
)


def _notification_column_key(lower: str) -> str | None:
    """Return the semantic key for one normalized notification header.

    The order is intentional: ``modo`` must claim ``Modo notificación``
    before the date branches inspect the same label.
    """
    return next(
        (key for tokens, key in _NOTIFICATION_COLUMN_MATCHERS if all(token in lower for token in tokens)),
        None,
    )


def _index_columns(headers: list[str]) -> dict[str, int]:
    """Map normalized column labels to indices so column order can drift safely."""
    return {
        key: index
        for index, header in enumerate(headers)
        if (key := _notification_column_key(header.lower())) is not None
    }


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

    concepto_raw = cell_text(cells, header_index.get("concepto")) or ""
    titular_raw = cell_text(cells, header_index.get("titular")) or ""
    destinatario_raw = cell_text(cells, header_index.get("destinatario")) or ""
    tipo_raw = cell_text(cells, header_index.get("tipo")) or ""
    modo_raw = cell_text(cells, header_index.get("modo"))
    leida_raw = cell_text(cells, header_index.get("leida"))
    emision_raw = cell_text(cells, header_index.get("fecha_emision"))
    notif_raw = cell_text(cells, header_index.get("fecha_notificacion"))

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


def _summary_table_tipo(table: Tag) -> Literal["notificacion", "comunicacion"] | None:
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


def notifications_query_url(*, today: date, lookback_years: int | None = None) -> str:
    """Return the query URL carrying an explicit, widened date window.

    AEAT's search defaults ``fecha desde`` to one month before today, so a bare
    request answers "what arrived this month" rather than "what is on the
    register". Reading it that way reported a near-empty inbox for an account
    holding older notifications -- the surface was answering the question it was
    asked. The window is therefore stated rather than inherited.

    The filters are sent as GET parameters. The form declares ``method="post"``,
    but the servlet honours the same fields on a query string, so the reader
    stays a pure navigation and needs no read-POST allowance on its guard
    policy.

    Args:
        today: The upper bound of the window, injected rather than read from the
            clock so the URL is a pure function of its inputs.
        lookback_years: Override for the configured lookback.

    Returns:
        The absolute query URL with its date window and both filters widened.
    """
    config = Settings.external_constants().aeat.notifications_query
    years = config.lookback_years if lookback_years is None else lookback_years
    # ``date.replace`` is wrong here: it raises on 29 February. Going through the
    # ordinal-free construction keeps a leap-day "today" on a real date.
    desde = date(today.year - years, today.month, 1)
    params = {
        "F_FECHA_DESDE": desde.strftime(config.date_format),
        "F_FECHA_HASTA": today.strftime(config.date_format),
        "F_TIPO_CONSULTA": config.tipo_consulta_all,
        "F_LEIDA": config.leida_all,
    }
    separator = "&" if "?" in _NOTIF_QUERY_URL else "?"
    return f"{_NOTIF_QUERY_URL}{separator}{urlencode(params)}"


class NotificationDocument(BaseModel):
    """The PDF AEAT serves for one already-read notification.

    Attributes:
        certificado_id: The notification the document belongs to.
        pdf_bytes: The document as served. Held in memory by the caller and
            written only to encrypted storage; never to disk.
        pdf_sha256: Digest of :attr:`pdf_bytes`, for evidence integrity.
        source_url: The detail endpoint the document was served from.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    certificado_id: AeatCertificadoId
    pdf_bytes: bytes
    pdf_sha256: ContentDigest
    source_url: AnyHttpUrl
    mode: Literal["read"] = "read"


def notification_detail_url(certificado_id: str) -> str:
    """Return the detail-page URL for one notification."""
    return f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.notifications_detail}?{urlencode({'ncc': certificado_id})}"


def assert_notification_content_readable(row: RemoteNotification) -> None:
    """Refuse to fetch the content of any notification AEAT has not recorded as read.

    **This guard exists for a legal reason, not a technical one.** AEAT serves a
    notification's content and performs its *comparecencia* through the same
    control. For a notification already read, driving it redisplays a document
    and changes nothing. For an unread one, that same control is the act by
    which the notification becomes legally served -- it starts the appeal and
    payment periods, and AEAT requires the taxpayer's own signature to complete
    it.

    That signature is the taxpayer's to give. An agent must never stand in for
    it, must never provoke the flow that asks for it, and must never cause a
    notification to be served as a side effect of reading a mailbox. So the
    predicate is not "is this fetchable" but "has AEAT already recorded that the
    taxpayer read this" -- and anything else is refused, including a notification
    that is already SERVED but still unread. Service and reading are different
    events, and only the second one licenses this fetch.

    Fail-closed by construction: ``leida`` is ``None`` for pending rows and for
    rows whose column AEAT did not render, and both refuse here.

    Args:
        row: The notification whose content a caller wants.

    Raises:
        SedeNavigationError: When the row is anything other than already read.
    """
    if row.leida is True:
        return
    raise SedeNavigationError(
        "refusing to fetch notification content: AEAT does not report this notification as read, "
        "and the control that serves its content is the same one that performs the comparecencia. "
        "Driving it would make the notification legally served and start its deadlines, which "
        "requires the taxpayer's signature and is theirs alone to give. Open it in the sede "
        f"personally. certificado_id={row.certificado_id!r} leida={row.leida!r} "
        f"fecha_notificacion={row.fecha_notificacion!r}",
        failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        translated_message=tr("adapters.sede.errors.notification_content_requires_operator"),
        context={
            "certificado_id": str(row.certificado_id),
            "leida": str(row.leida),
            "blocked_operation": "notification_comparecencia",
        },
    )


async def fetch_notification_document(
    session: AeatSession,
    row: RemoteNotification,
    *,
    settings: Settings | None = None,
) -> NotificationDocument:
    """Fetch the PDF of one ALREADY-READ notification.

    Guarded by :func:`assert_notification_content_readable`, which refuses every
    row AEAT does not already report as read. The refusal is checked before any
    request crosses the wire, so a refused row produces no AEAT contact at all.

    Args:
        session: An authenticated :class:`AeatSession`.
        row: The notification to fetch. Must be already read.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        The :class:`NotificationDocument` as served.

    Raises:
        SedeNavigationError: When the row is not already read, or the landing is
            off-policy.
    """
    assert_notification_content_readable(row)

    settings = settings or Settings()
    url = notification_detail_url(str(row.certificado_id))
    _assert_read_http("GET", url)
    assert_read_http_for(_READ_GUARD_POLICY, "POST", url)

    storage_state = storage_state_for_session(session)
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        page = await context.new_page()
        # Land the detail page first so AEAT sees the referring navigation.
        await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        assert_notifications_read_landing(_notifications_landing_url(page, requested_url=url))
        response = await context.request.post(
            url,
            form={
                "accion": _EXTERNAL.aeat.notifications_query.detail_view_action,
                "ncc": str(row.certificado_id),
            },
        )
        body = await response.body()
        assert_pdf_response(
            status=response.status,
            content_type=response.headers.get("content-type", ""),
            body=body,
            subject=f"notification ncc={row.certificado_id!r}",
        )
        return NotificationDocument(
            certificado_id=row.certificado_id,
            pdf_bytes=body,
            pdf_sha256=sha256_hex(body),
            source_url=AnyHttpUrl(url),
        )
    finally:
        await close_async_resources(context, browser_session, task_name="cadrumo-notification-document-close")


async def fetch_notifications_query(
    session: AeatSession,
    *,
    settings: Settings | None = None,
    today: date | None = None,
) -> NotificationsSnapshot:
    """Live-fetch ``SvInteresadosQuery`` over a widened date window using Cl@ve.

    Args:
        session: An authenticated :class:`AeatSession`.
        settings: Optional :class:`core.config.Settings` override.
        today: Upper bound of the search window; defaults to the current date.

    Returns:
        A :class:`NotificationsSnapshot` parsed from the live HTML.
    """
    return await _fetch_and_parse(
        session,
        url=notifications_query_url(today=today or now().date()),
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
    # Both requests are known before a browser context exists. Refusing either
    # here proves an unrecognised path cannot produce even a warm-up navigation.
    _assert_read_http("GET", _NOTIF_SUMMARY_URL)
    _assert_read_http("GET", url)

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
            await page.goto(_NOTIF_SUMMARY_URL, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
            assert_notifications_read_landing(
                _notifications_landing_url(page, requested_url=_NOTIF_SUMMARY_URL),
            )
        except (PlaywrightError, OSError) as exc:
            log.debug(
                "fetch_notifications: warm-up navigation to %s suppressed: %s",
                _NOTIF_SUMMARY_URL,
                exc,
                exc_info=True,
            )
        try:
            await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto {url!r} failed: {exc}") from exc
        # Follow the redirect chain rather than assuming the request host:
        # capture where AEAT actually landed and re-assert that host through
        # the host-suffix read guard so an off-AEAT redirect fails closed
        # while a ``www{n}`` load-balancer dispatch is tolerated.
        landing_url = _notifications_landing_url(page, requested_url=url)
        assert_notifications_read_landing(landing_url)
        landing = urlsplit(landing_url)
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
    assert_read_http_for(_READ_GUARD_POLICY, method, url)


def assert_notifications_read_landing(landing_url: str | None) -> None:
    """Refuse a DEHú landing outside the exact notification read routes."""
    assert_read_landing(
        landing_url,
        surface="DEHu notifications",
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=_READ_GUARD_POLICY.allowed_read_paths,
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
    "NotificationDocument",
    "NotificationsSnapshot",
    "RemoteNotification",
    "assert_notification_content_readable",
    "assert_notifications_read_landing",
    "fetch_notification_document",
    "fetch_notifications_query",
    "fetch_notifications_summary",
    "notification_detail_url",
    "notifications_query_url",
    "parse_notifications_query",
    "parse_notifications_summary",
]
