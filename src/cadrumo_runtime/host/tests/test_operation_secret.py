"""The installed runtime hands an export secret only to its original submitter."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
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
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationResult,
    OperationSecret,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileLogin, ProfileStatus, SessionRequest
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from .served_runtime import ServedRuntime, SyntheticLogin, serving_runtime
from .test_modelo_metadata import issue_scoped_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_EXPORT_SECRET = b"native-bundle-export-passphrase"


def _submit_export(
    client: FrontendClient, profile_id: UUID, destination: Path, deadline: float
) -> tuple[OperationPublicDefinitionContractV1, str, OperationSecretRequirement]:
    contract = client.contract(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, deadline=deadline)
    assert contract.ephemeral_secret_required and contract.result_schema is not None
    submitted = client.operation(
        OperationSubmit(
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
    assert isinstance(submitted, OperationSubmitted)
    operation_id = submitted.receipt.operation_id
    requirement = submitted.receipt.secret_requirement
    assert requirement is not None
    assert requirement.identity.operation_id == operation_id
    assert requirement.secret_kind == "profile.bundle-export.passphrase"  # noqa: S105 - public kind
    return contract, operation_id, requirement


def _refuse_stolen_and_mismatched_answers(
    client: FrontendClient, peer: FrontendClient, requirement: OperationSecretRequirement
) -> None:
    stolen = bytearray(_EXPORT_SECRET)
    with pytest.raises(FrontendRefusedError):
        peer.submit_secret(requirement, stolen, timeout=15)
    assert stolen == bytes(len(_EXPORT_SECRET))
    assert peer.status().status.connected

    mismatched = requirement.model_copy(update={"revision": requirement.revision + 1})
    wrong_revision = bytearray(_EXPORT_SECRET)
    with pytest.raises(FrontendRefusedError):
        client.submit_secret(mismatched, wrong_revision, timeout=15)
    assert wrong_revision == bytes(len(_EXPORT_SECRET))
    assert client.status().status.connected


def _refuse_another_frontend_session(
    served: ServedRuntime, profile_id: UUID, api_key: bytes, requirement: OperationSecretRequirement, deadline: float
) -> None:
    # The requirement belongs to the session that submitted it, whichever
    # frontend another session is on; the served.server refuses before its protected byte frame.
    raw_mcp = asyncio.run(served.launch.open(timeout=10))
    try:
        login = raw_mcp.login(
            ProfileLogin(
                request_id=uuid4(),
                profile_id=profile_id,
                frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
                method="api_key",
            ),
            bytearray(api_key),
            deadline=deadline,
        )
        assert isinstance(login, ProfileStatus)
        mcp_session = login.status.session_id
        assert mcp_session is not None
        forbidden = bytearray(_EXPORT_SECRET)
        refusal = raw_mcp.operation_secret(
            OperationSecret(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=mcp_session,
                requirement=requirement,
            ),
            forbidden,
            deadline=deadline,
        )
        assert isinstance(refusal, AccessRefusal)
        assert forbidden == bytes(len(_EXPORT_SECRET))
        status = raw_mcp.session(
            SessionRequest(
                action="session_status",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=mcp_session,
            ),
            deadline=deadline,
        )
        assert isinstance(status, ProfileStatus)
    finally:
        raw_mcp.close()


def _accept_original_answer_once(
    client: FrontendClient, requirement: OperationSecretRequirement, operation_id: str
) -> None:
    secret = bytearray(_EXPORT_SECRET)
    accepted = client.submit_secret(requirement, secret, timeout=20)
    assert isinstance(accepted, OperationAcknowledged)
    assert accepted.operation_id == operation_id
    assert secret == bytes(len(_EXPORT_SECRET))
    duplicate = bytearray(_EXPORT_SECRET)
    with pytest.raises(FrontendRefusedError):
        client.submit_secret(requirement, duplicate, timeout=15)
    assert duplicate == bytes(len(_EXPORT_SECRET))
    assert client.status().status.connected
    # An empty protected frame is invalid. This connection can
    # stay usable only if the occupied wait refuses before
    # asking the caller to send any secret frame.
    with pytest.raises(FrontendRefusedError):
        client.submit_secret(requirement, bytearray(), timeout=15)
    assert client.status().status.connected


def _run_export_to_terminal(
    client: FrontendClient, profile_id: UUID, operation_id: str, destination: Path, deadline: float
) -> int:
    started = client.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=client.session_id,
            operation_id=operation_id,
        ),
        deadline=deadline,
    )
    assert isinstance(started, OperationAcknowledged)
    while True:
        observed = client.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=client.session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=deadline,
        )
        assert isinstance(observed, OperationObserved)
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        projection = observed.observation.projection
        if projection.terminal_condition is not None:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert projection.effect is OperationEffect.UPDATED
    assert destination.is_file() and destination.stat().st_size > 0
    return projection.revision


def _assert_projected_export(
    client: FrontendClient,
    profile_id: UUID,
    operation_id: str,
    terminal_revision: int,
    contract: OperationPublicDefinitionContractV1,
    destination: Path,
    deadline: float,
) -> None:
    projected = client.operation(
        OperationResult(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=client.session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal_revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
        ),
        deadline=deadline,
    )
    assert isinstance(projected, OperationProjected)
    envelope = OperationResultProjectionSuccessV1[ProfileBundleExportOperationProjection].model_validate_json(
        canonical_json_bytes(projected.document)
    )
    assert envelope.definition_contract_digest == contract.definition_contract_digest
    assert envelope.result_schema == contract.result_schema
    assert envelope.projection.profile_id == str(profile_id)
    assert envelope.projection.destination == destination
    assert envelope.projection.transport is ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED


def test_original_export_secret_is_one_use_and_another_sessions_answer_is_refused_before_bytes(tmp_path: Path) -> None:
    """Wrong peers cannot answer the copied requirement; genuine export settles."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        destination = tmp_path / "private-transfer.bundle"
        # A third session, admitted by a genuine key on another frontend, also answers the wait.
        api_key = issue_scoped_key(subject)
        close_active_bucket_session()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("profile-export-secret-native-login"),
            secret_store=lambda: subject.native,
            drain_seconds=15,
        ) as served:
            client = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            )
            peer = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            )
            with client, peer:
                client.login_password(bytearray(PROFILE_INPUT.encode()))
                peer.login_password(bytearray(PROFILE_INPUT.encode()))
                deadline = time.monotonic() + 90
                contract, operation_id, requirement = _submit_export(client, profile_id, destination, deadline)
                _refuse_stolen_and_mismatched_answers(client, peer, requirement)
                _refuse_another_frontend_session(served, profile_id, api_key, requirement, deadline)
                _accept_original_answer_once(client, requirement, operation_id)
                terminal_revision = _run_export_to_terminal(client, profile_id, operation_id, destination, deadline)
                _assert_projected_export(
                    client, profile_id, operation_id, terminal_revision, contract, destination, deadline
                )
