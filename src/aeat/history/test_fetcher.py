"""Unit tests for :class:`HistoryFetcher`.

Uses real Protocol-conforming Python classes for the
:class:`ExpedienteSource` and :class:`FilingDetailFetcher`
collaborators — **no** ``unittest.mock``, **no** patches, **no**
fakes, per the project testing charter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ..config import Settings
from ..status import Expediente
from . import (
    FilingHistory,
    HistoryFetcher,
    HistoryModelo,
    HistoryUnsupportedModeloError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-pages" / "filing-history"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


class _FakeExpedienteSource:
    """Real Protocol-conforming source backed by a caller-supplied tuple."""

    def __init__(self, rows: tuple[Expediente, ...]) -> None:
        self._rows = rows
        self.calls: list[tuple[str | None, str | None]] = []

    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
    ) -> tuple[Expediente, ...]:
        self.calls.append((modelo, period))
        matched = [
            row
            for row in self._rows
            if (modelo is None or row.modelo == modelo) and (period is None or row.period == period)
        ]
        return tuple(matched)


class _FakeDetailFetcher:
    """Real Protocol-conforming detail fetcher keyed by expediente_id."""

    def __init__(self, pages: dict[str, tuple[str, AnyHttpUrl]]) -> None:
        self._pages = pages
        self.calls: list[str] = []

    async def fetch_detail_html(
        self,
        expediente: Expediente,
    ) -> tuple[str, AnyHttpUrl]:
        self.calls.append(expediente.expediente_id)
        html, url = self._pages[expediente.expediente_id]
        return html, url


def _expediente_130() -> Expediente:
    return Expediente(
        expediente_id="2025X1234567L0001",
        modelo="130",
        period="2025-1T",
        status="Presentada",
        presented_at=datetime(2025, 4, 15, 10, 22, 31, tzinfo=UTC),
        csv="ABCD1234EFGH5678",
        justificante_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/justificante/0001"),
        source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/mis-expedientes"),
        fetched_at=datetime(2025, 4, 15, 10, 25, 0, tzinfo=UTC),
    )


def _expediente_303() -> Expediente:
    return Expediente(
        expediente_id="2025X1234567L0002",
        modelo="303",
        period="2025-1T",
        status="Presentada",
        presented_at=datetime(2025, 4, 20, 9, 0, 0, tzinfo=UTC),
        csv="ZZZZ9999YYYY0000",
        justificante_url=None,
        source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/mis-expedientes"),
        fetched_at=datetime(2025, 4, 20, 9, 5, 0, tzinfo=UTC),
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(aeat_filing_history_dir=tmp_path / "filing-history")


def _detail_pages() -> dict[str, tuple[str, AnyHttpUrl]]:
    return {
        "2025X1234567L0001": (
            _load_fixture("modelo_130_detail.html"),
            AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/detail/130/0001"),
        ),
        "2025X1234567L0002": (
            _load_fixture("modelo_303_detail.html"),
            AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/detail/303/0002"),
        ),
    }


class TestHistoryFetcher:
    @pytest.mark.asyncio
    async def test_empty_history_on_first_call(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(),))
        detail = _FakeDetailFetcher(_detail_pages())
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=_settings(tmp_path),
        )
        records = await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        assert len(records) == 1
        assert records[0].metadata.modelo == "130"
        assert records[0].calculations.casillas["01"] == "12.345,67"

    @pytest.mark.asyncio
    async def test_second_call_hits_cache(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(),))
        detail = _FakeDetailFetcher(_detail_pages())
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=_settings(tmp_path),
        )
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        assert detail.calls == ["2025X1234567L0001"]
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        # Second call: source list still runs but detail fetcher
        # should not re-hit because the record is fresh.
        assert detail.calls == ["2025X1234567L0001"]

    @pytest.mark.asyncio
    async def test_use_cache_false_forces_refetch(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(),))
        detail = _FakeDetailFetcher(_detail_pages())
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=_settings(tmp_path),
        )
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130, use_cache=False)
        assert detail.calls == ["2025X1234567L0001", "2025X1234567L0001"]

    @pytest.mark.asyncio
    async def test_unsupported_modelo_raises(self, tmp_path: Path) -> None:
        # `coerce_modelo` rejects before the source is consulted, so we
        # pass empty collaborators here — the error short-circuits the
        # whole pipeline.
        fetcher = HistoryFetcher(
            expediente_source=_FakeExpedienteSource(()),
            detail_fetcher=_FakeDetailFetcher({}),
            settings=_settings(tmp_path),
        )
        with pytest.raises(HistoryUnsupportedModeloError):
            await fetcher.fetch_for_modelo("111")

    @pytest.mark.asyncio
    async def test_archive_html_when_enabled(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(),))
        detail = _FakeDetailFetcher(_detail_pages())
        settings = Settings(
            aeat_filing_history_dir=tmp_path / "filing-history",
            aeat_filing_history_archive_html=True,
        )
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=settings,
        )
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        archive_path = settings.aeat_filing_history_dir / "pages" / "2025X1234567L0001.html"
        assert archive_path.exists()
        assert "<table" in archive_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_archive_html_disabled_by_default(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(),))
        detail = _FakeDetailFetcher(_detail_pages())
        settings = _settings(tmp_path)
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=settings,
        )
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        pages_dir = settings.aeat_filing_history_dir / "pages"
        assert not pages_dir.exists()

    @pytest.mark.asyncio
    async def test_persistence_round_trip(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource((_expediente_130(), _expediente_303()))
        detail = _FakeDetailFetcher(_detail_pages())
        settings = _settings(tmp_path)
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=settings,
        )
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_130)
        await fetcher.fetch_for_modelo(HistoryModelo.MODELO_303)
        history_file = settings.aeat_filing_history_dir / "history.json"
        assert history_file.exists()
        reloaded = FilingHistory.model_validate_json(history_file.read_text(encoding="utf-8"))
        assert set(reloaded.entries.keys()) == {
            "2025X1234567L0001",
            "2025X1234567L0002",
        }

    @pytest.mark.asyncio
    async def test_fetch_filed_modelo_single_row(self, tmp_path: Path) -> None:
        source = _FakeExpedienteSource(())
        detail = _FakeDetailFetcher(_detail_pages())
        fetcher = HistoryFetcher(
            expediente_source=source,
            detail_fetcher=detail,
            settings=_settings(tmp_path),
        )
        record = await fetcher.fetch_filed_modelo(_expediente_303())
        assert record.metadata.modelo == "303"
        assert record.metadata.expediente_id == "2025X1234567L0002"
