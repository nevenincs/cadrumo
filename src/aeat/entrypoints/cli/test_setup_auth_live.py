"""Live tests for the official ``aeat setup auth`` CLI surface."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

import pytest
from typer.testing import CliRunner

from ...adapters.outbound.aeat.browser import default_browser_session_factory
from ...adapters.persistence.storage.sql import dispose_engine
from ...core.config import Settings
from . import app

pytestmark = [pytest.mark.live_read, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


@pytest.mark.asyncio
async def test_setup_auth_clave_movil_live_playwright_access_without_full_auth_gate() -> None:
    """Central Playwright reaches AEAT Cl@ve access without requiring full auth approval."""

    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")

    settings = Settings().model_copy(update={"aeat_browser_headless": True})
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = await context.new_page()
        selector_url = settings.aeat_clave_sede_access_url_template.format(
            target=quote(settings.aeat_sede_expedientes_path, safe="")
        )

        response = await browser_session.navigate(page, selector_url)
        assert response is None or 200 <= response.status < 500
        await page.locator('button[name="autoriza-P"]').first.wait_for(state="visible", timeout=30_000)
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


def test_setup_auth_login_clave_movil_live_headless_non_qr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Official CLI performs real Cl@ve Móvil authentication when explicitly enabled."""

    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")
    if os.environ.get("AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH") != "1":
        pytest.skip("AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH is not 1")

    settings = Settings()
    if not settings.aeat_clave_movil_dni_nie:
        pytest.skip("AEAT_CLAVE_MOVIL_DNI_NIE is not configured")
    if not settings.aeat_clave_prefer_non_qr:
        pytest.skip("Headless Cl@ve CLI login requires AEAT_CLAVE_PREFER_NON_QR=true")
    identity_kind = settings.aeat_clave_movil_dni_nie[:1].upper()
    if identity_kind in {"X", "Y", "Z"} and not settings.aeat_clave_movil_nie_soporte:
        pytest.skip("NIE non-QR login requires AEAT_CLAVE_MOVIL_NIE_SOPORTE")
    if identity_kind not in {"X", "Y", "Z"} and not settings.aeat_clave_movil_dni_fecha:
        pytest.skip("DNI non-QR login requires AEAT_CLAVE_MOVIL_DNI_FECHA")

    stable_live_dir = Path(os.environ.get("AEAT_LIVE_CLI_STATE_DIR", ".tmp/aeat-live-cli-auth")).resolve()
    stable_live_dir.mkdir(parents=True, exist_ok=True)
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(stable_live_dir / 'aeat-live-cli.db').as_posix()}")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(stable_live_dir / "tokens"))
    monkeypatch.setenv("AEAT_BROWSER_HEADLESS", "1")
    try:
        init = _invoke(["setup", "init", "--name", "live-cli", "--tax-id", settings.aeat_clave_movil_dni_nie])
        assert init.exit_code == 0, init.output
        configure = _invoke(["setup", "auth", "configure", "--provider", "clave_movil"])
        assert configure.exit_code == 0, configure.output

        login = _invoke(["--format", "json", "setup", "auth", "login"])
        assert login.exit_code == 0, login.output
        login_payload = json.loads(login.output)
        assert login_payload["auth"]["provider"] == "clave_movil"
        assert login_payload["auth"]["authenticated_at"] is not None
        assert login_payload["session"]["provider_kind"] == "clave_movil"
        assert login_payload["assertion"]["is_valid"] is True

        whoami = _invoke(["--format", "json", "setup", "auth", "whoami"])
        assert whoami.exit_code == 0, whoami.output
        whoami_payload = json.loads(whoami.output)
        assert whoami_payload["provider"] == "clave_movil"
        assert whoami_payload["session"]["provider_kind"] == "clave_movil"

        status = _invoke(["--format", "json", "setup", "auth", "status"])
        assert status.exit_code == 0, status.output
        status_payload = json.loads(status.output)
        assert status_payload["ready"] is True
        assert status_payload["session"]["provider_kind"] == "clave_movil"

    finally:
        dispose_engine()
