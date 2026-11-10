"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from typing import Any

from pydantic import SecretStr

from cadrumo.core.config import load_settings
from cadrumo_client.transport.service_client import InstalledServiceClient

from .adapters.agent_attachment_gateway import GatewayAttachments
from .adapters.agent_background_runs import BackgroundRunEndpoint, HostedBackgroundRuns
from .adapters.agent_process import WindowsAgentInvocationRunner
from .adapters.agent_programs import (
    profile_agent_root,
)
from .adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from .adapters.agent_provider_catalog import AgentProviderCatalogSource
from .adapters.provider_catalog_metadata import declared_provider_catalog_response
from .adapters.served_catalog_models import ServedCatalogModels
from .contracts import HostedCertificationStatus
from .gateway_credentials import GatewayCredentials
from .host.auth_attempt import AuthAttempt
from .host.bounded_read import BoundedRead, Identity
from .host.controller import (
    AgentHostController,
    AgentHostState,
    AgentReady,
)
from .host.store_lifecycle import (
    InvocationCancellation,
)
from .providers.application.agent_credentials import ProviderSettingsAgentCredentialSource
from .providers.application.attachment_releases import (
    AttachmentReleases,
    DisclosureRefusalCode,
)
from .providers.application.contracts import LocalEngineStatus, LocalModelListResult, ProviderSettingsRefusal
from .providers.application.local_model_list import LocalModelListService
from .providers.application.model_runs import ModelRunService
from .providers.application.next_steps import CONSOLE_SIGN_IN_COMMAND
from .providers.application.ports import ProviderCatalogUnavailableError
from .providers.application.resolution import ProviderCredentialResolver
from .providers.application.service import AssistantAuthChoice, BaseUrlChange, ProviderSettingsService
from .providers.domain.record import LocalEngine, LocalPlacement
from .providers.persistence.attachment_disclosures import SecureAttachmentDisclosureStore
from .providers.persistence.store import SecureLocalModelListStore, SecureProviderSettingsStore
from .service_attachment_admin import answer_attachment_admin
from .service_support import (
    ADMIN_READ_FRESH_SECONDS,
    ADMIN_READ_SECONDS,
    LIFECYCLE_ADMISSION_SECONDS,
)


def _disclosure_bar() -> DisclosureRefusalCode | None:
    """Name the first bar to an off-host attachment release.

    The service holds no door to the exact profile's cloud eligibility, which only
    the runtime can read, so a deployment that opted in is still refused here
    rather than assumed eligible.
    """
    settings = load_settings()
    if settings.cadrumo_evidence_gestor_mode:
        return DisclosureRefusalCode.GESTOR_MODE
    if not settings.cadrumo_evidence_cloud_upload_permitted:
        return DisclosureRefusalCode.CLOUD_UPLOAD_NOT_PERMITTED
    return DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE


class AgentServiceAdministration(ABC):
    """Own service state and guarded provider administration."""

    def __init__(
        self,
        *,
        client: InstalledServiceClient,
        storage_root: Path,
        gateway_bearer: bytearray,
        emit: Callable[[dict[str, Any]], None],
        local_engine_default: LocalEngine,
        wake: Callable[[], None] | None = None,
    ) -> None:
        """Bind provider custody and process ownership to the verified service connection.

        ``local_engine_default`` is the engine a profile that chose none runs,
        as the desktop derived it from the package.
        """
        self.client = client
        self._root = storage_root
        self._guard = RLock()
        self._closing = Event()
        self._startup_cancellation: InvocationCancellation | None = None
        self._preparation_runner: WindowsAgentInvocationRunner | None = None
        self._read_cancellation = InvocationCancellation()
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
        self._credentials = GatewayCredentials(
            ProviderSettingsAgentCredentialSource(store=self._store, resolver=resolver, catalog_source=self._catalog),
            gateway_bearer,
            self._host_token,
            self._closing,
            startup_cancellation=lambda: self._startup_cancellation,
            close_read=client.connection.close,
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
        self._attachment_releases = AttachmentReleases(
            gateway=GatewayAttachments(
                endpoint=self._background_endpoint, bearer=gateway_bearer, host_token=self._host_token
            ),
            store=SecureAttachmentDisclosureStore(client=client),
            off_host=self._lane_reads_off_host,
            eligibility=_disclosure_bar,
            session=self._disclosure_session,
        )
        self._login_status = AgentProviderAuthStatusProbe(
            context=self._login_context, cancellation=self._read_cancellation
        )
        self._local_models = LocalModelListService(
            store=model_list, catalog_source=self._catalog, default_engine=local_engine_default
        )
        self._providers = ProviderSettingsService(
            store=self._store,
            catalog_source=self._catalog,
            selected_engine=self._local_models.selected_engine,
            cli_state_probe=self._login_status.probe,
        )
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

    def _submit_sign_in_code(self, attempt_id: str | None, secret: bytearray | None) -> dict[str, Any]:
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
        run_id: str | None = None,
        permission_request_id: str | None = None,
        scope: str | None = None,
        grant_id: str | None = None,
        conversation_id: str | None = None,
        engine: str | None = None,
        placement: str | None = None,
    ) -> Any:
        """Apply one bounded masked administration request under the live lease."""
        if action.startswith("attachment_"):
            return answer_attachment_admin(
                self._attachment_releases,
                closing=self._closing.is_set(),
                action=action,
                run_id=run_id,
                request_id=permission_request_id,
                scope=scope,
                grant_id=grant_id,
                conversation_id=conversation_id,
            )
        if action == "connect_submit_code":
            return self._submit_sign_in_code(attempt_id, secret)
        if action in {"connect_status", "connect_cancel"}:
            return self._observe_sign_in(attempt_id, cancel=action == "connect_cancel")
        if action == "provider_lanes":
            return self._provider_lanes()
        if action == "local_models":
            return self._local_model_list()
        if action == "local_engine":
            return self._local_engine()
        if action in {"catalog", "status"}:
            return self._cached_read(action)
        arguments: dict[str, Any] = {
            "provider": provider,
            "expected_revision": expected_revision,
            "base_url": base_url,
            "choice": choice,
            "method": method,
            "attempt_id": attempt_id,
            "model": model,
            "secret": secret,
            "engine": engine,
            "placement": placement,
        }
        return self._lifecycle_admin(action, arguments)

    def _cached_read(self, action: str) -> Any:
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        # Each reads what the profile and the tree are now; a result is
        # served only for the lease and tree it was read under. The lease is
        # compared by value: a claim replaces the client's lease object with an
        # equal one, and claims land during a slow read from any thread (the
        # status read's generation observation, the main loop's reclaim, the
        # reread after an inactive lease). Only a newly issued lease differs.
        key = (self.client.lease, Identity(self._controller))
        read = self._catalog_read if action == "catalog" else self._status_read
        return read.answer(key, within=ADMIN_READ_SECONDS)

    def _lifecycle_admin(self, action: str, arguments: dict[str, Any]) -> Any:
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

    def _disclosure_session(self) -> object | None:
        """Identify the signed-in agent session; sign-out, lock, expiry and agent stop each change it."""
        controller = self._controller
        if self.client.lease is None or controller is None:
            return None
        generations = self._credentials.current_generations()
        return None if generations is None else (generations.sign_in, Identity(controller))

    def _lane_reads_off_host(self, provider: str, transport: str) -> bool:
        """Read the lane's typed flag; a lane the catalogue does not name is treated as leaving."""
        try:
            entry = self._catalog.catalog().entry(f"{provider}_{transport}")
        except ProviderCatalogUnavailableError:
            return True
        return True if entry is None else entry.reads_off_host

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

    def _change_provider(
        self,
        action: str,
        provider: str,
        expected_revision: str,
        base_url: str | None,
        choice: str | None,
        secret: bytearray | None,
    ) -> dict[str, Any]:
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

    def _provider_admin(
        self,
        action: str,
        provider: str,
        expected_revision: str,
        base_url: str | None,
        choice: str | None,
        method: str | None,
        secret: bytearray | None,
    ) -> dict[str, Any]:
        if action == "sign_in":
            return self._prepare_sign_in(provider, expected_revision=expected_revision)
        if action == "connect" and method in {"browser", "browser-code", "device"}:
            return self._connect(provider, expected_revision=expected_revision, method=method)
        return self._change_provider(action, provider, expected_revision, base_url, choice, secret)

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
        engine: str | None = None,
        placement: str | None = None,
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
        if action == "local_engine_choose":
            return self._choose_local_engine(engine, placement, expected_revision)
        if provider is None or expected_revision is None:
            return {"kind": "refused", "code": "invalid_request"}
        return self._provider_admin(action, provider, expected_revision, base_url, choice, method, secret)

    def _provider_lanes(self) -> dict[str, Any]:
        """Read the lanes without the supplier check; a plain store read that never waits on the agent tree.

        It answers the ``providers`` part of ``status`` and runs no command-line probe, so a cli
        lane's program state is ``unknown``.
        """
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self.client.lease
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._providers.lanes().model_dump(mode="json")
        if self.client.lease != lease:
            return {"kind": "refused", "code": "signed_out"}
        return observed

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

    def _local_engine(self) -> dict[str, Any]:
        """Read the local engine setting; a plain store read that never waits on the agent tree."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        lease = self.client.lease
        if lease is None:
            return {"kind": "refused", "code": "signed_out"}
        observed = self._local_models.engine_status().model_dump(mode="json")
        if self.client.lease != lease:
            return {"kind": "refused", "code": "signed_out"}
        return observed

    def _choose_local_engine(
        self, engine: str | None, placement: str | None, expected_revision: str | None
    ) -> dict[str, Any]:
        if engine is None or placement is None or expected_revision is None:
            return {"kind": "refused", "code": "invalid_request"}
        before = self._local_models.engine_status()
        result = self._local_models.choose_engine(
            LocalEngine(engine), LocalPlacement(placement), expected_revision=expected_revision
        )
        # The tree is replaced only when the setting it runs under changes,
        # not when an unchosen default becomes the person's choice.
        changed = (
            isinstance(result, LocalEngineStatus)
            and isinstance(before, LocalEngineStatus)
            and result.revision != expected_revision
            and (before.engine, before.placement) != (result.engine, result.placement)
        )
        controller = self._controller
        if changed and controller is not None:
            # The setting moves no provider-settings generation: the tree it
            # superseded is marked and replaced on the start thread, which
            # retires it and publishes what follows.
            controller.supersede()
            self._forget_reads()
            self._replace_superseded()
        return result.model_dump(mode="json")

    def _apply_local_model_change(
        self, action: str, lane: str | None, model: str | None, expected_revision: str
    ) -> LocalModelListResult | None:
        models = self._local_models
        if action == "local_models_reset":
            return models.reset(expected_revision=expected_revision) if lane is None and model is None else None
        if lane is None or model is None:
            return None
        if action == "local_model_add":
            return models.add(lane, model=model, expected_revision=expected_revision)
        if action == "local_model_remove":
            return models.remove(lane, model=model, expected_revision=expected_revision)
        if action == "reading_model_choose":
            return models.choose_reading(lane, model=model, expected_revision=expected_revision)
        return None

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
        result = self._apply_local_model_change(action, lane, model, expected_revision)
        if result is None:
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
        self._login_status.forget()

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
        status["console_sign_in_command"] = CONSOLE_SIGN_IN_COMMAND
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

    @abstractmethod
    def _admit_stop(self) -> dict[str, Any]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _background_endpoint(self) -> BackgroundRunEndpoint | None:
        """Provide the later service phase operation."""

    @abstractmethod
    def _clear_hosted_certifications(self) -> None:
        """Provide the later service phase operation."""

    @abstractmethod
    def _connect(self, provider: str, *, expected_revision: str, method: str) -> dict[str, Any]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _hosted_certifications(self) -> list[dict[str, str]]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _live_catalog(self) -> dict[str, Any] | None:
        """Provide the later service phase operation."""

    @abstractmethod
    def _picker_catalog(self, document: dict[str, Any]) -> dict[str, Any]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _prepare_sign_in(self, provider: str, *, expected_revision: str, gui: bool = False) -> dict[str, Any]:
        """Provide the later service phase operation."""

    @abstractmethod
    def _remember_hosted_certifications(
        self, controller: AgentHostController, ready: AgentReady, document: dict[str, Any]
    ) -> None:
        """Provide the later service phase operation."""

    @abstractmethod
    def _replace_superseded(self) -> bool:
        """Provide the later service phase operation."""

    @abstractmethod
    def _schedule_start(self) -> bool:
        """Provide the later service phase operation."""

    @abstractmethod
    def _served_catalog(self, ready: AgentReady) -> dict[str, Any]:
        """Provide the later service phase operation."""
