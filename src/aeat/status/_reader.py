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

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from pydantic import AnyHttpUrl, TypeAdapter

from aeat.config import Settings
from aeat.logging import get_logger

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

    Example:
        ```python
        reader = StatusReader(
            browser_session=session,
            cert_backend=cert,
            cache=StatusCache(settings.aeat_status_cache_dir, settings.aeat_status_cache_ttl_s),
            settings=settings,
            tax_id="X1234567L",
        )
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

    async def _ensure_ready(self) -> Page:
        """Lazily create the authenticated browser context and page.

        The certificate backend is preloaded exactly once, before the
        first navigation. Subsequent calls reuse the same page.

        Raises:
            StatusAuthError: If the certificate preload or context
                creation fails.
        """
        if self._page is not None:
            return self._page
        try:
            context = await self._browser_session.create_context()
            await self._cert_backend.preload_into_browser_context(context)
            page = await context.new_page()
        except Exception as exc:  # pragma: no cover - live path
            raise StatusAuthError(f"failed to prepare authenticated context: {exc}") from exc
        self._context = context
        self._page = page
        return page

    async def _fetch_html(self, path: str) -> tuple[str, AnyHttpUrl]:
        """Navigate to ``base_url + path`` and return ``(html, url)``.

        Raises:
            StatusAuthError: If navigation fails.
        """
        page = await self._ensure_ready()
        url = self._settings.aeat_base_url.rstrip("/") + path
        try:
            await page.goto(url)
            html = await page.content()
        except Exception as exc:  # pragma: no cover - live path
            raise StatusAuthError(f"failed to navigate to {url}: {exc}") from exc
        return html, _URL_ADAPTER.validate_python(url)

    async def close(self) -> None:
        """Close the underlying browser context, if any.

        Safe to call multiple times.
        """
        if self._context is not None:
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
        surface = AeatStatusKind.EXPEDIENTE
        key = make_cache_key(
            tax_id=self._tax_id,
            surface=surface,
            params={"since": since},
        )
        if use_cache:
            cached = self._cache.get_tuple(surface=surface, key=key, model=Expediente)
            if cached is not None:
                logger.info("status cache hit: expedientes (%d row(s))", len(cached))
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
        raise StatusReaderError("calendario surface not yet implemented (#43 follow-up)")
