"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import replace
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from time import monotonic
from typing import Any, override
from urllib.parse import urlencode

from pydantic import SecretStr

from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.logging import get_logger
from cadrumo.core.storage_environment import storage_mode
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.service_client import InstalledServiceClient

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
from .adapters.agent_provider_catalog import AgentProviderCatalogSource
from .adapters.provider_catalog_metadata import declared_provider_catalog_response
from .contracts import HostedCertificationStatus
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
from .host.lane_root import is_marked_lane_root
from .host.launch_environment import (
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    agent_binary_directories,
    agent_launch_environment,
)
from .host.launcher_protocol import launcher_refusal_for
from .host.store_lifecycle import AgentStoreLifecycle
from .providers.application.agent_credentials import ProviderSettingsAgentCredentialSource
from .providers.application.contracts import ProviderSettingsRefusal
from .providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from .providers.application.resolution import ProviderCredentialResolver
from .providers.application.service import AssistantAuthChoice, BaseUrlChange, ProviderSettingsService
from .providers.domain.catalog import MAX_CATALOG_LANES
from .providers.persistence.store import SecureProviderSettingsStore

_LOGGER = get_logger(__name__)
HOSTED_CERTIFICATION_CACHE_SECONDS = 5.0


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
        code = "service_failed"
        _LOGGER.warning("agent runtime refused reason=%s", error.reason.value)
    else:
        code = "service_failed"
        _LOGGER.error("agent service failed error_type=%s", type(error).__name__)
    return {"event": "refused", "code": code}


def _controller_is_ready(controller: AgentHostController) -> bool:
    """Read the controller's live state without inferring readiness from credentials."""
    return controller.state is AgentHostState.READY


class _GatewayCredentials(AgentCredentialSource):
    def __init__(self, source: AgentCredentialSource, gateway_bearer: bytearray, closing: Event) -> None:
        self._source = source
        self._gateway_bearer = gateway_bearer
        self._closing = closing

    @override
    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        if self._closing.is_set():
            raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
        return replace(self._source.resolve_for_agent(), gateway_bearer=bytearray(self._gateway_bearer))

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
        agent_source: str | None,
        gateway_bearer: bytearray,
        emit: Callable[[dict[str, Any]], None],
    ) -> None:
        """Bind provider custody and process ownership to the verified service connection."""
        self.client = client
        self._root = storage_root
        self._agent_source = agent_source
        self._guard = RLock()
        self._closing = Event()
        self._start_request_guard = Lock()
        self._start_thread: Thread | None = None
        self._gateway_bearer = gateway_bearer
        self._catalog = AgentProviderCatalogSource(agent_source=agent_source)
        self._store = SecureProviderSettingsStore(client=client)
        resolver = ProviderCredentialResolver(
            store=self._store, catalog_source=self._catalog, environment=os.environ, storage_mode=storage_mode().mode
        )
        self._credentials = _GatewayCredentials(
            ProviderSettingsAgentCredentialSource(store=self._store, resolver=resolver, catalog_source=self._catalog),
            gateway_bearer,
            self._closing,
        )
        self._providers = ProviderSettingsService(
            store=self._store, catalog_source=self._catalog, environment=os.environ, storage_mode=storage_mode().mode
        )
        self._controller: AgentHostController | None = None
        self._hosted_certification_lock = Lock()
        self._hosted_certification_snapshot: (
            tuple[AgentHostController, AgentReady, tuple[HostedCertificationStatus, ...], float] | None
        ) = None
        self._workspace: Path | None = None
        self._ownership = ExitStack()
        self._owned = False
        self._emit = emit

    def admin(
        self,
        action: str,
        *,
        provider: str | None = None,
        expected_revision: str | None = None,
        base_url: str | None = None,
        choice: str | None = None,
        secret: bytearray | None = None,
    ) -> Any:
        """Apply one bounded masked administration request under the live lease."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if action == "catalog":
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
                    return document
            self._clear_hosted_certifications()
            return declared_provider_catalog_response(agent_source=self._agent_source)
        if self.client.lease is None:
            return {"kind": "refused", "code": "signed_out"}
        if action == "status":
            status = self._providers.status().model_dump(mode="json")
            status["hosted_certifications"] = self._hosted_certifications()
            return status
        if action == "start":
            with self._start_request_guard:
                if self._closing.is_set():
                    return {"kind": "refused", "code": "service_stopping"}
                if self._start_thread is None or not self._start_thread.is_alive():
                    self._start_thread = Thread(target=self._background_start, name="agent-service-start")
                    self._start_thread.start()
            return {"kind": "starting"}
        if action == "stop":
            self.stop()
            return {"kind": "stopped"}
        if provider is None or expected_revision is None:
            return {"kind": "refused", "code": "invalid_request"}
        if action == "sign_in":
            return self._prepare_sign_in(provider, expected_revision=expected_revision)
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
            result = self._providers.remove_credential(provider, expected_revision=expected_revision)
        elif action == "reset":
            result = self._providers.reset(provider, expected_revision=expected_revision)
        elif action == "auth" and choice is not None:
            result = self._providers.set_assistant_auth(
                provider, choice=AssistantAuthChoice(choice), expected_revision=expected_revision
            )
        else:
            return {"kind": "refused", "code": "invalid_request"}
        # Startup and background observation revalidate the committed generation.
        return result.model_dump(mode="json")

    def _prepare_sign_in(self, provider: str, *, expected_revision: str) -> dict[str, Any]:
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
                or lane.provider not in self._catalog.sign_in_providers()
            ):
                return {"kind": "refused", "code": "sign_in_unavailable"}
            root = profile_agent_root(self._root, lease.profile_id)
            image = agent_image(self._agent_source, agent_root=root)
            result = self._providers.set_assistant_auth(
                provider, choice=AssistantAuthChoice.PROVIDER_SIGN_IN, expected_revision=expected_revision
            )
            if isinstance(result, ProviderSettingsRefusal):
                return result.model_dump(mode="json")
            self.stop()
            if self._closing.is_set() or self.client.lease != lease:
                return {"kind": "refused", "code": "signed_out"}
            root.mkdir(parents=True, exist_ok=True)
            environment = {HOSTED_ROOT_VARIABLE: str(root)}
            external = agent_binary_directories(python=hosted_python(), received=os.environ)
            if external is not None and external != "":
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = external
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

    def start(self) -> dict[str, Any]:
        """Prepare stores and launch one tree under an exclusive cross-process reservation."""
        with self._guard:
            if self._closing.is_set():
                return {"event": "refused", "code": "service_stopping"}
            lease = self.client.lease
            if lease is None or self._credentials.current_generations() is None:
                return {"event": "refused", "code": "signed_out"}
            if self._agent_source is not None and not is_marked_lane_root(self._root):
                return {"event": "refused", "code": "root_unmarked"}
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
            self._workspace = profile_agent_workspace(agent_root)
            image = agent_image(self._agent_source, agent_root=agent_root)
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
                ),
            )
            AgentStoreLifecycle(
                runner=WindowsAgentInvocationRunner(),
                launch=launch,
                command_line=AGENT_COMMAND_LINE,
                aside=HostedStoresAside(agent_root),
                quiesced=lambda: self._owned and self._controller is None,
            ).prepare()
            controller = AgentHostController(
                launcher=WindowsAgentProcessLauncher(), credentials=self._credentials, launch=launch
            )
            self._clear_hosted_certifications()
            self._controller = controller
            try:
                ready = controller.start()
            except AgentHostError as error:
                if controller.state is AgentHostState.DETACHED:
                    self._controller = None
                return service_failure(error)
            event = self._ready_event(ready)
            self._emit(event)
            return event

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

    def runtime_changed(self) -> None:
        """Forget observed generations: a pushed frame may mean a new lease or a retired session."""
        self._store.invalidate_generations()

    def observe(self) -> bool:
        """Revalidate exact generations and synchronously retire any stale tree."""
        with self._guard:
            if self._controller is None:
                return self._store.observe_generations() is not None
            return self._controller.published() is not None

    def stop(self) -> None:
        """Confirm contained shutdown before releasing the tree's ownership."""
        with self._guard:
            controller = self._controller
            if controller is not None:
                self._clear_hosted_certifications()
                controller.stop()
                self._controller = None
                self._emit({"event": "stopped", "code": "agent_retired"})

    def close(self) -> None:
        """Settle process containment before releasing the exclusive reservation."""
        try:
            self.request_close()
        finally:
            try:
                self.stop()
                thread = self._start_thread
                if thread is not None:
                    thread.join()
                self._ownership.close()
                self._owned = False
            finally:
                wipe(self._gateway_bearer)

    def request_close(self) -> None:
        """Invalidate startup publication immediately without waiting on lifecycle work."""
        self._closing.set()
        self._clear_hosted_certifications()
        self.client.lease = None
        self.client.connection.close()
