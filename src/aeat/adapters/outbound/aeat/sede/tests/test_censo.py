"""Unit tests for the authenticated G313 browser fetch path."""

from __future__ import annotations

from collections.abc import Mapping
from textwrap import dedent

import pytest

from ......core.config import Settings
from .. import G313_LAUNCHER_URL, censo_fact_set_to_mapping, fetch_g313_censo
from .._censo_live import _fetch_g313_censo_with_storage_state

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_AEAT = Settings.external_constants().aeat


_G313_HTML = dedent(
    """
    <html>
      <body>
        <table class="datos-censales">
          <tr><td>Referencia catastral:</td><td>1234567AB1234S0001WX</td></tr>
          <tr><td>Vivienda habitual:</td><td>Sí</td></tr>
          <tr><td>Fecha de alta de la actividad:</td><td>15/03/2018</td></tr>
          <tr><td>Tipo de establecimiento:</td><td>propio</td></tr>
          <tr><td>Porcentaje de retención:</td><td>15%</td></tr>
          <tr><td>Superficie total de la vivienda:</td><td>120,50 m²</td></tr>
          <tr><td>Superficie afecta a la actividad:</td><td>24,10 m²</td></tr>
          <tr><td>Epígrafe IAE:</td><td>721</td></tr>
        </table>
      </body>
    </html>
    """,
)


class _RecordingPage:
    def __init__(self, html: str) -> None:
        self._html = html
        self.goto_calls: list[tuple[str, str]] = []

    async def goto(self, url: str, *, wait_until: str | None) -> None:
        assert wait_until is not None
        self.goto_calls.append((url, wait_until))

    async def content(self) -> str:
        return self._html


class _RecordingContext:
    def __init__(self, page: _RecordingPage) -> None:
        self._page = page
        self.close_calls = 0

    async def new_page(self) -> _RecordingPage:
        return self._page

    async def close(self) -> None:
        self.close_calls += 1


class _RecordingBrowserSession:
    def __init__(self, html: str) -> None:
        self.page = _RecordingPage(html)
        self.context = _RecordingContext(self.page)
        self.storage_states: list[Mapping[str, object]] = []
        self.close_calls = 0

    async def create_context(self, *, storage_state: Mapping[str, object]) -> _RecordingContext:
        self.storage_states.append(storage_state)
        return self.context

    async def close(self) -> None:
        self.close_calls += 1


def test_g313_live_driver_is_exported_from_public_sede_surface() -> None:
    assert callable(fetch_g313_censo)
    assert callable(censo_fact_set_to_mapping)
    assert f"{_AEAT.domains.sede}{_AEAT.sede_paths.censo_g313_launcher}" == G313_LAUNCHER_URL


@pytest.mark.asyncio
async def test_g313_fetch_uses_authenticated_storage_and_parses_page_content() -> None:
    storage_state: Mapping[str, object] = {
        "cookies": (
            {
                "name": "AEAT_SESSION",
                "value": "recorded-session",
                "domain": _AEAT.domains.sede.removeprefix("https://"),
                "path": "/",
            },
        ),
        "origins": (),
    }
    browser_session = _RecordingBrowserSession(_G313_HTML)

    async def browser_session_factory(settings: Settings) -> _RecordingBrowserSession:
        assert isinstance(settings, Settings)
        return browser_session

    fact_set = await _fetch_g313_censo_with_storage_state(
        storage_state,
        settings=Settings(),
        browser_session_factory=browser_session_factory,
    )

    assert browser_session.storage_states == [storage_state]
    assert browser_session.page.goto_calls == [(G313_LAUNCHER_URL, "domcontentloaded")]
    assert browser_session.context.close_calls == 1
    assert browser_session.close_calls == 1
    assert censo_fact_set_to_mapping(fact_set) == {
        "activities.iae_epigraph": "721",
        "address.cadastral_reference": "1234567AB1234S0001WX",
        "address.is_habitual_vivienda": "true",
        "censo.activity_start_date": "2018-03-15",
        "censo.elected_withholding_pct": "15",
        "censo.establecimiento_type": "propio",
        "vivienda_office.office_m2": "24.1",
        "vivienda_office.total_m2": "120.5",
    }
