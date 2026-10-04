"""Native profile API-key enrollment support for CLI integration tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.linux_worker_process import LinuxProcessScope
from cadrumo.adapters.local_runtime.login_policy import compose_runtime_login_policy
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_retirement import retire_profile_automation
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import (
    RuntimeFailureObservation,
    observe_native_runtime_failures,
)


@dataclass(frozen=True, slots=True)
class RuntimeHealthDiagnostic:
    """Public runtime liveness facts exposed by the native fixture."""

    ready: bool
    stop_requested: bool
    serve_task_done: bool


@dataclass(frozen=True, slots=True)
class NativeProfileWorkerDiagnostic:
    """Read-only identity and native containment facts for an admitted worker."""

    identity: ProfileWorkerIdentity
    runtime_process_id: int
    worker_process_id: int
    alive: bool
    admitted_session_count: int
    exact_session_admitted: bool
    linux_scope_owns_worker: bool | None
    windows_job_owns_worker: bool | None
    guardian_process_id: int | None
    control_group: str | None
    kernel_control_groups_match: bool | None


@dataclass(frozen=True, slots=True)
class NativeServerCustodyDiagnostic:
    """Exact server custody identities and presence checks, without secret material."""

    binding: ProfileAccessBinding
    backend: NativeSecretBackend
    control_anchor_present: bool
    grant_ids: tuple[UUID, ...]
    key_ids: tuple[UUID, ...]
    wrap_count: int
    wrapping_keys_valid: bool
    runtime_uses_same_store: bool


def _retire_server_native_custody(
    store: AutomationControlStore,
    native: AutomationSecretStore,
    owned_wrap_accounts: set[str],
    runtime_drained: Event,
) -> None:
    """Retire this test profile after runtime shutdown and verify exact owned records."""
    if not runtime_drained.is_set():
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    if not retire_profile_automation(root=store.root, profile_id=store.binding.profile_id, secrets_store=native):
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    if native.read(CONTROL_NAMESPACE, store.account) is not None:
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)
    for account in owned_wrap_accounts:
        if native.read(WRAP_NAMESPACE, account) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)


class _ServerNativeCustodyRetirement:
    """Retain exact test-owned native records until post-drain retirement succeeds."""

    def __init__(
        self,
        store: AutomationControlStore,
        native: AutomationSecretStore,
        owned_wrap_accounts: set[str],
        runtime_drained: Event,
    ) -> None:
        self.store, self.native = store, native
        self.owned_wrap_accounts, self.runtime_drained = owned_wrap_accounts, runtime_drained
        self.released = False

    def _retire(self) -> None:
        _retire_server_native_custody(self.store, self.native, self.owned_wrap_accounts, self.runtime_drained)
        self.released = True

    async def close(self) -> None:
        if not self.released:
            await await_cancellation_complete(
                asyncio.to_thread(self._retire), task_name="native-api-custody-retirement"
            )


@dataclass(frozen=True)
class NativeApiCliSession[Prepared]:
    """One enrolled profile served by its exact native CLI worker."""

    profile_id: UUID
    profile_label: str
    client_id: UUID
    credential_reference: UUID
    binding: ProfileAccessBinding
    prepared: Prepared
    runtime_failure_observations: list[RuntimeFailureObservation] = field(repr=False)
    runtime_failure_events: list[RuntimeFailureObservation] = field(repr=False)
    runtime_health: Callable[[], RuntimeHealthDiagnostic] = field(repr=False)
    registered_sessions: Callable[[], tuple[UUID, ...]] = field(repr=False)
    worker_health: Callable[[UUID], NativeProfileWorkerDiagnostic] = field(repr=False)
    server_custody_health: Callable[[], NativeServerCustodyDiagnostic] = field(repr=False)
    _credential: SecretBytes = field(repr=False)
    _client_native: MemoryNativePort = field(repr=False)

    def invoke_password(self, *command: str, output_format: str = "json") -> Result:
        """Run one CLI command with the fixture's human password."""
        result = invoke_cached_cli(
            (
                "--format",
                output_format,
                "--profile",
                self.profile_label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
        )
        if PROFILE_INPUT in result.output:
            pytest.fail("profile credential appeared in CLI output", pytrace=False)
        return result

    def invoke_api_key(self, *command: str) -> Result:
        """Run one JSON CLI command through the raw API-key stdin channel."""
        key = self._credential.get_secret_value().decode("ascii")
        result = invoke_cached_cli(
            (
                "--format",
                "json",
                "--profile",
                self.profile_label,
                "--profile-auth-method",
                "api-key",
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"api_key": key}),
        )
        if key in result.output:
            pytest.fail("API credential appeared in CLI output", pytrace=False)
        return result

    def invoke_credential_reference(self, *command: str, stdin: str | None = None) -> Result:
        """Run one JSON CLI command using the enrolled native credential reference, feeding ``stdin`` if given."""
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                runtime_credentials,
                "installed_automation_secret_store",
                lambda: self._client_native,
            )
            result = invoke_cached_cli(
                (
                    "--format",
                    "json",
                    "--profile",
                    str(self.profile_id),
                    "--profile-auth-method",
                    "api-key",
                    "--profile-credential-ref",
                    str(self.credential_reference),
                    *command,
                ),
                input=stdin,
            )
        if str(self.credential_reference) in result.output:
            pytest.fail("API credential reference appeared in CLI output", pytrace=False)
        return result


@contextmanager
def native_api_cli_session[Prepared](
    tmp_path: Path,
    *,
    scope_for_destination: Callable[[UUID], AccessScope],
    prepare_profile: Callable[[UUID, Path], Prepared],
    profile_label: str = "Enrollment tests",
    server_native_store: AutomationSecretStore | None = None,
) -> Iterator[NativeApiCliSession[Prepared]]:
    """Enroll an exact API scope and serve it through the native CLI worker.

    The supplied callback owns profile-specific encrypted test data. The
    scope builder receives the enrolled client id, which is also the
    destination bound by the real enrollment and disclosure checks.
    An explicit server native store owns control and grant-wrap records through
    the same canonical enrollment/runtime paths, with retirement at teardown.
    """
    root = tmp_path / "cadrumo-storage"
    root.mkdir(parents=True, exist_ok=True)
    os_owner = owner_id()
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )
    runtime_owner = NativeRuntimeFixtureOwner(endpoint, Event(), timeout=20)
    cleanup_attempted = False
    outer_primary: BaseException | None = None
    try:
        installation = runtime_installation(
            storage_root=root,
            os_owner_id=os_owner,
            storage_identity=endpoint.storage_identity,
        )
        with (
            administration_subject(
                tmp_path,
                os_owner_id=os_owner,
                installation_id=installation.installation_id,
                profile_label=profile_label,
            ) as subject,
        ):
            selected_native = subject.native if server_native_store is None else server_native_store
            owned_wrap_accounts: set[str] = set()
            runtime_drained = Event()
            runtime_drained.set()
            if server_native_store is not None:
                assert selected_native.read(CONTROL_NAMESPACE, subject.store.account) is None
                subject.store.secrets = selected_native
                runtime_owner.after_drain = _ServerNativeCustodyRetirement(
                    subject.store, selected_native, owned_wrap_accounts, runtime_drained
                )
            requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
            subject.owner.requesting = requester
            subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
                requester=requester,
                secrets_store=subject.client_native,
            )
            profile_id = subject.store.binding.profile_id
            prepared = prepare_profile(profile_id, root)
            scope = scope_for_destination(requester.client_id)
            owner_facts = subject.owner.current
            assert owner_facts.session is not None
            subject.owner.current = changed(
                owner_facts,
                profile=changed(owner_facts.profile, scope=scope),
                session=changed(owner_facts.session, scope=scope),
            )
            subject.proposal = changed(subject.proposal, scope=scope)

            request_id = uuid4()
            subject.service.request(request_id, subject.proposal)
            approval = subject.approve(request_id)
            record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
            credential = subject.owner.delivery.endpoint.possession(record)
            assert credential is not None
            assert approval.credential_reference is not None
            assert approval.key_id is not None
            if server_native_store is not None:
                _, control = subject.store.read()
                owned_wrap_accounts.update(
                    subject.store.account + "/" + str(entry.wrap_key_id)
                    for entry in control.grants
                    if entry.wrap_key_id is not None
                )
                del control
            close_active_bucket_session()

            stop, boot = Event(), uuid4()
            with override_settings(cadrumo_dev_runtime_session_override="1"):
                login_policy = compose_runtime_login_policy(
                    os_owner_id=owner_id(), runtime_boot_id=boot, stop=stop, native_inventory=None
                )
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=login_policy.capture,
                login_inventory=login_policy.inventory,
                secret_store=lambda: selected_native,
            )
            runtime_owner.stop = stop
            runtime_owner.drained = runtime_drained
            profiles.prepare_registry()
            server = RetainedRuntimeTransportServer(
                endpoint,
                product_version=version("cadrumo"),
                stop=stop,
                profiles=profiles,
                boot_id=boot,
            )
            failure_observations: list[RuntimeFailureObservation] = []
            failure_events: list[RuntimeFailureObservation] = []

            def record_failure_observation(observation: RuntimeFailureObservation) -> None:
                failure_observations.append(observation)
                del failure_observations[:-32]
                if (
                    observation.exception_type is not None
                    or observation.stage.endswith("_raised")
                    or observation.stage == "runtime_server_failure"
                ):
                    failure_events.append(observation)
                    del failure_events[:-32]

            pool = ThreadPoolExecutor(max_workers=1)
            runtime_owner.executor = pool
            runtime_drained.clear()
            running = pool.submit(server.serve)
            runtime_owner.running = running
            runtime_owner.server = server
            runtime_primary: BaseException | None = None
            try:
                assert server.ready.wait(3)

                def runtime_health() -> RuntimeHealthDiagnostic:
                    return RuntimeHealthDiagnostic(
                        ready=server.ready.is_set(),
                        stop_requested=stop.is_set(),
                        serve_task_done=running.done(),
                    )

                def registered_sessions() -> tuple[UUID, ...]:
                    """Snapshot exact-profile connection session IDs, not an access decision."""
                    with profiles._guard:
                        sessions: list[UUID] = []
                        for connection in profiles._connections.values():
                            session_id = connection.session_id
                            if connection.profile_id == profile_id and session_id is not None:
                                sessions.append(session_id)
                        return tuple(sorted(sessions))

                def worker_health(session_id: UUID) -> NativeProfileWorkerDiagnostic:
                    """Observe an existing exact-profile worker without creating or admitting one."""
                    with profiles._guard:
                        host = profiles._profiles.get(profile_id)
                        assert host is not None, "the exact profile has not admitted a runtime worker"
                        worker = host.owner.operation_worker()
                    assert worker.identity.binding == subject.store.binding
                    worker.require_alive()
                    status = worker.status()
                    assert status.identity == worker.identity
                    scope = worker._scope
                    process_ids = scope.active_process_ids()
                    control_channel = worker._channel
                    operation_channel = worker._operation_channel
                    assert control_channel is not None and operation_channel is not None
                    peer = control_channel.peer
                    worker_pid = peer.process_id
                    assert worker_pid is not None and peer.os_owner_id == worker.identity.binding.os_owner_id
                    assert operation_channel.peer == peer
                    assert worker_pid in process_ids, "the verified control peer must belong to its native scope"
                    guardian_pid = None
                    control_group = None
                    scope_owns_worker = None
                    windows_job_owns_worker = None
                    control_groups_match = None
                    if isinstance(scope, LinuxProcessScope):
                        assert process_ids == (worker_pid,), "the Linux scope must own only the verified worker"
                        guardian = scope._guardian
                        assert guardian is not None
                        guardian_pid = guardian.pid
                        control_group = scope._cgroup
                        scope_owns_worker = scope.owns_process(worker_pid)
                        assert scope_owns_worker
                        control_groups_match = all(
                            f"0::{control_group}" in (Path("/proc") / str(pid) / "cgroup").read_text().splitlines()
                            for pid in (worker_pid, guardian_pid)
                        )
                    else:
                        assert isinstance(scope, WindowsProcessScope)
                        # Re-read native Job membership through the worker's
                        # owner predicate after selecting the exact verified
                        # control-channel peer; the job may also contain the
                        # venv redirector process.
                        windows_job_owns_worker = worker._owns_native_process(worker_pid)
                        assert windows_job_owns_worker
                    return NativeProfileWorkerDiagnostic(
                        identity=status.identity,
                        runtime_process_id=os.getpid(),
                        worker_process_id=worker_pid,
                        alive=True,
                        admitted_session_count=len(status.sessions),
                        exact_session_admitted=session_id in status.sessions,
                        linux_scope_owns_worker=scope_owns_worker,
                        windows_job_owns_worker=windows_job_owns_worker,
                        guardian_process_id=guardian_pid,
                        control_group=control_group,
                        kernel_control_groups_match=control_groups_match,
                    )

                def server_custody_health() -> NativeServerCustodyDiagnostic:
                    """Inspect only existing exact native records; never unwrap or install custody."""
                    with profiles._guard:
                        host = profiles._profiles.get(profile_id)
                        assert host is not None, "the exact profile has not admitted a runtime host"
                        assert host.store.binding == subject.store.binding
                        runtime_uses_same_store = host.store.secrets is selected_native
                    assert subject.store.secrets is selected_native
                    control_present = selected_native.read(CONTROL_NAMESPACE, subject.store.account) is not None
                    _, control = subject.store.read()
                    assert control.binding == subject.store.binding
                    accounts = tuple(
                        subject.store.account + "/" + str(entry.wrap_key_id)
                        for entry in control.grants
                        if entry.wrap_key_id is not None
                    )
                    owned_wrap_accounts.update(accounts)
                    wrapping_keys_valid = True
                    for account in accounts:
                        wrapping_key = selected_native.read(WRAP_NAMESPACE, account)
                        if wrapping_key is None or len(wrapping_key.get_secret_value()) != 32:
                            wrapping_keys_valid = False
                        del wrapping_key
                    return NativeServerCustodyDiagnostic(
                        binding=control.binding,
                        backend=selected_native.backend,
                        control_anchor_present=control_present,
                        grant_ids=tuple(entry.grant.grant_id for entry in control.grants),
                        key_ids=tuple(item.key.key_id for entry in control.grants for item in entry.keys),
                        wrap_count=len(accounts),
                        wrapping_keys_valid=wrapping_keys_valid,
                        runtime_uses_same_store=runtime_uses_same_store,
                    )

                with observe_native_runtime_failures(
                    server,
                    profiles,
                    failure_observer=record_failure_observation,
                ):
                    yield NativeApiCliSession(
                        profile_id=profile_id,
                        profile_label=profile_label,
                        client_id=requester.client_id,
                        credential_reference=approval.credential_reference,
                        binding=subject.store.binding,
                        prepared=prepared,
                        runtime_failure_observations=failure_observations,
                        runtime_failure_events=failure_events,
                        runtime_health=runtime_health,
                        registered_sessions=registered_sessions,
                        worker_health=worker_health,
                        server_custody_health=server_custody_health,
                        _credential=credential,
                        _client_native=subject.client_native,
                    )
            except BaseException as error:
                runtime_primary = error
                raise
            finally:
                cleanup_attempted = True
                runtime_owner.close_from_sync(task_name="native-api-runtime-close", primary_error=runtime_primary)
    except BaseException as error:
        outer_primary = error
        raise
    finally:
        if not cleanup_attempted:
            runtime_owner.close_from_sync(task_name="native-api-runtime-close", primary_error=outer_primary)


__all__ = [
    "NativeApiCliSession",
    "NativeProfileWorkerDiagnostic",
    "NativeServerCustodyDiagnostic",
    "RuntimeHealthDiagnostic",
    "native_api_cli_session",
]
