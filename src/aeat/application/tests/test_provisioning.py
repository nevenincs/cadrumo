"""Real-behavior tests for the external-dependency probes.

Each probe answers "is this external service available right now?" and must
return a typed :class:`DependencyStatus` — never raise — when the dependency is
absent. These tests exercise the real probes against a deliberately-unreachable
Ollama endpoint and a controlled Playwright cache directory; no mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.application.provisioning import (
    DependencyStatus,
    probe_ollama_vision,
    probe_playwright_browser,
    probe_subprocess_providers,
)
from aeat.core.config import override_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_probe_ollama_vision_unreachable_returns_unavailable_with_remediation() -> None:
    """An unreachable Ollama endpoint yields unavailable + a `serve` remediation, never an exception."""
    # Port 1 is reserved/closed — the connection is refused fast.
    with override_settings(aeat_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        status = probe_ollama_vision()
    assert isinstance(status, DependencyStatus)
    assert status.service == "ollama-vision"
    assert status.available is False
    assert "not reachable" in status.detail
    assert "ollama serve" in status.remediation


def test_probe_playwright_browser_absent_when_cache_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty browsers cache reports unavailable with the install command."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    status = probe_playwright_browser()
    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.remediation == "playwright install chromium"


def test_probe_playwright_browser_present_when_chromium_build_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `chromium-*` build directory in the cache reports available."""
    (tmp_path / "chromium-1234").mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    status = probe_playwright_browser()
    assert status.service == "playwright-chromium"
    assert status.available is True
    assert status.remediation == ""


def test_probe_playwright_browser_missing_root_is_unavailable_not_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nonexistent cache root reports unavailable rather than raising OSError."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "does-not-exist"))
    status = probe_playwright_browser()
    assert status.available is False


def test_probe_subprocess_providers_returns_typed_statuses_and_never_raises() -> None:
    """Each subprocess provider yields one DependencyStatus; the probe never raises on absence."""
    statuses = probe_subprocess_providers()
    assert isinstance(statuses, tuple)
    assert statuses, "expected at least one subprocess LLM provider to be probed"
    for status in statuses:
        assert isinstance(status, DependencyStatus)
        assert status.service.startswith("llm-provider:")
        # A reachable provider carries no remediation; an absent one names the fix.
        if not status.available:
            assert "PATH" in status.remediation
