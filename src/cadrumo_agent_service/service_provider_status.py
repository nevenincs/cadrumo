"""Answer the provider status from what is kept, and read the slow parts in the background.

The status is a plain store read like ``provider_lanes``, with each
command-line lane's program state and the sign-in methods as last kept: a lane
no reading has reached yet is ``unknown``, and no method is offered before the
agent has named its methods. Reading them runs the agent, which can take longer
than an administration exchange, so the read is asked for in the background and
a later status serves it. Store reads and login observations carry their own
profile authority; the lifecycle lock only serializes changes to the process
tree, not these reads.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from threading import Event
from typing import Any

from .adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from .adapters.agent_provider_catalog import AgentProviderCatalogSource
from .host.background_refresh import BackgroundRefresh
from .providers.application.contracts import ProviderSettingsRefusal
from .providers.application.next_steps import CONSOLE_SIGN_IN_COMMAND
from .providers.application.ports import ProviderCatalogUnavailableError
from .providers.application.service import ProviderSettingsService


class ProviderStatusRead:
    """The ``status`` admin read: never waits for an agent program."""

    def __init__(
        self,
        *,
        providers: Callable[[], ProviderSettingsService],
        catalog: Callable[[], AgentProviderCatalogSource],
        login_status: Callable[[], AgentProviderAuthStatusProbe],
        closing: Event,
        lease: Callable[[], object | None],
        hosted_certifications: Callable[[], list[dict[str, str]]],
    ) -> None:
        """Bind the reads the status combines, looked up on each read, and the state it is refused under."""
        self._providers = providers
        self._catalog = catalog
        self._login_status = login_status
        self._closing = closing
        self._lease = lease
        self._hosted_certifications = hosted_certifications
        self._login_reading_wanted = False
        self._refresh = BackgroundRefresh(self._read_kept, due=self._due, name="provider-status")

    def answer(self) -> dict[str, Any]:
        """Serve the settings with the kept login readings and sign-in methods, asking for fresher ones."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self._lease()
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._providers().status()
        if isinstance(observed, ProviderSettingsRefusal):
            return observed.model_dump(mode="json")
        status = observed.model_dump(mode="json")
        # Only a command-line lane carries a program state for the login reading to establish.
        self._login_reading_wanted = any(entry.get("cli_state") is not None for entry in status.get("providers", ()))
        self._refresh.request()
        status["hosted_certifications"] = self._hosted_certifications()
        status["console_sign_in_command"] = CONSOLE_SIGN_IN_COMMAND
        # Before the methods are read, and while the agent cannot name them,
        # login is offered nowhere; existing key management is unaffected.
        methods = self._catalog().kept_gui_sign_in_methods() or {}
        status["sign_in_providers"] = list(methods)
        status["sign_in_methods"] = {provider: list(choices) for provider, choices in methods.items()}
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self._lease() != lease:
            return {"kind": "refused", "code": "signed_out"}
        return status

    def _due(self) -> bool:
        """Say whether a kept login reading or the sign-in methods need reading again."""
        if self._closing.is_set() or self._lease() is None:
            return False
        if self._catalog().kept_gui_sign_in_methods() is None:
            return True
        return self._login_reading_wanted and self._login_status().due()

    def _read_kept(self) -> None:
        """Read what the status serves as last kept, off the request path, each within its own bound."""
        if self._closing.is_set():
            return
        if self._catalog().kept_gui_sign_in_methods() is None:
            # The next status read asks again; until then login is offered nowhere.
            with suppress(ProviderCatalogUnavailableError):
                self._catalog().gui_sign_in_methods()
        if self._login_reading_wanted and self._login_status().due():
            self._login_status().refresh()
