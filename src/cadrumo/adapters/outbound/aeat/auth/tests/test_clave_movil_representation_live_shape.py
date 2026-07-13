"""Cl@ve representation dispatcher live-shape regressions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import override

import pytest

from ..._playwright import PlaywrightError
from .._clave_movil import ClaveMovilAuthProvider
from .test_clave_movil import (
    _CLAVE_SURFACE,
    _DOMAINS,
    _PRE303_SURFACE,
    _aeat_url,
    _RecordingPage,
    _settings_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _LiveCheckedOwnNameRepresentationPage(_RecordingPage):
    @override
    async def content(self) -> str:
        return f"""
        <body class="modal-open">
          <form id="repForm" method="get" action="{_CLAVE_SURFACE.dialogo_representacion_path}">
            <input id="propio" name="representacion" type="radio" checked>
            <label for="propio">Actuar en nombre propio</label>
            <input id="representante" name="representacion" type="radio">
            <label for="representante">Actuar como representante de:</label>
            <button type="submit">CONFIRMAR Buscar</button>
          </form>
          <div id="{_PRE303_SURFACE.alert_modal_selector.lstrip("#")}" class="modal fade show">
            <div class="modal-footer">
              <button type="button">Continuar</button>
            </div>
          </div>
        </body>
        """

    @override
    async def click(self, selector: str) -> None:
        if selector in (
            _PRE303_SURFACE.representation_own_name_label_selector,
            _PRE303_SURFACE.representation_own_name_selector,
        ):
            raise PlaywrightError("own-name radio was already checked")
        await super().click(selector)


def test_representation_dispatcher_handles_live_checked_own_name_shape(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
    provider = ClaveMovilAuthProvider(settings)
    page = _LiveCheckedOwnNameRepresentationPage(target_path=settings.aeat_sede_expedientes_path)
    page.url = _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path)

    async def run() -> None:
        await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=1_000)

    asyncio.run(run())
    continue_selector = (
        f"{_PRE303_SURFACE.alert_modal_selector}.show "
        f'button:has-text("{_PRE303_SURFACE.alert_continue_button_text.title()}")'
    )
    assert page.clicks == [
        continue_selector,
        _PRE303_SURFACE.representation_submit_selector,
    ]
