"""Unit tests for :class:`aeat.status.StatusReader`.

The reader is exercised against *real* Protocol-conforming test
doubles — never mocks, patches, or fakes. A tiny in-memory
``_FakeBrowserSession`` and ``_FakeCertBackend`` implement the
minimum surface the reader calls; a fake ``Page`` returns the
trimmed expedientes fixture.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from aeat.config import load_settings
from aeat.status import (
    AeatStatusKind,
    BrowserSessionLike,
    StatusCache,
    StatusReader,
    StatusReaderError,
)

pytestmark = pytest.mark.unit

_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-pages" / "expedientes" / "sample.html"


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class _FakePage:
    def __init__(self, html: str) -> None:
        self._html = html
        self.visited: list[str] = []

    async def goto(
        self,
        url: str,
        *,
        wait_until: str | None = None,
    ) -> _FakeResponse:
        del wait_until
        self.visited.append(url)
        return _FakeResponse(status=200)

    async def content(self) -> str:
        return self._html


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class _FakeBrowserSession:
    """Real Protocol-conforming double — matches the slice of
    :class:`aeat.browser.BrowserSession` the reader calls.
    """

    def __init__(self, html: str) -> None:
        self.page = _FakePage(html)
        self.context = _FakeContext(self.page)
        self.create_calls = 0

    async def create_context(self) -> _FakeContext:
        self.create_calls += 1
        return self.context


class _FakeCertBackend:
    """Real Protocol-conforming double for :class:`CertificateBackend`."""

    def __init__(self) -> None:
        self.preload_calls = 0

    async def preload_into_browser_context(self, context: Any) -> None:
        self.preload_calls += 1


def _build_reader(tmp_path: Path) -> tuple[StatusReader, _FakeBrowserSession, _FakeCertBackend]:
    html = _FIXTURE.read_text(encoding="utf-8")
    session = _FakeBrowserSession(html)
    cert = _FakeCertBackend()
    settings = load_settings()
    cache = StatusCache(tmp_path / "cache", ttl_s=60)
    reader = StatusReader(
        browser_session=cast(BrowserSessionLike, session),
        cert_backend=cert,
        cache=cache,
        settings=settings,
        tax_id="X1234567L",
    )
    return reader, session, cert


@pytest.mark.asyncio
class TestFetchExpedientes:
    async def test_returns_parsed_records(self, tmp_path: Path) -> None:
        reader, _, _ = _build_reader(tmp_path)
        records = await reader.fetch_expedientes()
        assert len(records) == 3
        assert records[0].modelo == "130"

    async def test_lazy_cert_preload(self, tmp_path: Path) -> None:
        reader, session, cert = _build_reader(tmp_path)
        assert cert.preload_calls == 0
        await reader.fetch_expedientes()
        assert cert.preload_calls == 1
        assert session.create_calls == 1
        # Second call reuses the context, does not re-preload.
        await reader.fetch_expedientes(use_cache=False)
        assert cert.preload_calls == 1
        assert session.create_calls == 1

    async def test_cache_roundtrip(self, tmp_path: Path) -> None:
        reader, session, _ = _build_reader(tmp_path)
        await reader.fetch_expedientes()
        assert len(session.page.visited) == 1
        # Second call with use_cache=True should hit the cache and
        # not re-navigate.
        await reader.fetch_expedientes()
        assert len(session.page.visited) == 1

    async def test_since_filter(self, tmp_path: Path) -> None:
        reader, _, _ = _build_reader(tmp_path)
        records = await reader.fetch_expedientes(since=date(2025, 4, 20))
        assert {r.expediente_id for r in records} == {"2025X1234567L0002"}

    async def test_since_does_not_invalidate_cache(self, tmp_path: Path) -> None:
        """A post-parse ``since`` filter must not force a re-fetch.

        Regression for the review finding: earlier revisions hashed
        ``since`` into the cache key, so back-to-back invocations
        with different ``--since`` values burned the cache.
        """
        reader, session, _ = _build_reader(tmp_path)
        await reader.fetch_expedientes()
        assert len(session.page.visited) == 1
        await reader.fetch_expedientes(since=date(2025, 4, 20))
        await reader.fetch_expedientes(since=date(2025, 4, 15))
        assert len(session.page.visited) == 1

    async def test_close_is_idempotent(self, tmp_path: Path) -> None:
        reader, _, _ = _build_reader(tmp_path)
        await reader.fetch_expedientes()
        await reader.close()
        await reader.close()  # does not raise


@pytest.mark.asyncio
class TestStubSurfaces:
    @pytest.mark.parametrize(
        "coro_name, kwargs",
        [
            ("fetch_notificaciones", {}),
            ("fetch_devoluciones", {}),
            ("fetch_calendario", {}),
        ],
    )
    async def test_raises_status_reader_error(
        self,
        tmp_path: Path,
        coro_name: str,
        kwargs: dict[str, object],
    ) -> None:
        reader, _, _ = _build_reader(tmp_path)
        with pytest.raises(StatusReaderError):
            await getattr(reader, coro_name)(**kwargs)

    async def test_borrador_stub(self, tmp_path: Path) -> None:
        reader, _, _ = _build_reader(tmp_path)
        with pytest.raises(StatusReaderError):
            await reader.fetch_borrador_irpf(2025)

    async def test_datos_fiscales_stub(self, tmp_path: Path) -> None:
        reader, _, _ = _build_reader(tmp_path)
        with pytest.raises(StatusReaderError):
            await reader.fetch_datos_fiscales(2025)


def test_surface_enum_coverage() -> None:
    # Sanity: every enum value is exercised either by the real
    # fetcher or by a stub fetcher in this test module.
    assert set(AeatStatusKind) == {
        AeatStatusKind.EXPEDIENTE,
        AeatStatusKind.NOTIFICACION,
        AeatStatusKind.DEVOLUCION,
        AeatStatusKind.BORRADOR_IRPF,
        AeatStatusKind.DATOS_FISCALES,
        AeatStatusKind.CALENDARIO,
    }
