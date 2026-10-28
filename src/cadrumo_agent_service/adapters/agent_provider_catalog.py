"""Obtain the provider catalog from cadrumo-agent, at run time.

Cadrumo keeps no list of providers. The agent reports the ones it supports with
its offline declaration command, which needs no gateway and no state home. This
module is the one place that names that invocation and the one place that runs
it: a change in the agent's command or document shape is made here and in the
domain parser, nowhere else.

The invocation runs in a minimal environment built from the operating-system
allow-list, so no provider key in the runtime's own environment reaches the
agent. A successful answer is kept for the source's lifetime; a failure is never
replaced by a stored copy.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from threading import Condition, Lock
from typing import Final, Literal, override

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY, OrchestrationTimeoutError, TimeoutDeadline

from ..host.controller import AgentHostError, AgentHostRefusal
from ..host.launch_environment import system_environment
from ..host.store_lifecycle import AgentInvocationRunner, InvocationCancellation
from ..providers.application.ports import (
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    ProviderCatalogUnavailableReason,
)
from ..providers.domain.catalog import MAX_CATALOG_LANES, ProviderCatalog, ProviderId, parse_provider_catalog
from .agent_process import WindowsAgentInvocationRunner
from .agent_programs import AGENT_COMMAND_LINE, AgentProgramRefusalError, agent_image

_LOGGER = get_logger(__name__)

CATALOG_VERB: Final = ("providers", "--declared", "--json")
"""The agent's offline provider declaration, serving schema version 5."""
CATALOG_ARGUMENTS: Final = (*AGENT_COMMAND_LINE, *CATALOG_VERB)
AUTH_CAPABILITIES_ARGUMENTS: Final = (*AGENT_COMMAND_LINE, "auth", "providers", "--json")
GUI_AUTH_CAPABILITIES_ARGUMENTS: Final = (*AGENT_COMMAND_LINE, "auth", "providers", "--interface", "gui", "--json")
CATALOG_OUTPUT_MAX_BYTES: Final = 256 * 1024


class _SignInCapabilities(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[1]
    providers: tuple[ProviderId, ...] = Field(max_length=MAX_CATALOG_LANES)


class _GuiSignInCapabilities(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    schema_version: Literal[2, 3]
    providers: dict[ProviderId, tuple[Literal["browser", "browser-code", "device"], ...]] = Field(
        max_length=MAX_CATALOG_LANES
    )


class AgentProviderCatalogSource(ProviderCatalogSource):
    """Run the agent's offline catalog command and parse what it prints."""

    def __init__(
        self,
        *,
        received: Mapping[str, str] | None = None,
        runner: AgentInvocationRunner | None = None,
    ) -> None:
        """Bind the agent to run: the package's image."""
        self._runner: AgentInvocationRunner = WindowsAgentInvocationRunner() if runner is None else runner
        self._received = os.environ if received is None else received
        # One lock per document: a first sign-in capability read runs the
        # agent, and the catalog, already read at start, must not wait for it.
        self._lock = Condition()
        self._catalog_pending = False
        self._cancellation = InvocationCancellation()
        self._runner_lock = Lock()
        self._active_runners: set[WindowsAgentInvocationRunner] = set()
        self._unsettled_runners: set[WindowsAgentInvocationRunner] = set()
        self._sign_in_lock = Lock()
        self._gui_sign_in_lock = Lock()
        self._catalog: ProviderCatalog | None = None
        self._sign_ins: tuple[str, ...] | None = None
        self._gui_sign_ins: dict[str, tuple[Literal["browser", "browser-code", "device"], ...]] | None = None

    def request_close(self) -> None:
        """Wake source-owned invocations without performing cleanup on the request thread."""
        self._cancellation.cancel()

    def close(self) -> None:
        """Retain every unresolved tree until its exact scope confirms termination."""
        self.request_close()
        with self._runner_lock:
            retained = tuple(self._active_runners | self._unsettled_runners)
        failure: BaseException | None = None
        for runner in retained:
            try:
                runner.settle()
            except BaseException as error:
                failure = error if failure is None else failure
            finally:
                if runner.settled:
                    with self._runner_lock:
                        self._active_runners.discard(runner)
                        self._unsettled_runners.discard(runner)
        if failure is not None:
            raise failure

    @override
    def catalog(
        self, *, deadline: TimeoutDeadline | None = None, cancellation: InvocationCancellation | None = None
    ) -> ProviderCatalog:
        """Read or join one declaration, responding to cancellation and its owner's timeout."""
        deadline = DEFAULT_TIMEOUT_POLICY.deadline() if deadline is None else deadline
        cancellation = InvocationCancellation() if cancellation is None else cancellation

        def wake() -> None:
            with self._lock:
                self._lock.notify_all()

        release_source = self._cancellation.subscribe(cancellation.cancel)
        release_wait = cancellation.subscribe(wake)
        try:
            with self._lock:
                while self._catalog_pending:
                    if cancellation.is_set():
                        raise AgentHostError(AgentHostRefusal.CANCELLED)
                    self._lock.wait(deadline.remaining_seconds())
                if cancellation.is_set():
                    raise AgentHostError(AgentHostRefusal.CANCELLED)
                if self._catalog is not None:
                    return self._catalog
                self._catalog_pending = True
            try:
                result = self._fetch(deadline, cancellation)
                with self._lock:
                    if cancellation.is_set():
                        raise AgentHostError(AgentHostRefusal.CANCELLED)
                    deadline.remaining_seconds()
                    self._catalog = result
                    return result
            finally:
                with self._lock:
                    self._catalog_pending = False
                    self._lock.notify_all()
        finally:
            release_wait()
            release_source()

    def _fetch(self, deadline: TimeoutDeadline, cancellation: InvocationCancellation) -> ProviderCatalog:
        try:
            return parse_provider_catalog(
                self._invoke(CATALOG_ARGUMENTS, deadline=deadline, cancellation=cancellation).decode("utf-8")
            )
        except (CoreValidationError, UnicodeDecodeError) as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error

    def sign_in_providers(self) -> tuple[str, ...]:
        """Read the agent's supported operator login actions, separate from credential kinds."""
        with self._sign_in_lock:
            if self._sign_ins is None:
                try:
                    result = _SignInCapabilities.model_validate_json(self._invoke(AUTH_CAPABILITIES_ARGUMENTS))
                    if len(set(result.providers)) != len(result.providers):
                        raise ValueError("duplicate_sign_in_provider")
                except ValueError as error:
                    raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error
                self._sign_ins = result.providers
            return self._sign_ins

    def gui_sign_in_providers(self) -> tuple[str, ...]:
        """Read GUI support from the agent, separately from terminal handlers."""
        return tuple(self.gui_sign_in_methods())

    def gui_sign_in_methods(self) -> dict[str, tuple[Literal["browser", "browser-code", "device"], ...]]:
        """Return the provider-owned methods; the service invents no login capability."""
        with self._gui_sign_in_lock:
            if self._gui_sign_ins is None:
                try:
                    result = _GuiSignInCapabilities.model_validate_json(self._invoke(GUI_AUTH_CAPABILITIES_ARGUMENTS))
                    if any(not methods or len(set(methods)) != len(methods) for methods in result.providers.values()):
                        raise ValueError("invalid_sign_in_methods")
                    if result.schema_version == 2 and any(
                        "browser-code" in methods for methods in result.providers.values()
                    ):
                        raise ValueError("invalid_sign_in_methods")
                except ValueError as error:
                    raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error
                self._gui_sign_ins = result.providers
            return dict(self._gui_sign_ins)

    def _invoke(
        self,
        arguments: tuple[str, ...],
        *,
        deadline: TimeoutDeadline | None = None,
        cancellation: InvocationCancellation | None = None,
    ) -> bytes:
        deadline = DEFAULT_TIMEOUT_POLICY.deadline() if deadline is None else deadline
        cancellation = self._cancellation if cancellation is None else cancellation
        directory = Path(tempfile.gettempdir())
        try:
            image = agent_image(agent_root=directory, received=self._received)
        except AgentProgramRefusalError as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND) from error
        runner = self._runner
        owned: WindowsAgentInvocationRunner | None = None
        with self._runner_lock:
            if self._unsettled_runners:
                raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)
            if isinstance(runner, WindowsAgentInvocationRunner):
                owned = WindowsAgentInvocationRunner(deadline=deadline, cancellation=cancellation)
                self._active_runners.add(owned)
                runner = owned
        try:
            try:
                completed = runner.run(
                    executable=image.executable,
                    arguments=arguments,
                    directory=image.directory,
                    environment=system_environment(self._received),
                    timeout=deadline.remaining_seconds(),
                    output_limit=CATALOG_OUTPUT_MAX_BYTES,
                )
            finally:
                if owned is not None:
                    with self._runner_lock:
                        self._active_runners.discard(owned)
                        if not owned.settled:
                            self._unsettled_runners.add(owned)
        except AgentHostError as error:
            if error.reason in {AgentHostRefusal.CANCELLED, AgentHostRefusal.TIMEOUT}:
                raise
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED) from error
        except OrchestrationTimeoutError:
            raise
        except (OSError, RefusalError) as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED) from error
        if completed.status is None:
            raise AgentHostError(AgentHostRefusal.TIMEOUT)
        if completed.status != 0:
            _LOGGER.warning("agent provider catalog command failed status=%s", completed.status)
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)
        if len(completed.standard_output) > CATALOG_OUTPUT_MAX_BYTES:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED)
        return completed.standard_output


__all__ = ["CATALOG_ARGUMENTS", "AgentProviderCatalogSource"]
