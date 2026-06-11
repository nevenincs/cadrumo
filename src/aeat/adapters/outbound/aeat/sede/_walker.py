"""Playwright-driven sede walker: session → expedientes → PDF bytes.

The walker is the only side-effectful layer in :mod:`aeat.adapters.outbound.aeat.sede`. It
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

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from .....core.config import Settings, load_settings
from .....core.external_constants import PDF_MIME_TYPE as _PDF_MIME_TYPE
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import now
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_TIMEOUT_SHORT_MS as _TIMEOUT_SHORT_MS,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._errors import (
    ExpedienteNotFoundError,
    JustificanteFetchError,
    SedeNavigationError,
)
from ._parse import parse_expediente_detail, parse_resumen_tree
from ._schema import Expediente, JustificanteRef, SedeCapture

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_RESUMEN_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"

DEFAULT_EXPAND_TIMEOUT_MS: int = 10_000


def _get_expand_timeout_ms() -> int:
    return load_settings().aeat_browser_form_interaction_timeout_ms


def _get_navigation_timeout_ms() -> int:
    return load_settings().aeat_browser_navigation_timeout_ms


@asynccontextmanager
async def _open_browser_page(
    session: AeatSession,
    settings: Settings,
) -> AsyncIterator[tuple[Any, Any]]:
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
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            yield context, page
        finally:
            try:
                await context.close()
            except Exception as exc:
                log.debug("sede walker: context.close suppressed: %s", exc, exc_info=True)
    finally:
        await browser_session.close()


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
            :func:`aeat.core.config.load_settings`.

    Returns:
        Tuple of :class:`Expediente` records, ordered as AEAT renders
        them (most recent first in every captured case so far).

    Raises:
        SedeNavigationError: If ``goto`` or a required expansion fails.
    """
    settings = settings or Settings()
    async with _open_browser_page(session, settings) as (_context, page):
        try:
            await page.goto(_RESUMEN_URL, wait_until=_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto {_RESUMEN_URL!r} failed: {exc}") from exc

        await _expand_matching_branches(page, modelo=modelo)
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
            await page.goto(_RESUMEN_URL, wait_until=_WAIT_DOMCONTENTLOADED)
        except Exception as _exc:
            log.debug("sede walker: warm-up goto %s suppressed: %s", _RESUMEN_URL, _exc, exc_info=True)
        try:
            await page.goto(detail_url, wait_until=_WAIT_DOMCONTENTLOADED)
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
            await page.goto(_RESUMEN_URL, wait_until=_WAIT_DOMCONTENTLOADED)
        except Exception as _exc:
            log.debug("sede walker: warm-up goto %s suppressed: %s", _RESUMEN_URL, _exc, exc_info=True)
        try:
            await page.goto(detail_url, wait_until=_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(f"goto expediente detail {detail_url!r} failed: {exc}") from exc
        detail_html = await page.content()
        ref = parse_expediente_detail(
            detail_html,
            expediente_id=expediente.expediente_id,
            base_url=_SEDE_BASE,
        )

        pdf_response = await context.request.get(str(ref.pdf_url))
        if not (200 <= pdf_response.status < 300):
            raise JustificanteFetchError(f"pdf fetch for CSV={ref.csv!r} returned HTTP {pdf_response.status}")
        content_type = pdf_response.headers.get("content-type", "")
        body = await pdf_response.body()
        if not body:
            raise JustificanteFetchError(f"empty PDF body for CSV={ref.csv!r}")
        if _PDF_MIME_TYPE not in content_type.lower():
            raise JustificanteFetchError(f"unexpected content-type {content_type!r} for CSV={ref.csv!r}")
        sha256 = hashlib.sha256(body).hexdigest()
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

    content = getattr(page, "content", None)
    wait_for_load_state = getattr(page, "wait_for_load_state", None)
    if content is None:
        raise SedeNavigationError("page does not expose content(); cannot snapshot HTML")
    last_exc: BaseException | None = None
    for _ in range(8):
        if wait_for_load_state is not None:
            try:
                await wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=_TIMEOUT_SHORT_MS)
            except PlaywrightError as wait_exc:
                log.debug(
                    "sede walker: wait_for_load_state did not settle; proceeding to content() anyway (%s)", wait_exc,
                )
        try:
            return await content()
        except PlaywrightError as exc:
            last_exc = exc
            await _asyncio.sleep(0.5)
    raise SedeNavigationError(f"failed to snapshot page HTML after 8 attempts: {last_exc!r}")


async def _expand_matching_branches(page: object, *, modelo: str | None) -> None:
    """Click tree anchors until the relevant subtree is fully expanded.

    Two strategies, selected by ``modelo``:

    * When ``modelo`` is set (e.g. ``"100"``), target the leaf
      ``mostrarListado`` anchor whose visible text contains
      ``Modelo <N>``. Clicking that anchor lazy-loads the full
      expediente subtree beneath it in one AJAX round-trip.
    * When ``modelo`` is ``None``, click every ``mostrarListado``
      anchor in document order — this expands the whole corpus. The
      JS dedup guards against clicking a category header twice.
    """
    import asyncio as _asyncio

    evaluate = getattr(page, "evaluate", None)
    if evaluate is None:
        return

    if modelo is not None:
        clicked = await evaluate(
            """
            (modelo) => {
                const wanted = 'Modelo ' + modelo;
                const anchor = Array.from(document.querySelectorAll('a'))
                    .find(a =>
                        (a.textContent || '').includes(wanted) &&
                        ((a.getAttribute('onclick') || '').includes('mostrarListado'))
                    );
                if (!anchor) return false;
                anchor.click();
                return true;
            }
            """,
            modelo,
        )
        if not clicked:
            log.debug("_expand_matching_branches: no mostrarListado anchor found for modelo=%s", modelo)
            return
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
    "capture_justificante",
    "find_expediente",
    "resolve_justificante_ref",
    "walk_expedientes_tree",
]
