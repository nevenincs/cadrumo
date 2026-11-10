"""Observe provider login through the supplier, never through credential files."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Literal

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
from ..host.store_lifecycle import AgentInvocationResult, InvocationCancellation
from ..providers.application.contracts import CliObservation, CliState, CliStateCause
from ..providers.domain.catalog import ProviderCatalogEntry
from .agent_process import WindowsAgentInvocationRunner
from .agent_programs import AGENT_COMMAND_LINE, AgentProgramRefusalError, agent_image, hosted_python

_ProbeCause = Literal[
    "cli_not_found",
    "home_in_git_project",
    "home_unavailable",
    "probe_start_failed",
    "probe_timed_out",
    "probe_output_unreadable",
    "probe_cleanup_unconfirmed",
]
CONFIRMATION_SECONDS = 20.0
"""The bound on the one fresh read that confirms a completed sign-in."""


class _Statuses(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: Literal[2]
    providers: dict[str, CliState]
    causes: dict[str, _ProbeCause | None]


@dataclass(frozen=True, slots=True)
class _Reading:
    states: Mapping[str, CliState]
    causes: Mapping[str, CliStateCause | None]
    failure: CliStateCause | None = None

    def observe(self, provider: str) -> CliObservation:
        if self.failure is not None:
            return CliObservation(CliState.UNKNOWN, self.failure)
        return CliObservation(self.states.get(provider, CliState.UNKNOWN), self.causes.get(provider))


def _failed(cause: CliStateCause) -> _Reading:
    return _Reading({}, {}, cause)


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
        self._cached: tuple[tuple[Path, str], float, _Reading] | None = None
        self._epoch_lock = Lock()
        self._epoch = 0

    def forget(self) -> None:
        """Drop the kept read, and any read already under way, without waiting for one to finish."""
        with self._epoch_lock:
            self._epoch += 1
            self._cached = None

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

    def probe(self, entry: ProviderCatalogEntry) -> CliObservation:
        """Read masked provider status, rejecting results from a retired context."""
        if not entry.auth_kind.accepts_provider_sign_in:
            return CliObservation(CliState.UNKNOWN)
        context = self._context()
        if context is None:
            return CliObservation(CliState.UNKNOWN)
        with self._lock:
            cached = self._cached
            if cached is None or cached[0] != context or monotonic() - cached[1] >= 5:
                with self._epoch_lock:
                    epoch = self._epoch
                reading = self._read(context[0], DEFAULT_TIMEOUT_POLICY.timeout_seconds)
                if self._context() != context:
                    return CliObservation(CliState.UNKNOWN)
                # A failed read, or one begun before the cache was dropped, is never kept.
                if reading.failure is None:
                    with self._epoch_lock:
                        if epoch == self._epoch:
                            self._cached = (context, monotonic(), reading)
            else:
                reading = cached[2]
            return reading.observe(entry.provider)

    def confirm(self, provider: str, *, root: Path) -> CliObservation:
        """Read one provider's status fresh, within its own bound, and keep nothing."""
        with self._lock:
            return self._read(root, CONFIRMATION_SECONDS).observe(provider)

    def _read(self, root: Path, timeout: float) -> _Reading:
        try:
            image = agent_image(agent_root=root)
            environment = _status_environment(root)
            runner = self._claim_runner()
            if runner is None:
                return _failed(CliStateCause.STATUS_READ_FAILED)
            try:
                completed = runner.run(
                    executable=image.executable,
                    arguments=(*AGENT_COMMAND_LINE, "auth", "status", "--json", "--causes"),
                    directory=image.directory,
                    environment=environment,
                    timeout=timeout,
                    output_limit=4096,
                )
            finally:
                self._release_runner(runner)
            return _parsed_statuses(completed)
        except (AgentProgramRefusalError, AgentHostError, RefusalError, OSError, ValueError):
            return _failed(CliStateCause.STATUS_READ_FAILED)

    def _claim_runner(self) -> WindowsAgentInvocationRunner | None:
        """Start one supplier runner, or none while an earlier one's scope is unconfirmed."""
        with self._runner_lock:
            if self._unsettled_runner is not None:
                return None
            runner = WindowsAgentInvocationRunner(cancellation=self._cancellation)
            self._active_runner = runner
            return runner

    def _release_runner(self, runner: WindowsAgentInvocationRunner) -> None:
        """Retain a runner whose scope did not settle, so no later read starts beside it."""
        with self._runner_lock:
            if self._active_runner is runner:
                self._active_runner = None
            if not runner.settled:
                self._unsettled_runner = runner


def _status_environment(root: Path) -> dict[str, str]:
    environment = system_environment(os.environ)
    environment[HOSTED_ROOT_VARIABLE] = str(root)
    external = agent_binary_directories(python=hosted_python(), received=os.environ)
    if external is not None and external != "":
        environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
    return environment


def _parsed_statuses(completed: AgentInvocationResult) -> _Reading:
    if completed.status != 0:
        return _failed(CliStateCause.STATUS_READ_FAILED)
    try:
        result = _Statuses.model_validate_json(completed.standard_output)
    except ValueError:
        return _failed(CliStateCause.STATUS_UNREADABLE)
    return _Reading(
        result.providers,
        {provider: None if cause is None else CliStateCause(cause) for provider, cause in result.causes.items()},
    )
