"""The local AI as one setup item of the dependency registry: its program and every role's model.

The person sees, plans and sets up the local AI as one thing. Underneath it is
made of parts, each over the existing runtime lifecycle in
:mod:`.provisioning_host` and :mod:`.provisioning_runtime`:

* :class:`LocalAiProgramPart` is the program that runs models. Its quick check
  locates the program and asks its loopback version endpoint; setting it up
  runs the platform installer the person approved in the setup plan, then
  starts the program's server.
* :class:`LocalAiModelPart` is the model one catalogue role reads with. Its
  quick check finds the model in the program's inventory -- or, while the
  program is not running, in Cadrumo's own model store on disk -- and compares
  the installed digest with the one the catalogue pins. Its full check also
  loads the model when admission permits, generates one token, and asks the
  role's fitness probe. Setting it up fetches the model with byte progress,
  retrying a transient failure on the schedule the setup operation supplies.

:class:`LocalAiSetupItem` is the registry's provisioner. Its reading is the
worst of its parts' readings, so the local AI is ready only when the program
and every role's model are. Its plan lists the program, then the model of
each role that is not ready, and one setup carries them out in that order with
one progress figure over the whole download.

Roles may share one model. Each role keeps its own part, and the part names the
model and its pinned digest as the target version, so a plan counts one
download per distinct target; a later part whose model is already on disk
when its turn comes moves no byte.

Nothing here decides readiness after a setup: the setup operation runs the
item's independent full check afterwards. A check never downloads, installs or
starts anything, and reports what it cannot read as ``unreadable``.
"""

from __future__ import annotations

import asyncio
import shutil
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from time import monotonic
from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.config import Settings, load_settings
from ..core.model_catalogue import ModelRole, model_candidate
from ..core.storage_taxonomy import StorageCategory
from .dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyHostName,
    DependencyItemDeclaration,
    DependencyNote,
    DependencyPlanEntry,
    DependencyPlanPart,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencySetupEvents,
    DependencySetupStep,
    DependencyStaleReason,
    combine_plan_parts,
    known_part_bytes_of,
)
from .dependency_registry import LOCAL_AI_DECLARATION
from .local_reader import (
    FITNESS_PROBED_ROLES,
    RoleFitnessState,
    RoleModelTarget,
    TextExtractionFitnessProbe,
    recorded_role_fitness,
    role_model_targets,
    select_role_model,
    verify_role_target,
)
from .operator_actions.models import PreconditionVerdict
from .provisioning import LICENCE_ADVISORIES, ModelSelection, probe_model_runtime_hardware_floor
from .provisioning_contracts import (
    RUNTIME_MINIMUM_VERSION,
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
)
from .provisioning_host import (
    ExecutableLookup,
    InstallerRunner,
    RuntimeInstaller,
    RuntimeSpawner,
    available_runtime_installer,
    install_runtime,
    locate_runtime_executable,
    read_runtime_version,
    runtime_proxy_environment,
    start_runtime,
)
from .provisioning_runtime import (
    TRANSIENT_PULL_FAILURES,
    InstalledModel,
    PullFailureKind,
    PullOutcome,
    PullProgress,
    StoredWeightsState,
    assess_model_load_contention,
    fetch_runtime_model,
    normalised_weights_digest,
    read_installed_models,
    read_runtime_residents,
    read_stored_weights,
    runtime_model_names_match,
)

__all__ = [
    "LOCAL_AI_PROGRAM_PART",
    "HostReachability",
    "LocalAiModelPart",
    "LocalAiProgramPart",
    "LocalAiSetupItem",
    "TransferRetryDelay",
    "local_ai_setup_item",
    "pull_failure_category",
    "runtime_version_at_least",
]

LOCAL_AI_PROGRAM_PART: Final = "program"
"""The part id of the local AI program; every other part is named by the catalogue role its model serves."""

_ITEM_ID: Final = LOCAL_AI_DECLARATION.item_id

type HostReachability = Callable[[tuple[str, ...]], Awaitable[DependencyFailureCategory | None]]
"""Network preflight over an item's source hosts: ``None`` when every host is reachable.

Supplied by the composition root, which binds the shared preflight. Its answer
is one of the network failure categories: offline, a host that cannot be
reached, a secure connection that failed, or a network that blocks the host.
"""

type TransferRetryDelay = Callable[[int, float], float | None]
"""Backoff schedule for a transient transfer failure.

Called with the number of the attempt that just failed (from 1) and the seconds
since the first attempt began; returns the delay before the next attempt, or
``None`` when the retry budget is spent. Supplied by the composition root.
"""

_PROGRESS_POLL_S: Final = 0.5
_CANCEL_POLL_S: Final = 0.25

_PULL_FAILURE_CATEGORY: Final[Mapping[PullFailureKind, DependencyFailureCategory]] = {
    PullFailureKind.RUNTIME_UNREACHABLE: DependencyFailureCategory.PROGRAM_NOT_RUNNING,
    PullFailureKind.STALLED: DependencyFailureCategory.HOST_UNREACHABLE,
    PullFailureKind.TRUNCATED: DependencyFailureCategory.HOST_UNREACHABLE,
    PullFailureKind.CANCELLED: DependencyFailureCategory.CANCELLED,
    PullFailureKind.NETWORK_TRANSIENT: DependencyFailureCategory.HOST_UNREACHABLE,
    PullFailureKind.NAME_RESOLUTION: DependencyFailureCategory.HOST_UNREACHABLE,
    PullFailureKind.SECURE_CONNECTION: DependencyFailureCategory.SECURE_CONNECTION_FAILED,
    PullFailureKind.BLOCKED_BY_NETWORK: DependencyFailureCategory.BLOCKED_BY_NETWORK,
    PullFailureKind.DISK_FULL: DependencyFailureCategory.DISK_FULL,
    PullFailureKind.NO_PERMISSION: DependencyFailureCategory.NO_PERMISSION,
    PullFailureKind.INTEGRITY: DependencyFailureCategory.DAMAGED_DOWNLOAD,
    PullFailureKind.NOT_FOUND: DependencyFailureCategory.UNEXPECTED,
    PullFailureKind.OTHER: DependencyFailureCategory.UNEXPECTED,
}


def pull_failure_category(kind: PullFailureKind) -> DependencyFailureCategory:
    """Return the closed failure category a person sees for one fetch failure."""
    return _PULL_FAILURE_CATEGORY[kind]


def runtime_version_at_least(version: str, minimum: tuple[int, ...] = RUNTIME_MINIMUM_VERSION) -> bool | None:
    """Return whether a reported program version meets ``minimum``, or ``None`` when it does not parse."""
    numbers: list[int] = []
    for part in version.strip().removeprefix("v").split("-", 1)[0].split("."):
        if not part.isdigit():
            return None
        numbers.append(int(part))
    if not numbers:
        return None
    width = max(len(numbers), len(minimum))
    return tuple(numbers + [0] * (width - len(numbers))) >= tuple(list(minimum) + [0] * (width - len(minimum)))


def _reading(
    item_id: str,
    mode: DependencyCheckMode,
    outcome: DependencyProbeOutcome,
    *,
    stale: DependencyStaleReason | None = None,
    blocked: DependencyBlockedReason | None = None,
    failure: DependencyFailureCategory | None = None,
    note: DependencyNote | None = None,
    version: str | None = None,
    facts: Mapping[str, ProvisioningFactValue] | None = None,
) -> DependencyProbeReading:
    return DependencyProbeReading(
        item_id=item_id,
        mode=mode,
        outcome=outcome,
        stale_reason=stale,
        blocked_reason=blocked,
        failure_category=failure,
        note=note,
        version=version,
        facts={} if facts is None else dict(facts),
    )


def _network_reading(
    item_id: str,
    mode: DependencyCheckMode,
    category: DependencyFailureCategory,
    facts: Mapping[str, ProvisioningFactValue],
) -> DependencyProbeReading:
    """Return the reading of an item that is not installed and whose source the network keeps out of reach."""
    if category is DependencyFailureCategory.OFFLINE:
        return _reading(
            item_id, mode, DependencyProbeOutcome.BLOCKED, blocked=DependencyBlockedReason.OFFLINE, facts=facts
        )
    return _reading(item_id, mode, DependencyProbeOutcome.FAILED, failure=category, facts=facts)


async def _preflight(reachability: HostReachability | None, hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
    return None if reachability is None else await reachability(hosts)


class LocalAiProgramPart:
    """The program that runs local models: the first part of the local AI."""

    def __init__(
        self,
        *,
        source_hosts: tuple[DependencyHostName, ...],
        run_installer: InstallerRunner,
        spawn: RuntimeSpawner,
        reachability: HostReachability | None = None,
        which: ExecutableLookup = shutil.which,
    ) -> None:
        """Bind the program's download hosts and the installer, server-start and preflight ports."""
        if not source_hosts:
            raise ValueError("the local model program names the hosts it is installed from")
        self._hosts = source_hosts
        self._run_installer = run_installer
        self._spawn = spawn
        self._reachability = reachability
        self._which = which

    @property
    def _item_id(self) -> str:
        return _ITEM_ID

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Locate the program and ask whether it answers; a full check also asks for its model inventory."""
        reading = await asyncio.to_thread(self._local_reading, mode)
        if mode is DependencyCheckMode.FULL and reading.outcome is DependencyProbeOutcome.ABSENT:
            category = await _preflight(self._reachability, self._hosts)
            if category is not None:
                return _network_reading(self._item_id, mode, category, reading.facts)
        return reading

    def _local_reading(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        settings = load_settings()
        version = read_runtime_version(settings)
        located = locate_runtime_executable(which=self._which) is not None
        facts: dict[str, ProvisioningFactValue] = {
            "executable_located": located,
            "runtime_reachable": version is not None,
        }
        if version is not None:
            return self._answering_reading(mode, settings, version, facts)
        if located:
            return _reading(
                self._item_id,
                mode,
                DependencyProbeOutcome.FAILED,
                failure=DependencyFailureCategory.PROGRAM_NOT_RUNNING,
                facts=facts,
            )
        if available_runtime_installer(which=self._which) is RuntimeInstaller.NONE:
            # No installer Cadrumo may run here: the person installs the program.
            return _reading(
                self._item_id,
                mode,
                DependencyProbeOutcome.BLOCKED,
                blocked=DependencyBlockedReason.NEEDS_PERSON,
                facts=facts,
            )
        return _reading(self._item_id, mode, DependencyProbeOutcome.ABSENT, facts=facts)

    def _answering_reading(
        self,
        mode: DependencyCheckMode,
        settings: Settings,
        version: str,
        facts: dict[str, ProvisioningFactValue],
    ) -> DependencyProbeReading:
        if mode is DependencyCheckMode.FULL and read_installed_models(settings) is None:
            return _reading(self._item_id, mode, DependencyProbeOutcome.UNREADABLE, facts=facts)
        # A program that already answers may have been started outside Cadrumo,
        # with its own network settings rather than Cadrumo's proxy.
        note = DependencyNote.OWN_NETWORK_SETTINGS if runtime_proxy_environment(settings) else None
        reported = None if version == "unknown" else version
        meets = None if reported is None else runtime_version_at_least(reported)
        if meets is False:
            return _reading(
                self._item_id,
                mode,
                DependencyProbeOutcome.DIFFERS,
                stale=DependencyStaleReason.PROGRAM_TOO_OLD,
                note=note,
                version=reported,
                facts=facts,
            )
        return _reading(self._item_id, mode, DependencyProbeOutcome.PRESENT, note=note, version=reported, facts=facts)

    async def plan(self) -> DependencyPlanPart:
        """Plan an install when the program is missing or too old, otherwise only a start of its server."""
        reading = await asyncio.to_thread(self._local_reading, DependencyCheckMode.QUICK)
        needs_installer = reading.outcome in {
            DependencyProbeOutcome.ABSENT,
            DependencyProbeOutcome.BLOCKED,
            DependencyProbeOutcome.DIFFERS,
        }
        return DependencyPlanPart(
            part_id=LOCAL_AI_PROGRAM_PART,
            # The platform installer does not say in advance how much it fetches.
            download_bytes=None if needs_installer else 0,
            source_hosts=self._hosts,
            destination=None if needs_installer else StorageCategory.OLLAMA_HOME,
            installs_outside_program=needs_installer,
        )

    async def provision(self, part: DependencyPlanPart, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Install the program when the plan says so, then make its server answer."""
        if part.part_id != LOCAL_AI_PROGRAM_PART:
            raise ValueError("plan part belongs to another part of the local AI")
        changed = False
        if part.installs_outside_program:
            if events.cancellation_requested:
                return self._result(changed=False, failure=DependencyFailureCategory.CANCELLED)
            await events.step(DependencySetupStep.INSTALL)
            located = await asyncio.to_thread(locate_runtime_executable, which=self._which)
            # The installer runs to its end once started, and replaces an older
            # program in place, so cancellation waits for it.
            async with events.irreversible():
                installed = await asyncio.to_thread(
                    install_runtime,
                    run=self._run_installer,
                    which=self._which,
                    replace_existing=located is not None,
                )
            if not installed.installed:
                return self._result(
                    changed=installed.installer_exit_code is not None, failure=_install_failure(installed.facts)
                )
            changed = not installed.already_installed
        if events.cancellation_requested:
            return self._result(changed=changed, failure=DependencyFailureCategory.CANCELLED)
        await events.step(DependencySetupStep.INSTALL)
        started = await asyncio.to_thread(start_runtime, spawn=self._spawn, which=self._which)
        if not started.running:
            return self._result(changed=changed, failure=_start_failure(started.precondition_verdict))
        return self._result(changed=changed or not started.already_running, facts=dict(started.facts))

    def _result(
        self,
        *,
        changed: bool,
        failure: DependencyFailureCategory | None = None,
        facts: Mapping[str, ProvisioningFactValue] | None = None,
    ) -> DependencyProvisionResult:
        return DependencyProvisionResult(
            item_id=self._item_id, changed=changed, failure_category=failure, facts={} if facts is None else dict(facts)
        )


def _install_failure(facts: Mapping[str, ProvisioningFactValue]) -> DependencyFailureCategory:
    if facts.get("installer") == RuntimeInstaller.NONE.value:
        return DependencyFailureCategory.PROGRAM_MISSING
    if facts.get("install_error_type") == PermissionError.__name__:
        return DependencyFailureCategory.NO_PERMISSION
    return DependencyFailureCategory.UNEXPECTED


def _start_failure(verdict: PreconditionVerdict | None) -> DependencyFailureCategory:
    condition = None if verdict is None else verdict.failed_condition_id
    if condition == ProvisioningPreconditionCondition.RUNTIME_INSTALLED.value:
        return DependencyFailureCategory.PROGRAM_MISSING
    return DependencyFailureCategory.PROGRAM_NOT_RUNNING


class _TransferRelay:
    """Carries the latest per-layer fetch figures from the worker thread to the event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._layers: dict[str, int] = {}
        self._published: int | None = None

    def record(self, progress: PullProgress) -> None:
        if progress.completed_bytes is None:
            return
        with self._lock:
            self._layers[progress.digest or ""] = progress.completed_bytes

    def completed(self) -> int:
        with self._lock:
            return sum(self._layers.values())

    async def publish(self, events: DependencySetupEvents, total: int | None) -> None:
        completed = self.completed()
        if total is not None:
            completed = min(completed, total)
        if completed == self._published:
            return
        self._published = completed
        await events.transferred(completed=completed, total=total)


_READINESS_FAILURES: Final[Mapping[str, DependencyFailureCategory]] = {
    ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value: DependencyFailureCategory.PROGRAM_NOT_RUNNING,
    ProvisioningPreconditionCondition.MODEL_INSTALLED.value: DependencyFailureCategory.DAMAGED_DOWNLOAD,
}


class LocalAiModelPart:
    """The model one catalogue role reads with: one part of the local AI."""

    def __init__(
        self,
        role: ModelRole,
        *,
        source_hosts: tuple[DependencyHostName, ...],
        retry_delay: TransferRetryDelay,
        text_probe: TextExtractionFitnessProbe | None = None,
        reachability: HostReachability | None = None,
    ) -> None:
        """Bind the role, the model registry hosts, the retry schedule and the fitness and preflight ports."""
        if not source_hosts:
            raise ValueError("a local model names the hosts it is downloaded from")
        self._role = role
        self._hosts = source_hosts
        self._retry_delay = retry_delay
        self._text_probe = text_probe
        self._reachability = reachability

    @property
    def role(self) -> ModelRole:
        """The catalogue role this part's model serves."""
        return self._role

    @property
    def _item_id(self) -> str:
        return _ITEM_ID

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Find the role's model and compare its digest; a full check also loads, answers and judges fitness."""
        reading = await asyncio.to_thread(self._local_reading, mode)
        if mode is not DependencyCheckMode.FULL:
            return reading
        if reading.outcome is DependencyProbeOutcome.ABSENT:
            category = await _preflight(self._reachability, self._hosts)
            return reading if category is None else _network_reading(self._item_id, mode, category, reading.facts)
        if reading.outcome in {DependencyProbeOutcome.PRESENT, DependencyProbeOutcome.DIFFERS}:
            return await asyncio.to_thread(self._exercised_reading, reading)
        return reading

    def _selection(self, settings: Settings, *, explicit: str | None = None) -> ModelSelection:
        # Catalogue selection, honouring an operator-set model, is what the
        # role's reader would use: it keeps the capability and licence bars a
        # default configuration relies on.
        return select_role_model(self._role, settings, explicit=explicit)

    def _model(self, settings: Settings) -> str | None:
        return _selected_model(self._selection(settings))

    def _local_reading(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        settings = load_settings()
        floor = probe_model_runtime_hardware_floor(settings)
        if not floor.available:
            return _reading(
                self._item_id,
                mode,
                DependencyProbeOutcome.BLOCKED,
                blocked=DependencyBlockedReason.HARDWARE,
                facts=floor.facts,
            )
        model = self._model(settings)
        if model is None:
            return self._selection_refusal(mode, settings)
        facts: dict[str, ProvisioningFactValue] = {"model": model}
        inventory = read_installed_models(settings)
        if inventory is None:
            return self._stored_reading(mode, settings, model, facts)
        entry = next((row for row in inventory if runtime_model_names_match(model, row.name)), None)
        if entry is None:
            return _reading(
                self._item_id, mode, DependencyProbeOutcome.ABSENT, facts={**facts, "model_installed": False}
            )
        facts["model_installed"] = True
        return self._digest_reading(mode, settings, model, entry.digest, facts)

    def _selection_refusal(self, mode: DependencyCheckMode, settings: Settings) -> DependencyProbeReading:
        # No catalogued model clears the role's capability and licence bars.
        selection = self._selection(settings)
        return _reading(
            self._item_id,
            mode,
            DependencyProbeOutcome.FAILED,
            failure=DependencyFailureCategory.UNEXPECTED,
            facts=dict(selection.facts),
        )

    def _stored_reading(
        self,
        mode: DependencyCheckMode,
        settings: Settings,
        model: str,
        facts: dict[str, ProvisioningFactValue],
    ) -> DependencyProbeReading:
        # The program is not answering, so Cadrumo's own store is read instead:
        # the store the program uses whenever Cadrumo starts it.
        stored = read_stored_weights(model, settings)
        facts = {**facts, "runtime_reachable": False, "stored_weights": stored.state.value}
        if stored.state is StoredWeightsState.UNREADABLE:
            return _reading(self._item_id, mode, DependencyProbeOutcome.UNREADABLE, facts=facts)
        if stored.state is not StoredWeightsState.COMPLETE:
            # A partial download is not a model; the next setup resumes it.
            return _reading(self._item_id, mode, DependencyProbeOutcome.ABSENT, facts=facts)
        return self._digest_reading(mode, settings, model, stored.digest, facts)

    def _digest_reading(
        self,
        mode: DependencyCheckMode,
        settings: Settings,
        model: str,
        digest: str | None,
        facts: dict[str, ProvisioningFactValue],
    ) -> DependencyProbeReading:
        candidate = model_candidate(model)
        pin = None if candidate is None else candidate.weights_pin
        if pin is None or digest is None or normalised_weights_digest(digest) == pin.digest:
            return _reading(self._item_id, mode, DependencyProbeOutcome.PRESENT, version=model, facts=facts)
        facts = {**facts, "pinned_digest_matches": False}
        if self._role in FITNESS_PROBED_ROLES:
            # A different version than the one tested: the role's recorded
            # fitness for exactly these weights decides between stale and failed.
            state = recorded_role_fitness(self._role, model, digest, settings)
            if state is RoleFitnessState.UNFIT:
                return _reading(
                    self._item_id,
                    mode,
                    DependencyProbeOutcome.FAILED,
                    failure=DependencyFailureCategory.UNEXPECTED,
                    facts=facts,
                )
            if state is RoleFitnessState.TIMED_OUT:
                return _reading(
                    self._item_id,
                    mode,
                    DependencyProbeOutcome.BLOCKED,
                    blocked=DependencyBlockedReason.HARDWARE,
                    facts=facts,
                )
        return _reading(
            self._item_id,
            mode,
            DependencyProbeOutcome.DIFFERS,
            stale=DependencyStaleReason.DIFFERENT_MODEL_VERSION,
            version=model,
            facts=facts,
        )

    def _exercised_reading(self, reading: DependencyProbeReading) -> DependencyProbeReading:
        """Load the model when admission permits, generate one token, and ask the role's fitness probe."""
        settings = load_settings()
        model = self._model(settings)
        if model is None:
            return reading
        residents = read_runtime_residents(settings)
        if residents is None:
            # Downloaded, but the program is not answering to load it.
            return reading.model_copy(update={"note": DependencyNote.DOWNLOADED_NOT_LOADED})
        requirement = _requirement_bytes(self._role, model, settings)
        resident = any(runtime_model_names_match(model, row.name) for row in residents)
        if not resident:
            if requirement is None:
                return reading.model_copy(update={"note": DependencyNote.DOWNLOADED_NOT_LOADED})
            snapshot = assess_model_load_contention(model, requirement, residents=residents, settings=settings)
            if not snapshot.admitted:
                return reading.model_copy(update={"note": DependencyNote.DOWNLOADED_NOT_LOADED})
        verified = verify_role_target(
            RoleModelTarget(model=model, roles=(self._role,), requirement_bytes=requirement),
            settings=settings,
            text_probe=self._text_probe,
        )
        if verified.ready:
            return reading
        condition = "" if verified.precondition_verdict is None else verified.precondition_verdict.failed_condition_id
        facts = {**reading.facts, "model_answered": verified.answered, "readiness_condition": condition}
        if condition == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT.value:
            return _reading(
                self._item_id,
                reading.mode,
                DependencyProbeOutcome.BLOCKED,
                blocked=DependencyBlockedReason.HARDWARE,
                facts=facts,
            )
        failure = _READINESS_FAILURES.get(condition, DependencyFailureCategory.UNEXPECTED)
        return _reading(self._item_id, reading.mode, DependencyProbeOutcome.FAILED, failure=failure, facts=facts)

    async def plan(self, *, model_name: str | None) -> DependencyPlanPart:
        """Plan the fetch of this role's model, or of ``model_name`` when the person named one."""
        settings = await asyncio.to_thread(load_settings)
        selection = await asyncio.to_thread(lambda: self._selection(settings, explicit=model_name))
        model = _selected_model(selection)
        candidate = None if model is None else model_candidate(model)
        pin = None if candidate is None else candidate.weights_pin
        target = None if model is None else (model if pin is None else f"{model}@{pin.digest}")
        return DependencyPlanPart(
            part_id=self._role.value,
            download_bytes=None if pin is None else pin.download_bytes,
            source_hosts=self._hosts,
            destination=StorageCategory.OLLAMA_MODELS,
            target_version=target,
            advisories=tuple(advisory for advisory in selection.advisories if advisory in LICENCE_ADVISORIES),
        )

    async def provision(self, entry: DependencyPlanPart, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Fetch exactly the model the approved part names, retrying transient failures, keeping partial bytes."""
        if entry.part_id != self._role.value:
            raise ValueError("plan part belongs to another part of the local AI")
        if entry.target_version is None:
            # No model could be named when the plan was made: nothing to fetch.
            settings = await asyncio.to_thread(load_settings)
            refusal = await asyncio.to_thread(self._selection_refusal, DependencyCheckMode.QUICK, settings)
            return self._result(changed=False, failure=refusal.failure_category or DependencyFailureCategory.UNEXPECTED)
        model = entry.target_version.split("@", 1)[0]
        inventory = await asyncio.to_thread(read_installed_models)
        if inventory is None:
            return self._result(changed=False, failure=DependencyFailureCategory.PROGRAM_NOT_RUNNING)
        if _already_installed(model, entry.target_version, inventory):
            # Another role sharing this model fetched it earlier in the same setup.
            return self._result(changed=False, facts={"model": model, "model_installed": True})
        await events.step(DependencySetupStep.DOWNLOAD)
        return await self._fetch_with_retry(model, entry, events)

    async def _fetch_with_retry(
        self, model: str, entry: DependencyPlanPart, events: DependencySetupEvents
    ) -> DependencyProvisionResult:
        started = monotonic()
        attempt = 1
        relay = _TransferRelay()
        while True:
            outcome = await self._fetch_once(model, entry, events, relay)
            moved = relay.completed()
            if outcome.pulled:
                return self._result(changed=True, transferred=moved, facts=dict(outcome.facts))
            kind = outcome.failure_kind or PullFailureKind.OTHER
            if kind is PullFailureKind.CANCELLED or kind not in TRANSIENT_PULL_FAILURES:
                return self._result(changed=moved > 0, failure=pull_failure_category(kind), transferred=moved)
            delay = self._retry_delay(attempt, monotonic() - started)
            if delay is None:
                return self._result(changed=moved > 0, failure=pull_failure_category(kind), transferred=moved)
            attempt += 1
            await events.retrying(attempt=attempt, delay_s=delay)
            if await _cancelled_while_waiting(events, delay):
                return self._result(changed=moved > 0, failure=DependencyFailureCategory.CANCELLED, transferred=moved)

    async def _fetch_once(
        self, model: str, entry: DependencyPlanPart, events: DependencySetupEvents, relay: _TransferRelay
    ) -> PullOutcome:
        stop = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(fetch_runtime_model, model, on_progress=relay.record, stop=stop))
        while not task.done():
            await asyncio.wait({task}, timeout=_PROGRESS_POLL_S)
            if events.cancellation_requested:
                stop.set()
            await relay.publish(events, entry.download_bytes)
        return task.result()

    def _result(
        self,
        *,
        changed: bool,
        failure: DependencyFailureCategory | None = None,
        transferred: int = 0,
        facts: Mapping[str, ProvisioningFactValue] | None = None,
    ) -> DependencyProvisionResult:
        return DependencyProvisionResult(
            item_id=self._item_id,
            changed=changed,
            failure_category=failure,
            transferred_bytes=transferred,
            facts={} if facts is None else dict(facts),
        )


def _selected_model(selection: ModelSelection) -> str | None:
    """Return the model a role is set up with, or ``None`` when no catalogued model can serve it.

    Selection also refuses when free memory is short this moment. That says
    nothing about which model to download, so the smallest eligible model it
    names is still the one set up; whether it may load is decided when it
    loads, and until then it reads as downloaded but not loaded.
    """
    if selection.selected:
        return selection.runtime_id
    verdict = selection.precondition_verdict
    if verdict is None or verdict.failed_condition_id != ProvisioningPreconditionCondition.SELECTED_MODEL_FITS.value:
        return None
    named = selection.facts.get("selected_model")
    return named if isinstance(named, str) and named else None


def _requirement_bytes(role: ModelRole, model: str, settings: Settings) -> int | None:
    target = next(
        (
            target
            for target in role_model_targets((role,), settings)
            if target.model is not None and runtime_model_names_match(model, target.model)
        ),
        None,
    )
    return None if target is None else target.requirement_bytes


def _already_installed(model: str, target_version: str, inventory: tuple[InstalledModel, ...]) -> bool:
    _, _, pinned = target_version.partition("@")
    entry = next((row for row in inventory if runtime_model_names_match(model, row.name)), None)
    if entry is None:
        return False
    return not pinned or (entry.digest is not None and normalised_weights_digest(entry.digest) == pinned)


async def _cancelled_while_waiting(events: DependencySetupEvents, delay_s: float) -> bool:
    deadline = monotonic() + delay_s
    while True:
        if events.cancellation_requested:
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(_CANCEL_POLL_S, remaining))


_USABLE: Final = frozenset({DependencyProbeOutcome.PRESENT, DependencyProbeOutcome.DIFFERS})


def _first(
    readings: Sequence[DependencyProbeReading], outcome: DependencyProbeOutcome
) -> DependencyProbeReading | None:
    return next((reading for reading in readings if reading.outcome is outcome), None)


def _hardware_block(readings: Sequence[DependencyProbeReading]) -> DependencyProbeReading | None:
    return next(
        (
            reading
            for reading in readings
            if reading.outcome is DependencyProbeOutcome.BLOCKED
            and reading.blocked_reason is DependencyBlockedReason.HARDWARE
        ),
        None,
    )


def _combined_reading(
    mode: DependencyCheckMode,
    program: DependencyProbeReading,
    models: Sequence[tuple[ModelRole, DependencyProbeReading]],
) -> DependencyProbeReading:
    """Return the local AI's one reading: the worst of its parts', the program's first among equals.

    A computer below the model floor decides first, because nothing set up here
    changes it. Then a part that could not be read, then a failure, then a
    block, then anything missing, then anything that differs from what was
    tested. Only when every part is present is the local AI present.
    """
    facts: dict[str, ProvisioningFactValue] = {f"program.{key}": value for key, value in program.facts.items()}
    for role, reading in models:
        facts.update({f"{role.value}.{key}": value for key, value in reading.facts.items()})
    parts = (program, *(reading for _role, reading in models))
    decisive = (
        _hardware_block(parts)
        or _first(parts, DependencyProbeOutcome.UNREADABLE)
        or _first(parts, DependencyProbeOutcome.FAILED)
        or _first(parts, DependencyProbeOutcome.BLOCKED)
        or _first(parts, DependencyProbeOutcome.ABSENT)
        or _first(parts, DependencyProbeOutcome.DIFFERS)
    )
    if decisive is not None and decisive.outcome not in _USABLE:
        return _reading(
            _ITEM_ID,
            mode,
            decisive.outcome,
            blocked=decisive.blocked_reason,
            failure=decisive.failure_category,
            version=program.version,
            facts=facts,
        )
    note = next((reading.note for reading in parts if reading.note is not None), None)
    if decisive is not None:
        return _reading(
            _ITEM_ID,
            mode,
            DependencyProbeOutcome.DIFFERS,
            stale=decisive.stale_reason,
            note=note,
            version=program.version,
            facts=facts,
        )
    return _reading(_ITEM_ID, mode, DependencyProbeOutcome.PRESENT, note=note, version=program.version, facts=facts)


class _PartEvents:
    """One part's view of the item's event port: its bytes counted after the parts before it.

    The person follows one figure for the whole local AI, so a part's transfer
    is reported as the bytes of the earlier parts plus its own, against the
    item's total. A part whose download an earlier part already fetched
    reports no bytes of its own.
    """

    def __init__(self, events: DependencySetupEvents, *, offset: int, own: int, total: int) -> None:
        self._events = events
        self._offset = offset
        self._own = own
        self._total = total

    async def step(self, step: DependencySetupStep) -> None:
        await self._events.step(step)

    async def transferred(self, *, completed: int, total: int | None) -> None:
        del total
        if self._own <= 0 or self._total <= 0:
            return
        await self._events.transferred(completed=self._offset + min(completed, self._own), total=self._total)

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        await self._events.retrying(attempt=attempt, delay_s=delay_s)

    @property
    def cancellation_requested(self) -> bool:
        return self._events.cancellation_requested

    def irreversible(self) -> AbstractAsyncContextManager[None]:
        return self._events.irreversible()


class LocalAiSetupItem:
    """The local AI -- its program and every role's model -- as one item of the setup registry."""

    def __init__(self, program: LocalAiProgramPart, models: Sequence[LocalAiModelPart]) -> None:
        """Bind the program part and one model part per catalogue role, in catalogue order."""
        roles = [model.role for model in models]
        if roles != list(ModelRole):
            raise ValueError("the local AI has one model part per catalogue role, in catalogue order")
        self._program = program
        self._models = tuple(models)

    @property
    def declaration(self) -> DependencyItemDeclaration:
        """The registry declaration of the local AI."""
        return LOCAL_AI_DECLARATION

    async def _model_readings(self, mode: DependencyCheckMode) -> list[tuple[ModelRole, DependencyProbeReading]]:
        if mode is DependencyCheckMode.QUICK:
            readings = await asyncio.gather(*(model.check(mode) for model in self._models))
            return [(model.role, reading) for model, reading in zip(self._models, readings, strict=True)]
        # A full check may load each model in turn; one at a time keeps memory predictable.
        return [(model.role, await model.check(mode)) for model in self._models]

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Check the program and every role's model; the local AI reads as the worst of them."""
        program = await self._program.check(mode)
        return _combined_reading(mode, program, await self._model_readings(mode))

    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        """Plan the program, then the model of each role that is not ready, or of every role for ``model_name``.

        The program part is always planned: when it is already installed it
        only starts the program's server, which every model fetch needs.
        """
        program = await self._program.plan()
        parts: list[DependencyPlanPart] = [program]
        for model in self._models:
            if model_name is None:
                reading = await model.check(DependencyCheckMode.QUICK)
                if reading.outcome is DependencyProbeOutcome.PRESENT:
                    continue
            parts.append(await model.plan(model_name=model_name))
        destination = StorageCategory.OLLAMA_MODELS if len(parts) > 1 else program.destination
        return combine_plan_parts(_ITEM_ID, tuple(parts), destination=destination)

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Carry out each approved part in order, stopping at the first that does not finish."""
        if entry.item_id != _ITEM_ID:
            raise ValueError("plan entry belongs to another setup item")
        models = {model.role.value: model for model in self._models}
        total = entry.download_bytes or 0
        changed = False
        transferred = 0
        for index, part in enumerate(entry.parts):
            offset = known_part_bytes_of(entry.parts[:index])
            own = known_part_bytes_of(entry.parts[: index + 1]) - offset
            scoped = _PartEvents(events, offset=offset, own=own, total=total)
            if part.part_id == LOCAL_AI_PROGRAM_PART:
                result = await self._program.provision(part, scoped)
            else:
                result = await models[part.part_id].provision(part, scoped)
            changed = changed or result.changed
            transferred += result.transferred_bytes
            if result.failure_category is not None:
                return DependencyProvisionResult(
                    item_id=_ITEM_ID,
                    changed=changed,
                    failure_category=result.failure_category,
                    transferred_bytes=transferred,
                )
        return DependencyProvisionResult(item_id=_ITEM_ID, changed=changed, transferred_bytes=transferred)


def local_ai_setup_item(
    *,
    runtime_hosts: tuple[DependencyHostName, ...],
    model_hosts: tuple[DependencyHostName, ...],
    run_installer: InstallerRunner,
    spawn: RuntimeSpawner,
    retry_delay: TransferRetryDelay,
    text_probe: TextExtractionFitnessProbe | None = None,
    reachability: HostReachability | None = None,
) -> LocalAiSetupItem:
    """Return the local AI's setup item: its program part and one model part per catalogue role."""
    return LocalAiSetupItem(
        LocalAiProgramPart(
            source_hosts=runtime_hosts, run_installer=run_installer, spawn=spawn, reachability=reachability
        ),
        tuple(
            LocalAiModelPart(
                role,
                source_hosts=model_hosts,
                retry_delay=retry_delay,
                text_probe=text_probe,
                reachability=reachability,
            )
            for role in ModelRole
        ),
    )
