"""The :class:`StatusReader` driver for the AEAT status surfaces.

The reader composes :class:`aeat.browser.BrowserSession` (already on
main via #16) with a :class:`CertificateBackend` Protocol stub (the
concrete implementation lands in #8). The public API is async and
strictly read-only — the reader never submits forms and never
mutates AEAT state.

v1 ships a fully-wired ``fetch_expedientes`` path. The other
``fetch_*`` methods raise :class:`StatusReaderError` with a clear
"surface not yet implemented (#43 follow-up)" message until their
parsers land.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Self
from urllib.parse import quote, urljoin

from pydantic import AnyHttpUrl, TypeAdapter

from ..config import Settings
from ..logging import get_logger
from ._cache import StatusCache
from ._cache_key import make_cache_key
from ._errors import StatusAuthError, StatusReaderError
from ._models import (
    AeatStatusKind,
    BorradorIrpf,
    CalendarioEntry,
    DatosFiscales,
    Devolucion,
    Expediente,
    Notificacion,
)
from ._parsers import parse_expedientes
from ._protocols import BrowserSessionLike, CertificateBackend

if TYPE_CHECKING:  # pragma: no cover - type-only imports
    from playwright.async_api import BrowserContext, Page

    from ..history import FiledModelo

logger = get_logger(__name__)

_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)

_EXPEDIENTES_PATH = "/wlpl/TC-UTIL/Expediente?COPT=Y"

# Default template when Settings.aeat_status_detail_url_template is
# blank (defensive — Settings default populates a valid template but
# explicit empty-string overrides should not crash the reader).
_EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT = "/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"


class StatusReader:
    """Read-only driver for the authenticated AEAT status surfaces.

    Ownership contract:
        The caller owns the ``browser_session`` and the
        ``cert_backend``; :meth:`close` only releases the
        :class:`BrowserContext` the reader itself created. The
        underlying Playwright runtime and certificate backend must
        be torn down by the caller.

    Example:
        ```python
        async with StatusReader(
            browser_session=session,
            cert_backend=cert,
            cache=StatusCache(settings.aeat_status_cache_dir, settings.aeat_status_cache_ttl_s),
            settings=settings,
            tax_id="X1234567L",
        ) as reader:
            expedientes = await reader.fetch_expedientes()
        ```
    """

    def __init__(
        self,
        *,
        browser_session: BrowserSessionLike,
        cert_backend: CertificateBackend,
        cache: StatusCache,
        settings: Settings,
        tax_id: str,
    ) -> None:
        """Initialise the reader.

        Args:
            browser_session: A :class:`BrowserSessionLike` object —
                typically a real :class:`aeat.browser.BrowserSession`,
                but any Protocol-conforming class works.
            cert_backend: A :class:`CertificateBackend` implementation
                (real or a Protocol-conforming test double).
            cache: The short-lived status cache.
            settings: The resolved :class:`aeat.config.Settings`.
            tax_id: Spanish tax identifier of the authenticated user.
        """
        self._browser_session = browser_session
        self._cert_backend = cert_backend
        self._cache = cache
        self._settings = settings
        self._tax_id = tax_id
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._tracing_active = False
        # Lazy lock: allocated on first `_ensure_ready` call so the
        # reader can be constructed outside a running event loop
        # without binding to one prematurely.
        self._ready_lock: asyncio.Lock | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        await self.close()

    async def _ensure_ready(self) -> Page:
        """Lazily create the authenticated browser context and page.

        The certificate backend is preloaded exactly once, before the
        first navigation. Subsequent calls reuse the same page.
        Concurrent callers are serialised by :class:`asyncio.Lock` so
        two in-flight fetches cannot spawn duplicate contexts and
        leak the loser.

        Raises:
            StatusAuthError: If the certificate preload or context
                creation fails.
        """
        if self._page is not None:
            return self._page
        if self._ready_lock is None:
            self._ready_lock = asyncio.Lock()
        async with self._ready_lock:
            # Re-check under the lock: another task may have raced
            # ahead and fully initialised the page while we waited.
            if self._page is not None:
                return self._page
            context: BrowserContext | None = None
            try:
                context = await self._browser_session.create_context()
                # Assign first so close() can reach a leaked context
                # if the cert preload or new_page call fails halfway.
                self._context = context
                await self._cert_backend.preload_into_browser_context(context)
                await self._maybe_start_tracing(context)
                page = await context.new_page()
            except Exception as exc:  # pragma: no cover - live path
                if context is not None:
                    try:
                        await context.close()
                    except Exception:  # pragma: no cover - defensive
                        logger.exception("failed to close leaked browser context")
                self._context = None
                raise StatusAuthError(f"failed to prepare authenticated context: {exc}") from exc
            self._page = page
            return page

    async def _fetch_html(self, path: str) -> tuple[str, AnyHttpUrl]:
        """Navigate to ``base_url + path`` and return ``(html, url)``.

        Raises:
            StatusAuthError: If navigation fails.
        """
        page = await self._ensure_ready()
        url = urljoin(self._settings.aeat_base_url, path)
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            if response is not None and response.status >= 400:
                raise StatusAuthError(f"AEAT returned HTTP {response.status} for {url}")
            html = await page.content()
        except StatusAuthError:
            raise
        except Exception as exc:  # pragma: no cover - live path
            raise StatusAuthError(f"failed to navigate to {url}: {exc}") from exc
        return html, _URL_ADAPTER.validate_python(url)

    async def _maybe_start_tracing(self, context: BrowserContext) -> None:
        """Start Playwright tracing when a trace dir is configured.

        The trace dir defaults to ``<repo>/var/browser-traces``;
        operators opt in by *creating* that directory. When the
        directory does not exist we treat tracing as disabled —
        otherwise every unit test would accidentally start a
        tracing session.
        """
        trace_dir = self._settings.aeat_status_browser_trace_dir
        if not trace_dir.is_dir():
            return
        try:
            await context.tracing.start(screenshots=True, snapshots=True)
        except Exception:  # pragma: no cover - live path
            logger.exception("failed to start playwright tracing")
            return
        self._tracing_active = True

    async def close(self) -> None:
        """Close the :class:`BrowserContext` the reader created, if any.

        Ownership contract: the caller still owns the
        ``browser_session`` and ``cert_backend`` and must tear down
        the Playwright runtime and certificate backend separately.
        Safe to call multiple times.
        """
        if self._context is not None:
            if self._tracing_active:
                trace_path = (
                    self._settings.aeat_status_browser_trace_dir
                    / f"status-reader-{int(datetime.now(UTC).timestamp())}.zip"
                )
                try:
                    await self._context.tracing.stop(path=trace_path)
                except Exception:  # pragma: no cover - live path
                    logger.exception("failed to stop playwright tracing")
                self._tracing_active = False
            await self._context.close()
            self._context = None
            self._page = None

    async def fetch_expedientes(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[Expediente, ...]:
        """Fetch the user's filing history from *Mis expedientes*.

        Args:
            since: If given, drop every row with ``presented_at`` strictly
                earlier than this date. Applied post-parse.
            use_cache: When True (default), honour the short-lived
                file cache. Pass False to force a fresh fetch.

        Returns:
            A tuple of :class:`Expediente` records, ordered as AEAT
            returns them.

        Raises:
            StatusAuthError: If the authenticated context cannot be
                prepared.
            StatusParseError: If the AEAT page cannot be parsed.
        """
        # `since` is a post-parse filter — omit it from the cache key
        # so back-to-back invocations with different --since values
        # still hit the cached page.
        surface = AeatStatusKind.EXPEDIENTE
        key = make_cache_key(
            tax_id=self._tax_id,
            surface=surface,
            base_url=self._settings.aeat_base_url,
        )
        if use_cache:
            cached = self._cache.get_tuple(surface=surface, key=key, model=Expediente)
            if cached is not None:
                logger.debug("status cache hit: expedientes (%d row(s))", len(cached))
                return self._filter_since(cached, since)

        html, url = await self._fetch_html(_EXPEDIENTES_PATH)
        fetched_at = datetime.now(UTC)
        records = parse_expedientes(html, source_url=url, fetched_at=fetched_at)
        self._cache.put_tuple(surface=surface, key=key, records=records)
        return self._filter_since(records, since)

    @staticmethod
    def _filter_since(
        records: tuple[Expediente, ...],
        since: date | None,
    ) -> tuple[Expediente, ...]:
        if since is None:
            return records
        return tuple(r for r in records if r.presented_at.date() >= since)

    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
    ) -> tuple[Expediente, ...]:
        """Return every expediente matching ``modelo`` / ``period``.

        Structurally conforms to the
        :class:`aeat.history.ExpedienteSource` Protocol, so a
        :class:`StatusReader` can be passed directly as the
        ``expediente_source`` of :class:`aeat.history.HistoryFetcher`.
        ``None`` on either filter means "do not filter on this field".

        The ``use_cache`` keyword is a superset of the Protocol (which
        does not declare it). Callers conforming to the Protocol need
        not pass it; callers that want a fresh fetch can override.

        Args:
            modelo: Filter by modelo code (``"303"``, ``"130"``, …).
                ``None`` disables the filter.
            period: Filter by period string (``"2025-1T"``, ``"2025"``).
                ``None`` disables the filter.
            use_cache: When True (default), honour the short-lived
                file cache.

        Returns:
            A tuple of matching :class:`Expediente` records, ordered
            as AEAT returns them.

        Raises:
            StatusAuthError: If the authenticated context cannot be
                prepared.
            StatusParseError: If the listing page cannot be parsed.
        """
        records = await self.fetch_expedientes(use_cache=use_cache)
        if modelo is None and period is None:
            return records
        return tuple(
            r for r in records if (modelo is None or r.modelo == modelo) and (period is None or r.period == period)
        )

    def _build_detail_url(self, expediente: Expediente) -> AnyHttpUrl:
        """Resolve the detail-page URL for ``expediente``.

        Resolution order (ADR D6):

        1. ``expediente.detail_url`` — parser-captured anchor, the
           authoritative source when AEAT renders one.
        2. Templated fallback — ``urljoin(aeat_base_url,
           template.format(expediente_id=quote(id, safe="")))``.

        ``justificante_url`` is never used as a detail-URL fallback:
        it points at a signed PDF receipt that the history parsers
        cannot consume.
        """
        if expediente.detail_url is not None:
            return expediente.detail_url
        template = self._settings.aeat_status_detail_url_template or _EXPEDIENTE_DETAIL_PATH_TEMPLATE_DEFAULT
        # Settings.field_validator enforces the presence of
        # ``{expediente_id}``; we quote so special characters in the
        # expediente id cannot break the URL shape.
        path = template.format(expediente_id=quote(expediente.expediente_id, safe=""))
        absolute = urljoin(self._settings.aeat_base_url, path)
        return _URL_ADAPTER.validate_python(absolute)

    async def fetch_detail_html(
        self,
        expediente: Expediente,
    ) -> tuple[str, AnyHttpUrl]:
        """Return ``(raw_html, resolved_url)`` for an expediente's detail page.

        Structurally conforms to the
        :class:`aeat.history.FilingDetailFetcher` Protocol.
        Read-only: exactly one ``page.goto(..., wait_until="domcontentloaded")``
        followed by ``page.content()``. No form submission, no click.

        Raises:
            StatusReaderError: If the detail navigation fails, returns
                HTTP ≥ 400, or responds with an empty body. Message
                carries the ``expediente_id`` and the HTTP status when
                applicable.
            StatusParseError: If the resolved URL fails
                :class:`pydantic.AnyHttpUrl` validation.
        """
        page = await self._ensure_ready()
        url = self._build_detail_url(expediente)
        try:
            response = await page.goto(str(url), wait_until="domcontentloaded")
        except Exception as exc:  # pragma: no cover - live path
            raise StatusReaderError(
                f"detail navigation failed for expediente {expediente.expediente_id!r}: {exc}"
            ) from exc
        if response is not None and response.status >= 400:
            raise StatusReaderError(
                f"AEAT returned HTTP {response.status} for detail page of expediente {expediente.expediente_id!r}"
            )
        html = await page.content()
        if not html:
            raise StatusReaderError(f"AEAT returned empty detail page for expediente {expediente.expediente_id!r}")
        return html, url

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[FiledModelo, ...]:
        """Fetch every filed modelo matching ``(modelo, period)``.

        Lists expedientes filtered by ``(modelo, period)``, navigates
        to each expediente's detail page, parses the casilla→value
        mapping, and returns strict pydantic records. The method is
        the composition facade over :class:`aeat.history.HistoryFetcher`
        for the #227 amendment read surface (closes Kent audit
        wall 23).

        Args:
            modelo: Required modelo code (``"303"``, ``"130"``, …).
                Unsupported modelos raise
                :class:`aeat.history.HistoryUnsupportedModeloError`
                via the history parser registry.
            period: Required period string (``"2025-1T"``, ``"2025"``).
            use_cache: When True (default), honour the filing-history
                TTL cache (``AEAT_FILING_HISTORY_CACHE_TTL_S``).

        Returns:
            A tuple of :class:`aeat.history.FiledModelo`, one per
            matching expediente, ordered as AEAT returns them.

        Raises:
            StatusAuthError: If the authenticated context cannot be
                prepared (propagated from ``list_expedientes``).
            StatusParseError: If the listing page cannot be parsed or
                the resolved detail URL fails validation.
            StatusReaderError: If the detail navigation fails, returns
                HTTP ≥ 400, or responds with an empty body.
            aeat.history.HistoryFetchError: If either collaborator
                raises unexpectedly.
            aeat.history.HistoryParseError: If the modelo-specific
                parser cannot interpret the detail page.
            aeat.history.HistoryUnsupportedModeloError: If ``modelo``
                has no registered parser.
        """
        # Function-scoped import: forward-design guard against a
        # partial-init ImportError under future ``aeat.status.__init__``
        # reordering. Do NOT hoist to module top. See ADR D5.
        from ..history import HistoryFetcher

        fetcher = HistoryFetcher(
            expediente_source=self,
            detail_fetcher=self,
            settings=self._settings,
        )
        return await fetcher.fetch_for_modelo(modelo, period=period, use_cache=use_cache)

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[Notificacion, ...]:
        """Fetch *Mis notificaciones*. Not yet implemented (#43 follow-up).

        Raises:
            StatusReaderError: Always — this surface is a v1 stub.
        """
        del since, use_cache
        raise StatusReaderError("notificaciones surface not yet implemented (#43 follow-up)")

    async def fetch_devoluciones(
        self,
        *,
        year: int | None = None,
        use_cache: bool = True,
    ) -> tuple[Devolucion, ...]:
        """Fetch *Mis devoluciones*. Not yet implemented (#43 follow-up).

        Raises:
            StatusReaderError: Always — this surface is a v1 stub.
        """
        del year, use_cache
        raise StatusReaderError("devoluciones surface not yet implemented (#43 follow-up)")

    async def fetch_borrador_irpf(
        self,
        year: int,
        *,
        use_cache: bool = True,
    ) -> BorradorIrpf | None:
        """Fetch the IRPF draft state. Not yet implemented (#43 follow-up).

        Raises:
            StatusReaderError: Always — this surface is a v1 stub.
        """
        del year, use_cache
        raise StatusReaderError("borrador irpf surface not yet implemented (#43 follow-up)")

    async def fetch_datos_fiscales(
        self,
        year: int,
        *,
        use_cache: bool = True,
    ) -> DatosFiscales:
        """Fetch third-party tax data. Not yet implemented (#43 follow-up).

        Raises:
            StatusReaderError: Always — this surface is a v1 stub.
        """
        del year, use_cache
        raise StatusReaderError("datos fiscales surface not yet implemented (#43 follow-up)")

    async def fetch_calendario(
        self,
        *,
        use_cache: bool = True,
    ) -> tuple[CalendarioEntry, ...]:
        """Fetch the personalised calendar. Not yet implemented (#43 follow-up).

        Raises:
            StatusReaderError: Always — this surface is a v1 stub.
        """
        del use_cache
        raise StatusReaderError("calendario surface not yet implemented (#43 follow-up)")
