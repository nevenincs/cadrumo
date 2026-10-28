"""Observe provider login through the supplier, never through credential files."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from time import monotonic

from pydantic import BaseModel, ConfigDict

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY

from ..host.controller import AgentHostError
from ..host.launch_environment import (
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    agent_binary_directories,
    system_environment,
)
from ..host.store_lifecycle import InvocationCancellation
from ..providers.application.contracts import CliState
from ..providers.domain.catalog import ProviderCatalogEntry
from .agent_process import WindowsAgentInvocationRunner
from .agent_programs import AGENT_COMMAND_LINE, AgentProgramRefusalError, agent_image, hosted_python


class _Statuses(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int
    providers: dict[str, CliState]


class AgentProviderAuthStatusProbe:
    """Cache bounded, masked observations under the exact live profile authority."""

    def __init__(
        self, *, context: Callable[[], tuple[Path, str] | None], cancellation: InvocationCancellation | None = None
    ) -> None:
        """Bind the supplier invocation to a current profile authority callback."""
        self._context = context
        self._cancellation = InvocationCancellation() if cancellation is None else cancellation
        self._runner_lock = Lock()
        self._active_runner: WindowsAgentInvocationRunner | None = None
        self._unsettled_runner: WindowsAgentInvocationRunner | None = None
        self._lock = Lock()
        self._cached: tuple[tuple[Path, str], float, dict[str, CliState]] | None = None

    def close(self) -> None:
        """Cancel reads and confirm every retained supplier scope before releasing ownership."""
        self._cancellation.cancel()
        with self._runner_lock:
            retained = tuple({runner for runner in (self._active_runner, self._unsettled_runner) if runner is not None})
        failure: BaseException | None = None
        for runner in retained:
            try:
                runner.settle()
            except BaseException as error:
                failure = error if failure is None else failure
            finally:
                if runner.settled:
                    with self._runner_lock:
                        if self._active_runner is runner:
                            self._active_runner = None
                        if self._unsettled_runner is runner:
                            self._unsettled_runner = None
        if failure is not None:
            raise failure

    def probe(self, entry: ProviderCatalogEntry) -> CliState:
        """Read masked provider status, rejecting results from a retired context."""
        if not entry.auth_kind.accepts_provider_sign_in:
            return CliState.UNKNOWN
        context = self._context()
        if context is None:
            return CliState.UNKNOWN
        with self._lock:
            cached = self._cached
            if cached is None or cached[0] != context or monotonic() - cached[1] >= 5:
                states = self._read(context[0])
                if self._context() != context:
                    return CliState.UNKNOWN
                self._cached = (context, monotonic(), states)
            else:
                states = cached[2]
            return states.get(entry.provider, CliState.UNKNOWN)

    def _read(self, root: Path) -> dict[str, CliState]:
        try:
            image = agent_image(agent_root=root)
            environment = system_environment(os.environ)
            environment[HOSTED_ROOT_VARIABLE] = str(root)
            external = agent_binary_directories(python=hosted_python(), received=os.environ)
            if external is not None and external != "":
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
            with self._runner_lock:
                if self._unsettled_runner is not None:
                    return {}
                runner = WindowsAgentInvocationRunner(cancellation=self._cancellation)
                self._active_runner = runner
            try:
                completed = runner.run(
                    executable=image.executable,
                    arguments=(*AGENT_COMMAND_LINE, "auth", "status", "--json"),
                    directory=image.directory,
                    environment=environment,
                    timeout=DEFAULT_TIMEOUT_POLICY.timeout_seconds,
                    output_limit=4096,
                )
            finally:
                with self._runner_lock:
                    if self._active_runner is runner:
                        self._active_runner = None
                    if not runner.settled:
                        self._unsettled_runner = runner
            if completed.status != 0:
                return {}
            result = _Statuses.model_validate_json(completed.standard_output)
            return result.providers if result.schema_version == 1 else {}
        except (AgentProgramRefusalError, AgentHostError, RefusalError, OSError, ValueError):
            return {}
