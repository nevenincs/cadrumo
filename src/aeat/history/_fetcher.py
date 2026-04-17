"""Composition layer that fetches, parses, and persists filed modelos.

:class:`HistoryFetcher` wraps an :class:`ExpedienteSource` Protocol and
a :class:`FilingDetailFetcher` Protocol, running every fetched detail
page through the modelo-specific parser registry and persisting the
result to a single on-disk :class:`FilingHistory` JSON file.

The fetcher is **read-only** against AEAT — it never POSTs, never
submits a form, and never mutates remote state. See
[[2026-04-16-aeat-history-fetch-adr]] decision D1. Every navigation
delegated to the :class:`FilingDetailFetcher` implementation is a
plain ``page.goto(url, wait_until="domcontentloaded")``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import Settings
from ..logging import get_logger
from ..status import Expediente
from ._errors import HistoryFetchError
from ._models import FiledModelo, FilingHistory, HistoryModelo
from ._parsers import coerce_modelo, parse_filing_detail
from ._protocols import ExpedienteSource, FilingDetailFetcher

logger = get_logger(__name__)

_HISTORY_FILENAME = "history.json"
_PAGES_DIRNAME = "pages"


class HistoryFetcher:
    """Compose an :class:`ExpedienteSource` + :class:`FilingDetailFetcher`.

    Attributes:
        expediente_source: The upstream source of
            :class:`aeat.status.Expediente` rows.
        detail_fetcher: The per-filing detail-page fetcher.
        settings: The resolved :class:`aeat.config.Settings`.
        history_file: Path to the persisted :class:`FilingHistory`
            JSON file.
    """

    def __init__(
        self,
        *,
        expediente_source: ExpedienteSource,
        detail_fetcher: FilingDetailFetcher,
        settings: Settings,
        history_file: Path | None = None,
    ) -> None:
        """Construct a filing-history fetcher.

        Args:
            expediente_source: Any :class:`ExpedienteSource`-
                conformant object.
            detail_fetcher: Any :class:`FilingDetailFetcher`-
                conformant object.
            settings: Resolved :class:`aeat.config.Settings`.
            history_file: Override path for the persisted history
                file. Defaults to
                ``settings.aeat_filing_history_dir / "history.json"``.
        """
        self.expediente_source = expediente_source
        self.detail_fetcher = detail_fetcher
        self.settings = settings
        self.history_file = (
            history_file if history_file is not None else settings.aeat_filing_history_dir / _HISTORY_FILENAME
        )

    def load_history(self) -> FilingHistory:
        """Load the persisted :class:`FilingHistory`, or return an empty one.

        Raises:
            HistoryFetchError: If the file exists but cannot be parsed.
        """
        if not self.history_file.exists():
            return FilingHistory()
        try:
            return FilingHistory.model_validate_json(self.history_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HistoryFetchError(f"could not load filing history from {self.history_file}: {exc}") from exc

    def save_history(self, history: FilingHistory) -> None:
        """Persist ``history`` to :attr:`history_file`.

        Raises:
            HistoryFetchError: If the file or its parent directory
                cannot be written (permission, disk-full, etc.).
        """
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(
                history.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise HistoryFetchError(f"could not persist filing history to {self.history_file}: {exc}") from exc

    def _archive_html_if_enabled(self, expediente_id: str, raw_html: str) -> None:
        """Write the fetched detail-page HTML to the archive if configured.

        Controlled by :attr:`Settings.aeat_filing_history_archive_html`.
        When false (default), this is a no-op. When true, writes
        ``{aeat_filing_history_dir}/pages/{expediente_id}.html`` so
        the raw HTML is available for offline debugging without
        re-hitting AEAT.

        Raises:
            HistoryFetchError: If archiving is enabled but the write
                fails.
        """
        if not self.settings.aeat_filing_history_archive_html:
            return
        page_path = self.settings.aeat_filing_history_dir / _PAGES_DIRNAME / f"{expediente_id}.html"
        try:
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(raw_html, encoding="utf-8")
        except OSError as exc:
            raise HistoryFetchError(f"could not archive detail-page HTML to {page_path}: {exc}") from exc

    def _is_fresh(self, record: FiledModelo) -> bool:
        """Return ``True`` if ``record`` is within the cache TTL."""
        ttl = timedelta(seconds=self.settings.aeat_filing_history_cache_ttl_s)
        return datetime.now(UTC) - record.metadata.fetched_at < ttl

    async def fetch_filed_modelo(
        self,
        expediente: Expediente,
        *,
        use_cache: bool = True,
    ) -> FiledModelo:
        """Fetch and parse the detail page for a single ``expediente``.

        Args:
            expediente: The :class:`aeat.status.Expediente` row to
                expand into a :class:`FiledModelo`.
            use_cache: Serve from the persisted history if the record
                is within the configured TTL. Pass ``False`` to force
                a fresh detail-page fetch.

        Returns:
            The :class:`FiledModelo` for ``expediente``.

        Raises:
            HistoryUnsupportedModeloError: If ``expediente.modelo``
                has no registered parser.
            HistoryFetchError: If the detail fetcher cannot retrieve
                the page.
            HistoryParseError: If the parser cannot interpret the
                detail page.
        """
        history = self.load_history()
        if use_cache:
            existing = history.get(expediente.expediente_id)
            if existing is not None and self._is_fresh(existing):
                logger.debug(
                    "filing-history cache hit: %s",
                    expediente.expediente_id,
                )
                return existing

        modelo_key: HistoryModelo = coerce_modelo(expediente.modelo)
        try:
            raw_html, detail_url = await self.detail_fetcher.fetch_detail_html(expediente)
        except Exception as exc:
            raise HistoryFetchError(
                f"detail fetcher failed for expediente {expediente.expediente_id!r}: {exc}"
            ) from exc

        fetched_at = datetime.now(UTC)
        record = parse_filing_detail(
            modelo_key,
            raw_html,
            expediente=expediente,
            source_url=detail_url,
            fetched_at=fetched_at,
        )
        history.upsert(record)
        self.save_history(history)
        self._archive_html_if_enabled(expediente.expediente_id, raw_html)
        return record

    async def fetch_for_modelo(
        self,
        modelo: HistoryModelo | str,
        *,
        period: str | None = None,
        use_cache: bool = True,
    ) -> tuple[FiledModelo, ...]:
        """List expedientes for ``modelo`` and expand every one.

        Args:
            modelo: The :class:`HistoryModelo` or raw modelo string.
                Unsupported modelos raise
                :class:`HistoryUnsupportedModeloError`.
            period: Optional period filter (``"2025-1T"``, ``"2025"``)
                passed straight to the :class:`ExpedienteSource`.
            use_cache: Per-record cache honouring per
                :meth:`fetch_filed_modelo`.

        Returns:
            A tuple of :class:`FiledModelo`, one per listed
            expediente, in the order :class:`ExpedienteSource`
            returns them.

        Raises:
            HistoryUnsupportedModeloError: If ``modelo`` has no parser.
            HistoryFetchError: If the list or any detail fetch fails.
        """
        modelo_key = coerce_modelo(modelo)
        try:
            expedientes = await self.expediente_source.list_expedientes(
                modelo=modelo_key.value,
                period=period,
            )
        except Exception as exc:
            raise HistoryFetchError(f"expediente source failed for modelo {modelo_key.value!r}: {exc}") from exc

        records: list[FiledModelo] = []
        for expediente in expedientes:
            record = await self.fetch_filed_modelo(
                expediente,
                use_cache=use_cache,
            )
            records.append(record)
        return tuple(records)
