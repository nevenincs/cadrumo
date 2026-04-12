"""Unit tests for BrowserSession factory."""

from pathlib import Path

import pytest
from playwright.async_api import BrowserContext

from aeat.browser.evasion import EvasionStrategy
from aeat.browser.profile import Profile
from aeat.browser.session import BrowserSession
from aeat.config import Settings


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
