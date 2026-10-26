"""Headless QR refusal exposes a public URL before acquiring browser resources."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest

from cadrumo.adapters.outbound.aeat.auth import clave_movil
from cadrumo.adapters.outbound.aeat.auth.clave_movil import ClaveMovilAuthProvider
from cadrumo.adapters.outbound.aeat.auth.errors import AuthConfigurationError
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.core.config import Settings
from cadrumo.core.errors.error_codes import resolve_error_message, scrub_error_context

from ......tests.aeat_literal_fixtures import (
    WWW6_PRIVATE_QUERY_DISCLOSURE_CANARY,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_authentication_url_does_not_exempt_live_session_links_from_redaction() -> None:
    from cadrumo.core.authentication_links import aeat_authentication_url

    url = aeat_authentication_url() + "&session=private-marker"
    scrubbed = scrub_error_context({"authentication_url": url})
    assert scrubbed is not None
    assert "private-marker" not in scrubbed["authentication_url"]
    assert "?" not in scrubbed["authentication_url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("headless", [True, False])
async def test_no_desktop_refuses_before_browser_start_and_returns_public_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, headless: bool
) -> None:
    monkeypatch.setattr(clave_movil, "interactive_desktop_available", lambda: False)

    async def forbidden_factory(settings):
        pytest.fail("A headless QR refusal must not start Playwright or Chromium")

    provider = ClaveMovilAuthProvider(
        Settings(cadrumo_browser_headless=headless, cadrumo_clave_prefer_non_qr=False),
        browser_session_factory=forbidden_factory,
    )
    with pytest.raises(AuthConfigurationError) as caught:
        await provider._fresh_login_locked(
            dni_nie="12345678Z",
            storage_state_path=tmp_path / "unused",
            target_url=WWW6_PRIVATE_QUERY_DISCLOSURE_CANARY,
        )
    error = caught.value
    assert error.context is not None
    url = error.context["authentication_url"]
    assert isinstance(url, str)
    assert urlsplit(url).scheme == "https"
    assert "do-not-publish" not in url
    assert provider._browser_session is None
    assert provider.active_session is None
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context_mapping()["authentication_url"] == url
    assert detail.message_key == "adapters.auth.clave_movil.errors.desktop_unavailable"
    for locale in ("en", "es", "ca", "hu"):
        rendered = resolve_error_message(error, locale=locale)
        assert url in rendered
        assert "%{" not in rendered
        assert rendered != error.translated_message
