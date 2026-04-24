"""Test-only helpers that parse HTML fixtures into typed remote records.

The helpers here wire the public :class:`aeat.history.HistoryFetcher`
against Protocol-conforming Python classes that serve pre-captured
HTML fixtures from ``tests/fixtures/remote_filings/``. The result is
the same :class:`aeat.history.FiledModelo` a live filing-detail fetch
would produce, which the :mod:`aeat.remote.filings._adapters` layer
then projects into a :class:`aeat.remote.RemoteFiling`.

No ``unittest.mock`` / ``Mock`` / ``patch`` is ever used; every
collaborator is a real Protocol-conforming class. The module is
test-only — nothing under it is part of the public :mod:`aeat.remote`
API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import AnyHttpUrl

from ...config import Settings
from ...history import FiledModelo, HistoryFetcher
from ...status import Expediente
from .._schema import RemoteFiling
from ._adapters import remote_filing_from_history

_FIXTURE_ROOT: Path = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "remote_filings"


class _FixtureFilingDetailFetcher:
    """Protocol-conforming ``FilingDetailFetcher`` serving an HTML fixture."""

    def __init__(self, html: str, detail_url: AnyHttpUrl) -> None:
        self._html = html
        self._detail_url = detail_url

    async def fetch_detail_html(self, expediente: Expediente) -> tuple[str, AnyHttpUrl]:
        """Return the pre-loaded HTML fixture for ``expediente``."""
        del expediente
        return self._html, self._detail_url


class _FixtureExpedienteSource:
    """Protocol-conforming ``ExpedienteSource`` yielding a single fixture row."""

    def __init__(self, expediente: Expediente) -> None:
        self._expediente = expediente

    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        use_cache: bool = True,
    ) -> tuple[Expediente, ...]:
        """Return the single fixture expediente, filtered by ``modelo``/``period``."""
        del use_cache
        row = self._expediente
        if modelo is not None and row.modelo != modelo:
            return ()
        if period is not None and row.period != period:
            return ()
        return (row,)


def load_fixture(name: str) -> str:
    """Return the raw HTML for the fixture named ``name``.

    Args:
        name: The file name (with extension) of a fixture under
            ``tests/fixtures/remote_filings/``.

    Returns:
        The UTF-8 decoded HTML body.
    """
    return (_FIXTURE_ROOT / name).read_text(encoding="utf-8")


def make_expediente(
    *,
    modelo: str,
    period: str,
    expediente_id: str,
    status: str,
    presented_at: datetime,
) -> Expediente:
    """Build a minimal :class:`aeat.history.Expediente` for fixture tests."""
    return Expediente(
        expediente_id=expediente_id,
        modelo=modelo,
        period=period,
        status=status,
        presented_at=presented_at,
        csv="TESTCSV0000000001",
        justificante_url=None,
        source_page_url=AnyHttpUrl("https://sede.example.test/mis-expedientes"),
        fetched_at=presented_at,
    )


async def parse_fixture_to_remote_filing(
    *,
    fixture_name: str,
    expediente: Expediente,
    tmp_path: Path,
) -> tuple[FiledModelo, RemoteFiling]:
    """Run an HTML fixture through the public history reader and project to remote.

    Args:
        fixture_name: File name under ``tests/fixtures/remote_filings/``.
        expediente: The :class:`aeat.history.Expediente` the fixture is
            deemed to describe.
        tmp_path: Per-test temporary directory; used as the on-disk
            history cache root so unit tests never write outside the
            sandbox.

    Returns:
        A ``(filed_modelo, remote_filing)`` tuple. The first element
        is the raw history output (useful for assertions against the
        history-layer surface); the second is the strict typed
        projection the remote fetchers consume.
    """
    html = load_fixture(fixture_name)
    detail_url = AnyHttpUrl(f"https://sede.example.test/wlpl/detail/{expediente.modelo}/{expediente.expediente_id}")
    detail_fetcher = _FixtureFilingDetailFetcher(html, detail_url)
    expediente_source = _FixtureExpedienteSource(expediente)
    settings = Settings(
        aeat_filing_history_dir=tmp_path / "filing-history",
        aeat_filing_history_archive_html=False,
    )
    history_fetcher = HistoryFetcher(
        expediente_source=expediente_source,
        detail_fetcher=detail_fetcher,
        settings=settings,
    )
    filed = await history_fetcher.fetch_filed_modelo(expediente, use_cache=False)
    remote = remote_filing_from_history(filed)
    return filed, remote


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Return a UTC :class:`datetime` for the supplied components."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


__all__ = [
    "load_fixture",
    "make_expediente",
    "parse_fixture_to_remote_filing",
    "utc",
]
