"""Full-scope worker leases retain strict framing and reject partial authority."""

from __future__ import annotations

import base64
import time
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeProfileStatus, RuntimeProfileStatusTransfer, RuntimeReply
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseRequest,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerRequest,
)
from cadrumo.application.runtime.submission_payload import SUBMISSION_PAYLOAD_CHUNK_BYTES, SubmissionPayloadChunk
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    ProfileAccessBinding,
    ProfileAccessStatus,
    SessionKind,
)
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from ..framing import MAXIMUM_FRAME_BYTES, read_document, read_profile_status, write_document, write_profile_status
from ..worker_lease_transfer import read_worker_lease, write_worker_lease
from .profile_worker_support import changed, lease

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class LeaseChannel:
    """Finite in-memory wire that refuses truncation and records frame sizes."""

    def __init__(self) -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.data = bytearray()
        self.closed = False
        self.frame_sizes: list[int] = []

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        if self.closed or len(self.data) < count or time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        result = bytes(self.data[:count])
        del self.data[:count]
        return result

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert not self.closed and time.monotonic() < deadline
        self.frame_sizes.append(len(payload) - 5)
        self.data.extend(payload)

    def read_ready(self) -> bool:
        return bool(self.data)

    def close(self) -> None:
        self.closed = True


def _request(action: str) -> ProfileWorkerRequest:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    session = lease(identity)
    session = changed(
        session,
        scope=changed(
            session.scope,
            disclosures=frozenset(
                DisclosurePermission(
                    destination_id=uuid4(), projection_id="synthetic.result", category=DisclosureCategory.TAX_VALUES
                )
                for _ in range(700)
            ),
        ),
    )
    if action == "bind_human":
        session = changed(
            session,
            kind=SessionKind.HUMAN,
            originating_login_id="synthetic-login",
            grant_id=None,
            grant_generation=None,
            key_id=None,
            key_generation=None,
        )
        return ProfileWorkerRequest(
            ProfileWorkerHumanBindingRequest(request_id=uuid4(), candidate_id=uuid4(), lease=session)
        )
    return ProfileWorkerRequest(
        ProfileWorkerLeaseRequest.model_validate({"action": action, "request_id": uuid4(), "lease": session})
    )


@pytest.mark.parametrize("action", ["install", "refresh", "share", "bind_human"])
def test_complete_scope_survives_bounded_frames(action: str) -> None:
    request, channel, deadline = _request(action), LeaseChannel(), time.monotonic() + 5
    assert len(canonical_json_bytes(request.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES
    write_worker_lease(channel, request, deadline=deadline)
    assert max(channel.frame_sizes) <= MAXIMUM_FRAME_BYTES
    header = read_document(channel, ProfileWorkerRequest, deadline=deadline).root
    assert isinstance(header, ProfileWorkerLeaseTransferRequest)
    assert read_worker_lease(channel, header, deadline=deadline) == request
    assert not channel.data and not channel.closed


@pytest.mark.parametrize("fault", ["digest", "offset", "request_id", "truncated", "command"])
def test_invalid_transfer_closes_without_returning_authority(fault: str) -> None:
    request = _request("bind_human")
    if fault == "command":
        request = ProfileWorkerRequest(ProfileWorkerControlRequest(action="stop", request_id=request.root.request_id))
    payload = canonical_json_bytes(request.model_dump(mode="json"))
    header = ProfileWorkerLeaseTransferRequest(
        request_id=uuid4() if fault == "request_id" else request.root.request_id,
        byte_count=len(payload),
        payload_digest="0" * 64 if fault == "digest" else sha256_hex(payload),
    )
    channel, deadline = LeaseChannel(), time.monotonic() + 5
    for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
        if fault == "truncated" and offset > 0:
            break
        write_document(
            channel,
            SubmissionPayloadChunk(
                offset=offset + 1 if fault == "offset" else offset,
                encoded=base64.b64encode(payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]).decode("ascii"),
            ),
            deadline=deadline,
        )
    with pytest.raises(RuntimeRefusalError):
        read_worker_lease(channel, header, deadline=deadline)
    assert channel.closed


def test_transfer_limit_refuses_before_any_partial_command_is_written() -> None:
    command = _request("bind_human").root
    assert isinstance(command, ProfileWorkerHumanBindingRequest)
    command = changed(command, lease=changed(command.lease, originating_login_id="x" * 1_048_576))
    channel = LeaseChannel()
    with pytest.raises(RuntimeRefusalError) as caught:
        write_worker_lease(channel, ProfileWorkerRequest(command), deadline=time.monotonic() + 5)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert channel.closed and not channel.data and not channel.frame_sizes


@pytest.mark.parametrize("fault", [None, "connection", "digest", "truncated"])
def test_login_status_preserves_full_scope_and_correlates_transfer(fault: str | None) -> None:
    command = _request("bind_human").root
    assert isinstance(command, ProfileWorkerHumanBindingRequest)
    session = command.lease
    status = RuntimeProfileStatus(
        request_id=command.request_id,
        runtime_boot_id=session.runtime_boot_id,
        connection_id=session.connection_id,
        status=ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=session.binding.profile_id,
            session_id=session.session_id,
            session_expires_at=session.expires_at,
            grant_state=None,
            grant_expires_at=None,
            grant_valid=False,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.NOT_REQUIRED,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NEEDS_USER,
            effective_scope=session.scope,
            denial=None,
        ),
    )
    channel, deadline = LeaseChannel(), time.monotonic() + 5
    write_profile_status(channel, status, deadline=deadline)
    assert max(channel.frame_sizes) <= MAXIMUM_FRAME_BYTES
    header = read_document(channel, RuntimeReply, deadline=deadline).root
    assert isinstance(header, RuntimeProfileStatusTransfer)
    if fault is None:
        assert read_profile_status(channel, header, deadline=deadline) == status
        assert not channel.data and not channel.closed
        return
    if fault == "connection":
        header = changed(header, connection_id=uuid4())
    elif fault == "digest":
        header = changed(header, payload_digest="0" * 64)
    else:
        channel.data.pop()
    with pytest.raises(RuntimeRefusalError):
        read_profile_status(channel, header, deadline=deadline)
    assert channel.closed
