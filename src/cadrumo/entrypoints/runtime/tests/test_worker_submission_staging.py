"""Worker-local upload staging cannot become an operation before final bytes."""

from __future__ import annotations

import base64
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerSubmissionAbortRequest,
    ProfileWorkerSubmissionBeginRequest,
    ProfileWorkerSubmissionChunkRequest,
    ProfileWorkerSubmissionFinishRequest,
)
from cadrumo.application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.hashing import sha256_hex
from cadrumo.entrypoints.runtime.worker_submission_staging import WorkerSubmissionStaging

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SESSION = UUID("a4314f2e-1158-4110-aaf2-b7d6584ddf36")
_CONNECTION = UUID("68993340-a529-4d50-a41c-d1a15bfd8f26")


def _begin(body: bytes, *, upload_id: UUID | None = None) -> ProfileWorkerSubmissionBeginRequest:
    return ProfileWorkerSubmissionBeginRequest(
        request_id=uuid4(),
        upload_id=upload_id or uuid4(),
        connection_id=_CONNECTION,
        session_id=_SESSION,
        frontend=OperationFrontendProjection.CLI,
        definition_id="user-profile.patch",
        subject_ref="profile:exact",
        idempotency_key="same-intent",
        descriptor=SubmissionPayloadDescriptor(byte_count=len(body), payload_digest=sha256_hex(body)),
    )


def _chunk(
    begin: ProfileWorkerSubmissionBeginRequest, body: bytes, *, offset: int = 0
) -> ProfileWorkerSubmissionChunkRequest:
    return ProfileWorkerSubmissionChunkRequest(
        request_id=uuid4(),
        upload_id=begin.upload_id,
        connection_id=begin.connection_id,
        session_id=begin.session_id,
        chunk=SubmissionPayloadChunk(offset=offset, encoded=base64.b64encode(body).decode("ascii")),
    )


def _finish(begin: ProfileWorkerSubmissionBeginRequest) -> ProfileWorkerSubmissionFinishRequest:
    return ProfileWorkerSubmissionFinishRequest(
        request_id=uuid4(),
        upload_id=begin.upload_id,
        connection_id=begin.connection_id,
        session_id=begin.session_id,
    )


def _abort(begin: ProfileWorkerSubmissionBeginRequest) -> ProfileWorkerSubmissionAbortRequest:
    return ProfileWorkerSubmissionAbortRequest(
        request_id=uuid4(),
        upload_id=begin.upload_id,
        connection_id=begin.connection_id,
        session_id=begin.session_id,
    )


def test_exact_session_multichunk_finish_returns_only_verified_payload() -> None:
    """Staging preserves intent coordinates until complete digest-checked UTF-8."""
    body = b'{"long":"' + b"x" * SUBMISSION_PAYLOAD_CHUNK_BYTES + b'"}'
    begin = _begin(body)
    staging = WorkerSubmissionStaging()

    staging.begin(begin)
    staging.append(_chunk(begin, body[:SUBMISSION_PAYLOAD_CHUNK_BYTES]))
    staging.append(_chunk(begin, body[SUBMISSION_PAYLOAD_CHUNK_BYTES:], offset=SUBMISSION_PAYLOAD_CHUNK_BYTES))
    submitted = staging.finish(_finish(begin))

    assert submitted.payload_json == body.decode("utf-8")
    assert submitted.session_id == begin.session_id
    assert submitted.frontend is begin.frontend
    assert submitted.definition_id == begin.definition_id
    assert submitted.subject_ref == begin.subject_ref
    assert submitted.idempotency_key == begin.idempotency_key
    assert body.decode("utf-8") not in repr(submitted)
    assert "same-intent" not in repr(submitted)
    with pytest.raises(AutomationCustodyError) as replay:
        staging.finish(_finish(begin))
    assert replay.value.reason is AutomationCustodyCode.MISSING


def test_wrong_binding_cannot_append_or_abort_another_connection_upload() -> None:
    """The UUID is never a transferable staging bearer."""
    body = b'{"x":1}'
    begin = _begin(body)
    staging = WorkerSubmissionStaging()
    staging.begin(begin)

    with pytest.raises(AutomationCustodyError) as wrong_chunk:
        staging.append(_chunk(begin, body).model_copy(update={"connection_id": uuid4()}))
    assert wrong_chunk.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    with pytest.raises(AutomationCustodyError) as wrong_abort:
        staging.abort(_abort(begin).model_copy(update={"session_id": uuid4()}))
    assert wrong_abort.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    with pytest.raises(AutomationCustodyError) as wrong_finish:
        staging.finish(_finish(begin).model_copy(update={"connection_id": uuid4()}))
    assert wrong_finish.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED

    staging.append(_chunk(begin, body))
    assert staging.finish(_finish(begin)).payload_json == body.decode("utf-8")


def test_bad_digest_drops_only_its_upload_and_other_session_can_finish() -> None:
    """One malformed client does not poison the worker or a peer upload."""
    body = b'{"x":1}'
    bad, good = _begin(b'{"x":2}'), _begin(body)
    staging = WorkerSubmissionStaging()
    staging.begin(bad)
    staging.begin(good)
    staging.append(_chunk(bad, body))
    staging.append(_chunk(good, body))

    with pytest.raises(AutomationCustodyError) as mismatch:
        staging.finish(_finish(bad))
    assert mismatch.value.reason is AutomationCustodyCode.INVALID
    assert staging.finish(_finish(good)).payload_json == body.decode("utf-8")


def test_invalid_utf8_and_noncontiguous_chunks_release_only_their_uploads() -> None:
    """Malformed bytes fail closed while another upload remains usable."""
    body = b'{"x":1}'
    invalid_utf8, bad_offset, good = _begin(b"\xff\xfe"), _begin(body), _begin(body)
    staging = WorkerSubmissionStaging()
    staging.begin(invalid_utf8)
    staging.begin(bad_offset)

    staging.append(_chunk(invalid_utf8, b"\xff\xfe"))
    with pytest.raises(AutomationCustodyError) as undecodable:
        staging.finish(_finish(invalid_utf8))
    assert undecodable.value.reason is AutomationCustodyCode.INVALID

    with pytest.raises(AutomationCustodyError) as noncontiguous:
        staging.append(_chunk(bad_offset, body, offset=1))
    assert noncontiguous.value.reason is AutomationCustodyCode.INVALID
    staging.begin(good)
    staging.append(_chunk(good, body))
    assert staging.finish(_finish(good)).payload_json == body.decode("utf-8")


def test_capacity_expiry_retirement_and_abort_are_bounded() -> None:
    """Expired or retired sessions release slots; abort remains idempotent."""
    now = 10.0
    staging = WorkerSubmissionStaging(clock=lambda: now)
    first, second, third = (_begin(b'{"x":1}') for _ in range(3))
    staging.begin(first)
    staging.begin(second)
    with pytest.raises(AutomationCustodyError) as full:
        staging.begin(third)
    assert full.value.reason is AutomationCustodyCode.CONFLICT

    staging.expire(live_sessions=())
    staging.begin(third)
    staging.abort(_abort(third))
    staging.abort(_abort(third))
    staging.begin(first)
    now += SUBMISSION_PAYLOAD_TIMEOUT_SECONDS + 1
    with pytest.raises(AutomationCustodyError) as expired:
        staging.append(_chunk(first, b'{"x":1}'))
    assert expired.value.reason is AutomationCustodyCode.MISSING

    staging.close()
    with pytest.raises(AutomationCustodyError) as closed:
        staging.begin(second)
    assert closed.value.reason is AutomationCustodyCode.UNAVAILABLE


def test_retired_session_wipes_only_its_upload_and_abort_is_still_safe() -> None:
    """The worker's fresh custody snapshot discards retired payloads immediately."""
    body = b'{"x":1}'
    retired, live = _begin(body), _begin(body)
    live = live.model_copy(update={"session_id": uuid4()})
    staging = WorkerSubmissionStaging()
    staging.begin(retired)
    staging.begin(live)

    staging.expire(live_sessions=(live.session_id,))
    staging.abort(_abort(retired))
    with pytest.raises(AutomationCustodyError) as missing:
        staging.append(_chunk(retired, body))
    assert missing.value.reason is AutomationCustodyCode.MISSING
    staging.append(_chunk(live, body))
    assert staging.finish(_finish(live)).payload_json == body.decode("utf-8")
