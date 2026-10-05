"""Runtime operation behavior for profile connections."""

from __future__ import annotations

import time
from contextlib import ExitStack
from datetime import datetime
from typing import TYPE_CHECKING

from ...adapters.local_runtime.runtime_frame_io import read_secret, write_document
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationFinancialInput,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationReview,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeSecretReady,
)
from ...application.runtime.profile_worker import ProfileWorkerOperationReceipt
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    FinancialOperandInputDescriptor,
)
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessDenied,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from ...core.logging import get_logger
from .operation_projection import prepare_operation_projection
from .profile_host import ProfileConnection, RuntimeProfileHost
from .submission_stream import stream_operation_submission

_log = get_logger(__name__)

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


type _RuntimeOperationReplyRequest = (
    RuntimeOperationContract
    | RuntimeOperationSubmitPayload
    | RuntimeOperationSubmit
    | RuntimeOperationControl
    | RuntimeOperationObserve
    | RuntimeOperationResult
    | RuntimeOperationResultPage
    | RuntimeOperationReview
    | RuntimeOperationManage
)


class ProfileConnectionOperationMixin:
    """Own the operation behavior of the profile connection service."""

    def _operation_secret(
        self: RuntimeProfileConnections,
        host: RuntimeProfileHost,
        connection: ProfileConnection,
        channel: RuntimeByteChannel,
        request: RuntimeOperationSecret,
    ) -> None:
        """Preflight before bytes, then reauthorize their one-use canonical delivery."""
        if connection.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        worker = host.owner.operation_worker()

        def checked(receipt: ProfileWorkerOperationReceipt) -> None:
            release = receipt.release
            if (
                receipt.operation_id != request.requirement.identity.operation_id
                or release.operation_id != receipt.operation_id
                or release.connection_id != connection.context.connection_id
                or release.session_id != request.session_id
                or release.request.profile_id != request.profile_id
                or release.request.frontend != connection.frontend
                or release.request.destination_id != connection.client_id
                or release.request.action is not AccessAction.SUBMIT
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        ready = worker.operation_secret(request.session_id, request.requirement, frontend=connection.frontend)
        checked(ready)
        with host.authorize(ready.release):
            write_document(
                channel,
                RuntimeSecretReady(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=connection.context.connection_id,
                ),
                deadline=time.monotonic() + 5,
            )
        # Never hold the profile fence while awaiting a client secret or a
        # worker callback. Each delivery and output acquires fresh authority.
        with read_secret(channel, deadline=time.monotonic() + 5) as secret:
            delivered = worker.operation_secret(
                request.session_id, request.requirement, frontend=connection.frontend, secret=secret
            )
        checked(delivered)
        with host.authorize(delivered.release) as allowed:
            remaining = (allowed.expires_at - self._wall_clock()).total_seconds()
            if remaining <= 0:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
            write_document(
                channel,
                RuntimeOperationAcknowledged(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=connection.context.connection_id,
                    operation_id=delivered.operation_id,
                ),
                deadline=time.monotonic() + min(5, remaining),
            )

    def operation(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeOperationRequest,
    ) -> None:
        """Hold newly observed authority through the final bounded frontend write."""
        reply: RuntimeOperationReply | RuntimeAccessRefusal
        deadline = time.monotonic() + 5
        with ExitStack() as release_guard:
            try:
                connection, host = self._operation_target(context, channel, request)
                if isinstance(request, RuntimeOperationFinancialInput):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(request, RuntimeOperationSecret):
                    self._operation_secret(host, connection, channel, request)
                    return
                reply, expires_at = self._operation_reply(
                    connection, host, context, channel, request, release_guard=release_guard
                )
                deadline = self._operation_deadline(expires_at)
            except (AutomationCustodyError, RuntimeRefusalError, ProfileAccessRefusedError) as error:
                release_guard.close()
                # The client sees only the code; the log keeps which check refused and where.
                _log.warning("runtime operation refused code=%s", error.reason, exc_info=error)
                reply = RuntimeAccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=error.reason,
                )
                deadline = time.monotonic() + 5
            # Write errors propagate: a partially written frame is never retried
            # as a refusal. No private payload escapes the scope of its fence.
            write_document(channel, reply, deadline=deadline)

    def _operation_target(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeOperationRequest,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if not self._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        with self._guard:
            host = self._profiles.get(connection.profile_id)
        if host is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return connection, host

    def _operation_reply(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: _RuntimeOperationReplyRequest,
        *,
        release_guard: ExitStack,
    ) -> tuple[RuntimeOperationReply, datetime | None]:
        if isinstance(request, RuntimeOperationContract):
            return self._contract_reply(connection, host, context, request, release_guard=release_guard)
        if isinstance(request, RuntimeOperationSubmitPayload):
            return self._submit_payload_reply(connection, host, channel, request, release_guard=release_guard)
        # Worker callbacks need this same profile guard; never hold it while
        # waiting for the native execution channel.
        reply, release = prepare_operation_projection(host, connection, request)
        allowed = release_guard.enter_context(host.authorize(release))
        return reply, allowed.expires_at

    def _contract_reply(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeOperationContract,
        *,
        release_guard: ExitStack,
    ) -> tuple[RuntimeOperationContractReply, datetime | None]:
        # Public registry discovery has no private domain operands. Hold the
        # profile fence while observing its current scope.
        release_guard.enter_context(host.guard)
        status = self._status(connection, host, request.request_id, request.session_id)
        if isinstance(status, AccessDenied):
            raise ProfileAccessRefusedError(status.code)
        if status.status.denial is not None:
            raise ProfileAccessRefusedError(status.status.denial)
        if request.definition_id not in status.status.effective_scope.operations:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        description = host.owner.operation_worker().describe(request.session_id, request.definition_id)
        contract = description.contract
        if connection.frontend not in contract.permitted_frontends:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        reply = RuntimeOperationContractReply(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            contract=contract,
            request_json_schema=description.request_json_schema,
        )
        return reply, status.status.session_expires_at

    def _submit_payload_reply(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        channel: RuntimeByteChannel,
        request: RuntimeOperationSubmitPayload,
        *,
        release_guard: ExitStack,
    ) -> tuple[RuntimeOperationReply, datetime | None]:
        self._require_upload_session(connection, host, request)
        contract = host.owner.operation_worker().describe(request.session_id, request.definition_id).contract
        if connection.frontend not in contract.permitted_frontends:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        if isinstance(request.descriptor, FinancialOperandInputDescriptor) != (
            contract.transient_financial_operand is not None
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if isinstance(request.descriptor, FinancialOperandInputDescriptor) and request.idempotency_key is not None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        reply, release = stream_operation_submission(
            host,
            connection,
            request,
            channel,
            slots=self._submission_slots,
            require_session=lambda: self._require_upload_session(connection, host, request),
            deadline=time.monotonic() + SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
        )
        allowed = release_guard.enter_context(host.authorize(release))
        return reply, allowed.expires_at

    def _operation_deadline(self: RuntimeProfileConnections, expires_at: datetime | None) -> float:
        if expires_at is None:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
        remaining = (expires_at - self._wall_clock()).total_seconds()
        if remaining <= 0:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
        return time.monotonic() + min(5, remaining)

    def _require_upload_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        request: RuntimeOperationSubmitPayload,
    ) -> None:
        """Recheck connection and coarse SUBMIT scope while no operation yet exists."""
        if not self._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        current = self._connected(connection.context.connection_id)
        if current is not connection or connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        with host.guard:
            status = self._status(connection, host, request.request_id, request.session_id)
            if isinstance(status, AccessDenied):
                raise ProfileAccessRefusedError(status.code)
            if status.status.denial is not None:
                raise ProfileAccessRefusedError(status.status.denial)
            scope = status.status.effective_scope
            if request.definition_id not in scope.operations or AccessAction.SUBMIT not in scope.actions:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            expires_at = status.status.session_expires_at
            if expires_at is None or expires_at <= self._wall_clock():
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
