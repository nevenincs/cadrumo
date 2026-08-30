"""Playwright-driven sede walker: session → expedientes → PDF bytes.

The walker is the only side-effectful layer in :mod:`adapters.outbound.aeat.sede`. It
takes an :class:`AeatSession` whose encrypted browser state carries
valid AEAT cookies, drives a read-only Playwright session over the
sede, and exposes three operations to callers:

* :func:`walk_expedientes_tree` — listing traversal.
* :func:`resolve_justificante_ref` — expediente → CSV handle.
* :func:`capture_justificante` — expediente → authoritative PDF capture.

All three are read-only by construction: only ``page.goto`` and
``context.request.get`` cross the wire. No ``click()`` onto submit
buttons, no form POSTs, no mutation verbs anywhere in the public
surface.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....core.hashing import sha256_hex
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import now
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._adapter_utils import assert_pdf_response as _assert_pdf_response
from ._adapter_utils import assert_read_http_for, assert_read_landing, landed_origin
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_TIMEOUT_SHORT_MS as _TIMEOUT_SHORT_MS,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from .errors import (
    ExpedienteNotFoundError,
    SedeFailureMode,
    SedeNavigationError,
)
from .parse import parse_expediente_detail, parse_resumen_tree
from .schema import Expediente, JustificanteRef, SedeCapture

if TYPE_CHECKING:
    from .....application.auth.session_types import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_SEDE_HOST = urlsplit(_SEDE_BASE).netloc
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_RESUMEN_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"

DEFAULT_EXPAND_TIMEOUT_MS: int = 10_000


@runtime_checkable
class _HtmlSnapshotPage(Protocol):
    """Structural page surface required to capture a Sede HTML snapshot."""

    async def content(self) -> object:
        """Return the current page markup."""
        ...


# The walker navigates to URLs it did NOT construct. ``Expediente.detail_url``
# comes from an ``href`` on the resumen page, and the parser deliberately
# preserves a supplied external netloc, so a page that AEAT did not author --
# or a fixture -- can name any host it likes. This session is authenticated:
# navigating it off the AEAT apex sends AEAT session cookies to a host of the
# page's choosing.
#
# Every adjacent authenticated reader (declarations, censal, IVA wallet)
# already preflights each GET against a policy. This walker did not, so it was
# the one authenticated sede reader that would follow an arbitrary absolute
# URL. Same shape as the declarations read policy: exact numbered host plus the
# AEAT apex suffix, because AEAT load-balances the authenticated surface across
# its ``www{n}`` pool and pinning one host would refuse a legitimate dispatch.
#
# ``allowed_browser_action_patterns`` is deliberately EMPTY. The walker drives
# no controls: it only navigates and fetches. An empty tuple means any future
# browser action added here fails the guard until it is declared, which is the
# refusal we want rather than a gap.
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-expedientes-walker-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_SEDE_HOST,),
    allowed_host_suffixes=(_AEAT_HOST_SUFFIX,),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)


def _assert_read_http(method: str, url: str) -> None:
    """Refuse a wire-crossing read the walker policy does not admit."""
    assert_read_http_for(_READ_GUARD_POLICY, method, url)


# The one page whose CONTENT this walker interprets. Expediente detail URLs
# are deliberately absent: they come off an ``href`` on the resumen page, so
# their paths are not knowable here and an allow-list over them would be
# invented rather than grounded. Those navigations keep the policy check
# alone -- host plus write-token scan -- which is the honest strength for a
# page-supplied target.
_RESUMEN_READ_PATH_PREFIXES: tuple[str, ...] = (urlsplit(_EXTERNAL.aeat.sede_paths.expedientes_resumen).path,)


def assert_resumen_landing(landing_url: str) -> None:
    """Refuse a landing that is not the expedientes resumen page.

    Called after the branch expansion, which JS-clicks every
    ``mostrarListado`` anchor in the tree. Those anchors are AJAX
    expanders, so the page is expected not to move -- but nothing
    established that it had not. The walker then snapshots the DOM and
    parses it AS the expedientes tree, so a navigation during expansion
    would be read as a tree with no error anywhere: the parser would
    simply find no rows, and an empty result is indistinguishable from a
    taxpayer with no expedientes.

    Args:
        landing_url: The URL AEAT actually served, read off the page.

    Raises:
        SedeNavigationError: When the walker is not on the resumen page.
    """
    assert_read_landing(
        landing_url,
        surface="expedientes walker",
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=_RESUMEN_READ_PATH_PREFIXES,
    )


def assert_landed_url_readable(landed_url: str, *, requested_url: str) -> str:
    """Return the landed URL, refusing a navigation that produced no readable one.

    The re-assertion after a ``goto`` used to be skipped entirely when the
    landed URL was empty, so the one case where the outcome could not be
    established was the one case that was not checked -- fail-open in
    exactly the position the re-assertion exists to cover.

    Args:
        landed_url: ``page.url`` after the navigation.
        requested_url: The URL the navigation asked for, for diagnostics.

    Returns:
        The landed URL, once established as readable.

    Raises:
        SedeNavigationError: When the navigation produced no readable URL.
    """
    if landed_origin(landed_url) is None:
        raise SedeNavigationError(
            "sede walker navigation produced no readable landing URL, so where the "
            "authenticated session ended up cannot be established; the read is refused "
            f"rather than continued blind. requested_url={requested_url!r}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.landing_unreadable"),
            context={"requested_url": requested_url, "landing_url": landed_url or "<empty>"},
        )
    return landed_url


# ADAPTER-INTERNAL-ALIAS-RATIONALE-PLAYWRIGHT-PAGE: page is a Playwright
# Page-like object; typed loosely so both sync and async Playwright pages
# satisfy this shared helper without importing either concrete type here.
async def _goto_guarded(page: Any, url: str) -> None:
    """Navigate to ``url`` only if the policy admits it, then re-assert the landing.

    Both halves matter. The requested URL is guarded because it may have come
    from a page rather than from this module. The LANDED URL is re-asserted
    because AEAT answers with a redirect chain, and a redirect is a second
    chance to leave the allowed host set -- checking only the request would
    guard the intent and not the outcome.
    """
    _assert_read_http("GET", url)
    await page.goto(url, wait_until=_WAIT_DOMCONTENTLOADED)
    landed = assert_landed_url_readable(getattr(page, "url", "") or "", requested_url=url)
    _assert_read_http("GET", landed)


@asynccontextmanager
async def _open_browser_page(
    session: AeatSession,
    settings: Settings,
) -> AsyncGenerator[tuple[Any, Any]]:
    """Yield ``(context, page)`` for a fresh authenticated Playwright session.

    Centralises the open / null-guard / context.close / browser.close
    nesting that every public ``_walker`` function needs to drive a
    sede page. The caller decides what to do with the page (warm-up
    goto, target navigation, request.get, etc.) and the context manager
    cleans up on exit even if the body raises.

    Args:
        session: Authenticated AEAT session whose storage-state path carries valid cookies.
        settings: Settings instance used for browser factory configuration.

    Yields:
        A ``(context, page)`` tuple ready for navigation.

    Raises:
        SedeNavigationError: When the session has no persisted auth state.
    """
    storage_state = storage_state_for_session(session)
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        page = await context.new_page()
        yield context, page
    finally:
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-sede-walker-close",
        )


async def walk_expedientes_tree(
    session: AeatSession,
    *,
    modelo: str | None = None,
    settings: Settings | None = None,
) -> tuple[Expediente, ...]:
    """Enumerate every expediente visible under *Mis Expedientes*.

    The sede renders an AJAX-expanded tree. This function expands
    every category branch whose label contains a ``Modelo <N>`` token
    (or all branches when ``modelo`` is None), then parses the
    resulting DOM for leaf expediente rows.

    Args:
        session: An authenticated session with encrypted cached AEAT
            cookies. Cl@ve-móvil and certificate sessions both qualify.
        modelo: When set, only expand category branches whose label
            references this modelo code (e.g. ``"100"`` for IRPF).
            Saves DOM expansion work on large corpora.
        settings: Optional :class:`Settings` override. Defaults to
            :func:`core.config.load_settings`.

    Returns:
        Tuple of :class:`Expediente` records, ordered as AEAT renders
        them (most recent first in every captured case so far).

    Raises:
        SedeNavigationError: If ``goto`` or a required expansion fails.
    """
    settings = settings or Settings()
    async with _open_browser_page(session, settings) as (_context, page):
        try:
            await _goto_guarded(page, _RESUMEN_URL)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto {_RESUMEN_URL!r} failed: {exc}") from exc

        await _expand_matching_branches(page, modelo=modelo)
        assert_resumen_landing(getattr(page, "url", "") or "")
        html = await _snapshot_html(page)
        expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
        if modelo is not None:
            expedientes = tuple(e for e in expedientes if e.modelo == modelo)
        log.info(
            "walk_expedientes_tree: found %d expediente(s) modelo=%s",
            len(expedientes),
            modelo,
        )
        return expedientes


async def resolve_justificante_ref(
    session: AeatSession,
    expediente: Expediente,
    *,
    settings: Settings | None = None,
) -> JustificanteRef:
    """Navigate to an expediente's detail page and extract its CSV ref.

    Args:
        session: Authenticated session with encrypted cached AEAT cookies.
        expediente: Expediente to look up. ``expediente.detail_url``
            is used verbatim.
        settings: Optional override.

    Returns:
        A :class:`JustificanteRef` ready for
        :func:`capture_justificante`.

    Raises:
        SedeNavigationError: If the detail page cannot be loaded.
    """
    settings = settings or Settings()
    detail_url = str(expediente.detail_url)
    async with _open_browser_page(session, settings) as (_context, page):
        # Warm the session on ResumenVlt so AEAT's redirect chain
        # sees the origin cookie; navigating straight to the
        # per-year endpoint without this is fine when cookies are
        # fresh but fails intermittently after idle periods.
        try:
            await _goto_guarded(page, _RESUMEN_URL)
        except PlaywrightError as _exc:
            log.debug("sede walker: warm-up goto %s suppressed: %s", _RESUMEN_URL, _exc, exc_info=True)
        # Guarded BEFORE the navigation: detail_url came off a page, not from
        # this module, so a refusal here must prevent the request rather than
        # report it afterwards.
        try:
            await _goto_guarded(page, detail_url)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto expediente detail {detail_url!r} failed: {exc}") from exc
        html = await page.content()
        ref = parse_expediente_detail(
            html,
            expediente_id=expediente.expediente_id,
            base_url=_SEDE_BASE,
        )
        log.info(
            "resolve_justificante_ref: resolved CSV=%s expediente=%s",
            ref.csv,
            expediente.expediente_id,
        )
        return ref


async def capture_justificante(
    session: AeatSession,
    expediente: Expediente,
    *,
    settings: Settings | None = None,
) -> SedeCapture:
    """End-to-end: expediente → CSV handle → PDF bytes → :class:`SedeCapture`.

    Bundles :func:`resolve_justificante_ref` + the raw PDF GET into
    one session-reusing call. The preferred entry point for callers
    that just want "the AEAT record for this expediente".

    Args:
        session: Authenticated session.
        expediente: Target expediente.
        settings: Optional override.

    Returns:
        A fully populated :class:`SedeCapture`.

    Raises:
        SedeNavigationError: On goto failures.
        JustificanteFetchError: On PDF download failures.
    """
    settings = settings or Settings()
    detail_url = str(expediente.detail_url)
    async with _open_browser_page(session, settings) as (context, page):
        try:
            await _goto_guarded(page, _RESUMEN_URL)
        except PlaywrightError as _exc:
            log.debug("sede walker: warm-up goto %s suppressed: %s", _RESUMEN_URL, _exc, exc_info=True)
        # Guarded BEFORE the navigation: detail_url came off a page, not from
        # this module, so a refusal here must prevent the request rather than
        # report it afterwards.
        try:
            await _goto_guarded(page, detail_url)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto expediente detail {detail_url!r} failed: {exc}") from exc
        detail_html = await page.content()
        ref = parse_expediente_detail(
            detail_html,
            expediente_id=expediente.expediente_id,
            base_url=_SEDE_BASE,
        )

        # ``JustificanteRef`` carries an absolute ``AnyHttpUrl``; guard it for
        # the same reason as the detail URL rather than trusting that this
        # module built it.
        _assert_read_http("GET", str(ref.pdf_url))
        pdf_response = await context.request.get(str(ref.pdf_url))
        content_type = pdf_response.headers.get("content-type", "")
        body = await pdf_response.body()
        _assert_pdf_response(
            status=pdf_response.status,
            content_type=content_type,
            body=body,
            subject=f"CSV={ref.csv!r}",
        )
        sha256 = sha256_hex(body)
        log.info(
            "capture_justificante: captured PDF expediente=%s CSV=%s size=%d sha256=%s",
            expediente.expediente_id,
            ref.csv,
            len(body),
            sha256[:16],
        )
        return SedeCapture(
            expediente=expediente,
            ref=ref,
            pdf_bytes=body,
            pdf_sha256=sha256,
            captured_at=now(),
        )


async def find_expediente(
    session: AeatSession,
    *,
    modelo: str,
    ejercicio: int,
    settings: Settings | None = None,
) -> Expediente:
    """Convenience lookup: first expediente matching ``(modelo, ejercicio)``.

    Args:
        session: Authenticated AEAT session.
        modelo: Modelo code to filter on (e.g. ``"100"``).
        ejercicio: Tax year to match.
        settings: Optional :class:`Settings` override.

    Returns:
        The first :class:`Expediente` whose ``ejercicio`` matches.

    Raises:
        ExpedienteNotFoundError: If no expediente in the corpus matches the filter.
    """
    expedientes = await walk_expedientes_tree(session, modelo=modelo, settings=settings)
    for expediente in expedientes:
        if expediente.ejercicio == ejercicio:
            return expediente
    raise ExpedienteNotFoundError(f"no expediente found for modelo={modelo!r} ejercicio={ejercicio}")


async def _snapshot_html(page: object) -> str:
    """Capture ``page.content()`` with retries across in-flight navigations.

    The sede's expansion clicks kick off AJAX that occasionally races
    ``page.content()`` ("page is navigating" error). A short retry
    loop with a brief sleep is robust without introducing an
    unbounded wait.
    """
    import asyncio as _asyncio

    wait_for_load_state = getattr(page, "wait_for_load_state", None)
    if not isinstance(page, _HtmlSnapshotPage):
        raise SedeNavigationError("page does not expose content(); cannot snapshot HTML")
    last_exc: BaseException | None = None
    for _ in range(8):
        if wait_for_load_state is not None:
            try:
                await wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=_TIMEOUT_SHORT_MS)
            except PlaywrightError as wait_exc:
                log.debug(
                    "sede walker: wait_for_load_state did not settle; proceeding to content() anyway (%s)",
                    wait_exc,
                )
        try:
            html = await page.content()
            if isinstance(html, str):
                return html
            raise SedeNavigationError("page content() returned a non-text payload; cannot snapshot HTML")
        except PlaywrightError as exc:
            last_exc = exc
            await _asyncio.sleep(0.5)
    raise SedeNavigationError(f"failed to snapshot page HTML after 8 attempts: {last_exc!r}")


async def _expand_matching_branches(page: object, *, modelo: str | None) -> None:
    """Click tree anchors until the relevant subtree is fully expanded.

    Two strategies, selected by ``modelo``:

    * When ``modelo`` is set (e.g. ``"100"``), target every leaf
      ``mostrarListado`` anchor whose visible text contains
      ``Modelo <N>``. AEAT's procedure tree can list the same modelo
      under more than one category branch (e.g. distinct
      autoliquidación / declaración-informativa / recargo procedure
      entries for the same modelo code); clicking only the first match
      would lazy-load one branch's subtree while leaving a sibling
      branch — and any expediente rows nested only under it — never
      expanded. Every matching anchor is clicked, deduplicated the same
      way as the ``modelo=None`` branch below.
    * When ``modelo`` is ``None``, click every ``mostrarListado``
      anchor in document order — this expands the whole corpus. The
      JS dedup guards against clicking a category header twice.
    """
    import asyncio as _asyncio

    evaluate = getattr(page, "evaluate", None)
    if evaluate is None:
        return

    if modelo is not None:
        clicked_count = await evaluate(
            """
            (modelo) => {
                const wanted = 'Modelo ' + modelo;
                const seen = new Set();
                let clickedCount = 0;
                Array.from(document.querySelectorAll('a')).forEach(a => {
                    const onc = a.getAttribute('onclick') || '';
                    if (!onc.includes('mostrarListado')) return;
                    if (!(a.textContent || '').includes(wanted)) return;
                    const key = a.id || onc;
                    if (seen.has(key)) return;
                    seen.add(key);
                    try { a.click(); clickedCount += 1; } catch (e) {}
                });
                return clickedCount;
            }
            """,
            modelo,
        )
        if not clicked_count:
            log.debug("_expand_matching_branches: no mostrarListado anchor found for modelo=%s", modelo)
            return
        log.debug(
            "_expand_matching_branches: expanded %d matching branch(es) for modelo=%s",
            clicked_count,
            modelo,
        )
    else:
        await evaluate(
            """
            () => {
                const seen = new Set();
                Array.from(document.querySelectorAll('a')).forEach(a => {
                    const onc = a.getAttribute('onclick') || '';
                    if (!onc.includes('mostrarListado')) return;
                    const key = a.id || onc;
                    if (seen.has(key)) return;
                    seen.add(key);
                    try { a.click(); } catch (e) {}
                });
            }
            """,
        )
    # Give AEAT's AJAX a beat to populate the DOM before the caller
    # snapshots it. networkidle is too strict (GA pings keep it busy);
    # a short fixed sleep is both faster and more reliable.
    await _asyncio.sleep(2.0)


__all__ = [
    "assert_landed_url_readable",
    "assert_resumen_landing",
    "capture_justificante",
    "find_expediente",
    "resolve_justificante_ref",
    "walk_expedientes_tree",
]
