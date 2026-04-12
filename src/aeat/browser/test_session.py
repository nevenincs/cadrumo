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


class MockContext:
    """Mock context."""

    def __init__(self, kwargs: dict) -> None:
        self.kwargs = kwargs


class MockBrowser:
    """Mock browser."""

    async def new_context(self, **kwargs) -> MockContext:
        """Return a mock context."""
        return MockContext(kwargs)


class MockChromium:
    """Mock chromium."""

    async def launch(self, **kwargs) -> MockBrowser:
        """Return a mock browser."""
        return MockBrowser()


class MockPlaywright:
    """Mock playwright instance for unit testing."""

    def __init__(self) -> None:
        self.chromium = MockChromium()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_session_creation(tmp_path: Path) -> None:
    """Test creating a browser context with a mocked Playwright instance."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    evasion = DummyEvasion()
    pw_mock = MockPlaywright()

    session = BrowserSession(
        playwright=pw_mock,  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=evasion,
    )

    context = await session.create_context()
    assert evasion.called
    assert context.kwargs["locale"] == "es-ES"  # type: ignore
    assert context.kwargs["timezone_id"] == "Europe/Madrid"  # type: ignore
    assert str(tmp_path / "state.json") in context.kwargs["storage_state"]  # type: ignore
