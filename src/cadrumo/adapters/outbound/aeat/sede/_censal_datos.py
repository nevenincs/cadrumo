"""Read-only censal *consulta* reader for the authenticated AEAT sede.

AEAT publishes the taxpayer's own censal state at the *Mis Datos
Censales* launcher (``MdcAcceso``), whose ``<h1>`` is *Consulta de Datos
Identificativos y Censales*. The page renders three data groups as
``table.celdasConBorde`` tables:

* **Datos Identificativos del Contribuyente** — NIF, name, birth data,
  nationality, marital status, and the two electronic-notification
  flags. Rendered row-wise as ``<b>``-wrapped label / value pairs.
* **Domicilio Fiscal** and **Domicilio de Notificación** — each split
  across several tables rendered *column*-wise: a row of ``<b>``-wrapped
  labels followed by a row of values, positionally aligned.

Every table carries a ``title`` attribute naming its group, which is the
section discriminator; the ``<th>`` heading renders only on the first
table of each group.

**This page sits next to a write surface.** It renders *Cambio de
Domicilio Fiscal* / *Cambio de Domicilio de Notificaciones* / *Baja de
Domicilio de Notificaciones* buttons whose scripts build relative
``ModifDomiDual`` / ``ModifDomiNotif`` targets, and it links the M036
filing tool. Reading the rendered DOM is a read; driving any of those
controls is not. This reader therefore navigates and parses only: it
submits nothing, fills nothing, clicks nothing, and
:func:`_assert_read_landing` fails closed at runtime if AEAT ever lands
it on a modification path. That runtime landing guard is the primary
wall; the module-level string check in the sede write-surface gate is
the weaker second one.

Public surface: :func:`parse_censal_datos`,
:func:`fetch_censal_datos`, :func:`censal_datos_url`, and the landing
predicates :func:`is_forbidden_censal_landing` and
:func:`forbidden_censal_landing_marker`, exported so conformance gates
exercise the real refusal rule instead of mirroring it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote, urlsplit

from bs4 import Tag

from .....application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from .....core import fold_diacritics
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
from .._html import parse_html
from .._playwright import Page, PlaywrightError
from ..browser import BrowserSession, DefaultBrowserSession, default_browser_session_factory
from ._adapter_utils import assert_read_http_for
from ._auth_state import storage_state_for_session
from ._browser_constants import PLAYWRIGHT_WAIT_DOMCONTENTLOADED
from ._walker import assert_landed_url_readable
from .errors import SedeFailureMode, SedeNavigationError, SedeParseError

if TYPE_CHECKING:
    from .....application.auth.session_types import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
# NO NUMBERED HOST IS PINNED. AEAT dispatches the authenticated sede across a
# ``www{n}`` load-balancer pool and assigns the number per session: some
# numbered hosts do not serve this route at all and others reject a session
# minted elsewhere, so a pinned ``www6`` is wrong rather than merely brittle.
# The reader therefore enters through the host-agnostic access selector (which
# is rooted at the unnumbered ``sede.`` origin) and reads the host AEAT
# actually assigns off the landed page. The guard admits any subdomain under
# the AEAT apex so whichever number is dispatched is tolerated.
_SEDE_ORIGIN = _EXTERNAL.aeat.domains.sede
_SEDE_HOST = urlsplit(_SEDE_ORIGIN).netloc
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_CENSAL_PATH = _EXTERNAL.aeat.sede_paths.censal_datos
_SELECTOR_MARKER = _EXTERNAL.aeat.clave_movil.selector_access_path_marker
_CENSAL_SELECTOR_URL = _EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(_CENSAL_PATH, safe=""),
)
# The sole control this reader drives, and only on the selector page.
_SELECTOR_AUTHORIZE_ACTION: Final = "clave-movil-authorize"

# Landing fragments that mark a censal MODIFICATION surface. Registry-borne
# because none of them contains the token an earlier draft forbade
# (``MOD036``): the filing tool is ``BU36-ASIS/M036/index.zul`` and the write
# sibling is ``BUGC-JDIT/ModifDomiDual``.
_FORBIDDEN_LANDING_MARKERS: Final[tuple[str, ...]] = _EXTERNAL.aeat.live_safety.censal_forbidden_landing_markers

_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-censal-datos-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_SEDE_HOST,),
    # Widened to the AEAT apex so whichever ``www{n}`` the selector dispatches
    # to is admitted; success detection stays on the censal path and marker.
    #
    # This is a DELIBERATE divergence from the posture
    # ``remote_state_policy_from_cross_reference`` takes, which sets no host
    # suffixes so a policy admits exactly the hosts its surface declares. That
    # posture carves out a surface whose reads genuinely span AEAT's numbered
    # pool, and this is one: the route is entered through the host-agnostic
    # selector and AEAT assigns the number per session, so the answering host
    # is not knowable when the policy is built.
    #
    # The carve-out's own remedy is to ENUMERATE the pool on ``allowed_hosts``,
    # which is what the declarations cross-references do (``www1``, ``www6``
    # declared in registry TOML). That remedy is not available here yet and the
    # reason is external: which numbered hosts serve the censal route is a fact
    # about AEAT, and this tree carries no observation of it. Some numbered
    # hosts do not serve the route and others refuse a session minted
    # elsewhere, so the set cannot be inferred from the ones that serve
    # declarations.
    #
    # Narrowing therefore waits on an operator probe: authenticate, run the
    # censal read repeatedly, and collect the ``host=`` values
    # ``_resolve_dispatched_origin`` logs. Enough runs to see the pool repeat
    # gives the enumeration; until then the apex widening is the honest
    # statement of what is known. Note the host guard is not the no-write wall
    # -- ``_FORBIDDEN_LANDING_MARKERS`` is -- so the widening does not loosen
    # the write refusal.
    allowed_host_suffixes=(_AEAT_HOST_SUFFIX,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.censal_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)

# Row-count-independent page marker taken from the consulta ``<h1>``. A parse
# that yields no identity NIF and lacks this marker is a wrong-service /
# auth-gate / maintenance landing rather than an empty censal record.
_CENSAL_PAGE_MARKER: Final = "datos identificativos y censales"

_PARENTHETICAL_RE: Final[re.Pattern[str]] = re.compile(r"\([^)]*\)")

_IDENTITY_SECTION: Final = "datos identificativos del contribuyente"
_FISCAL_SECTION: Final = "domicilio fiscal"
_NOTIFICATION_SECTION: Final = "domicilio de notificacion"

# Folded AEAT label -> model field. Folding lowercases, strips diacritics,
# removes any parenthetical qualifier, and drops a trailing colon, so
# "Complemento domicilio (ej.:Urbanización...)" and the notification
# variant that adds "Polígono Industrial" both reduce to one key.
_IDENTITY_LABELS: Final[Mapping[str, str]] = {
    "nif": "nif",
    "apellidos y nombre": "apellidos_y_nombre",
    "administracion de su domicilio fiscal": "administracion_domicilio_fiscal",
    "lugar de nacimiento": "lugar_nacimiento",
    "fecha de nacimiento": "fecha_nacimiento",
    "pasaporte": "pasaporte",
    "sexo": "sexo",
    "nacionalidad": "nacionalidad",
    "estado civil": "estado_civil",
    "obligado a notificaciones electronicas": "obligado_notificaciones_electronicas",
    "suscrito voluntariamente a notificaciones electronicas": "suscrito_voluntariamente_notificaciones_electronicas",
}

_DOMICILIO_LABELS: Final[Mapping[str, str]] = {
    "tipo via": "tipo_via",
    "nombre via": "nombre_via",
    "tipo de numero": "tipo_numero",
    "numero de casa": "numero_casa",
    "calificacion de numero": "calificacion_numero",
    "bloque": "bloque",
    "portal": "portal",
    "escalera": "escalera",
    "planta": "planta",
    "puerta": "puerta",
    "complemento domicilio": "complemento",
    "localidad/poblacion": "localidad",
    "referencia catastral": "referencia_catastral",
    "indicador de referencia catastral": "indicador_referencia_catastral",
    "codigo postal": "codigo_postal",
    "municipio": "municipio",
    "provincia": "provincia",
    "destinatario": "destinatario",
    "en calidad de": "en_calidad_de",
}

_AFFIRMATIVE: Final[frozenset[str]] = frozenset({"si", "s", "true"})
_NEGATIVE: Final[frozenset[str]] = frozenset({"no", "n", "false"})


# ── Parsing ────────────────────────────────────────────────────────────────


def parse_censal_datos(html: str, *, source_url: str) -> CensalObservation:
    """Parse a censal consulta page into a canonical censal observation.

    Args:
        html: Raw HTML body of a censal consulta page.
        source_url: URL the HTML was read from (recorded on the result).

    Returns:
        The application-owned observation carrying identity and both addresses.

    Raises:
        SedeParseError: When the HTML cannot be parsed at all, or carries
            no censal data table.
    """
    try:
        soup = parse_html(html)
    except Exception as exc:  # pragma: no cover — lxml always available
        raise SedeParseError(f"failed to parse censal HTML: {exc}") from exc
    for tag in soup(["script", "style"]):
        tag.decompose()

    identity_fields: dict[str, str] = {}
    fiscal_fields: dict[str, str] = {}
    notification_fields: dict[str, str] = {}
    tables_seen = 0

    for table in soup.find_all("table"):
        table = _require_tag(table, element="table")
        section = _section_of(table)
        if section is None:
            continue
        tables_seen += 1
        if section == _IDENTITY_SECTION:
            _collect(table, _IDENTITY_LABELS, identity_fields)
        elif section == _FISCAL_SECTION:
            _collect(table, _DOMICILIO_LABELS, fiscal_fields)
        else:
            _collect(table, _DOMICILIO_LABELS, notification_fields)

    if tables_seen == 0:
        raise SedeParseError(
            "censal page carries no recognised data table; AEAT page shape may have changed",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={"source_url": source_url},
        )

    return CensalObservation.model_validate(
        {
            "identity": _identity_from(identity_fields),
            "domicilio_fiscal": CensalObservationAddress(**fiscal_fields),
            "domicilio_notificacion": CensalObservationAddress(**notification_fields),
            "captured_at": now(),
            "source_url": source_url,
        },
        strict=True,
    )


def _deaccent(text: str) -> str:
    """Lowercase and strip diacritics so matching is accent-insensitive."""
    return fold_diacritics(text).casefold()


def _fold(text: str) -> str:
    """Lowercase, strip diacritics, drop parentheticals, and trim punctuation.

    AEAT qualifies several labels with a parenthetical example — the
    complemento label even differs between the fiscal and notification
    tables — so the qualifier is removed before matching.
    """
    without_parenthetical = _PARENTHETICAL_RE.sub("", text)
    return _deaccent(without_parenthetical).strip().rstrip(":").strip()


def _section_of(table: Tag) -> str | None:
    """Return the folded censal section a table belongs to, or ``None``.

    AEAT stamps every censal data table with a ``title`` naming its group,
    which is the reliable discriminator: the ``<th>`` heading renders only
    on the first table of each group.
    """
    raw_title = table.get("title")
    if not isinstance(raw_title, str):
        return None
    title = _fold(raw_title)
    if title in {_IDENTITY_SECTION, _FISCAL_SECTION, _NOTIFICATION_SECTION}:
        return title
    return None


def _collect(table: Tag, labels: Mapping[str, str], into: dict[str, str]) -> None:
    """Accumulate label/value pairs from one table into ``into``.

    Handles both AEAT censal table shapes: the identity table pairs a
    label cell with its value cell inside one row, while the address
    tables render a row of labels followed by a row of values that align
    positionally. A label cell is one whose entire content is ``<b>``-wrapped.
    """
    pending: list[str] = []
    for row_labels, row_values in _rows_of(table):
        if row_labels and row_values:
            # Identity shape: label and value share a row.
            for label, value in zip(row_labels, row_values, strict=False):
                _assign(labels, label, value, into)
            pending = []
            continue
        if row_labels:
            pending = row_labels
            continue
        if pending:
            # Address shape: this value row aligns with the labels above it.
            for label, value in zip(pending, row_values, strict=False):
                _assign(labels, label, value, into)
            pending = []


def _rows_of(table: Tag) -> Iterator[tuple[list[str], list[str]]]:
    """Yield ``(labels, values)`` for each ``<td>``-bearing row of ``table``."""
    for row in table.find_all("tr"):
        row = _require_tag(row, element="tr")
        cells = [_require_tag(cell, element="td") for cell in row.find_all("td")]
        if not cells:
            continue
        row_labels: list[str] = []
        row_values: list[str] = []
        for cell in cells:
            text = cell.get_text(" ", strip=True)
            if _is_label_cell(cell):
                row_labels.append(text)
            else:
                row_values.append(text)
        yield row_labels, row_values


def _require_tag(value: object, *, element: str) -> Tag:
    """Fail closed if the HTML parser violates its declared element shape."""
    if not isinstance(value, Tag):
        raise SedeParseError(
            f"censal parser returned a non-Tag {element} element",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
        )
    return value


def _is_label_cell(cell: Tag) -> bool:
    """Return whether a cell is a label — AEAT wraps every label in ``<b>``."""
    bold = cell.find("b")
    if not isinstance(bold, Tag):
        return False
    return bool(bold.get_text(strip=True))


def _assign(labels: Mapping[str, str], label: str, value: str, into: dict[str, str]) -> None:
    """Map one AEAT label to its model field and record a non-blank value."""
    field = labels.get(_fold(label))
    if field is None:
        return
    cleaned = _clean(value)
    if cleaned is not None:
        into[field] = cleaned


def _clean(value: str) -> str | None:
    """Strip AEAT's padding and non-breaking spaces, returning ``None`` when blank."""
    stripped = value.replace("\xa0", " ").strip()
    return stripped or None


def _identity_from(fields: Mapping[str, str]) -> CensalObservationIdentity:
    """Build the application-owned identity projection from parsed fields."""
    typed: dict[str, Any] = {key: value for key, value in fields.items()}
    raw_birth = typed.pop("fecha_nacimiento", None)
    birth_date = parse_date(raw_birth, fmt="ddmmyyyy", on_error="none") if raw_birth else None
    for flag in (
        "obligado_notificaciones_electronicas",
        "suscrito_voluntariamente_notificaciones_electronicas",
    ):
        raw_flag = typed.pop(flag, None)
        typed[flag] = _parse_flag(raw_flag)
    return CensalObservationIdentity(fecha_nacimiento=birth_date, **typed)


def _parse_flag(raw: str | None) -> bool | None:
    """Parse an AEAT ``Sí`` / ``No`` cell into a tri-state boolean."""
    if raw is None:
        return None
    folded = _fold(raw)
    if folded in _AFFIRMATIVE:
        return True
    if folded in _NEGATIVE:
        return False
    return None


# ── Live read ──────────────────────────────────────────────────────────────


async def fetch_censal_datos(
    session: AeatSession,
    *,
    taxpayer_nif: str,
    settings: Settings | None = None,
) -> CensalObservation:
    """Read the censal consulta surface with the authenticated session.

    The read navigates to the consulta view and parses the rendered DOM.
    It never submits a form, fills a field, or activates a control, and it
    refuses at runtime if AEAT lands it on a censal modification path.

    Args:
        session: An authenticated :class:`AeatSession` whose encrypted
            browser state carries valid AEAT cookies.
        taxpayer_nif: The session's own tax identifier. The product does
            not support acting as a representative, so this must be the
            authenticated taxpayer rather than a represented third party.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        The canonical application observation parsed from the live HTML.

    Raises:
        SedeNavigationError: When no persisted auth session exists, the
            navigation fails, AEAT lands on a modification surface, or the
            landing carries neither censal data nor the page marker.
    """
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    return await _navigate_and_parse(storage_state, taxpayer_nif=taxpayer_nif, settings=settings)


def censal_datos_url(taxpayer_nif: str, *, origin: str) -> str:
    """Build the censal consulta URL for one taxpayer against a resolved origin.

    ``origin`` is required and has no default. It previously defaulted to the
    unnumbered ``sede.`` origin, which let a caller build a URL against a host
    that is not known to serve this route while believing it was the reader's
    own address. The live read passes the host it read off the landed page.

    Args:
        taxpayer_nif: The authenticated taxpayer's own tax identifier.
        origin: Scheme and host AEAT dispatched the session to.

    Returns:
        The absolute consulta URL, query-escaped.
    """
    return f"{origin}{_CENSAL_PATH}?nifRepresentado={quote(taxpayer_nif, safe='')}&E_HNR=&EJERCICIO=0"


def _censal_landing_url(page: object, *, requested_url: str) -> str:
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
    taxpayer_nif: str,
    settings: Settings,
) -> CensalObservation:
    """Open the censal consulta through the access selector and parse the landing."""
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        page = await context.new_page()
        origin = await _resolve_dispatched_origin(page, browser_session=browser_session, settings=settings)

        url = censal_datos_url(taxpayer_nif, origin=origin)
        _assert_read_http("GET", url)
        try:
            await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto {url!r} failed: {exc}") from exc

        # Follow the redirect chain rather than trusting the requested URL:
        # re-assert the host AEAT actually served, then refuse outright if
        # that landing is a censal modification surface.
        landing_url = _censal_landing_url(page, requested_url=url)
        landing = urlsplit(landing_url)
        _assert_read_http("GET", f"{landing.scheme}://{landing.netloc}{landing.path}")
        _assert_read_landing(landing_url)

        html = await page.content()
        result = parse_censal_datos(html, source_url=url)
        if result.identity.nif is None and not _censal_marker_present(html):
            raise SedeNavigationError(
                "AEAT censal navigation returned a page with no censal marker and no identity data; "
                "this is a wrong-service / auth-gate / maintenance landing, not an empty censal record. "
                f"landing_host={landing.netloc!r} landing_path={landing.path!r} marker_present=False",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                translated_message=tr("adapters.sede.errors.censal_bad_landing"),
                context={
                    "requested_url": url,
                    "landing_host": landing.netloc,
                    "landing_path": landing.path,
                    "marker_present": False,
                },
            )
        log.info("fetch_censal_datos: read censal consulta from %s", landing.path)
        return result
    finally:
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-censal-close",
        )


def landed_on_censal_path(landing_url: str) -> bool:
    """Return whether a landing URL has arrived at the censal consulta path.

    The single reader of this condition. The dispatch wait and the judgement
    that follows it both consult this, so a wait that expires on a page which
    did land cannot produce a different answer from the check that reports it.

    Args:
        landing_url: The URL currently loaded.

    Returns:
        ``True`` when the URL carries the censal consulta path.
    """
    return _CENSAL_PATH in landing_url


async def _resolve_dispatched_origin(
    page: Page,
    *,
    browser_session: BrowserSession | DefaultBrowserSession,
    settings: Settings,
) -> str:
    """Return the scheme+host AEAT dispatched this session to.

    The numbered ``www{n}`` sede hosts are load-balanced per session — some do
    not serve the censal route and others reject a session minted elsewhere —
    so the host is never assumed. This enters through the host-agnostic access
    selector, lets AEAT dispatch, and reads the resulting host off the page.

    The one control driven here is the selector's own authorize button, which
    is an authentication dispatch rather than a censal control; it is declared
    in the policy's allowed browser actions. When the selector does not
    dispatch, this REFUSES rather than degrading to the unnumbered origin —
    see the raise site for why a fallback produced an illegible failure.

    **Log contract**, because reading a live run depends on it. A ``host=``
    record at info level is emitted on the resolved path only, and names the
    host read off the landed page. It therefore establishes that the session
    reached a numbered host — though not that the authorize click is what took
    it there, which this function cannot observe. Its absence means the reader
    either never ran or refused. Neither debug record says anything about
    dispatch in either direction: one reports only that the wait expired, and
    the other is the judgement of the landed page.

    Args:
        page: The Playwright page to drive.
        browser_session: Session wrapper providing the health-probing navigate.
        settings: Active settings, for the navigation timeout.

    Returns:
        An origin string such as ``"https://www12.agenciatributaria.gob.es"``.

    Raises:
        SedeNavigationError: When the selector does not dispatch the session to
            a host whose origin can be read off the landed page.
    """
    _assert_read_http("GET", _CENSAL_SELECTOR_URL)
    await browser_session.navigate(page, _CENSAL_SELECTOR_URL)
    await page.wait_for_load_state(PLAYWRIGHT_WAIT_DOMCONTENTLOADED)

    if _SELECTOR_MARKER in (getattr(page, "url", "") or ""):
        _assert_read_browser_action(_SELECTOR_AUTHORIZE_ACTION)
        await page.click(_EXTERNAL.aeat.clave_movil.authorize_button_selector)
        try:
            await page.wait_for_url(
                landed_on_censal_path,
                timeout=settings.cadrumo_browser_navigation_timeout_ms,
            )
        except PlaywrightError:
            # The wait expiring is a fact about the WAIT, never about the
            # dispatch: the page can land correctly just outside the wait's
            # window. Say only what happened, and let the single judgement
            # below decide whether the dispatch arrived.
            log.debug("censal selector wait expired; judging the landed page instead", exc_info=True)
        await page.wait_for_load_state(PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        # One reader of the condition, evaluated once, after the page settled.
        if not landed_on_censal_path(getattr(page, "url", "") or ""):
            log.debug(
                "censal selector dispatch did not reach the censal path; current_url=%s",
                getattr(page, "url", None),
            )

    landed = urlsplit(getattr(page, "url", "") or "")
    if not landed.scheme or not landed.netloc:
        # REFUSE rather than fall back to the unnumbered origin. This branch
        # once degraded to that origin on the assumption it "may well serve
        # the route"; a measurement on a sibling sede route found it returning
        # a genuine 404 with a valid session, so the assumption does not hold
        # in general and is unmeasured here. Worse, a fallback failure is
        # ILLEGIBLE downstream: the 404 body carries no censal table, so it
        # surfaces as a page-shape change blaming AEAT, or as a bad landing
        # telling the operator to re-authenticate — two confidently wrong
        # diagnoses for one dispatch failure. Refusing here names the actual
        # cause at the point it occurred.
        raise SedeNavigationError(
            "AEAT censal access selector did not dispatch the session to a numbered sede host, "
            "so no origin could be read off the landed page. The read is refused rather than "
            "retried against the unnumbered origin, which is not known to serve this route.",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.censal_no_dispatch"),
            context={"selector_url": _CENSAL_SELECTOR_URL, "landing_url": getattr(page, "url", None)},
        )
    origin = f"{landed.scheme}://{landed.netloc}"
    # A dispatch off the AEAT apex must not become the origin we then request.
    _assert_read_http("GET", f"{origin}{_CENSAL_PATH}")
    log.info("censal read dispatched to host=%s", landed.netloc)
    return origin


def _assert_read_browser_action(action: str) -> None:
    """Fail-closed guard: refuse any browser action the censal policy does not declare."""
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="browser_action", action=action),
    )


def _assert_read_http(method: str, url: str) -> None:
    """Fail-closed guard: refuse any non-read-only or off-AEAT censal navigation."""
    assert_read_http_for(_READ_GUARD_POLICY, method, url)


def forbidden_censal_landing_marker(landing_url: str) -> str | None:
    """Return the modification marker a landing carries, or ``None`` if it is a read.

    This is the single matching rule behind the no-write guard, exposed so
    conformance gates can exercise the real logic rather than re-implement
    it — a mirrored copy would keep passing if this rule ever changed shape.

    Args:
        landing_url: The URL AEAT actually served, after redirects.

    Returns:
        The first marker that matched, or ``None`` when the landing is safe.
    """
    folded = landing_url.casefold()
    for marker in _FORBIDDEN_LANDING_MARKERS:
        if marker.casefold() in folded:
            return marker
    return None


def is_forbidden_censal_landing(landing_url: str) -> bool:
    """Return whether a landing is a censal modification surface.

    Args:
        landing_url: The URL AEAT actually served, after redirects.

    Returns:
        ``True`` when the reader must refuse the landing.
    """
    return forbidden_censal_landing_marker(landing_url) is not None


def _assert_read_landing(landing_url: str) -> None:
    """Refuse a landing on a censal modification surface.

    The consulta page offers *Cambio de Domicilio Fiscal*, *Cambio de
    Domicilio de Notificaciones*, the M036 filing tool and an *Otras
    Modificaciones Censales* launcher, so a modification path is one
    control away. This is the PRIMARY no-write wall, and it is the runtime
    one: it keys on the real write paths, checked against where AEAT
    actually landed, rather than on a token those paths do not contain.

    The module-level string check in the sede write-surface gate is the
    weaker SECOND wall. It is deliberately kept, and deliberately not
    relied upon — do not delete this runtime half as redundant, because a
    static scan cannot see where a redirect chain ends.

    Args:
        landing_url: The URL AEAT actually served, after redirects.

    Raises:
        SedeNavigationError: When the landing carries a modification marker.
    """
    marker = forbidden_censal_landing_marker(landing_url)
    if marker is not None:
        raise SedeNavigationError(
            "AEAT censal navigation landed on a modification surface and was refused; "
            "this reader is read-only and never reaches a censal write path. "
            f"marker={marker!r}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.censal_modification_surface"),
            context={"landing_url": landing_url, "marker": marker},
        )


def _censal_marker_present(html: str) -> bool:
    """Return whether the HTML carries the row-count-independent censal page marker."""
    return _CENSAL_PAGE_MARKER in _deaccent(html)


__all__ = [
    "censal_datos_url",
    "fetch_censal_datos",
    "forbidden_censal_landing_marker",
    "is_forbidden_censal_landing",
    "landed_on_censal_path",
    "parse_censal_datos",
]
