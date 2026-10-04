"""A TUI controller uses the installed runtime's real worker and session guard."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject, changed
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass
class _NativeLogin:
    owner: str
    login_id: str = "tui-controller-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _client(endpoint: WindowsRuntimeEndpoint, profile_id: UUID, secret: bytes) -> RuntimeFrontendClient:
    connection = VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    client = RuntimeFrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
    try:
        client.login_api_key(bytearray(secret))
    except BaseException:
        client.close()
        raise
    return client


def _submit_view(client: RuntimeFrontendClient) -> RuntimeOperationController:
    return asyncio.run(
        RuntimeOperationController.submit(
            client,
            definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{client.profile_id}",
            payload=ProfileViewOperationRequest(profile_id=client.profile_id, page_kind=ProfileViewPageKind.FACTS),
        )
    )


async def _inspect_unregistered_review(controller: RuntimeOperationController, *, revision: int) -> object:
    control = await controller.response_control(interaction_id="a" * 64, revision=revision)
    return await control.inspect()


def test_native_tui_controller_keeps_start_and_review_authority_with_original_session(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as enrollment:
        requester = changed(enrollment.owner.requesting, destination_id=enrollment.owner.requesting.client_id)
        enrollment.owner.requesting = requester
        enrollment.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=enrollment.client_native
        )
        scope = changed(
            enrollment.proposal.scope,
            operations=frozenset({PROFILE_VIEW_OPERATION_DEFINITION_ID}),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=requester.client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    DisclosurePermission(
                        destination_id=requester.client_id,
                        projection_id=f"{PROFILE_VIEW_OPERATION_DEFINITION_ID}.result",
                        category=DisclosureCategory.PROFILE_VALUES,
                    ),
                }
            ),
        )
        current = enrollment.owner.current
        assert current.session is not None
        enrollment.owner.current = changed(
            current, profile=changed(current.profile, scope=scope), session=changed(current.session, scope=scope)
        )
        enrollment.proposal = changed(enrollment.proposal, scope=scope)
        enrollment_request = uuid4()
        enrollment.service.request(enrollment_request, enrollment.proposal)
        enrollment.approve(enrollment_request)
        record = enrollment.store.enrollment_state().requests[0]
        secret = enrollment.owner.delivery.endpoint.possession(record)
        assert secret is not None
        profile_id = enrollment.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _NativeLogin(owner_id()),
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[RuntimeFrontendClient] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                original = _client(endpoint, profile_id, secret.get_secret_value())
                another = _client(endpoint, profile_id, secret.get_secret_value())
                clients.extend((original, another))
                assert original.session_id != another.session_id
                controller = _submit_view(original)
                assert controller.actor_ref == f"session:{original.session_id}"
                before_refresh = original.status().status
                refreshed = original.refresh_api_key().status
                assert refreshed.denial is None
                assert refreshed.session_id == before_refresh.session_id == controller.session_id
                assert refreshed.profile_id == before_refresh.profile_id == profile_id
                assert refreshed.effective_scope == before_refresh.effective_scope
                assert original.session_id == controller.session_id
                assert controller.actor_ref == f"session:{original.session_id}"
                stolen = RuntimeOperationController(
                    client=another, operation_id=controller.operation_id, session_id=another.session_id
                )
                with pytest.raises(RuntimeFrontendRefusedError):
                    asyncio.run(stolen.start())
                with pytest.raises(RuntimeFrontendRefusedError):
                    asyncio.run(_inspect_unregistered_review(stolen, revision=1))
                assert asyncio.run(controller.start()) == controller.operation_id
                deadline = time.monotonic() + 10
                while True:
                    observed = asyncio.run(controller.observe(0, page_limit=32))
                    assert isinstance(observed, OperationObservationSuccessV1)
                    if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                        break
                    assert time.monotonic() < deadline
                    time.sleep(0.02)
                assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                with pytest.raises(RuntimeFrontendRefusedError):
                    asyncio.run(_inspect_unregistered_review(controller, revision=observed.projection.revision))
                cancelled = asyncio.run(controller.cancel(expected_revision=observed.projection.revision))
                assert isinstance(cancelled, OperationCancellationRefusalV1)
                assert cancelled.code is OperationCancellationRefusalCode.OPERATION_TERMINAL
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()
