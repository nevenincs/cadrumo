"""Own a runtime login and its connection across the installed TUI lifetime."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from textual.app import App

from ...application.user_profile.login_interaction import ProfileLoginChoice
from ...core.async_cleanup import await_cancellation_complete
from .secret.runtime_login import (
    RuntimeClientOpener,
    RuntimeCredentialClientOpener,
    RuntimeLoginHandoff,
    RuntimeLoginScreen,
    RuntimeRequesterFactory,
)

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType


class _RuntimeLoginApp(App[None]):
    """Accept exactly one screen-owned connection into the enclosing scope."""

    def __init__(
        self,
        *,
        choices: Sequence[ProfileLoginChoice],
        open_client: RuntimeClientOpener,
        open_credential_client: RuntimeCredentialClientOpener | None,
        requester_factory: RuntimeRequesterFactory | None,
        preselected: str | None,
    ) -> None:
        super().__init__()
        self.handoff: RuntimeLoginHandoff | None = None
        self._accepting = True
        self._login = RuntimeLoginScreen(
            choices=choices,
            open_client=open_client,
            open_credential_client=open_credential_client,
            requester_factory=requester_factory,
            accept_handoff=self._accept,
            preselected=preselected,
        )

    def _accept(self, handoff: RuntimeLoginHandoff) -> bool:
        if not self._accepting or not self.is_running or self.handoff is not None:
            return False
        self.handoff = handoff
        return True

    def _dismissed(self, result: RuntimeLoginHandoff | None) -> None:
        # Ownership transferred synchronously at _accept, not through this
        # optional Textual result callback. The outer finally owns cleanup
        # even if dismissal or application shutdown subsequently fails.
        self._accepting = False
        self.exit()

    def on_mount(self) -> None:
        self.push_screen(self._login, self._dismissed)

    def stop_accepting(self) -> None:
        """Fence late screen completion before outer cleanup starts."""
        self._accepting = False


@asynccontextmanager
async def runtime_login_session(
    *,
    choices: Sequence[ProfileLoginChoice],
    open_client: RuntimeClientOpener,
    open_credential_client: RuntimeCredentialClientOpener | None = None,
    requester_factory: RuntimeRequesterFactory | None = None,
    preselected: str | None = None,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> AsyncGenerator[RuntimeLoginHandoff | None]:
    """Keep the authenticated client owned until its entire frontend exits.

    The login screen owns opening and proving the connection. This scope
    acknowledges transfer before the screen dismisses, retains the exact
    client while the caller composes and runs its root, and closes it after
    normal exit, failure or cancellation. It never opens local custody.
    """
    app = _RuntimeLoginApp(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_credential_client,
        requester_factory=requester_factory,
        preselected=preselected,
    )
    try:
        await app.run_async(headless=headless, auto_pilot=auto_pilot)
        app.stop_accepting()
        yield app.handoff
    finally:
        app.stop_accepting()
        handoff = app.handoff
        app.handoff = None
        if handoff is not None:
            await await_cancellation_complete(
                asyncio.to_thread(handoff.client.close), task_name="tui-runtime-session-close"
            )
