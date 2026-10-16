"""Runtime operation behavior for profile connections."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, AccessDenied
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationContractReply,
    OperationControl,
    OperationFinancialInput,
    OperationManage,
    OperationObserve,
    OperationReply,
    OperationRequest,
    OperationResult,
    OperationResultPage,
    OperationReview,
    OperationSecret,
    OperationSubmit,
    OperationSubmitPayload,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SecretReady
from cadrumo_client.contracts.submission_payload import (
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    FinancialOperandInputDescriptor,
)
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerOperationReceipt

from .operation_projection import prepare_operation_projection
from .profile_host import ProfileConnection, RuntimeProfileHost
from .submission_stream import stream_operation_submission

_log = get_logger(__name__)

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


type _RuntimeOperationReplyRequest = (
    OperationContract
    | OperationSubmitPayload
    | OperationSubmit
    | OperationControl
    | OperationObserve
    | OperationResult
    | OperationResultPage
    | OperationReview
    | OperationManage
)


def _require_scope_admits(connection: ProfileConnection, definition_id: str) -> None:
    if connection.requested_scope is not None and definition_id not in connection.requested_scope.operations:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _session_mismatch(connection: ProfileConnection) -> AccessDenialCode:
    """Name why a request's session is not this connection's: a retirement such as a sign-out leaves none."""
    return (
        AccessDenialCode.AUTHENTICATION_REQUIRED
        if connection.session_id is None
        else AccessDenialCode.CONNECTION_MISMATCH
    )


class ProfileConnectionOperationMixin:
    """Own the operation behavior of the profile connection service."""

    def _operation_secret(
        self: RuntimeProfileConnections,
        host: RuntimeProfileHost,
        connection: ProfileConnection,
        channel: ByteChannel,
        request: OperationSecret,
    ) -> None:
        """Preflight before bytes, then reauthorize their one-use canonical delivery."""
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
                SecretReady(
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
                OperationAcknowledged(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=connection.context.connection_id,
                    operation_id=delivered.operation_id,
                ),
                deadline=time.monotonic() + min(5, remaining),
            )

    def operation(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: OperationRequest,
    ) -> None:
        """Hold newly observed authority through the final bounded frontend write."""
        reply: OperationReply | AccessRefusal
        deadline = time.monotonic() + 5
        with self._language_observed_after(context), ExitStack() as release_guard:
            try:
                release_guard.enter_context(self.operation_admission())
                connection, host = self._operation_target(context, channel, request)
                if isinstance(request, OperationFinancialInput):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(request, OperationSecret):
                    self._operation_secret(host, connection, channel, request)
                    return
                reply, expires_at = self._operation_reply(
                    connection, host, context, channel, request, release_guard=release_guard
                )
                deadline = self._operation_deadline(expires_at)
            except (AutomationCustodyError, RefusalError, ProfileAccessRefusedError) as error:
                release_guard.close()
                # Preserve bounded typed refusal facts; no secret or private result is disclosed.
                _log.warning("runtime operation refused code=%s", error.reason, exc_info=error)
                reply = AccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=error.reason,
                    sign_in=error.sign_in if isinstance(error, ProfileAccessRefusedError) else None,
                    request_faults=error.request_faults if isinstance(error, AutomationCustodyError) else (),
                    holder_operation_id=error.holder_operation_id
                    if isinstance(error, ProfileAccessRefusedError)
                    else None,
                )
                deadline = time.monotonic() + 5
            # Write errors propagate: a partially written frame is never retried
            # as a refusal. No private payload escapes the scope of its fence.
            write_document(channel, reply, deadline=deadline)

    @contextmanager
    def _language_observed_after(self: RuntimeProfileConnections, context: ConnectionContext) -> Generator[None]:
        """Look at the profile's language hint once this request ends; only an operation's worker moves it."""
        try:
            yield
        finally:
            with self._guard:
                connection = self._connections.get(context.connection_id)
            if connection is not None:
                self.observe_profile_language(connection.profile_id)

    def _operation_target(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: OperationRequest,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if not self._admitting():
            raise RefusalError(RefusalCode.DRAINING)
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(_session_mismatch(connection))
        with self._guard:
            host = self._profiles.get(connection.profile_id)
        if host is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return connection, host

    def _operation_reply(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        channel: ByteChannel,
        request: _RuntimeOperationReplyRequest,
        *,
        release_guard: ExitStack,
    ) -> tuple[OperationReply, datetime | None]:
        if isinstance(request, OperationContract):
            return self._contract_reply(connection, host, context, request, release_guard=release_guard)
        if isinstance(request, OperationSubmitPayload):
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
        context: ConnectionContext,
        request: OperationContract,
        *,
        release_guard: ExitStack,
    ) -> tuple[OperationContractReply, datetime | None]:
        # Public registry discovery has no private domain operands. The first
        # description after a sign-in composes the worker's registry, so the
        # profile fence is not held while the worker answers: every other
        # request of the profile would queue behind that composition.
        with host.guard:
            self._contract_scope(connection, host, request)
        description = host.owner.operation_worker().describe(request.session_id, request.definition_id)
        # Authority may have changed meanwhile; observe it again and hold the
        # fence through the final write, as before.
        release_guard.enter_context(host.guard)
        status = self._contract_scope(connection, host, request)
        contract = description.contract
        _require_scope_admits(connection, contract.definition_id)
        if operation_is_persons_act(
            contract.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required
        ):
            # The access policy refuses it at submission too; it is not described to an automation either.
            self._require_persons_frontend(connection.frontend)
        reply = OperationContractReply(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            contract=contract,
            request_json_schema=description.request_json_schema,
        )
        return reply, status.status.session_expires_at

    def _contract_scope(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        request: OperationContract,
    ) -> ProfileStatus:
        """Observe, under the caller's profile fence, that the session may see this definition now."""
        status = self._status(connection, host, request.request_id, request.session_id)
        if isinstance(status, AccessDenied):
            raise ProfileAccessRefusedError(status.code)
        if status.status.denial is not None:
            raise ProfileAccessRefusedError(status.status.denial)
        if request.definition_id not in status.status.effective_scope.operations:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return status

    def _submit_payload_reply(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        channel: ByteChannel,
        request: OperationSubmitPayload,
        *,
        release_guard: ExitStack,
    ) -> tuple[OperationReply, datetime | None]:
        self._require_upload_session(connection, host, request)
        contract = host.owner.operation_worker().describe(request.session_id, request.definition_id).contract
        _require_scope_admits(connection, contract.definition_id)
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
        request: OperationSubmitPayload,
    ) -> None:
        """Recheck connection and coarse SUBMIT scope while no operation yet exists."""
        if not self._admitting():
            raise RefusalError(RefusalCode.DRAINING)
        current = self._connected(connection.context.connection_id)
        if current is not connection:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        if connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(_session_mismatch(connection))
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
