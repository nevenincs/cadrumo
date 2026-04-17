"""Unit tests for BrowserSession factory."""

from pathlib import Path

import pytest
from playwright.async_api import BrowserContext

from ..config import PROJECT_ROOT, Settings
from ..errors import SiteHealthError
from ..status import SiteHealthState
from ._site_health_probe import probe_response
from .evasion import EvasionStrategy
from .profile import Profile
from .session import BrowserSession

_FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "site_health"
_PROBE_URL = "https://sede.agenciatributaria.gob.es/"


class DummyEvasion(EvasionStrategy):
    """A dummy evasion strategy that records when it was called."""

    def __init__(self) -> None:
        self.called = False

    async def apply(self, context: BrowserContext) -> None:
        """Record the call."""
        self.called = True


class StubContext:
    """Stub context capturing the kwargs it was created with."""

    def __init__(self, kwargs: dict) -> None:
        self.kwargs = kwargs


class StubBrowser:
    """Stub browser that yields a StubContext."""

    async def new_context(self, **kwargs) -> StubContext:
        """Return a stub context."""
        return StubContext(kwargs)


class StubChromium:
    """Stub chromium that yields a StubBrowser."""

    async def launch(self, **kwargs) -> StubBrowser:
        """Return a stub browser."""
        return StubBrowser()


class StubPlaywright:
    """Stub playwright instance for unit testing."""

    def __init__(self) -> None:
        self.chromium = StubChromium()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_session_creation(tmp_path: Path) -> None:
    """Test creating a browser context with a stub Playwright instance."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    evasion = DummyEvasion()
    pw_stub = StubPlaywright()

    session = BrowserSession(
        playwright=pw_stub,  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=evasion,
    )

    context = await session.create_context()
    assert evasion.called
    assert context.kwargs["locale"] == "es-ES"  # type: ignore
    assert context.kwargs["timezone_id"] == "Europe/Madrid"  # type: ignore
    assert str(tmp_path / "state.json") in context.kwargs["storage_state"]  # type: ignore


def _probe_or_raise(
    url: str,
    http_status: int,
    headers: dict[str, str],
    body: str,
    *,
    rate_limit_retry_after_default: int,
) -> None:
    """Thin test harness: call the helper and surface a ``SiteHealthError``.

    Mirrors the shape of ``BrowserSession.navigate`` without the
    Playwright dependency so the classification branch can be
    exercised via the real parser suite driven from on-disk HTML.
    """
    result = probe_response(
        url,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=rate_limit_retry_after_default,
    )
    if result is not None:
        raise SiteHealthError(status=result)


@pytest.mark.unit
def test_navigate_probe_raises_on_mantenimiento_fixture() -> None:
    body = (_FIXTURES_ROOT / "mantenimiento" / "interstitial.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.MANTENIMIENTO


@pytest.mark.unit
def test_navigate_probe_raises_on_waf_fixture() -> None:
    body = (_FIXTURES_ROOT / "waf_challenge" / "request_blocked.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 403, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.WAF_CHALLENGE


@pytest.mark.unit
def test_navigate_probe_raises_on_rate_limit_fixture() -> None:
    body = (_FIXTURES_ROOT / "rate_limited" / "429_retry_after.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(
            _PROBE_URL,
            429,
            {"Retry-After": "120"},
            body,
            rate_limit_retry_after_default=300,
        )
    assert excinfo.value.status.state is SiteHealthState.RATE_LIMITED
    assert excinfo.value.status.retry_after_seconds == 120


@pytest.mark.unit
def test_navigate_probe_passes_on_ok_fixture() -> None:
    body = (_FIXTURES_ROOT / "ok" / "sede_landing.html").read_text(encoding="utf-8")
    # Must not raise.
    _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
