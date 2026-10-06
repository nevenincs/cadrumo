"""Browser consent never opens the user's default profile on an unavailable desktop."""

from __future__ import annotations

import webbrowser
from types import SimpleNamespace
from typing import NoReturn

import pytest

from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .. import oauth_callback

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_unavailable_desktop_refuses_before_listener_url_or_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied() -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    def unexpected(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("unavailable desktop reached external-browser preparation")

    monkeypatch.setattr(oauth_callback, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(oauth_callback, "current_windows_desktop_logon", denied)
    monkeypatch.setattr(oauth_callback.socket, "socket", unexpected)
    monkeypatch.setattr(oauth_callback.webbrowser, "get", unexpected)
    with pytest.raises(webbrowser.Error, match="interactive desktop"):
        oauth_callback.receive_authorization_code(unexpected, state="synthetic-state", timeout_seconds=1)


def test_desktop_is_rechecked_before_every_browser_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def witness() -> None:
        events.append("desktop")

    def authorization(redirect: str) -> str:
        events.append("authorization")
        return "https://accounts.google.com/synthetic-test"

    def browser(url: str, **kwargs: object) -> bool:
        events.append("browser")
        return False

    monkeypatch.setattr(oauth_callback, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(oauth_callback, "current_windows_desktop_logon", witness)
    monkeypatch.setattr(oauth_callback.webbrowser, "get", lambda: SimpleNamespace(open=browser))
    for _ in range(2):
        with pytest.raises(webbrowser.Error, match="launcher refused"):
            oauth_callback.receive_authorization_code(authorization, state="synthetic-state", timeout_seconds=1)
    assert events == ["desktop", "authorization", "browser"] * 2
