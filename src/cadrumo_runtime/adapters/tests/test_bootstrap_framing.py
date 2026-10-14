"""Bootstrap credentials use only correlated secret readiness and strict frames."""

from __future__ import annotations

import time
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.custody_transactions import ProfileCustodyDeleteConfirmation
from cadrumo_client.contracts.bootstrap import PasswordReset, PasswordResetRefused
from cadrumo_client.contracts.bootstrap_delete import ProfileDeletePrepared
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal, Request, SecretReady
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .test_framing import CleanupChannel, _connection

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_delete_frontend_retains_transaction_identity_after_lost_commit() -> None:
    class LostReplyChannel(CleanupChannel):
        @override
        def read_exact(self, count: int, *, deadline: float) -> bytes:
            if not self.inbound:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            return super().read_exact(count, deadline=deadline)

        @override
        def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
            super().write_all(payload, deadline=deadline)
            # Build the prepared response from the real serialized request, so
            # the frontend-generated request UUID remains exactly correlated.
            if bytes(payload).startswith(b"J") and b'"profile_delete_prepare"' in payload:
                import json

                request = json.loads(payload[5:])
                response = ProfileDeletePrepared.model_validate(
                    {
                        "request_id": UUID(request["request_id"]),
                        "runtime_boot_id": wire.hello.boot_id,
                        "connection_id": uuid4(),
                        "profile_id": profile,
                        "confirmation": confirmation,
                    }
                )
                recorder = CleanupChannel(close_failures=0)
                write_document(recorder, response, deadline=deadline)
                self.inbound.extend(b"".join(recorder.writes))

    channel = LostReplyChannel(close_failures=0)
    wire = _connection(channel)
    profile = uuid4()
    confirmation = ProfileCustodyDeleteConfirmation(
        transaction_id=uuid4(),
        profile_id=profile,
        inventory_digest="sha256:" + "a" * 64,
        challenge="b" * 64,
    )
    client = FrontendClient(wire, profile_id=profile, frontend=OperationFrontendProjection.CLI)
    try:
        with pytest.raises(FrontendRefusedError) as refused:
            client.delete_profile(BucketDeletionFingerprint(digest="a" * 64, file_count=1, total_bytes=10))
        assert refused.value.reason == RefusalCode.CONNECTION_CLOSED.value
        assert refused.value.context is not None
        assert refused.value.context["transaction_id"] == str(confirmation.transaction_id)
    finally:
        client.close()


@pytest.mark.parametrize("readiness", ["refusal", "wrong-request", "ready"])
def test_reset_secret_is_sent_only_after_matching_readiness(readiness: str) -> None:
    channel = CleanupChannel(close_failures=0)
    wire = _connection(channel)
    channel.writes.clear()
    request = PasswordReset(request_id=uuid4(), profile_id=uuid4(), envelope_digest="sha256:" + "a" * 64)
    connection_id = uuid4()
    coordinates = dict(request_id=request.request_id, runtime_boot_id=wire.hello.boot_id, connection_id=connection_id)
    if readiness == "refusal":
        response = AccessRefusal.model_validate({**coordinates, "code": RefusalCode.UNAVAILABLE})
    else:
        response = SecretReady.model_validate(
            {
                **coordinates,
                "request_id": uuid4() if readiness == "wrong-request" else request.request_id,
            }
        )
    write_document(channel, response, deadline=time.monotonic() + 5)
    if readiness == "ready":
        write_document(
            channel,
            PasswordResetRefused.model_validate(
                {
                    **coordinates,
                    "profile_id": request.profile_id,
                    "code": "recovery_code_rejected",
                }
            ),
            deadline=time.monotonic() + 5,
        )
    channel.inbound.extend(b"".join(channel.writes))
    channel.writes.clear()
    secret = bytearray(b'{"recovery_code":"synthetic-secret"}')
    try:
        if readiness == "wrong-request":
            with pytest.raises(RefusalError) as refused:
                wire.password_reset(request, secret, deadline=time.monotonic() + 5)
            assert refused.value.reason is RefusalCode.INVALID_FRAME
        else:
            reply = wire.password_reset(request, secret, deadline=time.monotonic() + 5)
            assert isinstance(reply, PasswordResetRefused if readiness == "ready" else AccessRefusal)
        assert not any(secret)
        writes = b"".join(channel.writes)
        assert (b"synthetic-secret" in writes) is (readiness == "ready")
        assert b"recovery_code" not in request.model_dump_json().encode()
    finally:
        wire.close()


def test_reset_request_rejects_credentials_in_ordinary_json() -> None:
    request = PasswordReset(request_id=uuid4(), profile_id=uuid4(), envelope_digest="sha256:" + "a" * 64)
    assert Request.model_validate_json(request.model_dump_json()).root == request
    with pytest.raises(ValidationError):
        Request.model_validate({**request.model_dump(mode="json"), "recovery_code": "synthetic-secret"})


@pytest.mark.parametrize("code,seconds", [("throttled", None), ("recovery_code_rejected", 1)])
def test_reset_refusal_cannot_lose_or_invent_throttle_time(code: str, seconds: int | None) -> None:
    with pytest.raises(ValidationError):
        PasswordResetRefused.model_validate(
            {
                "request_id": uuid4(),
                "runtime_boot_id": uuid4(),
                "connection_id": uuid4(),
                "profile_id": uuid4(),
                "code": code,
                "remaining_seconds": seconds,
            }
        )
