"""Runtime operation behavior for profile connections."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from importlib.metadata import version
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.logging import get_logger
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationContractReply,
    OperationControl,
    OperationFinancialInput,
    OperationManage,
    OperationObserve,
    OperationObserved,
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
from cadrumo_client.contracts.session_events import OperationChanged, ProfileRecordsChanged
from cadrumo_client.contracts.submission_payload import (
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    FinancialOperandInputDescriptor,
)
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import (
    SEDE_VIEW_DEFINITION_ID,
    ViewAttachGranted,
    ViewAttachRequest,
    ViewConnect,
)
from cadrumo_client.transport.frame_io import read_secret, write_document
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerOperationReceipt

from .operation_projection import prepare_operation_projection
from .profile_connection import ProfileConnection
from .profile_host import RuntimeProfileHost
from .submission_stream import stream_operation_submission
from .view_stream_state import ViewAttachGrant
from .view_stream_worker_link import open_worker_view_leg

_log = get_logger(__name__)

# Operations one connection may wait on at once; the oldest watch gives way.
_OPERATION_WATCHES_PER_CONNECTION = 64

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


def _admitted_status(status: ProfileStatus | AccessDenied) -> ProfileStatus:
    """Return a session status that grants access; refuse a denied one, with a suspended session's window."""
    if isinstance(status, AccessDenied):
        raise ProfileAccessRefusedError(status.code, recovery_remaining_seconds=status.recovery_remaining_seconds)
    if status.status.denial is not None:
        raise ProfileAccessRefusedError(
            status.status.denial, recovery_remaining_seconds=status.status.recovery_remaining_seconds
        )
    return status


def _session_mismatch(connection: ProfileConnection) -> AccessDenialCode:
    """Name why a request's session is not this connection's: a retirement such as a sign-out leaves none."""
    return (
        AccessDenialCode.AUTHENTICATION_REQUIRED
        if connection.session_id is None
        else AccessDenialCode.CONNECTION_MISMATCH
    )


def _lost_in_flight(
    host: RuntimeProfileHost,
    request: OperationRequest,
    error: AutomationCustodyError | RefusalError | ProfileAccessRefusedError,
) -> ProfileAccessRefusedError | None:
    """Return the session's recovery refusal when the worker serving ``request`` was lost meanwhile.

    A failed worker channel, an owner left without a worker, or a session the
    authority already suspended may each be that loss. It is established here,
    not by the next request, so this request reports it. Any other failure, or
    one that left the worker serving, keeps its own answer.
    """
    if isinstance(error, ProfileAccessRefusedError) and error.reason is not AccessDenialCode.CUSTODY_RECOVERING:
        return None
    if isinstance(error, AutomationCustodyError) and error.reason is not AutomationCustodyCode.UNAVAILABLE:
        return None
    host.owner.observe_exit()
    try:
        host.authority.require_unsuspended(request.session_id)
    except ProfileAccessRefusedError as recovering:
        return recovering
    return None


def _carries_change(request: OperationRequest) -> bool:
    """Whether ``request`` asks the worker for a change, rather than to read or describe what exists."""
    return not isinstance(
        request,
        OperationContract | OperationObserve | OperationResult | OperationResultPage | OperationReview,
    )


def _named_operation(request: OperationRequest) -> OperationId | None:
    """The existing operation a change names; a submission names none until the worker answers it."""
    if isinstance(request, OperationControl):
        return request.operation_id
    if isinstance(request, OperationManage):
        return request.management.operation_id
    if isinstance(request, OperationSecret):
        return request.requirement.identity.operation_id
    return None


def log_operation_refusal(
    error: AutomationCustodyError | RefusalError | ProfileAccessRefusedError,
    lost: ProfileAccessRefusedError | None,
    request: OperationRequest,
    unknown: bool,
) -> None:
    """Log only refusal metadata, never private operands."""
    # A typed refusal is an answer, not a fault: name the request and the
    # registered fault codes, never a traceback, a payload or a message.
    _log.warning(
        "runtime operation refused code=%s request=%s definition=%s faults=%s effect=%s",
        error.reason if lost is None else lost.reason,
        type(request).__name__,
        request.definition_id if isinstance(request, OperationSubmit) else "-",
        ",".join(fault.type for fault in error.request_faults)
        if isinstance(error, AutomationCustodyError) and error.request_faults
        else "-",
        OperationEffect.UNKNOWN.value if unknown else "-",
    )


def operation_refusal(
    error: AutomationCustodyError | RefusalError | ProfileAccessRefusedError,
    served_by: RuntimeProfileHost | None,
    request: OperationRequest,
    context: ConnectionContext,
    boot: UUID,
) -> AccessRefusal:
    """Report a typed refusal and identify an uncertain in-flight effect."""
    lost = None if served_by is None else _lost_in_flight(served_by, request, error)
    unknown = lost is not None and _carries_change(request)
    log_operation_refusal(error, lost, request, unknown)
    if lost is not None:
        # The worker was lost while it served this request: the session is recovering,
        # and a change it carried may have taken effect, so it is never offered as safe to repeat.
        return AccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=boot,
            connection_id=context.connection_id,
            code=lost.reason,
            recovery_remaining_seconds=lost.recovery_remaining_seconds,
            effect=OperationEffect.UNKNOWN if unknown else None,
            operation_id=_named_operation(request) if unknown else None,
        )
    else:
        return AccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=boot,
            connection_id=context.connection_id,
            code=error.reason,
            sign_in=error.sign_in if isinstance(error, ProfileAccessRefusedError) else None,
            request_faults=error.request_faults if isinstance(error, AutomationCustodyError) else (),
            holder_operation_id=error.holder_operation_id if isinstance(error, ProfileAccessRefusedError) else None,
            recovery_remaining_seconds=error.recovery_remaining_seconds
            if isinstance(error, ProfileAccessRefusedError)
            else None,
        )


def operation_change_cues(
    boot: UUID,
    profile_id: UUID,
    reported: set[OperationId],
    operation_watches: dict[UUID, dict[OperationId, UUID]],
    connections: dict[UUID, ProfileConnection],
) -> list[OperationChanged]:
    """Build cues for live sessions watching one of the reported operations."""
    return [
        OperationChanged(
            runtime_boot_id=boot,
            connection_id=connection_id,
            profile_id=profile_id,
            session_id=connection.session_id,
        )
        for connection_id, watches in operation_watches.items()
        if (connection := connections.get(connection_id)) is not None
        and connection.profile_id == profile_id
        and connection.session_id is not None
        and any(watches.get(operation_id) == connection.session_id for operation_id in reported)
    ]


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
        # Set once the request may reach the worker; a loss after that may have taken its change with it.
        served_by: RuntimeProfileHost | None = None
        with self._language_observed_after(context), ExitStack() as release_guard:
            try:
                release_guard.enter_context(self.operation_admission())
                connection, host = self._operation_target(context, channel, request)
                if isinstance(request, OperationFinancialInput):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                # A suspended session learns how long it may still rebind before any worker is borrowed for it.
                host.owner.observe_exit()
                host.authority.require_unsuspended(request.session_id)
                served_by = host
                if isinstance(request, OperationSecret):
                    self._operation_secret(host, connection, channel, request)
                    return
                reply, expires_at = self._operation_reply(
                    connection, host, context, channel, request, release_guard=release_guard
                )
                self._watch_observed_operation(connection, request, reply)
                deadline = self._operation_deadline(expires_at)
            except (AutomationCustodyError, RefusalError, ProfileAccessRefusedError) as error:
                release_guard.close()
                reply = operation_refusal(error, served_by, request, context, self.boot)
                deadline = time.monotonic() + 5
            # Write errors propagate: a partially written frame is never retried
            # as a refusal. No private payload escapes the scope of its fence.
            write_document(channel, reply, deadline=deadline)

    def _watch_observed_operation(
        self: RuntimeProfileConnections, connection: ProfileConnection, request: OperationRequest, reply: OperationReply
    ) -> None:
        """Keep cueing a connection about an operation it observed until it observes it terminal."""
        if not isinstance(request, OperationObserve) or connection.session_id is None:
            return
        operation_id = request.observation.operation_id
        observation = reply.observation if isinstance(reply, OperationObserved) else None
        running = (
            isinstance(observation, OperationObservationSuccessV1)
            and observation.projection.lifecycle is not OperationLifecycle.TERMINAL
        )
        with self._guard:
            watches = self._operation_watches.setdefault(connection.context.connection_id, {})
            watches.pop(operation_id, None)
            if running:
                watches[operation_id] = connection.session_id
                while len(watches) > _OPERATION_WATCHES_PER_CONNECTION:
                    del watches[next(iter(watches))]
            elif not watches:
                del self._operation_watches[connection.context.connection_id]

    def _operations_advanced(
        self: RuntimeProfileConnections,
        profile_id: UUID,
        operation_ids: tuple[OperationId, ...],
        records_changed: bool = False,
    ) -> None:
        """Cue each connection of this profile still observing one of the operations its worker reported."""
        if records_changed:
            with self._guard:
                record_cues = [
                    ProfileRecordsChanged(
                        runtime_boot_id=self.boot,
                        connection_id=connection_id,
                        profile_id=profile_id,
                        session_id=connection.session_id,
                    )
                    for connection_id, connection in self._connections.items()
                    if connection.profile_id == profile_id and connection.session_id is not None
                ]
            for cue in record_cues:
                self._events.publish_cue(cue)
        reported = set(operation_ids)
        with self._guard:
            cues = operation_change_cues(self.boot, profile_id, reported, self._operation_watches, self._connections)
        for cue in cues:
            self._events.publish_cue(cue)

    @contextmanager
    def _language_observed_after(self: RuntimeProfileConnections, context: ConnectionContext) -> Generator[None]:
        """Bracket operations so a first read does not invalidate itself.

        Establish the initial hint before any read or mutation. The final
        observation still cues a change during the operation, including when
        the initial hint could not be read.
        """
        with self._guard:
            connection = self._connections.get(context.connection_id)
        if connection is not None:
            self.observe_profile_language(connection.profile_id, establish_baseline=True)
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
        connection = self._request_connection(context, channel, request)
        with self._guard:
            host = self._profiles.get(connection.profile_id)
        if host is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return connection, host

    def _request_connection(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: OperationRequest | ViewAttachRequest,
    ) -> ProfileConnection:
        """Check the shared native peer, runtime and exact profile session."""
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if not self._admitting():
            raise RefusalError(RefusalCode.DRAINING)
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(_session_mismatch(connection))
        return connection

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
        status = _admitted_status(self._status(connection, host, request.request_id, request.session_id))
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
            status = _admitted_status(self._status(connection, host, request.request_id, request.session_id))
            scope = status.status.effective_scope
            if request.definition_id not in scope.operations or AccessAction.SUBMIT not in scope.actions:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            expires_at = status.status.session_expires_at
            if expires_at is None or expires_at <= self._wall_clock():
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)

    def view_attach(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request: ViewAttachRequest
    ) -> None:
        """Issue a single-use attach token to the desktop session that submitted this running view.

        The view's worker leg is opened on the first attach. The token is bound
        to this session, profile, native peer, boot and operation.
        """
        reply: ViewAttachGranted | AccessRefusal
        try:
            with self.operation_admission():
                connection, host = self._view_target(context, channel, request)
                with self._views.opening:
                    if self._views.worker_bind(request.operation_id) is None:
                        worker = host.owner.operation_worker()
                        bind, worker_channel = open_worker_view_leg(
                            storage_root=self.root,
                            identity=worker.identity,
                            verify=worker.verify_view_channel,
                            product_version=version("cadrumo"),
                        )
                        if bind.definition_id != SEDE_VIEW_DEFINITION_ID or bind.operation_id != request.operation_id:
                            worker_channel.close()
                            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                        self._views.bind_worker(profile_id=connection.profile_id, bind=bind, channel=worker_channel)
                token = self._views.issue(
                    ViewAttachGrant(
                        operation_id=request.operation_id,
                        profile_id=connection.profile_id,
                        session_id=request.session_id,
                        person_connection_id=context.connection_id,
                        peer=context.peer,
                        runtime_boot_id=self.boot,
                    )
                )
                reply = ViewAttachGranted(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    operation_id=request.operation_id,
                    attach_token=token,
                )
        except (AutomationCustodyError, RefusalError, ProfileAccessRefusedError) as error:
            _log.warning("runtime view attach refused code=%s", error.reason)
            reply = self._view_refusal(context, request.request_id, error)
        write_document(channel, reply, deadline=time.monotonic() + 5)

    def view_connect(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request: ViewConnect
    ) -> None:
        """Admit this connection as a view connection by its attach token, then relay until it unbinds."""
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            leg = self._views.admit(
                attach_token=request.attach_token, operation_id=request.operation_id, context=context, channel=channel
            )
        except (AutomationCustodyError, RefusalError, ProfileAccessRefusedError) as error:
            _log.warning("runtime view connection refused code=%s", error.reason)
            refusal = self._view_refusal(context, request.request_id, error)
            write_document(channel, refusal, deadline=time.monotonic() + 5)
            return
        self._views.serve_window(leg, request.request_id)

    def _view_target(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request: ViewAttachRequest
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        """Require the exact desktop person connection, its profile and its current session."""
        connection = self._request_connection(context, channel, request)
        if connection.frontend is not OperationFrontendProjection.DESKTOP:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        with self._guard:
            host = self._profiles.get(connection.profile_id)
        if host is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        with host.guard:
            _admitted_status(self._status(connection, host, request.request_id, request.session_id))
        return connection, host

    def _view_refusal(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        request_id: UUID,
        error: AutomationCustodyError | RefusalError | ProfileAccessRefusedError,
    ) -> AccessRefusal:
        return AccessRefusal(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            code=error.reason,
        )
