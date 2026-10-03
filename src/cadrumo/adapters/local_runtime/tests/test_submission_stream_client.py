"""Bulk submissions use bounded frames only after exact runtime readiness."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest

from ....application.operations.frontend_requests import OperationSubmissionReceiptV1
from ....application.runtime.contracts import (
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ....application.runtime.operation_access import (
    RuntimeOperationPayloadReady,
    RuntimeOperationReply,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
    RuntimeOperationSubmitted,
)
from ....application.runtime.profile_access import RuntimeAccessRefusal, RuntimeRequest, RuntimeSessionRequest
from ....application.runtime.submission_payload import SUBMISSION_PAYLOAD_CHUNK_BYTES, SUBMISSION_PAYLOAD_MAX_BYTES
from ....application.user_profile.access_contracts import AccessDenialCode
from ....core.hashing import sha256_hex
from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake
from ..runtime_frame_io import read_document, read_secret, write_document
from .test_projection_page_client import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PROFILE_ID = UUID("b1270000-0000-4000-8000-000000000001")
_SESSION_ID = UUID("b1270000-0000-4000-8000-000000000002")
_CONNECTION_ID = UUID("b1270000-0000-4000-8000-000000000003")
_OPERATION_ID = "a" * 64


def _request(payload_json: str) -> RuntimeOperationSubmit:
    return RuntimeOperationSubmit(
        request_id=uuid4(),
        profile_id=_PROFILE_ID,
        session_id=_SESSION_ID,
        definition_id="test.submit",
        subject_ref="work-unit",
        payload_json=payload_json,
    )


def _exchange(
    request: RuntimeOperationSubmit,
    serve_request: Callable[[MemoryChannel, RuntimeServerHello], None],
    *,
    pin_connection: bool = False,
) -> RuntimeOperationReply | RuntimeAccessRefusal | RuntimeRefusalError:
    client_channel, server_channel = MemoryChannel(), MemoryChannel()
    client_channel.pair(server_channel)
    hello = RuntimeServerHello(product_version="upload-test", storage_identity="e" * 64, boot_id=uuid4())

    def serve() -> None:
        try:
            accept_runtime_handshake(server_channel, identity=hello, deadline=time.monotonic() + 10)
            serve_request(server_channel, hello)
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = VerifiedRuntimeConnection(
            client_channel,
            expected=RuntimeClientHello(product_version=hello.product_version, storage_identity=hello.storage_identity),
            deadline=time.monotonic() + 10,
        )
        try:
            if pin_connection:
                connection.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                    ),
                    deadline=time.monotonic() + 10,
                )
            try:
                outcome = connection.operation(request, deadline=time.monotonic() + 10)
            except RuntimeRefusalError as error:
                outcome = error
            serving.result(timeout=10)
            return outcome
        finally:
            connection.close()


def _receipt(request_id: UUID, boot_id: UUID) -> RuntimeOperationSubmitted:
    return RuntimeOperationSubmitted(
        request_id=request_id,
        runtime_boot_id=boot_id,
        connection_id=_CONNECTION_ID,
        receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=None),
    )


def test_small_submission_uses_one_document_frame() -> None:
    request = _request('{"row":"small"}')

    def serve(channel: MemoryChannel, hello: RuntimeServerHello) -> None:
        received = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 10).root
        assert isinstance(received, RuntimeOperationSubmit)
        assert received == request
        write_document(channel, _receipt(request.request_id, hello.boot_id), deadline=time.monotonic() + 10)

    outcome = _exchange(request, serve)
    assert isinstance(outcome, RuntimeOperationSubmitted)
    assert outcome.receipt.operation_id == _OPERATION_ID


@pytest.mark.parametrize("value", ["a" * 90_000, "ñ" * 45_000, '\\"' * 45_000], ids=["ascii", "unicode", "escaping"])
@pytest.mark.parametrize("final_refusal", [False, True], ids=["receipt", "refusal"])
def test_large_submission_streams_exact_bytes_after_readiness(value: str, final_refusal: bool) -> None:
    payload_json = json.dumps({"row": value}, ensure_ascii=False, separators=(",", ":"))
    request = _request(payload_json)
    expected = payload_json.encode("utf-8")
    assert len(expected) > 64 * 1024

    def serve(channel: MemoryChannel, hello: RuntimeServerHello) -> None:
        begin = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 10).root
        assert isinstance(begin, RuntimeOperationSubmitPayload)
        assert begin.request_id == request.request_id
        assert begin.profile_id == request.profile_id and begin.session_id == request.session_id
        assert begin.definition_id == request.definition_id and begin.subject_ref == request.subject_ref
        assert begin.descriptor.byte_count == len(expected)
        assert begin.descriptor.payload_digest == sha256_hex(expected)
        assert not channel.read_ready()  # The client awaits correlated readiness before any S frame.
        write_document(
            channel,
            RuntimeOperationPayloadReady(
                request_id=begin.request_id,
                runtime_boot_id=hello.boot_id,
                connection_id=_CONNECTION_ID,
                descriptor=begin.descriptor,
            ),
            deadline=time.monotonic() + 10,
        )
        chunks: list[bytes] = []
        while sum(map(len, chunks)) < begin.descriptor.byte_count:
            with read_secret(channel, deadline=time.monotonic() + 10) as chunk:
                assert 0 < len(chunk) <= SUBMISSION_PAYLOAD_CHUNK_BYTES
                chunks.append(bytes(chunk))
        assert b"".join(chunks) == expected
        assert sha256_hex(b"".join(chunks)) == begin.descriptor.payload_digest
        final = (
            RuntimeAccessRefusal(
                request_id=begin.request_id,
                runtime_boot_id=hello.boot_id,
                connection_id=_CONNECTION_ID,
                code=AccessDenialCode.OPERATION_UNAVAILABLE,
            )
            if final_refusal
            else _receipt(begin.request_id, hello.boot_id)
        )
        write_document(channel, final, deadline=time.monotonic() + 10)

    outcome = _exchange(request, serve)
    if final_refusal:
        assert isinstance(outcome, RuntimeAccessRefusal)
        assert outcome.code is AccessDenialCode.OPERATION_UNAVAILABLE
    else:
        assert isinstance(outcome, RuntimeOperationSubmitted)
        assert outcome.receipt.operation_id == _OPERATION_ID


@pytest.mark.parametrize("fault", ["request", "descriptor", "boot", "connection", "refusal"])
def test_wrong_readiness_or_early_refusal_sends_no_body(fault: str) -> None:
    request = _request('{"row":"' + "x" * 90_000 + '"}')

    def serve(channel: MemoryChannel, hello: RuntimeServerHello) -> None:
        if fault == "connection":
            status = read_document(channel, RuntimeSessionRequest, deadline=time.monotonic() + 10)
            write_document(
                channel,
                RuntimeAccessRefusal(
                    request_id=status.request_id,
                    runtime_boot_id=hello.boot_id,
                    connection_id=_CONNECTION_ID,
                    code=RuntimeRefusalCode.UNAVAILABLE,
                ),
                deadline=time.monotonic() + 10,
            )
        begin = read_document(channel, RuntimeRequest, deadline=time.monotonic() + 10).root
        assert isinstance(begin, RuntimeOperationSubmitPayload)
        if fault == "refusal":
            ready = RuntimeAccessRefusal(
                request_id=begin.request_id,
                runtime_boot_id=hello.boot_id,
                connection_id=_CONNECTION_ID,
                code=AccessDenialCode.OPERATION_UNAVAILABLE,
            )
        else:
            ready = RuntimeOperationPayloadReady(
                request_id=uuid4() if fault == "request" else begin.request_id,
                runtime_boot_id=uuid4() if fault == "boot" else hello.boot_id,
                connection_id=uuid4() if fault == "connection" else _CONNECTION_ID,
                descriptor=(
                    begin.descriptor.model_copy(update={"payload_digest": "f" * 64})
                    if fault == "descriptor"
                    else begin.descriptor
                ),
            )
        write_document(channel, ready, deadline=time.monotonic() + 10)
        with pytest.raises(RuntimeRefusalError) as no_body:
            channel.read_exact(1, deadline=time.monotonic() + 0.2)
        assert no_body.value.reason is (
            RuntimeRefusalCode.DEADLINE_EXCEEDED if fault == "refusal" else RuntimeRefusalCode.CONNECTION_CLOSED
        )

    outcome = _exchange(request, serve, pin_connection=fault == "connection")
    if fault == "refusal":
        assert isinstance(outcome, RuntimeAccessRefusal)
    else:
        assert isinstance(outcome, RuntimeRefusalError)
        assert outcome.reason is RuntimeRefusalCode.INVALID_FRAME


def test_payload_over_utf8_limit_refuses_before_first_document() -> None:
    request = _request('{"row":"' + "ñ" * (SUBMISSION_PAYLOAD_MAX_BYTES // 2) + '"}')

    def serve(channel: MemoryChannel, _hello: RuntimeServerHello) -> None:
        with pytest.raises(RuntimeRefusalError) as no_document:
            channel.read_exact(1, deadline=time.monotonic() + 0.2)
        assert no_document.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED

    outcome = _exchange(request, serve)
    assert isinstance(outcome, RuntimeRefusalError)
    assert outcome.reason is RuntimeRefusalCode.INVALID_FRAME


def test_non_utf8_python_string_refuses_before_first_document() -> None:
    request = _request('{"row":"x"}').model_copy(update={"payload_json": '{"row":"' + "\ud800" * 70_000 + '"}'})

    def serve(channel: MemoryChannel, _hello: RuntimeServerHello) -> None:
        with pytest.raises(RuntimeRefusalError) as no_document:
            channel.read_exact(1, deadline=time.monotonic() + 0.2)
        assert no_document.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED

    outcome = _exchange(request, serve)
    assert isinstance(outcome, RuntimeRefusalError)
    assert outcome.reason is RuntimeRefusalCode.INVALID_FRAME
