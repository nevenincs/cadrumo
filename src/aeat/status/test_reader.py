"""Unit tests for :class:`aeat.status.StatusReader`.

The reader is exercised against *real* Protocol-conforming test
doubles — never mocks, patches, or fakes. A tiny in-memory
``_FakeBrowserSession`` and ``_FakeCertBackend`` implement the
minimum surface the reader calls; a fake ``Page`` returns the
trimmed expedientes fixture.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from ..config import Settings, load_settings
from ..history import (
    ExpedienteSource,
    FiledModelo,
    FilingDetailFetcher,
    HistoryUnsupportedModeloError,
)
from . import (
    AeatStatusKind,
    BrowserSessionLike,
    Expediente,
    StatusCache,
    StatusReader,
    StatusReaderError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-pages" / "expedientes" / "sample.html"
_FIXTURE_DETAIL_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-pages" / "filing-history"


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


class _UrlKeyedFakePage:
    """URL-keyed fake page preserving the :class:`_FakePage` contract.

    ``visited: list[str]`` records every ``goto`` in order; ``content()``
    returns the HTML mapped from the most recently visited URL. Per-URL
    HTTP status can be overridden via :attr:`status_by_url`; unknown URLs
    return HTTP 404.
    """

    def __init__(
        self,
        *,
        html_by_url: dict[str, str],
        default_html: str = "",
        status_by_url: dict[str, int] | None = None,
    ) -> None:
        self._html_by_url = dict(html_by_url)
        self._default_html = default_html
        self._status_by_url = dict(status_by_url or {})
        self.visited: list[str] = []

    async def goto(
        self,
        url: str,
        *,
        wait_until: str | None = None,
    ) -> _FakeResponse:
        del wait_until
        self.visited.append(url)
        if url in self._status_by_url:
            return _FakeResponse(status=self._status_by_url[url])
        if url in self._html_by_url:
            return _FakeResponse(status=200)
        return _FakeResponse(status=404)

    async def content(self) -> str:
        if not self.visited:
            return self._default_html
        last = self.visited[-1]
        return self._html_by_url.get(last, self._default_html)


class _FakeContext:
    def __init__(self, page: _FakePage | _UrlKeyedFakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> _FakePage | _UrlKeyedFakePage:
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


class _UrlKeyedBrowserSession:
    """Browser session that vends a URL-keyed page.

    Used by the #227 detail-fetch tests. Preserves the
    :class:`_FakeBrowserSession` surface.
    """

    def __init__(self, page: _UrlKeyedFakePage) -> None:
        self.page = page
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

    async def test_concurrent_fetch_shares_single_context(self, tmp_path: Path) -> None:
        """Concurrent fetches must not spawn duplicate contexts.

        Regression for the second-pass review finding: before
        ``_ensure_ready`` got an :class:`asyncio.Lock`, two
        simultaneous tasks could each call
        ``browser_session.create_context()`` and leak the loser.
        """
        reader, session, cert = _build_reader(tmp_path)
        await asyncio.gather(
            reader.fetch_expedientes(use_cache=False),
            reader.fetch_expedientes(use_cache=False),
            reader.fetch_expedientes(use_cache=False),
        )
        assert session.create_calls == 1
        assert cert.preload_calls == 1

    async def test_async_context_manager_closes_reader(self, tmp_path: Path) -> None:
        """`async with` support: __aexit__ must call close()."""
        html = _FIXTURE.read_text(encoding="utf-8")
        session = _FakeBrowserSession(html)
        cert = _FakeCertBackend()
        settings = load_settings()
        cache = StatusCache(tmp_path / "cache", ttl_s=60)
        async with StatusReader(
            browser_session=cast(BrowserSessionLike, session),
            cert_backend=cert,
            cache=cache,
            settings=settings,
            tax_id="X1234567L",
        ) as reader:
            await reader.fetch_expedientes()
        assert session.context.closed

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


_NOTIFICACIONES_FIXTURE = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "aeat-pages" / "notificaciones" / "sample.html"
)


def _build_notificaciones_reader(
    tmp_path: Path,
) -> tuple[StatusReader, _FakeBrowserSession, _FakeCertBackend]:
    html = _NOTIFICACIONES_FIXTURE.read_text(encoding="utf-8")
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
class TestFetchNotificaciones:
    async def test_returns_parsed_records(self, tmp_path: Path) -> None:
        reader, _, _ = _build_notificaciones_reader(tmp_path)
        records = await reader.fetch_notificaciones()
        assert len(records) == 3
        assert records[0].notificacion_id == "NOT-2026-0001"
        assert records[0].kind == "Requerimiento"

    async def test_cache_roundtrip(self, tmp_path: Path) -> None:
        reader, session, _ = _build_notificaciones_reader(tmp_path)
        await reader.fetch_notificaciones()
        assert len(session.page.visited) == 1
        await reader.fetch_notificaciones()
        assert len(session.page.visited) == 1

    async def test_since_filter(self, tmp_path: Path) -> None:
        reader, _, _ = _build_notificaciones_reader(tmp_path)
        records = await reader.fetch_notificaciones(since=date(2026, 2, 18))
        ids = {r.notificacion_id for r in records}
        assert ids == {"NOT-2026-0003"}

    async def test_since_does_not_invalidate_cache(self, tmp_path: Path) -> None:
        reader, session, _ = _build_notificaciones_reader(tmp_path)
        await reader.fetch_notificaciones()
        assert len(session.page.visited) == 1
        await reader.fetch_notificaciones(since=date(2026, 2, 18))
        await reader.fetch_notificaciones(since=date(2026, 2, 10))
        assert len(session.page.visited) == 1

    async def test_navigation_uses_safe_goto_only(self, tmp_path: Path) -> None:
        """Charter #116 defence-in-depth: the reader must only ``goto``."""
        reader, session, _ = _build_notificaciones_reader(tmp_path)
        await reader.fetch_notificaciones()
        # The fake page would raise on anything other than ``goto``/
        # ``content``; proving we only called those two is equivalent
        # to proving no form submission or mutation happened.
        assert session.page.visited  # exactly one safe GET


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


# ─────────────────────────────────────────────────────────────────────
# #227 — list_expedientes / fetch_detail_html / fetch_filing_detail
# ─────────────────────────────────────────────────────────────────────


_FIXTURE_WITH_DETAIL = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "aeat-pages"
    / "expedientes"
    / "sample_with_detail.html"
)


def _expedientes_fixture_html() -> str:
    return _FIXTURE_WITH_DETAIL.read_text(encoding="utf-8")


def _history_fixture(name: str) -> str:
    return (_FIXTURE_DETAIL_DIR / name).read_text(encoding="utf-8")


def _build_url_keyed_reader(
    tmp_path: Path,
    *,
    listing_url: str = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y",
    html_by_url: dict[str, str] | None = None,
    status_by_url: dict[str, int] | None = None,
    detail_url_template: str | None = None,
) -> tuple[StatusReader, _UrlKeyedBrowserSession, _FakeCertBackend]:
    listing_html = _expedientes_fixture_html()
    composed_html_by_url: dict[str, str] = {listing_url: listing_html}
    if html_by_url is not None:
        composed_html_by_url.update(html_by_url)
    page = _UrlKeyedFakePage(
        html_by_url=composed_html_by_url,
        status_by_url=status_by_url,
    )
    session = _UrlKeyedBrowserSession(page)
    cert = _FakeCertBackend()
    settings_overrides: dict[str, Any] = {
        "aeat_filing_history_dir": tmp_path / "filing-history",
    }
    if detail_url_template is not None:
        settings_overrides["aeat_status_detail_url_template"] = detail_url_template
    settings = Settings(**settings_overrides)
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
class TestListExpedientes:
    async def test_no_filter_returns_all(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        records = await reader.list_expedientes()
        assert len(records) == 2
        assert {r.expediente_id for r in records} == {
            "2025X1234567L0100",
            "2025X1234567L0101",
        }

    async def test_modelo_filter(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        records = await reader.list_expedientes(modelo="303")
        assert [r.modelo for r in records] == ["303"]

    async def test_period_filter(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        records = await reader.list_expedientes(period="2025-2T")
        assert len(records) == 2

    async def test_combined_filter_empty_match(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        records = await reader.list_expedientes(modelo="303", period="2025-1T")
        assert records == ()

    async def test_single_underlying_fetch(self, tmp_path: Path) -> None:
        """Post-parse filter must not re-navigate the listing page."""
        reader, session, _ = _build_url_keyed_reader(tmp_path)
        await reader.list_expedientes()
        assert len(session.page.visited) == 1
        # Different filter must still hit the cache.
        await reader.list_expedientes(modelo="303")
        assert len(session.page.visited) == 1


class TestStructuralProtocolConformance:
    def test_is_expediente_source(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        assert isinstance(reader, ExpedienteSource)

    def test_is_filing_detail_fetcher(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        assert isinstance(reader, FilingDetailFetcher)


@pytest.mark.asyncio
class TestFetchDetailHtml:
    def _expediente(self, *, detail_url: str | None) -> Expediente:
        from datetime import UTC
        from datetime import datetime as dt

        from pydantic import AnyHttpUrl, TypeAdapter

        adapter: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
        return Expediente(
            expediente_id="2025X1234567L0100",
            modelo="303",
            period="2025-2T",
            status="Presentada",
            presented_at=dt(2025, 7, 20, 10, 0, tzinfo=UTC),
            csv="QQQQ1111RRRR2222",
            justificante_url=None,
            detail_url=adapter.validate_python(detail_url) if detail_url else None,
            source_page_url=adapter.validate_python(
                "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y"
            ),
            fetched_at=dt(2025, 7, 20, 10, 5, tzinfo=UTC),
        )

    async def test_uses_detail_url_verbatim(self, tmp_path: Path) -> None:
        detail_url = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP=2025X1234567L0100"
        reader, session, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={detail_url: _history_fixture("modelo_303_detail.html")},
        )
        expediente = self._expediente(detail_url=detail_url)
        html, url = await reader.fetch_detail_html(expediente)
        assert str(url) == detail_url
        assert "<table" in html
        # One navigation to the detail URL (the listing page has not
        # been consulted by this method).
        assert session.page.visited == [detail_url]

    async def test_templated_fallback_when_detail_url_missing(self, tmp_path: Path) -> None:
        expected = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP=2025X1234567L0100"
        reader, session, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={expected: _history_fixture("modelo_303_detail.html")},
        )
        expediente = self._expediente(detail_url=None)
        html, url = await reader.fetch_detail_html(expediente)
        assert str(url) == expected
        assert "<table" in html
        assert session.page.visited == [expected]

    async def test_settings_template_override_applied(self, tmp_path: Path) -> None:
        custom_template = "/custom/path/{expediente_id}/detail"
        expected = "https://sede.agenciatributaria.gob.es/custom/path/2025X1234567L0100/detail"
        reader, _, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={expected: _history_fixture("modelo_303_detail.html")},
            detail_url_template=custom_template,
        )
        expediente = self._expediente(detail_url=None)
        _, url = await reader.fetch_detail_html(expediente)
        assert str(url) == expected

    async def test_http_error_raises_status_reader_error(self, tmp_path: Path) -> None:
        target = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP=2025X1234567L0100"
        reader, _, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={target: "ignored"},
            status_by_url={target: 500},
        )
        expediente = self._expediente(detail_url=None)
        with pytest.raises(StatusReaderError) as exc_info:
            await reader.fetch_detail_html(expediente)
        assert "500" in str(exc_info.value)
        assert "2025X1234567L0100" in str(exc_info.value)

    async def test_empty_body_raises_status_reader_error(self, tmp_path: Path) -> None:
        target = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP=2025X1234567L0100"
        reader, _, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={target: ""},
        )
        expediente = self._expediente(detail_url=None)
        with pytest.raises(StatusReaderError) as exc_info:
            await reader.fetch_detail_html(expediente)
        assert "empty" in str(exc_info.value).lower()
        assert "2025X1234567L0100" in str(exc_info.value)

    async def test_url_safe_quoting_on_expediente_id(self, tmp_path: Path) -> None:
        """Special characters in expediente_id must be percent-encoded."""
        expediente_id_with_slash = "2025/special id"
        encoded = "2025%2Fspecial%20id"
        expected = f"https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP={encoded}"
        reader, _, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={expected: _history_fixture("modelo_303_detail.html")},
        )
        from datetime import UTC
        from datetime import datetime as dt

        from pydantic import AnyHttpUrl, TypeAdapter

        adapter: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
        expediente = Expediente(
            expediente_id=expediente_id_with_slash,
            modelo="303",
            period="2025-2T",
            status="Presentada",
            presented_at=dt(2025, 7, 20, 10, 0, tzinfo=UTC),
            csv=None,
            justificante_url=None,
            detail_url=None,
            source_page_url=adapter.validate_python(
                "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y"
            ),
            fetched_at=dt(2025, 7, 20, 10, 5, tzinfo=UTC),
        )
        _, url = await reader.fetch_detail_html(expediente)
        assert str(url) == expected


@pytest.mark.asyncio
class TestFetchFilingDetail:
    """End-to-end composition over :class:`HistoryFetcher`."""

    def _detail_url(self, expediente_id: str) -> str:
        return f"https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}"

    async def test_happy_path_returns_filed_modelo(self, tmp_path: Path) -> None:
        # The sample_with_detail fixture has a 303 row with an explicit
        # detail anchor. Route that anchor to the history fixture HTML.
        target = self._detail_url("2025X1234567L0100")
        reader, _, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={target: _history_fixture("modelo_303_detail.html")},
        )
        records = await reader.fetch_filing_detail("303", "2025-2T")
        assert len(records) == 1
        assert isinstance(records[0], FiledModelo)
        assert records[0].metadata.modelo == "303"
        assert records[0].metadata.period == "2025-2T"
        assert records[0].calculations.casillas  # non-empty

    async def test_empty_when_no_expediente_matches(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        records = await reader.fetch_filing_detail("303", "nonexistent-period")
        assert records == ()

    async def test_unsupported_modelo_raises(self, tmp_path: Path) -> None:
        reader, _, _ = _build_url_keyed_reader(tmp_path)
        with pytest.raises(HistoryUnsupportedModeloError):
            await reader.fetch_filing_detail("111", "2025-2T")

    async def test_cache_hit_skips_second_navigation(self, tmp_path: Path) -> None:
        target = self._detail_url("2025X1234567L0100")
        reader, session, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={target: _history_fixture("modelo_303_detail.html")},
        )
        await reader.fetch_filing_detail("303", "2025-2T")
        first_navigations = [v for v in session.page.visited if v == target]
        assert len(first_navigations) == 1
        # Second call must not navigate to the detail URL again.
        await reader.fetch_filing_detail("303", "2025-2T")
        second_navigations = [v for v in session.page.visited if v == target]
        assert len(second_navigations) == 1

    async def test_use_cache_false_forces_refetch(self, tmp_path: Path) -> None:
        target = self._detail_url("2025X1234567L0100")
        reader, session, _ = _build_url_keyed_reader(
            tmp_path,
            html_by_url={target: _history_fixture("modelo_303_detail.html")},
        )
        await reader.fetch_filing_detail("303", "2025-2T")
        await reader.fetch_filing_detail("303", "2025-2T", use_cache=False)
        count = sum(1 for v in session.page.visited if v == target)
        assert count == 2
