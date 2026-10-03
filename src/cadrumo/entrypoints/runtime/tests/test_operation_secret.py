"""The installed runtime hands an export secret only to its original submitter."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
)
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportTransport,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    ProfileBundleExportOperationProjection,
    ProfileBundleExportOperationRequest,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_EXPORT_SECRET = b"native-bundle-export-passphrase"


class _LoginObservation:
    login_id = "profile-export-secret-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Provide test-owned login facts while real profile custody stays installed."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_original_tui_export_secret_is_one_use_and_server_refuses_mcp_before_bytes(tmp_path: Path) -> None:
    """Wrong peers cannot answer the copied requirement; genuine export settles."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        destination = tmp_path / "private-transfer.bundle"
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                client = asyncio.run(
                    RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
                )
                peer = asyncio.run(
                    RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
                )
                with client, peer:
                    client.login_password(bytearray(PROFILE_INPUT.encode()))
                    peer.login_password(bytearray(PROFILE_INPUT.encode()))
                    deadline = time.monotonic() + 90
                    contract = client.contract(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, deadline=deadline)
                    assert contract.ephemeral_secret_required and contract.result_schema is not None
                    submitted = client.operation(
                        RuntimeOperationSubmit(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=client.session_id,
                            definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload_json=ProfileBundleExportOperationRequest(
                                profile_id=profile_id,
                                destination=destination,
                                purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                            ).model_dump_json(),
                        ),
                        deadline=deadline,
                    )
                    assert isinstance(submitted, RuntimeOperationSubmitted)
                    operation_id = submitted.receipt.operation_id
                    requirement = submitted.receipt.secret_requirement
                    assert requirement is not None
                    assert requirement.identity.operation_id == operation_id
                    assert requirement.secret_kind == "profile.bundle-export.passphrase"  # noqa: S105 - public kind

                    stolen = bytearray(_EXPORT_SECRET)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        peer.submit_secret(requirement, stolen, timeout=15)
                    assert stolen == bytes(len(_EXPORT_SECRET))
                    assert peer.status().status.connected

                    mismatched = requirement.model_copy(update={"revision": requirement.revision + 1})
                    wrong_revision = bytearray(_EXPORT_SECRET)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        client.submit_secret(mismatched, wrong_revision, timeout=15)
                    assert wrong_revision == bytes(len(_EXPORT_SECRET))
                    assert client.status().status.connected

                    # Bypass only the frontend helper's local MCP check to exercise
                    # the verified server's refusal before its protected byte frame.
                    raw_mcp = asyncio.run(launch.open(timeout=10))
                    try:
                        login = raw_mcp.login(
                            RuntimeProfileLogin(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                frontend=OperationFrontendProjection.MCP,
                                method="password",
                            ),
                            bytearray(PROFILE_INPUT.encode()),
                            deadline=deadline,
                        )
                        assert isinstance(login, RuntimeProfileStatus)
                        mcp_session = login.status.session_id
                        assert mcp_session is not None
                        forbidden = bytearray(_EXPORT_SECRET)
                        refusal = raw_mcp.operation_secret(
                            RuntimeOperationSecret(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=mcp_session,
                                requirement=requirement,
                            ),
                            forbidden,
                            deadline=deadline,
                        )
                        assert isinstance(refusal, RuntimeAccessRefusal)
                        assert forbidden == bytes(len(_EXPORT_SECRET))
                        status = raw_mcp.session(
                            RuntimeSessionRequest(
                                action="session_status",
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=mcp_session,
                            ),
                            deadline=deadline,
                        )
                        assert isinstance(status, RuntimeProfileStatus)
                    finally:
                        raw_mcp.close()

                    secret = bytearray(_EXPORT_SECRET)
                    accepted = client.submit_secret(requirement, secret, timeout=20)
                    assert isinstance(accepted, RuntimeOperationAcknowledged)
                    assert accepted.operation_id == operation_id
                    assert secret == bytes(len(_EXPORT_SECRET))
                    duplicate = bytearray(_EXPORT_SECRET)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        client.submit_secret(requirement, duplicate, timeout=15)
                    assert duplicate == bytes(len(_EXPORT_SECRET))
                    assert client.status().status.connected
                    # An empty protected frame is invalid. This connection can
                    # stay usable only if the occupied wait refuses before
                    # asking the caller to send any secret frame.
                    with pytest.raises(RuntimeFrontendRefusedError):
                        client.submit_secret(requirement, bytearray(), timeout=15)
                    assert client.status().status.connected

                    started = client.operation(
                        RuntimeOperationControl(
                            action="operation_start",
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=client.session_id,
                            operation_id=operation_id,
                        ),
                        deadline=deadline,
                    )
                    assert isinstance(started, RuntimeOperationAcknowledged)
                    while True:
                        observed = client.operation(
                            RuntimeOperationObserve(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=client.session_id,
                                observation=OperationObservationRequestV1(
                                    operation_id=operation_id, after_cursor=0, page_limit=32
                                ),
                            ),
                            deadline=deadline,
                        )
                        assert isinstance(observed, RuntimeOperationObserved)
                        assert isinstance(observed.observation, OperationObservationSuccessV1)
                        projection = observed.observation.projection
                        if projection.terminal_condition is not None:
                            break
                        assert time.monotonic() < deadline
                        time.sleep(0.02)
                    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert projection.effect is OperationEffect.UPDATED
                    assert destination.is_file() and destination.stat().st_size > 0

                    projected = client.operation(
                        RuntimeOperationResult(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=client.session_id,
                            result=OperationResultProjectionRequestV1(
                                operation_id=operation_id,
                                terminal_revision=projection.revision,
                                definition_contract_digest=contract.definition_contract_digest,
                                result_schema=contract.result_schema,
                            ),
                        ),
                        deadline=deadline,
                    )
                    assert isinstance(projected, RuntimeOperationProjected)
                    envelope = OperationResultProjectionSuccessV1[
                        ProfileBundleExportOperationProjection
                    ].model_validate_json(canonical_json_bytes(projected.document))
                    assert envelope.definition_contract_digest == contract.definition_contract_digest
                    assert envelope.result_schema == contract.result_schema
                    assert envelope.projection.profile_id == str(profile_id)
                    assert envelope.projection.destination == destination
                    assert envelope.projection.transport is ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
