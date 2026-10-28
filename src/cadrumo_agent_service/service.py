"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

import contextlib
import json
import os
import secrets
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import replace
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from time import monotonic
from typing import Any, override
from urllib.parse import urlencode
from uuid import uuid4

from pydantic import SecretStr

from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.logging import get_logger
from cadrumo.core.storage_environment import storage_mode
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
from cadrumo_client.transport.service_client import InstalledServiceClient

from .adapters.agent_background_runs import BackgroundRunEndpoint, HostedBackgroundRuns
from .adapters.agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from .adapters.agent_programs import (
    AGENT_COMMAND_LINE,
    AgentProgramRefusalError,
    HostedStoresAside,
    agent_image,
    hosted_aeat,
    hosted_python,
    hosted_relay,
    profile_agent_root,
    profile_agent_workspace,
)
from .adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from .adapters.agent_provider_catalog import AgentProviderCatalogSource
from .adapters.provider_catalog_metadata import DECLARED_CATALOG_KIND, declared_provider_catalog_response
from .adapters.served_catalog_models import ServedCatalogModels
from .contracts import HostedCertificationStatus
from .host.auth_attempt import AuthAttempt
from .host.bounded_read import BoundedRead, Identity
from .host.controller import (
    AgentCredentialSource,
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    AgentReady,
    ResolvedAgentCredentials,
)
from .host.credential_frame import wipe
from .host.launch_environment import (
    AUTH_BROWSER_EXECUTABLE_VARIABLE,
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    agent_binary_directories,
    agent_launch_environment,
    auth_browser_executable,
    system_environment,
)
from .host.launcher_protocol import launcher_refusal_for, runtime_launcher_refusal_for
from .host.store_lifecycle import AgentStoreLifecycle
from .providers.application.agent_credentials import ProviderSettingsAgentCredentialSource
from .providers.application.contracts import ProviderSettingsRefusal
from .providers.application.local_model_list import LocalModelListService
from .providers.application.model_runs import ModelRunService
from .providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from .providers.application.resolution import ProviderCredentialResolver
from .providers.application.service import AssistantAuthChoice, BaseUrlChange, ProviderSettingsService
from .providers.domain.catalog import MAX_CATALOG_LANES
from .providers.persistence.store import SecureLocalModelListStore, SecureProviderSettingsStore

_LOGGER = get_logger(__name__)
HOSTED_CERTIFICATION_CACHE_SECONDS = 5.0
LIFECYCLE_ADMISSION_SECONDS = 2.0
"""How long a request waits for tree lifecycle work, well inside the desktop's shortest exchange bound."""
ADMIN_READ_SECONDS = 1.5
"""How long a catalog or status request waits for its work before it is told the service is busy.

The work goes on, and a request in the next few seconds is served its result:
a cold catalog or a provider's sign-in probe can take longer than an
administration exchange may hold one of the service's few slots."""
ADMIN_READ_FRESH_SECONDS = 5.0
"""How long a finished catalog or status read is served to the requests that follow it."""


def service_failure(error: Exception) -> dict[str, Any]:
    """Keep typed launch refusals and log only bounded operational metadata."""
    if isinstance(error, AgentHostError):
        code = launcher_refusal_for(error).value
        _LOGGER.warning(
            "agent startup refused reason=%s agent_code=%s",
            error.reason.value,
            error.agent_code,
        )
    elif isinstance(error, AgentProgramRefusalError):
        code = error.code.value
        _LOGGER.warning("agent program unavailable code=%s", code)
    elif isinstance(error, RefusalError):
        unavailable = runtime_launcher_refusal_for(error)
        code = "service_failed" if unavailable is None else unavailable.value
        _LOGGER.warning("agent runtime refused reason=%s", error.reason.value)
    else:
        code = "service_failed"
        _LOGGER.error("agent service failed error_type=%s", type(error).__name__)
    return {"event": "refused", "code": code}


def _controller_is_ready(controller: AgentHostController) -> bool:
    """Read the controller's live state without inferring readiness from credentials."""
    return controller.state is AgentHostState.READY


def _without_lanes(
    document: dict[str, Any], turned_off: frozenset[tuple[str, str]], *, provider_field: str
) -> dict[str, Any]:
    """Return ``document`` without the lanes whose provider and transport are in ``turned_off``."""
    lanes = document.get("providers")
    if not isinstance(lanes, list):
        return document
    kept = [
        lane
        for lane in lanes
        if not (isinstance(lane, dict) and (lane.get(provider_field), lane.get("transport")) in turned_off)
    ]
    return {**document, "providers": kept}


class _GatewayCredentials(AgentCredentialSource):
    def __init__(
        self, source: AgentCredentialSource, gateway_bearer: bytearray, host_token: bytearray, closing: Event
    ) -> None:
        self._source = source
        self._gateway_bearer = gateway_bearer
        self._host_token = host_token
        self._closing = closing

    @override
    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        if self._closing.is_set():
            raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
        return replace(
            self._source.resolve_for_agent(),
            gateway_bearer=bytearray(self._gateway_bearer),
            host_token=bytearray(self._host_token),
        )

    @override
    def current_generations(self) -> AgentGenerations | None:
        return None if self._closing.is_set() else self._source.current_generations()


class AgentService:
    """Own one profile's contained tree and masked provider administration."""

    def __init__(
        self,
        *,
        client: InstalledServiceClient,
        storage_root: Path,
        gateway_bearer: bytearray,
        emit: Callable[[dict[str, Any]], None],
        wake: Callable[[], None] | None = None,
    ) -> None:
        """Bind provider custody and process ownership to the verified service connection."""
        self.client = client
        self._root = storage_root
        self._guard = RLock()
        self._closing = Event()
        self._reconnecting = Event()
        self._start_request_guard = Lock()
        self._start_thread: Thread | None = None
        self._stop_thread: Thread | None = None
        self._gateway_bearer = gateway_bearer
        # Minted here and handed only to the agent's start frame; it admits
        # background requests, which the desktop's bearer alone cannot.
        self._host_token = bytearray(secrets.token_urlsafe(32), "ascii")
        self._catalog = AgentProviderCatalogSource()
        self._store = SecureProviderSettingsStore(client=client)
        resolver = ProviderCredentialResolver(store=self._store, catalog_source=self._catalog)
        self._credentials = _GatewayCredentials(
            ProviderSettingsAgentCredentialSource(store=self._store, resolver=resolver, catalog_source=self._catalog),
            gateway_bearer,
            self._host_token,
            self._closing,
        )
        model_list = SecureLocalModelListStore(client=client)
        live_models = ServedCatalogModels(self._live_catalog)
        self._model_runs = ModelRunService(
            model_list=model_list,
            resolver=resolver,
            catalog_source=self._catalog,
            live_models=live_models,
            gateway=HostedBackgroundRuns(
                endpoint=self._background_endpoint, bearer=gateway_bearer, host_token=self._host_token
            ),
        )
        self._login_status = AgentProviderAuthStatusProbe(context=self._login_context)
        self._providers = ProviderSettingsService(
            store=self._store,
            catalog_source=self._catalog,
            storage_mode=storage_mode().mode,
            cli_state_probe=self._login_status.probe,
        )
        self._local_models = LocalModelListService(store=model_list, catalog_source=self._catalog)
        self._controller: AgentHostController | None = None
        self._auth_attempt: AuthAttempt | None = None
        self._auth_resume_valid: Callable[[], bool] | None = None
        self._wake = wake
        self._hosted_certification_lock = Lock()
        self._hosted_certification_snapshot: (
            tuple[AgentHostController, AgentReady, tuple[HostedCertificationStatus, ...], float] | None
        ) = None
        self._workspace: Path | None = None
        self._catalog_read = BoundedRead(self._catalog_document, name="catalog", fresh_seconds=ADMIN_READ_FRESH_SECONDS)
        self._status_read = BoundedRead(self._provider_status, name="status", fresh_seconds=ADMIN_READ_FRESH_SECONDS)
        self._ownership = ExitStack()
        self._owned = False
        self._emit = emit

    def _login_context(self) -> tuple[Path, str] | None:
        """Bind a login observation to current profile, settings and completed attempt."""
        lease = self.client.lease
        if self._closing.is_set() or lease is None:
            return None
        attempt = self._auth_attempt
        if attempt is not None and attempt.active:
            return None
        generations = self._credentials.current_generations()
        if generations is None or self.client.lease != lease:
            return None
        key = f"{lease.lease_id}:{generations.sign_in}:{generations.provider_settings}:{attempt.id if attempt else ''}"
        return profile_agent_root(self._root, lease.profile_id), key

    def admin(
        self,
        action: str,
        *,
        provider: str | None = None,
        expected_revision: str | None = None,
        base_url: str | None = None,
        choice: str | None = None,
        method: str | None = None,
        attempt_id: str | None = None,
        model: str | None = None,
        secret: bytearray | None = None,
    ) -> Any:
        """Apply one bounded masked administration request under the live lease."""
        if action == "connect_submit_code":
            if self._closing.is_set():
                return {"kind": "refused", "code": "service_stopping"}
            if self.client.lease is None:
                return {"kind": "refused", "code": "signed_out"}
            attempt = self._auth_attempt
            if attempt is None or attempt.id != attempt_id or secret is None:
                return {"kind": "refused", "code": "invalid_request"}
            try:
                return attempt.submit_code(secret)
            except ValueError:
                return {"kind": "refused", "code": "invalid_request"}
        if action in {"connect_status", "connect_cancel"}:
            return self._observe_sign_in(attempt_id, cancel=action == "connect_cancel")
        if action == "local_models":
            return self._local_model_list()
        if action in {"catalog", "status"}:
            if self._closing.is_set():
                return {"kind": "refused", "code": "service_stopping"}
            # Each reads what the profile and the tree are now; a result is
            # served only for the lease and tree it was read under.
            key = (Identity(self.client.lease), Identity(self._controller))
            read = self._catalog_read if action == "catalog" else self._status_read
            return read.answer(key, within=ADMIN_READ_SECONDS)
        arguments: dict[str, Any] = {
            "provider": provider,
            "expected_revision": expected_revision,
            "base_url": base_url,
            "choice": choice,
            "method": method,
            "attempt_id": attempt_id,
            "model": model,
            "secret": secret,
        }
        if action == "start":
            # A start does not change the tree here: it is handed to its own thread.
            return self._admin(action, **arguments)
        if action == "stop":
            # Retiring a tree waits for its run to settle and its job to end;
            # the request is answered once the retirement is admitted.
            return self._admit_stop()
        # Retiring or launching a tree holds the lifecycle lock for as long as
        # the tree takes; a request answers that it is busy instead of waiting
        # for its caller's deadline.
        if not self._guard.acquire(timeout=LIFECYCLE_ADMISSION_SECONDS):
            return {"kind": "refused", "code": "busy"}
        try:
            return self._admin(action, **arguments)
        finally:
            self._guard.release()

    def _observe_sign_in(self, attempt_id: str | None, *, cancel: bool) -> dict[str, Any]:
        """Observe the existing owner without waiting for gateway startup or reaping.

        The lifecycle guard protects tree changes and can be held for longer
        than an administration request. An attempt has its own snapshot lock
        and exact lease/generation predicate, so observing it needs no tree
        lock. Capture its owner once: cancellation must never reach a newer
        attempt that replaced the requested one.
        """
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self.client.lease is None:
            return {"kind": "refused", "code": "signed_out"}
        attempt = self._auth_attempt
        if attempt is None or attempt.id != attempt_id:
            return {"kind": "refused", "code": "invalid_request"}
        if cancel:
            attempt.cancel()
        return attempt.observe()

    def _admin(
        self,
        action: str,
        *,
        provider: str | None,
        expected_revision: str | None,
        base_url: str | None,
        choice: str | None,
        method: str | None,
        attempt_id: str | None,
        model: str | None,
        secret: bytearray | None,
    ) -> Any:
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self.client.lease is None:
            return {"kind": "refused", "code": "signed_out"}
        if self._auth_attempt is not None and self._auth_attempt.active:
            return {"kind": "refused", "code": "busy"}
        if action == "start":
            if not self._schedule_start():
                return {"kind": "refused", "code": "service_stopping"}
            return {"kind": "starting"}
        if action in {"local_model_add", "local_model_remove", "local_models_reset", "reading_model_choose"}:
            return self._change_local_models(action, lane=provider, model=model, expected_revision=expected_revision)
        if provider is None or expected_revision is None:
            return {"kind": "refused", "code": "invalid_request"}
        if action == "sign_in":
            return self._prepare_sign_in(provider, expected_revision=expected_revision)
        if action == "connect" and method in {"browser", "browser-code", "device"}:
            return self._connect(provider, expected_revision=expected_revision, method=method)
        if action == "set" and secret is not None:
            result = self._providers.set_credential(
                provider,
                secret=SecretStr(secret.decode("utf-8")),
                expected_revision=expected_revision,
                base_url=BaseUrlChange.KEEP
                if base_url is None
                else BaseUrlChange.CLEAR
                if base_url == ""
                else base_url,
            )
        elif action == "remove":
            result = self._providers.turn_off(provider, expected_revision=expected_revision)
        elif action == "turn_on":
            result = self._providers.turn_on(provider, expected_revision=expected_revision)
        elif action == "reset":
            result = self._providers.reset(provider, expected_revision=expected_revision)
        elif action == "auth" and choice is not None:
            result = self._providers.set_assistant_auth(
                provider, choice=AssistantAuthChoice(choice), expected_revision=expected_revision
            )
        else:
            return {"kind": "refused", "code": "invalid_request"}
        self._forget_reads()
        # A tree started under the settings this change superseded is replaced
        # on the start thread, which retires it and publishes what follows.
        self._replace_superseded()
        return result.model_dump(mode="json")

    def _local_model_list(self) -> dict[str, Any]:
        """Read the models added to the local model lists; a plain store read that never waits on the agent tree."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self.client.lease
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._local_models.status().model_dump(mode="json")
        if self.client.lease != lease:
            return {"kind": "refused", "code": "signed_out"}
        return observed

    def _change_local_models(
        self,
        action: str,
        *,
        lane: str | None,
        model: str | None,
        expected_revision: str | None,
    ) -> dict[str, Any]:
        if expected_revision is None:
            return {"kind": "refused", "code": "invalid_request"}
        models = self._local_models
        if action == "local_model_add" and lane is not None and model is not None:
            result = models.add(lane, model=model, expected_revision=expected_revision)
        elif action == "local_model_remove" and lane is not None and model is not None:
            result = models.remove(lane, model=model, expected_revision=expected_revision)
        elif action == "local_models_reset" and lane is None and model is None:
            result = models.reset(expected_revision=expected_revision)
        elif action == "reading_model_choose" and lane is not None and model is not None:
            result = models.choose_reading(lane, model=model, expected_revision=expected_revision)
        else:
            return {"kind": "refused", "code": "invalid_request"}
        # The list has a capability of its own: a change leaves the
        # provider-settings generation, the kept reads and the running tree as they are.
        return result.model_dump(mode="json")

    def _catalog_document(self) -> dict[str, Any]:
        """The published agent's catalog, or the declared one while none is ready."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        self._clear_hosted_certifications()
        controller = self._controller
        if controller is not None and controller.state is AgentHostState.READY:
            ready = controller.published()
            if ready is not None:
                try:
                    document = self._served_catalog(ready)
                except Exception:
                    self._clear_hosted_certifications()
                    raise
                self._remember_hosted_certifications(controller, ready, document)
                return self._picker_catalog(document)
        self._clear_hosted_certifications()
        return self._picker_catalog(declared_provider_catalog_response())

    def _forget_reads(self) -> None:
        """Serve no kept catalog or status once what they were read from has changed."""
        self._catalog_read.forget()
        self._status_read.forget()

    def _provider_status(self) -> dict[str, Any]:
        """Observe settings without waiting for gateway startup after sign-in.

        Store reads and login observations carry their own profile authority.
        The controller snapshot has its own lock; the lifecycle lock only
        serializes changes to the process tree, not these independent reads.
        """
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self.client.lease
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._providers.status()
        if isinstance(observed, ProviderSettingsRefusal):
            return observed.model_dump(mode="json")
        status = observed.model_dump(mode="json")
        status["hosted_certifications"] = self._hosted_certifications()
        try:
            methods = self._catalog.gui_sign_in_methods()
            status["sign_in_providers"] = list(methods)
            status["sign_in_methods"] = {provider: list(choices) for provider, choices in methods.items()}
        except ProviderCatalogUnavailableError:
            # Missing GUI capability disables login, not existing key management.
            status["sign_in_providers"] = []
            status["sign_in_methods"] = {}
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self.client.lease != lease:
            return {"kind": "refused", "code": "signed_out"}
        return status

    def _prepare_sign_in(self, provider: str, *, expected_revision: str, gui: bool = False) -> dict[str, Any]:
        """Prepare a person-terminal launch without observing provider credentials.

        The caller owns the terminal and must contain its child in the person's
        session. A prepared command does not establish provider authentication.
        """
        with self._guard:
            lease = self.client.lease
            if self._closing.is_set() or lease is None:
                return {"kind": "refused", "code": "signed_out"}
            lane = self._catalog.catalog().entry(provider)
            if (
                lane is None
                or not lane.auth_kind.accepts_provider_sign_in
                or lane.provider
                not in (self._catalog.gui_sign_in_providers() if gui else self._catalog.sign_in_providers())
            ):
                return {"kind": "refused", "code": "sign_in_unavailable"}
            root = profile_agent_root(self._root, lease.profile_id)
            image = agent_image(agent_root=root)
            if gui and not self._owned:
                try:
                    self._ownership.enter_context(exclusive_file_lock(root / "service-owner", timeout=0))
                except LockAcquisitionError:
                    return {"kind": "refused", "code": "busy"}
                self._owned = True
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
            root.mkdir(parents=True, exist_ok=True)
            environment = {HOSTED_ROOT_VARIABLE: str(root)}
            external = agent_binary_directories(python=hosted_python(), received=os.environ)
            if external is not None and external != "":
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
            if gui:
                browser = auth_browser_executable(hosted_python())
                if browser is not None:
                    environment[AUTH_BROWSER_EXECUTABLE_VARIABLE] = str(browser)
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
        """Prepare stores and launch one tree under an exclusive cross-process reservation."""
        with self._guard:
            started = monotonic()
            if self._closing.is_set():
                return {"event": "refused", "code": "service_stopping"}
            if self._reconnecting.is_set():
                # The credentials cannot be read until the lease returns, which is no sign-out: ask again.
                return {"event": "refused", "code": "busy"}
            if self._auth_attempt is not None and self._auth_attempt.active:
                return {"event": "refused", "code": "busy"}
            lease = self.client.lease
            if lease is None or self._credentials.current_generations() is None:
                return {"event": "refused", "code": "signed_out"}
            if self._controller is not None:
                ready = self._controller.published()
                if ready is not None:
                    return self._ready_event(ready)
                self.stop()
            agent_root = profile_agent_root(self._root, lease.profile_id)
            if not self._owned:
                try:
                    self._ownership.enter_context(exclusive_file_lock(agent_root / "service-owner", timeout=0))
                except LockAcquisitionError:
                    return {"event": "refused", "code": "already_running"}
                self._owned = True
            # The launch resolves credentials against the agent's own catalog,
            # whose first read runs the agent once; it runs beside the stores'
            # invocations instead of after them.
            Thread(target=self._prefetch_catalog, name="agent-service-catalog-prefetch", daemon=True).start()
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
            AgentStoreLifecycle(
                runner=WindowsAgentInvocationRunner(),
                launch=launch,
                command_line=AGENT_COMMAND_LINE,
                aside=HostedStoresAside(agent_root),
                quiesced=lambda: self._owned and self._controller is None,
            ).prepare()
            prepared = monotonic()
            controller = AgentHostController(
                launcher=WindowsAgentProcessLauncher(on_exit=self._wake), credentials=self._credentials, launch=launch
            )
            self._clear_hosted_certifications()
            self._controller = controller
            if self._closing.is_set():
                controller.cancel_start()
            try:
                ready = controller.start()
            except AgentHostError as error:
                if controller.state is AgentHostState.DETACHED:
                    self._controller = None
                return service_failure(error)
            if self._closing.is_set():
                controller.stop()
                self._controller = None
                return {"event": "refused", "code": "service_stopping"}
            finished = monotonic()
            _LOGGER.info(
                "agent start timing owner_seconds=%.3f stores_seconds=%.3f launch_to_ready_seconds=%.3f "
                "total_seconds=%.3f",
                owned - started,
                prepared - owned,
                finished - prepared,
                finished - started,
            )
            self._forget_reads()
            event = self._ready_event(ready)
            self._emit(event)
            return event

    def _prefetch_catalog(self) -> None:
        """Read the agent's catalog once, so the launch finds it read; a failure is the launch's to report."""
        with contextlib.suppress(ProviderCatalogUnavailableError):
            self._catalog.catalog()

    def _schedule_start(self) -> bool:
        """Hand a start to the start thread unless one is running; ``False`` once the service is closing."""
        with self._start_request_guard:
            if self._closing.is_set():
                return False
            if self._start_thread is None or not self._start_thread.is_alive():
                self._start_thread = Thread(target=self._background_start, name="agent-service-start")
                self._start_thread.start()
        return True

    def _admit_stop(self) -> dict[str, Any]:
        """Admit the tree's retirement and answer at once; the stopped event reports its end."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self.client.lease is None:
            return {"kind": "refused", "code": "signed_out"}
        self._auth_resume_valid = None
        if self._auth_attempt is not None:
            self._auth_attempt.cancel()
        controller = self._controller
        if controller is not None:
            controller.cancel_start()
        start = self._start_thread
        if self._controller is None and (start is None or not start.is_alive()):
            return {"kind": "stopped"}
        if not self._schedule_stop():
            return {"kind": "refused", "code": "busy"}
        return {"kind": "accepted"}

    def _schedule_stop(self) -> bool:
        """Hand the tree's retirement to its own thread; ``False`` while one is already under way."""
        with self._start_request_guard:
            if self._stop_thread is not None and self._stop_thread.is_alive():
                return False
            self._stop_thread = Thread(target=self._background_stop, name="agent-service-stop")
            self._stop_thread.start()
        return True

    def _background_stop(self) -> None:
        try:
            self.stop()
        except Exception as error:
            if not self._closing.is_set():
                self._emit(service_failure(error))

    def _replace_superseded(self) -> bool:
        """Start a replacement for a ready tree whose generations moved on while the profile stays signed in.

        The start retires the superseded tree, which publishes ``stopped``, and
        then publishes the new tree's ready line or the refusal that kept it
        from starting, so the desktop never keeps showing a retired agent.
        """
        controller = self._controller
        if controller is None or not controller.superseded() or self._credentials.current_generations() is None:
            return False
        if self._auth_attempt is not None and self._auth_attempt.active:
            # The sign-in retires this tree itself and resumes the agent once it settles.
            return False
        return self._schedule_start()

    def _background_start(self) -> None:
        try:
            result = self.start()
        except Exception as error:
            result = service_failure(error)
        if result.get("event") != "agent_ready" and not self._closing.is_set():
            self._emit(result)

    def _ready_event(self, ready: AgentReady) -> dict[str, Any]:
        return {
            "event": "agent_ready",
            "gateway_port": ready.gateway_port,
            "agent_version": ready.agent_version,
            "hosting_contract": ready.hosting_contract,
            "workspace_root": str(self._workspace),
        }

    def _picker_catalog(self, document: dict[str, Any]) -> dict[str, Any]:
        """Drop the lanes the signed-in profile turned off, so the picker never offers them.

        Only stored settings are read; no provider program is probed. Without a
        lease, or when the settings cannot be read, the catalog is returned
        unchanged: an off lane still resolves no credential for the agent.
        """
        if self.client.lease is None:
            return document
        turned_off = self._providers.turned_off_lanes()
        if turned_off is None or not turned_off:
            return document
        if document.get("kind") == DECLARED_CATALOG_KIND:
            declared = document.get("catalog")
            if not isinstance(declared, dict):
                return document
            # A declared lane names its provider identity ``provider``.
            return {**document, "catalog": _without_lanes(declared, turned_off, provider_field="provider")}
        return _without_lanes(document, turned_off, provider_field="provider_id")

    def _served_catalog(self, ready: AgentReady) -> dict[str, Any]:
        """Relay the admitted agent's actual bounded catalogue without projecting fields."""
        connection = HTTPConnection("127.0.0.1", ready.gateway_port, timeout=5)
        try:
            path = "/v1/provider-catalog?" + urlencode({"workspace_root": str(self._workspace)})
            connection.request(
                "GET",
                path,
                headers={
                    "Authorization": "Bearer " + self._gateway_bearer.decode("ascii"),
                    "Accept": "application/json",
                },
            )
            response = connection.getresponse()
            payload = response.read(256 * 1024 + 1)
            if response.status != 200 or len(payload) > 256 * 1024:
                raise ValueError("catalog_unavailable")
            document = json.loads(payload)
            if (
                not isinstance(document, dict)
                or document.get("api_version") != "v1"
                or not isinstance(document.get("providers"), list)
            ):
                raise ValueError("catalog_malformed")
            if self._controller is None or self._controller.published() != ready:
                raise ValueError("catalog_generation_changed")
            return document
        except (HTTPException, OSError, ValueError) as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED) from error
        finally:
            connection.close()

    def _live_catalog(self) -> dict[str, Any] | None:
        """Return the ready agent's served catalogue, or ``None`` when no agent is ready or it does not answer.

        A model list change and a lane lookup read it beside the declared
        catalogue; without it they read the declared catalogue alone. The read
        is bound to the generation it was asked of, as every served read is.
        """
        controller = self._controller
        if self._closing.is_set() or self.client.lease is None or controller is None or self._workspace is None:
            return None
        if not _controller_is_ready(controller):
            return None
        ready = controller.published()
        if ready is None:
            return None
        try:
            return self._served_catalog(ready)
        except ProviderCatalogUnavailableError:
            return None

    def _hosted_certifications(self) -> list[dict[str, str]]:
        """Return only a recently served snapshot bound to the controller's current generations."""
        controller = self._controller
        if self._closing.is_set() or controller is None or not _controller_is_ready(controller):
            self._clear_hosted_certifications()
            return []
        with self._hosted_certification_lock:
            snapshot = self._hosted_certification_snapshot
            if (
                snapshot is None
                or snapshot[0] is not controller
                or monotonic() - snapshot[3] >= HOSTED_CERTIFICATION_CACHE_SECONDS
            ):
                self._hosted_certification_snapshot = None
                return []
            certifications = snapshot[2]
        ready = controller.published()
        if (
            ready is None
            or ready != snapshot[1]
            or self._closing.is_set()
            or self._controller is not controller
            or not _controller_is_ready(controller)
        ):
            self._clear_hosted_certifications()
            return []
        with self._hosted_certification_lock:
            if self._hosted_certification_snapshot is not snapshot:
                return []
        return [certification.model_dump(mode="json") for certification in certifications]

    def _remember_hosted_certifications(
        self, controller: AgentHostController, ready: AgentReady, document: dict[str, Any]
    ) -> None:
        """Cache bounded facts only after the existing authenticated catalog request succeeds."""
        lanes = document.get("providers")
        certifications: tuple[HostedCertificationStatus, ...] = ()
        if isinstance(lanes, list) and len(lanes) <= MAX_CATALOG_LANES:
            parsed: list[HostedCertificationStatus] = []
            seen: set[tuple[str, str]] = set()
            try:
                for raw_lane in lanes:
                    certification = HostedCertificationStatus.model_validate(raw_lane, strict=True)
                    identity = (certification.provider, certification.transport)
                    if identity in seen:
                        return
                    seen.add(identity)
                    parsed.append(certification)
            except (TypeError, ValueError):
                parsed = []
            certifications = tuple(parsed)
        with self._hosted_certification_lock:
            if self._closing.is_set() or self._controller is not controller or not _controller_is_ready(controller):
                self._hosted_certification_snapshot = None
                return
            self._hosted_certification_snapshot = (controller, ready, certifications, monotonic())

    def _clear_hosted_certifications(self) -> None:
        """Forget every cached hosted fact when its source may no longer be observed."""
        with self._hosted_certification_lock:
            self._hosted_certification_snapshot = None

    def _background_endpoint(self) -> BackgroundRunEndpoint | None:
        """Return the ready agent's gateway while this service holds a lease and is not closing."""
        controller = self._controller
        workspace = self._workspace
        if self._closing.is_set() or self.client.lease is None or controller is None or workspace is None:
            return None
        ready = controller.published()
        return None if ready is None else BackgroundRunEndpoint(port=ready.gateway_port, workspace_root=workspace)

    def model_runs(self) -> ModelRunService | None:
        """Return the profile's run service while this service holds a lease and is not closing."""
        if self._closing.is_set() or self.client.lease is None:
            return None
        return self._model_runs

    def runtime_changed(self) -> None:
        """Forget observed generations: a pushed frame may mean a new lease or a retired session."""
        self._store.invalidate_generations()
        self._forget_reads()

    def observe(self) -> bool:
        """Revalidate exact generations: replace a superseded tree, or answer ``False`` for the caller to retire it."""
        with self._guard:
            if self._auth_attempt is not None and not self._auth_attempt.active:
                resume_valid = self._auth_resume_valid
                self._auth_resume_valid = None
                if resume_valid is not None and resume_valid():
                    self._background_start()
            if self._controller is None:
                return self._store.observe_generations() is not None
            return self._controller.published() is not None or self._replace_superseded()

    def stop(self) -> None:
        """Confirm contained shutdown before releasing the tree's ownership."""
        with self._guard:
            controller = self._controller
            if controller is not None:
                self._clear_hosted_certifications()
                controller.stop()
                self._controller = None
                self._forget_reads()
                self._emit({"event": "stopped", "code": "agent_retired"})

    def close(self) -> None:
        """Settle process containment before releasing the exclusive reservation."""
        try:
            self.request_close()
        finally:
            try:
                self.stop()
                if self._auth_attempt is not None:
                    self._auth_attempt.close()
                for thread in (self._start_thread, self._stop_thread):
                    if thread is not None:
                        thread.join()
                self._ownership.close()
                self._owned = False
            finally:
                wipe(self._gateway_bearer)
                wipe(self._host_token)

    def request_close(self) -> None:
        """Invalidate startup publication immediately without waiting on lifecycle work."""
        self._closing.set()
        controller = self._controller
        if controller is not None:
            controller.cancel_start()
        if self._auth_attempt is not None:
            self._auth_attempt.cancel()
        self._clear_hosted_certifications()
        self.client.lease = None
        self.client.connection.close()
