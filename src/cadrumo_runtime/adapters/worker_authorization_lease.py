"""One exact held worker authority permit, on a pooled verified channel, with explicit release."""

from __future__ import annotations

import asyncio
import sys
import time
from uuid import UUID, uuid4

from cadrumo.application.user_profile.automation_enrollment import AutomationInventory, EnrollmentTransition
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
)
from cadrumo.core.diagnostic_log import diagnostic_timing_event
from cadrumo.core.logging import get_logger
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.model_runs import ModelRunHeader, ModelRunOutcome
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.submission_payload import SubmissionPayloadDescriptor
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, read_document_transfer, write_document
from cadrumo_client.transport.model_run_frames import read_secret_chunks, write_secret_chunks
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityChecked,
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationPermit,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerAutomationInventoryTransfer,
    WorkerModelRun,
    WorkerModelRunResult,
    WorkerResponseScopePermit,
    WorkerResponseScopeRequest,
    WorkerServerStart,
    WorkerServerStarted,
)
from cadrumo_runtime.contracts.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublicationPhase,
    WorkerApprovalPublished,
    WorkerApprovalReady,
)

from ..application.approval_binding import RuntimeApprovalBinding
from .worker_authorization import runtime_server_start_definitions
from .worker_authorization_connections import WorkerAuthorizationConnections
from .worker_authorization_refusals import raise_worker_access_refusal
from .worker_transport import WorkerChannel

_LOGGER = get_logger(__name__)


class WorkerAuthorizationLease:
    """One permit on one pooled connection, with explicit acquisition/release, never an ordinary result.

    The connection goes back to its pool only when every exchange on it ended
    on its terminal frame: the release acknowledged, or the request's refusal
    acknowledged. Anything else closes it.
    """

    def __init__(
        self,
        *,
        connections: WorkerAuthorizationConnections,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    ) -> None:
        """Capture only trusted worker routing and registered operation coordinates."""
        self.connections, self.request = connections, request
        self.identity: ProfileWorkerIdentity = connections.identity
        self._channel: WorkerChannel | None = None
        # False while an instruction is in flight, and for good once one fails.
        self._settled = True
        self._abandoned = False
        self._permit: WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit | None = (
            None
        )
        self._publication_sent = False
        self._runtime_server_start_sent = False
        self._model_run_sent = False

    def _commit_phase(self, stage: str) -> None:
        if isinstance(self.request, WorkerAuthorizationRequest) and self.request.request.action is AccessAction.COMMIT:
            diagnostic_timing_event(
                _LOGGER,
                "worker_commit_phase",
                fields={"stage": stage, "transition": AccessAction.COMMIT.value},
                primary_error=sys.exception(),
            )

    def acquire(self) -> None:
        """Request a held fence on a verified connection to the retained native parent."""
        # The runtime may queue this admission behind a running COMMIT's fence.
        deadline = exchange_deadline()
        channel: WorkerChannel | None = self.connections.checkout(deadline)
        clean = False
        try:
            write_document(channel, self.request, deadline=deadline)
            reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if reply.request_id != self.request.request_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if isinstance(reply, AccessRefusal):
                if (
                    reply.runtime_boot_id != self.identity.runtime_boot_id
                    or reply.connection_id != self.request.connection_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                write_document(
                    channel, WorkerAuthorizationAcknowledgement(request_id=self.request.request_id), deadline=deadline
                )
                clean = True
                raise_worker_access_refusal(reply)
            received = (
                _read_inventory_permit(
                    channel, reply, self.request, runtime_boot_id=self.identity.runtime_boot_id, deadline=deadline
                )
                if isinstance(reply, WorkerAutomationInventoryTransfer)
                else reply
            )
            permit = _validated_authority_permit(received, self.request, self.identity)
            self._permit, self._channel = permit, channel
            channel = None
            self._commit_phase("permit_validated")
        finally:
            if channel is not None:
                self.connections.checkin(channel, reusable=clean)

    def abandon(self) -> None:
        """Close this lease's connection after its release instead of reusing it; the release itself still runs."""
        self._abandoned = True

    def inventory(self) -> AutomationInventory:
        """Return only an exact inventory permit, never an ordinary guard reply."""
        if not isinstance(self.request, WorkerAutomationInventoryRequest) or not isinstance(
            self._permit, WorkerAutomationInventoryPermit
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return self._permit.inventory

    def publish_approval(
        self, binding: RuntimeApprovalBinding, phase: WorkerApprovalPublicationPhase
    ) -> EnrollmentTransition | None:
        """Send one publication over this exact held COMMIT channel, without reacquiring it."""
        channel, permit, request = self._publication_channel(binding, phase)
        command = WorkerApprovalPublication(
            request_id=request.request_id,
            permit_id=permit.permit_id,
            command_id=uuid4(),
            binding=binding,
            phase=phase,
        )
        self._publication_sent = True
        self._settled = False
        write_document(channel, command, deadline=exchange_deadline())
        reply = self._publication_reply(channel, request, permit, command)
        self._settled = True
        if reply.receipt is None:
            if phase != "commit_review":
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return None
        if (
            reply.receipt.profile_id != binding.profile_binding.profile_id
            or reply.receipt.request_id != binding.enrollment_request_id
            or reply.receipt.review_digest != binding.review_digest
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return EnrollmentTransition(receipt=reply.receipt, published=reply.published)

    def start_runtime_server(self) -> int | None:
        """Ask the runtime to start the model runtime's server over this exact held COMMIT channel.

        Returns the server's process id, or ``None`` when the runtime started
        nothing. Nothing this process located is sent: the runtime resolves the
        program and its environment itself.
        """
        channel, permit, request = self._channel, self._permit, self.request
        if (
            channel is None
            or not isinstance(permit, WorkerAuthorizationPermit)
            or not isinstance(request, WorkerAuthorizationRequest)
            or request.request.action is not AccessAction.COMMIT
            or request.request.definition_id not in runtime_server_start_definitions()
            or self._runtime_server_start_sent
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        command = WorkerServerStart(request_id=request.request_id, permit_id=permit.permit_id, command_id=uuid4())
        self._runtime_server_start_sent = True
        self._settled = False
        write_document(channel, command, deadline=exchange_deadline())
        reply = read_document(channel, WorkerServerStarted, deadline=exchange_deadline())
        if (
            reply.request_id != request.request_id
            or reply.permit_id != permit.permit_id
            or reply.command_id != command.command_id
            or reply.runtime_boot_id != self.identity.runtime_boot_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._settled = True
        return reply.process_id

    def model_run(
        self, role: str, header: ModelRunHeader | None, body: bytearray, *, answer_seconds: float
    ) -> tuple[ModelRunOutcome, bytearray]:
        """Ask the runtime, over this exact held START channel, to have the agent service answer.

        A lookup sends no header and an empty body. ``answer_seconds`` bounds the
        wait for the service's answer; the body is wiped once sent, and the
        reply text belongs to the caller, who wipes it.
        """
        channel, permit, request = self._channel, self._permit, self.request
        if (
            channel is None
            or not isinstance(permit, WorkerAuthorizationPermit)
            or not isinstance(request, WorkerAuthorizationRequest)
            or request.request.action is not AccessAction.START
            or self._model_run_sent
        ):
            body[:] = bytes(len(body))
            raise RefusalError(RefusalCode.INVALID_FRAME)
        command = WorkerModelRun(
            request_id=request.request_id,
            permit_id=permit.permit_id,
            command_id=uuid4(),
            role=role,
            header=header,
            body_byte_count=len(body),
        )
        self._model_run_sent = True
        self._settled = False
        try:
            write_document(channel, command, deadline=exchange_deadline())
        except BaseException:
            body[:] = bytes(len(body))
            raise
        write_secret_chunks(channel, body, deadline=exchange_deadline())
        reply = read_document(channel, WorkerModelRunResult, deadline=time.monotonic() + answer_seconds)
        if (
            reply.request_id != request.request_id
            or reply.permit_id != permit.permit_id
            or reply.command_id != command.command_id
            or reply.runtime_boot_id != self.identity.runtime_boot_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        text = read_secret_chunks(channel, reply.outcome.text_byte_count, deadline=exchange_deadline())
        self._settled = True
        return reply.outcome, text

    def release(self) -> None:
        """Acknowledge body completion on the exact channel, preserving uncertain failure."""
        channel, permit = self._channel, self._permit
        self._channel, self._permit = None, None
        if channel is None:
            return
        clean = False
        try:
            self._commit_phase("release_executor_start")
            if permit is None:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            self._commit_phase("release_write_begin")
            write_document(
                channel,
                WorkerAuthorizationRelease(request_id=self.request.request_id, permit_id=permit.permit_id),
                deadline=exchange_deadline(),
            )
            self._commit_phase("release_write_end")
            reply = read_document(channel, WorkerAuthorizationReply, deadline=exchange_deadline()).root
            if (
                not isinstance(reply, WorkerAuthorizationReleased)
                or reply.request_id != self.request.request_id
                or reply.permit_id != permit.permit_id
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            write_document(
                channel,
                WorkerAuthorizationAcknowledgement(request_id=self.request.request_id),
                deadline=exchange_deadline(),
            )
            clean = self._settled and not self._abandoned
        finally:
            self.connections.checkin(channel, reusable=clean)

    async def close(self) -> None:
        """Complete blocking native release through the existing cleanup owner."""
        try:
            self._commit_phase("release_scheduled")
        finally:
            await asyncio.to_thread(self.release)

    def _publication_channel(
        self, binding: RuntimeApprovalBinding, phase: WorkerApprovalPublicationPhase
    ) -> tuple[WorkerChannel, WorkerAuthorizationPermit, WorkerAuthorizationRequest]:
        """Admit one addressed publication on the retained, unused COMMIT permit."""
        channel, permit, request = self._channel, self._permit, self.request
        expected = _publication_definition(phase)
        if (
            channel is None
            or not isinstance(permit, WorkerAuthorizationPermit)
            or not isinstance(request, WorkerAuthorizationRequest)
            or request.request.action is not AccessAction.COMMIT
            or request.request.definition_id != expected
            or self._publication_sent
            or binding.operation_id != request.operation_id
            or binding.session_id != request.session_id
            or binding.connection_id != request.connection_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return channel, permit, request

    def _publication_reply(
        self,
        channel: WorkerChannel,
        request: WorkerAuthorizationRequest,
        permit: WorkerAuthorizationPermit,
        command: WorkerApprovalPublication,
    ) -> WorkerApprovalPublished:
        """Read the exact publication response and preserve its refusal category."""
        reply = read_document(channel, WorkerAuthorizationReply, deadline=exchange_deadline()).root
        if (
            not isinstance(reply, AccessRefusal | WorkerApprovalPublished)
            or reply.request_id != request.request_id
            or reply.runtime_boot_id != self.identity.runtime_boot_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if isinstance(reply, AccessRefusal):
            if reply.connection_id != request.connection_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            # The refusal is the publication's whole reply; the held fence still awaits its release.
            self._settled = True
            raise_worker_access_refusal(reply)
        if (
            not isinstance(reply, WorkerApprovalPublished)
            or reply.permit_id != permit.permit_id
            or reply.command_id != command.command_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply


def _publication_definition(phase: WorkerApprovalPublicationPhase) -> str:
    """Address the registered decline or approval definition for this phase."""
    return (
        AUTOMATION_DECLINE_OPERATION_DEFINITION_ID if phase == "decline" else AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
    )


def _read_inventory_permit(
    channel: ByteChannel,
    header: WorkerAutomationInventoryTransfer,
    request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    *,
    runtime_boot_id: UUID,
    deadline: float,
) -> WorkerAutomationInventoryPermit:
    """Assemble the announced inventory permit, only for the inventory request it names."""
    if (
        not isinstance(request, WorkerAutomationInventoryRequest)
        or header.request_id != request.request_id
        or header.runtime_boot_id != runtime_boot_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    permit = read_document_transfer(
        channel,
        SubmissionPayloadDescriptor(byte_count=header.byte_count, payload_digest=header.payload_digest),
        WorkerAutomationInventoryPermit,
        deadline=deadline,
    )
    if (permit.request_id, permit.runtime_boot_id, permit.permit_id) != (
        header.request_id,
        header.runtime_boot_id,
        header.permit_id,
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return permit


def _validated_authority_permit(
    reply: AccessRefusal
    | WorkerAuthorizationPermit
    | WorkerResponseScopePermit
    | WorkerAutomationInventoryPermit
    | WorkerAuthorityChecked
    | WorkerAuthorizationReleased
    | WorkerApprovalReady
    | WorkerApprovalPhaseResult
    | WorkerApprovalPublished,
    request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    identity: ProfileWorkerIdentity,
) -> WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit:
    """Require an exact request-family, runtime boot, and live held authority permit."""
    if (
        not isinstance(reply, WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit)
        or reply.runtime_boot_id != identity.runtime_boot_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if (
        isinstance(request, WorkerResponseScopeRequest) != isinstance(reply, WorkerResponseScopePermit)
        or isinstance(request, WorkerAutomationInventoryRequest) != isinstance(reply, WorkerAutomationInventoryPermit)
        or isinstance(request, WorkerAuthorizationRequest) != isinstance(reply, WorkerAuthorizationPermit)
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    # Admission is checked as the stage starts; a lease already ended admits nothing.
    if reply.expires_at <= now():
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
    return reply
