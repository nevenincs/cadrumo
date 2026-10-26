"""Provider lifecycle retains failed owners and the original authentication error."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest

from cadrumo.application.auth.providers import AuthProvider
from cadrumo.application.auth.sessions import _provider_lifecycle
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ProviderResource:
    def __init__(self, *, fails: bool) -> None:
        self.fails = fails
        self.attempts = 0

    async def close(self) -> None:
        self.attempts += 1
        if self.fails:
            raise OSError("synthetic provider close failure")


@pytest.mark.parametrize("body", ["success", "failure", "cancel"])
@pytest.mark.parametrize("close_fails", [False, True])
def test_provider_cleanup_preserves_primary_and_retry_owner(body: str, close_fails: bool) -> None:
    provider = _ProviderResource(fails=close_fails)
    primary = asyncio.CancelledError() if body == "cancel" else ValueError("synthetic auth failure")

    async def run() -> BaseException | None:
        try:
            async with _provider_lifecycle(cast(AuthProvider, provider)):
                if body != "success":
                    raise primary
        except BaseException as error:
            return error
        return None

    caught = asyncio.run(run())
    assert provider.attempts == (2 if close_fails else 1)
    if body == "success":
        if not close_fails:
            assert caught is None
            return
        assert isinstance(caught, AsyncResourceCleanupError)
        cleanup = caught
    else:
        assert caught is primary
        field = "cleanup_error" if body == "cancel" else "async_cleanup_error"
        if not close_fails:
            assert field not in caught.__dict__
            return
        cleanup = caught.__dict__.get(field)
        assert isinstance(cleanup, AsyncResourceCleanupError)
    assert cleanup.resources == (provider,)
    provider.fails = False
    asyncio.run(cleanup.retry_cleanup())
    assert provider.attempts == 3


def test_clean_provider_exit_does_not_borrow_an_unrelated_caller_exception() -> None:
    provider = _ProviderResource(fails=True)
    unrelated = ValueError("synthetic unrelated caller failure")

    async def run() -> AsyncResourceCleanupError:
        try:
            raise unrelated
        except ValueError:
            with pytest.raises(AsyncResourceCleanupError) as caught:
                async with _provider_lifecycle(cast(AuthProvider, provider)):
                    pass
            return caught.value

    cleanup = asyncio.run(run())
    assert "async_cleanup_error" not in unrelated.__dict__
    assert cleanup.resources == (provider,)
    assert provider.attempts == 2
    provider.fails = False
    asyncio.run(cleanup.retry_cleanup())
    assert provider.attempts == 3
