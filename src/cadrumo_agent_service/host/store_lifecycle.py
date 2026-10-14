"""Bring a hosted agent root's stores to the running agent build before its gateway starts.

A hosted gateway only checks its two stores and refuses to start on stores that
do not match its build, a fresh root included; the host owns their lifecycle.
Before every gateway start the runtime runs the agent's own one-shot
invocations, with the gateway's program, directory and environment:

* ``version --json``: the agent's command-line contract must be ``v1``.
* ``stores-state``: read-only. ``absent`` runs ``setup``; ``older`` copies the
  stores aside and runs ``migrate`` with the revisions the state reported;
  ``current`` runs nothing; ``newer`` is a downgrade and is refused.
* ``stores-state`` again, which must read ``current``.

Each invocation writes one JSON object on standard output, parsed whole and
strictly; its standard error is diagnostic only and is never read. Each has a
hard time bound, after which its whole tree is ended. A ``setup`` or
``migrate`` whose outcome is not known is never retried within the start.

The copy taken before ``migrate`` is the agent's rollback snapshot. While it is
kept and the stores do not read ``current``, every start is refused, so no
second ``migrate`` runs over stores whose state is unsettled. It is removed as
soon as the stores read ``current``.

Diagnostics name a closed step and outcome only: never a path, a revision or the
agent's own text.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cadrumo.core.logging import get_logger

from .controller import AgentHostError, AgentHostRefusal, AgentLaunch

_LOGGER = get_logger(__name__)

AGENT_COMMAND_LINE_API: Final = "v1"
"""The one version of the agent's command-line contract this host speaks."""
STORE_OUTPUT_MAX_BYTES: Final = 64 * 1024
"""More standard output than any of the four invocations writes; a longer output is malformed."""

_REVISION_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$"
"""An opaque revision: a short token that cannot be read as an option when passed back as an argument."""

type StoreState = Literal["absent", "current", "older", "newer"]


class StoreStep(StrEnum):
    """The invocation or host action a diagnostic concerns."""

    VERSION = "version"
    STORES_STATE = "stores_state"
    SETUP = "setup"
    COPY_ASIDE = "copy_aside"
    MIGRATE = "migrate"
    RECHECK = "recheck"


class StoreOutcome(StrEnum):
    """Why a step did not bring the stores to current."""

    RUN_FAILED = "run_failed"
    """The invocation could not be started, or the end of its tree could not be confirmed."""
    TIMED_OUT = "timed_out"
    """The invocation was ended at its bound: whether it changed the stores is not known."""
    MALFORMED = "malformed"
    FAILED = "failed"
    INCOMPATIBLE = "incompatible"
    NEWER = "newer"
    NOT_QUIESCED = "not_quiesced"
    COPY_KEPT = "copy_kept"
    NOT_CURRENT = "not_current"


@dataclass(frozen=True, slots=True)
class StoreLifecycleBounds:
    """The hard time bound of each invocation, in seconds."""

    version: float = 15.0
    stores_state: float = 20.0
    setup: float = 45.0
    migrate: float = 90.0


@dataclass(frozen=True, slots=True)
class AgentInvocationResult:
    """What a one-shot invocation left: its exit status, or ``None`` when it was ended at its bound."""

    status: int | None
    standard_output: bytes


class AgentInvocationRunner(Protocol):
    """Run one agent invocation to completion in a contained tree that is ended whole afterwards."""

    def run(
        self,
        *,
        executable: Path,
        arguments: Sequence[str],
        directory: Path,
        environment: Mapping[str, str],
        timeout: float,
        output_limit: int,
    ) -> AgentInvocationResult:
        """Return the status and at most ``output_limit + 1`` bytes of standard output.

        Raise when the tree cannot be started, or when its end cannot be
        confirmed; the caller then knows nothing about what it did.
        """
        ...


class AgentStoresAside(Protocol):
    """The host's one copy of a hosted root's stores, taken before a migrate."""

    def clear_partial(self) -> None:
        """Remove a copy an interrupted start left unfinished; no migrate ran after it."""
        ...

    def kept(self) -> bool:
        """Whether a complete copy exists."""
        ...

    def keep(self) -> None:
        """Copy the stores aside durably, publishing the copy only once it is complete."""
        ...

    def discard(self) -> None:
        """Remove the complete copy."""
        ...


_STRICT: Final = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Version(BaseModel):
    model_config = _STRICT

    api_version: str = Field(max_length=16)
    package_version: str = Field(min_length=1, max_length=64)


class _StoreJudgement(BaseModel):
    model_config = _STRICT

    state: StoreState
    found: str | None = Field(max_length=64)
    expected: str = Field(max_length=64)


class _StoresState(BaseModel):
    model_config = _STRICT

    state: StoreState
    primary: _StoreJudgement
    checkpoint: _StoreJudgement


class _StoreChange(BaseModel):
    model_config = _STRICT

    store: Literal["primary", "checkpoint"]
    status: Literal["migrated", "initialized", "failed"]
    from_revision: str | None = Field(max_length=64)
    to_revision: str | None = Field(max_length=64)
    schema_version: str | None = Field(max_length=64)


class _StoreStepResult(BaseModel):
    model_config = _STRICT

    status: Literal["succeeded", "failed", "already-initialized"]
    target_head: str | None = Field(max_length=64)
    stores: tuple[_StoreChange, ...] = Field(max_length=8)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    failed_stage: Literal["precondition", "lock", "primary", "checkpoint", "checkpoint-identity", "compact"] | None
    # The agent's own text and its home's path: read for shape only and never shown.
    error_class: str | None = Field(repr=False)
    detail: str | None = Field(repr=False)
    app_home: str = Field(repr=False)


class AgentStoreLifecycle:
    """Run the store sequence for one gateway launch; every refusal is a typed ``AgentHostError``."""

    def __init__(
        self,
        *,
        runner: AgentInvocationRunner,
        launch: AgentLaunch,
        command_line: tuple[str, ...],
        aside: AgentStoresAside,
        quiesced: Callable[[], bool],
        bounds: StoreLifecycleBounds | None = None,
    ) -> None:
        """Bind the gateway's own launch, the agent's command-line prefix, the copy and the quiescence check.

        ``command_line`` is the arguments that name the agent's command-line
        module; each invocation appends its verb. ``quiesced`` answers whether
        no other tree of the profile is starting, running or being reaped.
        """
        self._runner = runner
        self._launch = launch
        self._command_line = command_line
        self._aside = aside
        self._quiesced = quiesced
        self._bounds = StoreLifecycleBounds() if bounds is None else bounds

    def prepare(self) -> None:
        """Bring the stores to current, or refuse with the closed reason the launcher maps."""
        self._require_api()
        self._run_host_action(StoreStep.COPY_ASIDE, self._aside.clear_partial)
        state = self._stores_state(StoreStep.STORES_STATE)
        kept = self._run_host_action(StoreStep.COPY_ASIDE, self._aside.kept)
        if kept:
            if state.state != "current":
                raise _refused(StoreStep.STORES_STATE, StoreOutcome.COPY_KEPT)
            # An earlier migrate did finish: its rollback snapshot is no longer needed.
            self._run_host_action(StoreStep.COPY_ASIDE, self._aside.discard)
            return
        if state.state == "current":
            return
        if state.state == "newer":
            raise _refused(StoreStep.STORES_STATE, StoreOutcome.NEWER, AgentHostRefusal.STORES_NEWER)
        if state.state == "absent":
            self._setup()
        else:
            self._migrate(state)
        if self._stores_state(StoreStep.RECHECK).state != "current":
            raise _refused(StoreStep.RECHECK, StoreOutcome.NOT_CURRENT)
        if self._run_host_action(StoreStep.COPY_ASIDE, self._aside.kept):
            self._run_host_action(StoreStep.COPY_ASIDE, self._aside.discard)

    def _require_api(self) -> None:
        result = self._invoke(StoreStep.VERSION, ("version", "--json"), self._bounds.version)
        if result.status != 0:
            raise _refused(StoreStep.VERSION, StoreOutcome.FAILED)
        version = _parse(StoreStep.VERSION, _Version, result.standard_output)
        if version.api_version != AGENT_COMMAND_LINE_API:
            raise _refused(StoreStep.VERSION, StoreOutcome.INCOMPATIBLE, AgentHostRefusal.AGENT_INCOMPATIBLE)

    def _stores_state(self, step: StoreStep) -> _StoresState:
        result = self._invoke(step, ("stores-state",), self._bounds.stores_state)
        if result.status != 0:
            # The verb is read-only and always exits 0: any other status is an agent that did not answer.
            raise _refused(step, StoreOutcome.FAILED)
        return _parse(step, _StoresState, result.standard_output)

    def _setup(self) -> None:
        result = self._invoke(StoreStep.SETUP, ("setup",), self._bounds.setup)
        _require_step_success(StoreStep.SETUP, result, succeeded=frozenset({"succeeded", "already-initialized"}))

    def _migrate(self, state: _StoresState) -> None:
        found, expected = state.primary.found, state.primary.expected
        if found is None or not _is_revision(found) or not _is_revision(expected):
            raise _refused(StoreStep.MIGRATE, StoreOutcome.MALFORMED)
        if not self._quiesced():
            raise _refused(StoreStep.MIGRATE, StoreOutcome.NOT_QUIESCED)
        self._run_host_action(StoreStep.COPY_ASIDE, self._aside.keep)
        # From here the copy is kept until the stores read current: a failed or unknown migrate leaves it.
        result = self._invoke(
            StoreStep.MIGRATE, ("migrate", "--expect-from", found, "--expect-head", expected), self._bounds.migrate
        )
        _require_step_success(StoreStep.MIGRATE, result, succeeded=frozenset({"succeeded"}))

    def _invoke(self, step: StoreStep, verb: tuple[str, ...], timeout: float) -> AgentInvocationResult:
        try:
            result = self._runner.run(
                executable=self._launch.executable,
                arguments=(*self._command_line, *verb),
                directory=self._launch.directory,
                environment=self._launch.environment,
                timeout=timeout,
                output_limit=STORE_OUTPUT_MAX_BYTES,
            )
        except Exception as error:
            raise _refused(step, StoreOutcome.RUN_FAILED) from error
        if result.status is None:
            raise _refused(step, StoreOutcome.TIMED_OUT)
        return result

    def _run_host_action[T](self, step: StoreStep, action: Callable[[], T]) -> T:
        try:
            return action()
        except OSError as error:
            raise _refused(step, StoreOutcome.FAILED) from error


def _require_step_success(step: StoreStep, result: AgentInvocationResult, *, succeeded: frozenset[str]) -> None:
    """A ``setup`` or ``migrate`` succeeded only when its exit status and its reported status agree."""
    if result.status not in {0, 1}:
        # Any other status leaves nothing parseable on standard output.
        raise _refused(step, StoreOutcome.FAILED)
    report = _parse(step, _StoreStepResult, result.standard_output)
    if (result.status == 0) != (report.status in succeeded):
        raise _refused(step, StoreOutcome.MALFORMED)
    if result.status != 0:
        raise _refused(step, StoreOutcome.FAILED, stage=report.failed_stage or "unstated")


def _parse[M: BaseModel](step: StoreStep, model: type[M], output: bytes) -> M:
    if len(output) > STORE_OUTPUT_MAX_BYTES:
        raise _refused(step, StoreOutcome.MALFORMED)
    try:
        return model.model_validate_json(output)
    except ValidationError:
        # The validation error quotes the input, which may hold the agent's text: it is dropped, not chained.
        raise _refused(step, StoreOutcome.MALFORMED) from None


def _is_revision(value: str) -> bool:
    return re.fullmatch(_REVISION_PATTERN, value) is not None


def _refused(
    step: StoreStep,
    outcome: StoreOutcome,
    reason: AgentHostRefusal = AgentHostRefusal.STORES_UNPREPARED,
    *,
    stage: str = "none",
) -> AgentHostError:
    # Closed values only: the step, the outcome and the agent's own closed stage name.
    _LOGGER.warning(
        "agent stores not brought to current step=%s outcome=%s failed_stage=%s", step.value, outcome.value, stage
    )
    return AgentHostError(reason)
