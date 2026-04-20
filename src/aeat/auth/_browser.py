from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..config import Settings


@runtime_checkable
class BrowserPageLike(Protocol):
    """Minimum structural shape of a Playwright ``Page``."""

    async def goto(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> BrowserResponseLike | None: ...
    async def close(self) -> None: ...


@runtime_checkable
class BrowserResponseLike(Protocol):
    """Minimum shape of a Playwright ``Response`` we read."""

    @property
    def status(self) -> int: ...


@runtime_checkable
class BrowserContextLike(Protocol):
    """Minimum structural shape of a Playwright ``BrowserContext``."""

    async def new_page(self) -> BrowserPageLike: ...
    async def storage_state(self) -> Any: ...
    async def close(self) -> None: ...


# A callable that decorates new_context(**kwargs) for Playwright.
# For cert providers, it adds client_certificates=[...].
# For Cl@ve, it might be a no-op.
BrowserContextProvisioner = Callable[[dict[str, Any]], None]


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Structural shape of :class:`aeat.browser.BrowserSession`."""

    @property
    def profile(self) -> Any:
        """The profile associated with this session."""
        ...

    async def create_context(
        self,
        *,
        provisioner: BrowserContextProvisioner | None = None,
        storage_state_path: Path | None = None,
    ) -> BrowserContextLike:
        """Create a new browser context."""
        ...

    async def close(self) -> None:
        """Close the browser session."""
        ...


class BrowserSessionFactory(Protocol):
    """Async callable returning a :class:`BrowserSessionLike`."""

    async def __call__(self, settings: Settings) -> BrowserSessionLike: ...
