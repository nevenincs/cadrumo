"""Answer the provider status from what is kept, and read the slow parts in the background.

The status is a plain store read like ``provider_lanes``, with each
command-line lane's program state and the sign-in methods as last kept: a lane
no reading has reached yet is ``unknown``, and no method is offered before the
agent has named its methods. Reading them runs the agent, which can take longer
than an administration exchange, so the read is asked for in the background and
a later status serves it; ``reads_pending`` tells the window whether such a
later status is still worth asking for, and each background read that ends is
told through ``settled``, the cue on which the window asks for it. Store reads and login observations carry their own
profile authority; the lifecycle lock only serializes changes to the process
tree, not these reads.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any

from cadrumo.core.logging import get_logger

from .adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from .adapters.agent_provider_catalog import AgentProviderCatalogSource
from .host.background_refresh import BackgroundRefresh
from .providers.application.contracts import (
    ProviderSettingsAnswer,
    ProviderSettingsRefusal,
    ProviderStatusEntry,
)
from .providers.application.next_steps import CONSOLE_SIGN_IN_COMMAND
from .providers.application.ports import ProviderCatalogUnavailableError
from .providers.application.service import ProviderSettingsService, ReadsPending

_LOGGER = get_logger(__name__)


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
        agent_starting: Callable[[], bool],
        settled: Callable[[], None] | None = None,
    ) -> None:
        """Bind the reads the status combines, looked up on each read, its refusal state and end-of-read cue."""
        self._providers = providers
        self._catalog = catalog
        self._login_status = login_status
        self._closing = closing
        self._lease = lease
        self._hosted_certifications = hosted_certifications
        self._agent_starting = agent_starting
        self._settled = settled
        self._login_reading_wanted = False
        # A method read that failed settles the methods as unavailable until one succeeds.
        self._methods_failed = False
        self._refresh = BackgroundRefresh(self._read_and_tell, due=self._due, name="provider-status")

    def answer(self) -> dict[str, Any]:
        """Serve the settings with the kept login readings and sign-in methods, asking for fresher ones."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self._lease()
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._providers().status(reads_pending=self.reads_pending())
        if isinstance(observed, ProviderSettingsRefusal):
            return observed.model_dump(mode="json")
        # Before the methods are read, and while the agent cannot name them,
        # login is offered nowhere; existing key management is unaffected.
        methods = self._catalog().kept_gui_sign_in_methods() or {}
        status = ProviderSettingsAnswer(
            providers=observed.providers,
            sign_in_providers=tuple(methods),
            sign_in_methods={provider: tuple(choices) for provider, choices in methods.items()},
            console_sign_in_command=CONSOLE_SIGN_IN_COMMAND,
            reads_pending=observed.reads_pending,
        ).model_dump(mode="json")
        status["hosted_certifications"] = self._hosted_certifications()
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self._lease() != lease:
            return {"kind": "refused", "code": "signed_out"}
        return status

    def reads_pending(self) -> ReadsPending:
        """Bind, before the lanes are read, the answer to whether their reads are still under way.

        Given the lanes as read, it asks for the reads they want in the background and says
        whether one has not settled: the agent's start, whose catalog the status serves once
        it is ready, the sign-in methods before a read of them succeeded or failed, or a
        command-line lane's login reading before one, failed or not, is kept for the current
        profile. The lanes themselves are the store's and never wait for the agent. The kept
        login reading is marked before the lanes are read, so a reading that lands meanwhile
        still leaves a later status asked for; the methods only ever go from unread to kept,
        so a later read of them serves at least what this one saw.
        """
        mark = self._login_status().reading_mark()

        def pending(lanes: tuple[ProviderStatusEntry, ...]) -> bool:
            # Only a command-line lane carries a program state for the login reading to establish.
            self._login_reading_wanted = any(lane.cli_state is not None for lane in lanes)
            self._refresh.request()
            # The failure flag is read after the kept methods, so a read that lands in between still counts as pending.
            methods_pending = self._catalog().kept_gui_sign_in_methods() is None and not self._methods_failed
            if methods_pending or self._agent_starting():
                return True
            return self._login_reading_wanted and not self._login_status().settled(mark)

        return pending

    def _due(self) -> bool:
        """Say whether a kept login reading or the sign-in methods need reading again."""
        if self._closing.is_set() or self._lease() is None:
            return False
        if self._catalog().kept_gui_sign_in_methods() is None:
            return True
        return self._login_reading_wanted and self._login_status().due()

    def _read_and_tell(self) -> None:
        """Read what the status serves as last kept, then cue the window, whether or not the read succeeded."""
        try:
            self._read_kept()
        finally:
            if self._settled is not None and not self._closing.is_set():
                self._settled()

    def _read_kept(self) -> None:
        """Read what the status serves as last kept, off the request path, each within its own bound."""
        if self._closing.is_set():
            return
        if self._catalog().kept_gui_sign_in_methods() is None:
            # The next status read asks again; until then login is offered nowhere.
            try:
                self._catalog().gui_sign_in_methods()
            except ProviderCatalogUnavailableError as error:
                self._methods_failed = True
                _LOGGER.warning("agent service sign-in methods read failed reason=%s", error.reason.value)
            except BaseException:
                self._methods_failed = True
                raise
        if self._login_reading_wanted and self._login_status().due():
            self._login_status().refresh()
