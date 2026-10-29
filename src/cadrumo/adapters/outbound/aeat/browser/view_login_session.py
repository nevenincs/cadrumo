"""Lend an open view context to its supervised sign-in provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from .....application.auth.protocols import BrowserContextProvisioner
from .....core.config import Settings
from .....core.errors.hierarchy import InternalInvariantError
from .._playwright import BrowserContext, Page

if TYPE_CHECKING:
    from .sede_view import SedeViewPage


class _LentViewContext:
    """The view context as a provider's login sees it: its pages open in the panel, and closing it is a no-op.

    The view owns its context; the login only borrows it. Every page the
    provider opens reaches the view's page observer and is shown, and a page
    the provider leaves open when the person interrupts it stays for the person.
    """

    def __init__(self, context: BrowserContext) -> None:
        self._context = context

    async def new_page(self) -> Page:
        """Open a page in the view; the panel shows it."""
        return await self._context.new_page()

    async def storage_state(self) -> Mapping[str, object]:
        """Capture the view's cookies and local storage."""
        return await self._context.storage_state()

    async def close(self) -> None:
        """Leave the view's context open: the view closes it."""
        return


class _LentViewSession:
    """A browser session whose one context is the open view's own."""

    def __init__(self, view: SedeViewPage) -> None:
        self._view = view

    async def create_context(
        self,
        *,
        provisioner: BrowserContextProvisioner | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _LentViewContext:
        """Lend the view's context; it already presents the configured provider's credential."""
        del provisioner
        if storage_state is not None:
            raise InternalInvariantError("a running Sede view is never re-seeded")
        return _LentViewContext(self._view.context)

    async def close(self) -> None:
        """Leave the view's browser running: the view closes it."""
        return


class ViewLoginSessionFactory:
    """Lend a provider's login the Sede view, so its headless pages show in the person's panel."""

    def __init__(self, view: SedeViewPage) -> None:
        """Bind the factory to the open ``view``."""
        self._view = view

    @property
    def lends_view(self) -> bool:
        """Always ``True``: the provider never opens a browser or window of its own."""
        return True

    async def __call__(self, settings: Settings) -> _LentViewSession:
        """Return a session over the view; ``settings`` cannot make it headed."""
        del settings
        return _LentViewSession(self._view)
