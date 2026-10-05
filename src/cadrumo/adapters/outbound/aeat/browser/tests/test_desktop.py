"""Desktop availability follows the launching process, not a browser preference."""

from types import SimpleNamespace

import pytest

from cadrumo.adapters.outbound.aeat.browser import desktop
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("display,expected", [(None, False), ("", False), (":0", True), ("localhost:10.0", True)])
def test_linux_display_requirement(monkeypatch: pytest.MonkeyPatch, display: str | None, expected: bool) -> None:
    monkeypatch.setattr(desktop, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.delenv("DISPLAY", raising=False)
    if display is not None:
        monkeypatch.setenv("DISPLAY", display)
    assert desktop.interactive_desktop_available() is expected


def test_windows_background_session_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.adapters.local_runtime import windows_desktop_logon

    monkeypatch.setattr(desktop, "sys", SimpleNamespace(platform="win32"))

    def unavailable():
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    monkeypatch.setattr(windows_desktop_logon, "current_windows_desktop_logon", unavailable)
    assert not desktop.interactive_desktop_available()
