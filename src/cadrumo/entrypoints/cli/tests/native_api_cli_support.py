"""Native profile API-key enrollment support for CLI integration tests."""

from __future__ import annotations

import json
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
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from ._runtime_profile_cli_fixture import (
    RuntimeFailureObservation,
    observe_native_runtime_failures,
    runtime_failure_observation,
)
from .cli_runner import invoke_cached_cli


class _ApiLoginObservation:
    """Synthetic OS-login observation for the real local worker transport."""

    login_id = "cli-native-api-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Return an active test-owned login tied to the current OS owner."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass(frozen=True, slots=True)
class RuntimeHealthDiagnostic:
    """Public runtime liveness facts exposed by the native fixture."""

    ready: bool
    stop_requested: bool
    serve_task_done: bool


@dataclass(frozen=True)
class NativeApiCliSession[Prepared]:
    """One enrolled profile served by its exact native CLI worker."""

    profile_id: UUID
    profile_label: str
    client_id: UUID
    credential_reference: UUID
    prepared: Prepared
    runtime_failure_observations: list[RuntimeFailureObservation] = field(repr=False)
    runtime_failure_events: list[RuntimeFailureObservation] = field(repr=False)
    runtime_health: Callable[[], RuntimeHealthDiagnostic] = field(repr=False)
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

    def invoke_credential_reference(self, *command: str) -> Result:
        """Run one JSON CLI command using the enrolled native credential reference."""
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
) -> Iterator[NativeApiCliSession[Prepared]]:
    """Enroll an exact API scope and serve it through the native CLI worker.

    The supplied callback owns profile-specific encrypted test data. The
    scope builder receives the enrolled client id, which is also the
    destination bound by the real enrollment and disclosure checks.
    """
    root = tmp_path / "cadrumo-storage"
    root.mkdir(parents=True, exist_ok=True)
    os_owner = owner_id()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root,
        os_owner_id=os_owner,
        storage_identity=endpoint.storage_identity,
    )
    try:
        with administration_subject(
            tmp_path,
            os_owner_id=os_owner,
            installation_id=installation.installation_id,
        ) as subject:
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
            close_active_bucket_session()

            stop, boot = Event(), uuid4()
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: _ApiLoginObservation(),
                secret_store=lambda: subject.native,
            )
            server = RuntimeTransportServer(
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

            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert server.ready.wait(3)

                    def runtime_health() -> RuntimeHealthDiagnostic:
                        return RuntimeHealthDiagnostic(
                            ready=server.ready.is_set(),
                            stop_requested=stop.is_set(),
                            serve_task_done=running.done(),
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
                            prepared=prepared,
                            runtime_failure_observations=failure_observations,
                            runtime_failure_events=failure_events,
                            runtime_health=runtime_health,
                            _credential=credential,
                            _client_native=subject.client_native,
                        )
                finally:
                    primary = sys.exception()
                    stop.set()
                    try:
                        running.result(timeout=20)
                    except Exception as server_error:
                        if primary is None:
                            raise
                        observation = runtime_failure_observation("runtime_server_future", server_error)
                        primary.add_note(f"RuntimeTransportServer failure observation={observation!r}")
    finally:
        endpoint.close()


__all__ = [
    "NativeApiCliSession",
    "RuntimeHealthDiagnostic",
    "native_api_cli_session",
]
