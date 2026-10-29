"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

import os
from abc import abstractmethod
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import Any, override
from uuid import uuid4

from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    OrchestrationTimeoutError,
    TimeoutDeadline,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest

from .adapters.agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from .adapters.agent_programs import (
    AGENT_COMMAND_LINE,
    HostedStoresAside,
    agent_image,
    hosted_aeat,
    hosted_python,
    hosted_relay,
    profile_agent_root,
    profile_agent_workspace,
)
from .host.auth_attempt import AuthAttempt
from .host.controller import (
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    AgentReady,
)
from .host.launch_environment import (
    AUTH_BROWSER_EXECUTABLE_VARIABLE,
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    agent_binary_directories,
    agent_launch_environment,
    auth_browser_executable,
    system_environment,
)
from .host.store_lifecycle import (
    INVOCATION_TERMINATION_TIMEOUT_SECONDS,
    AgentStoreLifecycle,
    InvocationCancellation,
)
from .providers.application.contracts import ProviderSettingsRefusal
from .providers.application.service import AssistantAuthChoice
from .service_administration import AgentServiceAdministration
from .service_support import (
    service_failure,
)

_LOGGER = get_logger("cadrumo_agent_service.service")


class AgentServiceStartup(AgentServiceAdministration):
    """Prepare and launch the owned service tree."""

    def _sign_in_environment(self, root: Path, *, gui: bool) -> dict[str, str]:
        root.mkdir(parents=True, exist_ok=True)
        environment = {HOSTED_ROOT_VARIABLE: str(root)}
        external = agent_binary_directories(python=hosted_python(), received=os.environ)
        if external is not None and external != "":
            environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
        if gui:
            browser = auth_browser_executable(hosted_python())
            if browser is not None:
                environment[AUTH_BROWSER_EXECUTABLE_VARIABLE] = str(browser)
        return environment

    def _claim_sign_in_owner(self, root: Path, *, gui: bool) -> bool:
        if gui and not self._owned:
            try:
                self._ownership.enter_context(exclusive_file_lock(root / "service-owner", timeout=0))
            except LockAcquisitionError:
                return False
            self._owned = True
        return True

    def _sign_in_available(self, provider: str, *, gui: bool) -> bool:
        lane = self._catalog.catalog().entry(provider)
        return not (
            lane is None
            or not lane.auth_kind.accepts_provider_sign_in
            or lane.provider
            not in (self._catalog.gui_sign_in_providers() if gui else self._catalog.sign_in_providers())
        )

    @override
    def _prepare_sign_in(self, provider: str, *, expected_revision: str, gui: bool = False) -> dict[str, Any]:
        """Prepare a person-terminal launch without observing provider credentials.

        The caller owns the terminal and must contain its child in the person's
        session. A prepared command does not establish provider authentication.
        """
        with self._guard:
            lease = self.client.lease
            if self._closing.is_set() or lease is None:
                return {"kind": "refused", "code": "signed_out"}
            if not self._sign_in_available(provider, gui=gui):
                return {"kind": "refused", "code": "sign_in_unavailable"}
            root = profile_agent_root(self._root, lease.profile_id)
            image = agent_image(agent_root=root)
            if not self._claim_sign_in_owner(root, gui=gui):
                return {"kind": "refused", "code": "busy"}
            if not gui and self._controller is not None:
                # A terminal login runs only once the tree is gone, and its
                # retirement takes longer than a request may wait: it is begun
                # here and announced by the stopped event, and the retry is
                # prepared at once. Nothing is changed before then.
                self._schedule_stop()
                return {"kind": "refused", "code": "busy"}
            result = self._providers.set_assistant_auth(
                provider, choice=AssistantAuthChoice.PROVIDER_SIGN_IN, expected_revision=expected_revision
            )
            if isinstance(result, ProviderSettingsRefusal):
                return result.model_dump(mode="json")
            # A browser or device login retires the tree on its own attempt,
            # before its helper starts, so its request is answered at once.
            if self._closing.is_set() or self.client.lease != lease:
                return {"kind": "refused", "code": "signed_out"}
            environment = self._sign_in_environment(root, gui=gui)
            return {
                "kind": "sign_in_prepared",
                "entry": result.entry.model_dump(mode="json"),
                "launch": {
                    "executable": str(image.executable),
                    "arguments": [*AGENT_COMMAND_LINE, "auth", "login", "--provider", result.entry.provider],
                    "directory": str(image.directory),
                    "environment": environment,
                },
            }

    @override
    def _connect(self, provider: str, *, expected_revision: str, method: str) -> dict[str, Any]:
        """Start a profile-bound helper; its provider owns OAuth and credential storage."""
        lane = self._catalog.catalog().entry(provider)
        if lane is None or method not in self._catalog.gui_sign_in_methods().get(lane.provider, ()):
            return {"kind": "refused", "code": "sign_in_unavailable"}
        self._auth_resume_valid = None
        lease = self.client.lease
        prepared = self._prepare_sign_in(provider, expected_revision=expected_revision, gui=True)
        if prepared.get("kind") != "sign_in_prepared":
            return prepared
        generations = self._credentials.current_generations()
        if lease is None or generations is None or self.client.lease != lease:
            return {"kind": "refused", "code": "signed_out"}

        def valid() -> bool:
            if self._closing.is_set() or self.client.lease != lease:
                return False
            current = self._credentials.current_generations()
            return current == generations and self.client.lease == lease and not self._closing.is_set()

        launch = prepared["launch"]
        attempt = AuthAttempt(
            provider=prepared["entry"]["provider"],
            lane=provider,
            executable=Path(launch["executable"]),
            directory=Path(launch["directory"]),
            arguments=(
                *AGENT_COMMAND_LINE,
                "auth",
                "connect",
                "--provider",
                prepared["entry"]["provider"],
                "--method",
                method,
                "--timeout",
                "300",
            ),
            environment=system_environment(os.environ) | launch["environment"],
            valid=valid,
            settled=self._wake,
            prepare=self.stop,
        )
        self._auth_attempt = attempt
        self._auth_resume_valid = valid
        self._forget_reads()
        return attempt.observe()

    def hold_for_recovery(self) -> int | None:
        """Say whether the runtime keeps this service's lease suspended, and for how many more whole seconds.

        A lost profile worker suspends every lease of the profile for a
        window, and the runtime restores a service's lease when its parent
        returns. Until then the service waits as it is: its tree and
        conversations stay, what needs the lease is answered as busy, and
        nothing claims, because a claim made meanwhile would withdraw the very
        lease that is waited for. The lease's own status is read instead.
        """
        remaining = self._recovery_seconds()
        if remaining is None:
            if self._reconnecting.is_set():
                self._reconnecting.clear()
                _LOGGER.info("agent service reconnected")
            return None
        if not self._reconnecting.is_set():
            self._reconnecting.set()
            _LOGGER.info("agent service reconnecting seconds=%d", remaining)
        return remaining

    def _recovery_seconds(self) -> int | None:
        """Read the lease's own status; the window's seconds when it is suspended, otherwise ``None``."""
        lease = self.client.lease
        if lease is None or self._closing.is_set():
            return None
        try:
            reply = self.client.connection.session(
                SessionRequest(
                    action="session_status",
                    request_id=uuid4(),
                    profile_id=lease.profile_id,
                    session_id=lease.session_id,
                ),
                deadline=monotonic() + MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
            )
        except RefusalError:
            # A connection that is gone ends the claim that follows, as it always did.
            return None
        if isinstance(reply, ProfileStatus) and reply.status.denial is AccessDenialCode.CUSTODY_RECOVERING:
            return reply.status.recovery_remaining_seconds or 0
        if isinstance(reply, AccessRefusal) and reply.code is AccessDenialCode.CUSTODY_RECOVERING:
            return reply.recovery_remaining_seconds or 0
        return None

    def start(self) -> dict[str, Any]:
        """Own one timeout and cancellation signal across the entire startup attempt."""
        with self._guard:
            deadline = DEFAULT_TIMEOUT_POLICY.deadline()
            if self._preparation_runner is not None and not self._preparation_runner.settled:
                raise AgentHostError(AgentHostRefusal.STORES_UNPREPARED)
            cancellation = self._startup_cancellation or InvocationCancellation()
            self._startup_cancellation = cancellation
            try:
                return self._start_owned(deadline, cancellation)
            except BaseException as error:
                if self._has_unsettled_tree():
                    raise AgentHostError(AgentHostRefusal.STORES_UNPREPARED) from error
                if isinstance(error, OrchestrationTimeoutError):
                    raise AgentHostError(AgentHostRefusal.TIMEOUT) from error
                raise
            finally:
                if self._startup_cancellation is cancellation:
                    self._startup_cancellation = None

    def _prepare_start_stores(
        self, agent_root: Path, launch: AgentLaunch, deadline: TimeoutDeadline, cancellation: InvocationCancellation
    ) -> None:
        failures: list[BaseException] = []

        def prefetch() -> None:
            try:
                self._catalog.catalog(deadline=deadline, cancellation=cancellation)
            except BaseException as error:
                failures.append(error)
                cancellation.cancel()

        preparation_runner = WindowsAgentInvocationRunner(deadline=deadline, cancellation=cancellation)
        self._preparation_runner = preparation_runner
        catalog_owner = Thread(target=prefetch, name="agent-service-catalog-prefetch")
        catalog_owner.start()
        try:
            AgentStoreLifecycle(
                runner=preparation_runner,
                launch=launch,
                command_line=AGENT_COMMAND_LINE,
                aside=HostedStoresAside(agent_root),
                quiesced=lambda: self._owned and self._controller is None,
                deadline=deadline,
                cancellation=cancellation,
            ).prepare()
            catalog_owner.join(deadline.remaining_seconds())
            if catalog_owner.is_alive():
                raise AgentHostError(AgentHostRefusal.TIMEOUT)
            if failures:
                raise failures[0]
            if cancellation.is_set():
                raise AgentHostError(AgentHostRefusal.CANCELLED)
        except BaseException as error:
            if failures and failures[0] is not error:
                raise failures[0] from error
            raise
        finally:
            if catalog_owner.is_alive():
                cancellation.cancel()
                catalog_owner.join(INVOCATION_TERMINATION_TIMEOUT_SECONDS)
                if catalog_owner.is_alive():
                    raise AgentHostError(AgentHostRefusal.STORES_UNPREPARED)

    def _startup_refusal(self) -> dict[str, Any] | None:
        if self._closing.is_set():
            return {"event": "refused", "code": "service_stopping"}
        if self._reconnecting.is_set():
            # The credentials cannot be read until the lease returns, which is no sign-out: ask again.
            return {"event": "refused", "code": "busy"}
        if self._auth_attempt is not None and self._auth_attempt.active:
            return {"event": "refused", "code": "busy"}
        return None

    def _existing_ready(self, deadline: TimeoutDeadline) -> AgentReady | None:
        if self._controller is not None:
            ready = self._controller.published(deadline=deadline)
            if ready is not None:
                return ready
            self.stop(deadline=deadline)
        return None

    def _launch_prepared(
        self,
        launch: AgentLaunch,
        deadline: TimeoutDeadline,
        cancellation: InvocationCancellation,
        started: float,
        owned: float,
        prepared: float,
    ) -> dict[str, Any]:
        controller = AgentHostController(
            launcher=WindowsAgentProcessLauncher(on_exit=self._wake), credentials=self._credentials, launch=launch
        )
        self._clear_hosted_certifications()
        self._controller = controller
        if self._closing.is_set() or cancellation.is_set():
            controller.cancel_start()
        release_cancel = cancellation.subscribe(controller.cancel_start)
        try:
            ready = controller.start(deadline=deadline)
        except AgentHostError as error:
            if controller.state is AgentHostState.DETACHED:
                self._controller = None
            return service_failure(error)
        finally:
            release_cancel()
        if self._closing.is_set() or cancellation.is_set():
            controller.stop(deadline=deadline)
            self._controller = None
            return {"event": "refused", "code": "service_stopping"}
        finished = monotonic()
        _LOGGER.info(
            "agent start timing owner_seconds=%.3f stores_seconds=%.3f launch_to_ready_seconds=%.3f total_seconds=%.3f",
            owned - started,
            prepared - owned,
            finished - prepared,
            finished - started,
        )
        self._forget_reads()
        event = self._ready_event(ready)
        self._emit(event)
        return event

    def _start_owned(self, deadline: TimeoutDeadline, cancellation: InvocationCancellation) -> dict[str, Any]:
        """Prepare stores and launch one tree under an exclusive cross-process reservation."""
        with self._guard:
            started = monotonic()
            refusal = self._startup_refusal()
            if refusal is not None:
                return refusal
            lease = self.client.lease
            if lease is None or self._credentials.current_generations(deadline=deadline) is None:
                return {"event": "refused", "code": "signed_out"}
            ready = self._existing_ready(deadline)
            if ready is not None:
                return self._ready_event(ready)
            agent_root = profile_agent_root(self._root, lease.profile_id)
            if not self._owned:
                try:
                    self._ownership.enter_context(exclusive_file_lock(agent_root / "service-owner", timeout=0))
                except LockAcquisitionError:
                    return {"event": "refused", "code": "already_running"}
                self._owned = True
            owned = monotonic()
            self._workspace = profile_agent_workspace(agent_root)
            image = agent_image(agent_root=agent_root)
            launch = AgentLaunch(
                executable=image.executable,
                arguments=image.arguments,
                directory=image.directory,
                environment=agent_launch_environment(
                    storage_root=self._root,
                    agent_root=agent_root,
                    relay=hosted_relay(),
                    aeat=hosted_aeat(),
                    python=hosted_python(),
                    received=os.environ,
                    profile_id=lease.profile_id,
                ),
            )
            self._prepare_start_stores(agent_root, launch, deadline, cancellation)
            prepared = monotonic()
            return self._launch_prepared(launch, deadline, cancellation, started, owned, prepared)

    @abstractmethod
    def _has_unsettled_tree(self) -> bool:
        """Provide the later service phase operation."""

    @abstractmethod
    def _ready_event(self, ready: AgentReady) -> dict[str, Any]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _schedule_stop(self) -> bool:
        """Provide the later service phase operation."""

    @abstractmethod
    def stop(self, *, deadline: TimeoutDeadline | None = None) -> None:
        """Provide the later service phase operation."""
