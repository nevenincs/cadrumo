"""Native worker acceptance for oversized and interrupted operation submissions."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import (
    MAXIMUM_FRAME_BYTES,
    VerifiedRuntimeConnection,
    read_document,
    write_document,
    write_secret,
)
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPayloadReady,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeReply,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from cadrumo.application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SubmissionPayloadDescriptor,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.modelos.work_unit import WorkUnit

from ..profile_connections import RuntimeProfileConnections
from .test_modelo_metadata import _admit, _connect, _issue_scoped_key, _LoginObservation, _seed_periods

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass(frozen=True, slots=True)
class _NativeBulkRuntime:
    endpoint: WindowsRuntimeEndpoint
    profile_id: UUID
    api_key: bytes
    work_unit: WorkUnit


@pytest.fixture
def native_bulk_runtime(tmp_path: Path) -> Iterator[_NativeBulkRuntime]:
    """Compose the real Windows runtime around a synthetic encrypted profile."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    try:
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        with administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject:
            profile_id = subject.store.binding.profile_id
            work_unit, _ = _seed_periods(profile_id)
            api_key = _issue_scoped_key(subject)
            close_active_bucket_session()

            stop, boot = Event(), uuid4()
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: _LoginObservation(),
                secret_store=lambda: subject.native,
            )
            server = RuntimeTransportServer(
                endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert server.ready.wait(3)
                    yield _NativeBulkRuntime(endpoint, profile_id, api_key, work_unit)
                finally:
                    primary = sys.exception()
                    stop.set()
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
    finally:
        endpoint.close()


def _connect_with_raw_channel(
    endpoint: WindowsRuntimeEndpoint,
) -> tuple[RuntimeByteChannel, VerifiedRuntimeConnection]:
    """Retain the endpoint-owned channel while the verified client admits a session."""
    channel = endpoint.connect(timeout=3)
    try:
        client = VerifiedRuntimeConnection(
            channel,
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    except BaseException:
        channel.close()
        raise
    return channel, client


def _rename_request(work_unit: WorkUnit | ModeloWorkRenamePublicResultV2, new_name: str) -> ModeloWorkRenameRequest:
    unit = work_unit.unit if isinstance(work_unit, ModeloWorkRenamePublicResultV2) else work_unit
    return ModeloWorkRenameRequest(
        work_unit_id=unit.work_unit_id,
        new_name=new_name,
        observed_name=unit.name,
        observed_updated_at=unit.updated_at,
        actor="native-bulk-submission-test",
    )


def _stream_request(
    *, profile_id: UUID, session_id: UUID, work_unit: WorkUnit | ModeloWorkRenamePublicResultV2, payload_json: str
) -> tuple[RuntimeOperationSubmitPayload, bytes]:
    content = payload_json.encode("utf-8")
    descriptor = SubmissionPayloadDescriptor(byte_count=len(content), payload_digest=sha256_hex(content))
    unit = work_unit.unit if isinstance(work_unit, ModeloWorkRenamePublicResultV2) else work_unit
    return (
        RuntimeOperationSubmitPayload(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
            subject_ref=unit.work_unit_id,
            descriptor=descriptor,
        ),
        content,
    )


def _begin_upload(
    channel: RuntimeByteChannel, request: RuntimeOperationSubmitPayload, *, deadline: float
) -> RuntimeOperationPayloadReady:
    write_document(channel, request, deadline=deadline)
    reply = read_document(channel, RuntimeReply, deadline=deadline).root
    assert isinstance(reply, RuntimeOperationPayloadReady), reply
    assert reply.request_id == request.request_id
    assert reply.descriptor == request.descriptor
    return reply


def _send_chunk(channel: RuntimeByteChannel, content: bytes, offset: int, *, deadline: float) -> None:
    chunk = bytearray(content[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES])
    assert chunk
    write_secret(channel, chunk, deadline=deadline)
    assert chunk == bytes(len(chunk))


def _rename_and_execute(
    connection: VerifiedRuntimeConnection,
    *,
    profile_id: UUID,
    session_id: UUID,
    work_unit: WorkUnit | ModeloWorkRenamePublicResultV2,
    new_name: str,
    payload_padding_bytes: int = 0,
) -> ModeloWorkRenamePublicResultV2:
    """Submit, start, observe and type-check a real registered encrypted rename."""
    unit = work_unit.unit if isinstance(work_unit, ModeloWorkRenamePublicResultV2) else work_unit
    contract = connection.operation(
        RuntimeOperationContract(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(contract, RuntimeOperationContractReply), contract
    assert contract.contract.result_schema is not None

    payload_json = " " * payload_padding_bytes + _rename_request(work_unit, new_name).model_dump_json()
    request = RuntimeOperationSubmit(
        request_id=uuid4(),
        profile_id=profile_id,
        session_id=session_id,
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        payload_json=payload_json,
    )
    if payload_padding_bytes:
        assert len(canonical_json_bytes(request.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES

    submitted = connection.operation(request, deadline=time.monotonic() + 20)
    assert isinstance(submitted, RuntimeOperationSubmitted), submitted
    operation_id = submitted.receipt.operation_id
    started = connection.operation(
        RuntimeOperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(started, RuntimeOperationAcknowledged), started
    assert started.operation_id == operation_id

    deadline = time.monotonic() + 20
    while True:
        observed = connection.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=deadline,
        )
        assert isinstance(observed, RuntimeOperationObserved), observed
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        projection = observed.observation.projection
        if projection.terminal_condition is not None:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)

    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert projection.effect is OperationEffect.UPDATED
    result = connection.operation(
        RuntimeOperationResult(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=projection.revision,
                definition_contract_digest=contract.contract.definition_contract_digest,
                result_schema=contract.contract.result_schema,
            ),
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(result, RuntimeOperationProjected), result
    assert result.operation_id == operation_id
    typed = OperationResultProjectionSuccessV1[ModeloWorkRenamePublicResultV2].model_validate_json(
        json.dumps(result.document)
    )
    assert typed.projection.work_unit_id == unit.work_unit_id
    assert typed.projection.name == new_name
    assert typed.projection.bucket_id == str(profile_id)
    assert typed.projection.unit.name == new_name
    return typed.projection


def test_native_bulk_submission_survives_disconnect_and_session_lock(native_bulk_runtime: _NativeBulkRuntime) -> None:
    """Exercise large JSON transport, partial-stream cleanup, and lock fencing."""
    endpoint = native_bulk_runtime.endpoint
    profile_id = native_bulk_runtime.profile_id
    work_unit: WorkUnit | ModeloWorkRenamePublicResultV2 = native_bulk_runtime.work_unit

    with ExitStack() as clients:
        initial = _connect(endpoint)
        clients.callback(initial.close)
        initial_session = _admit(initial, profile_id, method="api_key", proof=native_bulk_runtime.api_key)

        # The padding tests the byte-framed transport threshold only; it does not cover financial-row payloads.
        work_unit = _rename_and_execute(
            initial,
            profile_id=profile_id,
            session_id=initial_session,
            work_unit=work_unit,
            new_name="Oversized transport rename",
            payload_padding_bytes=MAXIMUM_FRAME_BYTES + 1,
        )
        initial.close()

        interrupted_channel, interrupted = _connect_with_raw_channel(endpoint)
        clients.callback(interrupted.close)
        interrupted_session = _admit(interrupted, profile_id, method="api_key", proof=native_bulk_runtime.api_key)
        partial_json = (
            " " * SUBMISSION_PAYLOAD_CHUNK_BYTES
            + _rename_request(work_unit, "Must not be submitted after disconnect").model_dump_json()
        )
        partial_request, partial_content = _stream_request(
            profile_id=profile_id,
            session_id=interrupted_session,
            work_unit=work_unit,
            payload_json=partial_json,
        )
        assert SUBMISSION_PAYLOAD_CHUNK_BYTES < len(partial_content) < 2 * SUBMISSION_PAYLOAD_CHUNK_BYTES
        _begin_upload(interrupted_channel, partial_request, deadline=time.monotonic() + 20)
        _send_chunk(interrupted_channel, partial_content, 0, deadline=time.monotonic() + 20)
        interrupted.close()

        survivor = _connect(endpoint)
        clients.callback(survivor.close)
        survivor_session = _admit(survivor, profile_id, method="api_key", proof=native_bulk_runtime.api_key)
        work_unit = _rename_and_execute(
            survivor,
            profile_id=profile_id,
            session_id=survivor_session,
            work_unit=work_unit,
            new_name="Survived disconnected upload",
        )
        survivor.close()

        upload_channel, uploader = _connect_with_raw_channel(endpoint)
        clients.callback(uploader.close)
        upload_session = _admit(uploader, profile_id, method="api_key", proof=native_bulk_runtime.api_key)
        survivor = _connect(endpoint)
        clients.callback(survivor.close)
        survivor_session = _admit(survivor, profile_id, method="api_key", proof=native_bulk_runtime.api_key)
        human = _connect(endpoint)
        clients.callback(human.close)
        human_session = _admit(human, profile_id, method="password", proof=PROFILE_INPUT.encode())

        locked_json = (
            " " * SUBMISSION_PAYLOAD_CHUNK_BYTES
            + _rename_request(work_unit, "Must not be submitted after lock").model_dump_json()
        )
        locked_request, locked_content = _stream_request(
            profile_id=profile_id,
            session_id=upload_session,
            work_unit=work_unit,
            payload_json=locked_json,
        )
        assert SUBMISSION_PAYLOAD_CHUNK_BYTES < len(locked_content) < 2 * SUBMISSION_PAYLOAD_CHUNK_BYTES
        _begin_upload(upload_channel, locked_request, deadline=time.monotonic() + 20)
        _send_chunk(upload_channel, locked_content, 0, deadline=time.monotonic() + 20)

        locked = human.session(
            RuntimeSessionRequest(
                action="session_lock",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=human_session,
                target_session_id=upload_session,
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(locked, RuntimeSessionsLocked), locked
        assert upload_session in locked.session_ids

        try:
            _send_chunk(upload_channel, locked_content, SUBMISSION_PAYLOAD_CHUNK_BYTES, deadline=time.monotonic() + 20)
            outcome = read_document(upload_channel, RuntimeReply, deadline=time.monotonic() + 20).root
        except RuntimeRefusalError as error:
            assert error.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        else:
            assert isinstance(outcome, RuntimeAccessRefusal), outcome
            assert outcome.code in {AccessDenialCode.SESSION_INACTIVE, AccessDenialCode.CONNECTION_MISMATCH}

        # Native submission is not autostart; this proves no successful receipt and a live survivor submit,
        # while canonical inventory remains outside this test's evidence.
        work_unit = _rename_and_execute(
            survivor,
            profile_id=profile_id,
            session_id=survivor_session,
            work_unit=work_unit,
            new_name="Survived locked upload",
        )
        assert work_unit.name == "Survived locked upload"
