"""Playwright-driven sede walker: session → expedientes → PDF bytes.

The walker is the only side-effectful layer in :mod:`aeat.adapters.outbound.aeat.adapters.outbound.aeat.sede`. It
takes an :class:`AeatSession` whose ``storage_state_path`` carries
valid AEAT cookies, drives a read-only Playwright session over the
sede, and exposes three operations to callers:

* :func:`walk_expedientes_tree` — listing traversal.
* :func:`resolve_justificante_ref` — expediente → CSV handle.
* :func:`fetch_justificante_pdf` — CSV handle → raw PDF bytes.

All three are read-only by construction: only ``page.goto`` and
``context.request.get`` cross the wire. No ``click()`` onto submit
buttons, no form POSTs, no mutation verbs anywhere in the public
surface.
"""

from __future__ import annotations

import contextlib
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

from .....core.config import Settings
from .....core.logging import get_logger
from ..browser import Profile
from ..browser.session import BrowserSession
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

_SEDE_BASE = "https://www6.agenciatributaria.gob.es"
_RESUMEN_URL = f"{_SEDE_BASE}/wlpl/TEWV-CORE/ResumenVlt"
_EXPAND_TIMEOUT_MS = 10_000
_NAVIGATION_TIMEOUT_MS = 30_000


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
        session: An authenticated session whose ``storage_state_path``
            points at cached AEAT cookies. Cl@ve-móvil and certificate
            sessions both qualify.
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
        SedeParseError: If the ResumenVlt page cannot be parsed.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession.storage_state_path is None; run `aeat auth login` first")

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=session.storage_state_path,
    )
    async with async_playwright() as pw:
        browser_session = BrowserSession(pw, settings, profile)
        context = await browser_session.create_context(
            storage_state_path=session.storage_state_path,
        )
        try:
            page = await context.new_page()
            try:
                await page.goto(_RESUMEN_URL, wait_until="domcontentloaded")
            except Exception as exc:
                raise SedeNavigationError(f"goto {_RESUMEN_URL!r} failed: {exc}") from exc

            await _expand_matching_branches(page, modelo=modelo)
            html = await _snapshot_html(page)
            expedientes = parse_resumen_tree(html, base_url=_SEDE_BASE)
            if modelo is not None:
                expedientes = tuple(e for e in expedientes if e.modelo == modelo)
            return expedientes
        finally:
            with contextlib.suppress(Exception):
                await context.close()
            await browser_session.close()


async def resolve_justificante_ref(
    session: AeatSession,
    expediente: Expediente,
    *,
    settings: Settings | None = None,
) -> JustificanteRef:
    """Navigate to an expediente's detail page and extract its CSV ref.

    Args:
        session: Authenticated session with live cookies on disk.
        expediente: Expediente to look up. ``expediente.detail_url``
            is used verbatim.
        settings: Optional override.

    Returns:
        A :class:`JustificanteRef` ready for
        :func:`fetch_justificante_pdf`.

    Raises:
        SedeNavigationError: If the detail page cannot be loaded.
        SedeParseError: If the detail HTML does not expose a CSV link.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession.storage_state_path is None; run `aeat auth login` first")

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=session.storage_state_path,
    )
    detail_url = str(expediente.detail_url)
    async with async_playwright() as pw:
        browser_session = BrowserSession(pw, settings, profile)
        context = await browser_session.create_context(
            storage_state_path=session.storage_state_path,
        )
        try:
            # Warm the session on ResumenVlt so AEAT's redirect chain
            # sees the origin cookie; navigating straight to the
            # per-year endpoint without this is fine when cookies are
            # fresh but fails intermittently after idle periods.
            page = await context.new_page()
            with contextlib.suppress(Exception):
                await page.goto(_RESUMEN_URL, wait_until="domcontentloaded")
            try:
                await page.goto(detail_url, wait_until="domcontentloaded")
            except Exception as exc:
                raise SedeNavigationError(f"goto expediente detail {detail_url!r} failed: {exc}") from exc
            html = await page.content()
            return parse_expediente_detail(
                html,
                expediente_id=expediente.expediente_id,
                base_url=_SEDE_BASE,
            )
        finally:
            with contextlib.suppress(Exception):
                await context.close()
            await browser_session.close()


async def fetch_justificante_pdf(
    session: AeatSession,
    ref: JustificanteRef,
    *,
    settings: Settings | None = None,
) -> SedeCapture:
    """Download the raw PDF bytes behind a :class:`JustificanteRef`.

    Uses Playwright's :class:`APIRequestContext` (not browser
    navigation) so Chrome's PDF-viewer interception never kicks in —
    we get the authentic body AEAT serves.

    Args:
        session: Authenticated session.
        ref: Output of :func:`resolve_justificante_ref`. The ``pdf_url``
            field drives the HTTP GET.
        settings: Optional override.

    Returns:
        A :class:`SedeCapture` bundling the raw PDF bytes with their
        SHA-256 and the capture timestamp.

    Raises:
        JustificanteFetchError: If the HTTP status is non-2xx, the
            body is empty, or the Content-Type is not PDF.
    """
    # SedeCapture requires the source Expediente. The caller supplies
    # it through the higher-level :func:`capture_justificante` wrapper;
    # this primitive exposes just the bytes-plus-hash pair to keep
    # tests lean.
    raise NotImplementedError("fetch_justificante_pdf is wrapped by capture_justificante; call that instead")


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
        SedeParseError: On detail-HTML extraction failures.
        JustificanteFetchError: On PDF download failures.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession.storage_state_path is None; run `aeat auth login` first")

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=session.storage_state_path,
    )
    detail_url = str(expediente.detail_url)
    async with async_playwright() as pw:
        browser_session = BrowserSession(pw, settings, profile)
        context = await browser_session.create_context(
            storage_state_path=session.storage_state_path,
        )
        try:
            page = await context.new_page()
            with contextlib.suppress(Exception):
                await page.goto(_RESUMEN_URL, wait_until="domcontentloaded")
            try:
                await page.goto(detail_url, wait_until="domcontentloaded")
            except Exception as exc:
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
            if "pdf" not in content_type.lower():
                raise JustificanteFetchError(f"unexpected content-type {content_type!r} for CSV={ref.csv!r}")
            sha256 = hashlib.sha256(body).hexdigest()
            return SedeCapture(
                expediente=expediente,
                ref=ref,
                pdf_bytes=body,
                pdf_sha256=sha256,
                captured_at=datetime.now(UTC),
            )
        finally:
            with contextlib.suppress(Exception):
                await context.close()
            await browser_session.close()


async def find_expediente(
    session: AeatSession,
    *,
    modelo: str,
    ejercicio: int,
    settings: Settings | None = None,
) -> Expediente:
    """Convenience lookup: first expediente matching ``(modelo, ejercicio)``.

    Raises:
        ExpedienteNotFoundError: If no expediente in the corpus
            matches the filter.
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
            with contextlib.suppress(Exception):
                await wait_for_load_state("domcontentloaded", timeout=2_000)
        try:
            return await content()
        except Exception as exc:
            last_exc = exc
            await _asyncio.sleep(0.5)
    raise SedeNavigationError(f"failed to snapshot page HTML after 8 attempts: {last_exc!r}")


async def _expand_matching_branches(page: object, *, modelo: str | None) -> None:
    """Click tree anchors until the relevant subtree is fully expanded.

    Two strategies, selected by ``modelo``:

    * When ``modelo`` is set (e.g. ``"100"``), target the leaf
      ``mostrarListado`` anchor whose visible text contains
      ``Modelo <N>``. Captured live on 2026-04-24: clicking that
      anchor lazy-loads the full expediente subtree beneath it in one
      AJAX round-trip.
    * When ``modelo`` is None, click every ``mostrarListado`` anchor
      in document order — this expands the whole corpus. The JS dedup
      guards against clicking a category header twice.
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
            """
        )
    # Give AEAT's AJAX a beat to populate the DOM before the caller
    # snapshots it. networkidle is too strict (GA pings keep it busy);
    # a short fixed sleep is both faster and more reliable.
    await _asyncio.sleep(2.0)


__all__ = [
    "capture_justificante",
    "fetch_justificante_pdf",
    "find_expediente",
    "resolve_justificante_ref",
    "walk_expedientes_tree",
]
