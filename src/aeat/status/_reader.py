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
from urllib.parse import urljoin

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

logger = get_logger(__name__)

_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)

_EXPEDIENTES_PATH = "/wlpl/TC-UTIL/Expediente?COPT=Y"


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
