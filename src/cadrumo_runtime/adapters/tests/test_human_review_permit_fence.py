"""Production dual-principal permit fencing with explicit admission and frame ports.

Native admission is covered by runtime claim tests. This isolated proof executes
the real permit exchange and release handshake, with event-synchronized competing
retirements and no worker process or native-identity claim.
"""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Condition, Event, RLock
from time import monotonic
from typing import Literal, cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessDenialCode, OperationResponseScopeAllowed
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.contracts import ChannelWake, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_runtime.contracts.worker_authorization import (
    RuntimeHumanReviewClaimAttestation,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationOwner,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
    WorkerHumanReviewScopeRequest,
    WorkerResponseScopePermit,
)

from ..worker_authorization import WorkerAuthorizationServer
from ..worker_transport import WorkerChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _FrameBuffer:
    def __init__(self) -> None:
        self.condition, self.payload, self.closed = Condition(), bytearray(), False


class _ProofChannel:
    def __init__(self, incoming: _FrameBuffer, outgoing: _FrameBuffer) -> None:
        self.incoming, self.outgoing = incoming, outgoing
        self.body_waiting = Event()
        self.peer = Peer(os_owner_id="explicit-frame-proof-port", process_id=None)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self.incoming.condition:
            ready = self.incoming.condition.wait_for(
                lambda: len(self.incoming.payload) >= count or self.incoming.closed,
                timeout=max(0, deadline - monotonic()),
            )
            if not ready or len(self.incoming.payload) < count:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            content = bytes(self.incoming.payload[:count])
            del self.incoming.payload[:count]
            return content

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert monotonic() < deadline
        with self.outgoing.condition:
            self.outgoing.payload.extend(payload)
            self.outgoing.condition.notify_all()

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        # This occurs after production has executed its hold_fence branch.
        self.body_waiting.set()
        with self.incoming.condition:
            assert self.incoming.condition.wait_for(
                lambda: bool(self.incoming.payload) or self.incoming.closed,
                timeout=5,
            ), "release handshake did not arrive"
            return bool(self.incoming.payload)

    def read_ready(self) -> bool:
        with self.incoming.condition:
            return bool(self.incoming.payload)

    def close(self) -> None:
        for buffer in (self.incoming, self.outgoing):
            with buffer.condition:
                buffer.closed = True
                buffer.condition.notify_all()


def _request(identity: ProfileWorkerIdentity) -> WorkerHumanReviewScopeRequest:
    claimant, connection, destination = uuid4(), uuid4(), uuid4()
    policy = OperationAccessPolicy(
        definition_id="config.provision.setup",
        definition_contract_digest="b" * 64,
        actions=frozenset({AccessAction.START, AccessAction.REVIEW, AccessAction.RESPOND}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )

    def action(selected: AccessAction) -> OperationAccessRequest:
        return OperationAccessRequest(
            profile_id=identity.binding.profile_id,
            definition_id=policy.definition_id,
            action=selected,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=destination,
        )

    return WorkerHumanReviewScopeRequest(
        request_id=uuid4(),
        connection_id=connection,
        session_id=claimant,
        operation_id="a" * 64,
        request=action(AccessAction.RESPOND),
        policy=policy,
        invocation=WorkerAuthorizationRequest(
            request_id=uuid4(),
            connection_id=uuid4(),
            session_id=uuid4(),
            operation_id="a" * 64,
            request=action(AccessAction.START).model_copy(
                update={"frontend": OperationFrontendProjection.EXTERNAL_CLIENT}
            ),
            policy=policy,
        ),
        review=WorkerAuthorizationRequest(
            request_id=uuid4(),
            connection_id=connection,
            session_id=claimant,
            operation_id="a" * 64,
            request=action(AccessAction.REVIEW),
            policy=policy,
        ),
        attestation=RuntimeHumanReviewClaimAttestation(
            worker_id=identity.worker_id,
            profile_binding=identity.binding,
            runtime_boot_id=identity.runtime_boot_id,
            connection_id=connection,
            session_id=claimant,
            frontend=OperationFrontendProjection.CLI,
            source_ref="explicit-verified-person-proof",
            verified_at=now(),
        ),
    )


class _ReviewAuthority:
    def __init__(self, request: WorkerHumanReviewScopeRequest) -> None:
        self.request = request
        self.original, self.claimant = RLock(), RLock()
        self.retired: set[str] = set()
        self.probed, self.blocked, self.overtook, self.decision = Event(), Event(), Event(), Event()

    @contextmanager
    def authorize(self, request: WorkerHumanReviewScopeRequest) -> Generator[OperationResponseScopeAllowed]:
        assert request == self.request
        with self.original, self.claimant:
            if self.retired:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
            yield OperationResponseScopeAllowed(
                profile_id=request.request.profile_id,
                session_id=request.session_id,
                expires_at=now() + timedelta(minutes=1),
            )

    def retire(self, principal: Literal["invocation", "claimant"]) -> None:
        lock = self.original if principal == "invocation" else self.claimant
        if lock.acquire(blocking=False):
            try:
                self.overtook.set()
                self.retired.add(principal)
            finally:
                lock.release()
            self.probed.set()
            return
        self.blocked.set()
        self.probed.set()
        with lock:
            assert self.decision.is_set(), "retirement overtook the protected decision"
            self.retired.add(principal)


class _PermitServer(WorkerAuthorizationServer):
    def __init__(self, identity: ProfileWorkerIdentity) -> None:
        self.identity = identity
        self._stop, self._failed = NativeWake(), Event()
        self._wall_clock, self._owner = now, None
        self._contain = self._unexpected_containment

    @staticmethod
    def _unexpected_containment() -> None:
        raise AssertionError("the proof-port exchange must release normally")


@pytest.mark.parametrize("principal", ["invocation", "claimant"])
def test_human_review_permit_holds_retirement_until_explicit_release(
    principal: Literal["invocation", "claimant"],
) -> None:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="proof-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    request = WorkerHumanReviewScopeRequest.model_validate_json(_request(identity).model_dump_json())
    authority, server = _ReviewAuthority(request), _PermitServer(identity)
    incoming, outgoing = _FrameBuffer(), _FrameBuffer()
    worker, parent = _ProofChannel(incoming, outgoing), _ProofChannel(outgoing, incoming)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            exchange = pool.submit(
                server._permit_exchange,
                cast(WorkerChannel, parent),
                cast(WorkerAuthorizationOwner, authority),
                request,
                [False],
            )
            permit = read_document(worker, WorkerAuthorizationReply, deadline=monotonic() + 5).root
            assert isinstance(permit, WorkerResponseScopePermit)
            assert parent.body_waiting.wait(5), "protected body did not start"
            retirement = pool.submit(authority.retire, principal)
            assert authority.probed.wait(5), "retirement did not attempt its fence"
            try:
                assert authority.blocked.is_set() and not authority.overtook.is_set()
                authority.decision.set()
            finally:
                write_document(
                    worker,
                    WorkerAuthorizationRelease(
                        request_id=request.request_id,
                        permit_id=permit.permit_id,
                    ),
                    deadline=monotonic() + 5,
                )
                released = read_document(worker, WorkerAuthorizationReleased, deadline=monotonic() + 5)
                assert released.permit_id == permit.permit_id
                write_document(
                    worker,
                    WorkerAuthorizationAcknowledgement(
                        request_id=request.request_id,
                    ),
                    deadline=monotonic() + 5,
                )
                exchange.result(timeout=5)
                retirement.result(timeout=5)
            assert authority.retired == {principal}
            with pytest.raises(ProfileAccessRefusedError) as ended:
                server._permit_exchange(
                    cast(WorkerChannel, parent),
                    cast(WorkerAuthorizationOwner, authority),
                    request,
                    [False],
                )
            assert ended.value.reason is AccessDenialCode.SESSION_INACTIVE
            assert not worker.read_ready(), "retired authority issued a second permit"
    finally:
        worker.close()
        parent.close()
        server.close()
