"""Profile admission and management over one verified runtime transport."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from uuid import UUID, uuid4

from pydantic import BaseModel

from ..contracts.bootstrap import (
    PasswordReset,
    PasswordResetCompleted,
    PasswordResetPrepare,
    PasswordResetPrepared,
    PasswordResetRefused,
)
from ..contracts.bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.deadline_budget import OrchestrationTimeoutError, TimeoutDeadline
from ..contracts.profile_access import (
    AccessRefusal,
    ProfileLogin,
    ProfileLoginPending,
    ProfileLoginStatusQuery,
    ProfileStatus,
)
from ..contracts.profile_selection import ActiveProfileReply, ActiveProfileRequest, LoginTargetReply, LoginTargetRequest
from ..contracts.session_events import ConnectionEvent, ProfileLoginChanged
from ..contracts.sign_in import SignInStatusReply, SignInStatusRequest
from .frame_io import write_document
from .profile_operations_transport import ProfileOperationsTransport


def _validate_delete_reply(
    request: ProfileDeletePrepare | ProfileDelete,
    reply: ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused,
) -> None:
    if reply.profile_id != request.profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if isinstance(reply, ProfileDeletePrepared) and (
        not isinstance(request, ProfileDeletePrepare) or reply.confirmation.profile_id != request.profile_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if isinstance(reply, ProfileDeleted) and (
        not isinstance(request, ProfileDelete)
        or reply.receipt.profile_id != request.profile_id
        or reply.receipt.transaction_id != request.confirmation.transaction_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)


class ProfileTransport(ProfileOperationsTransport):
    """Profile admission and management over one verified runtime transport."""

    def delete_profile(
        self,
        request: ProfileDeletePrepare | ProfileDelete,
        *,
        deadline: float,
    ) -> ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused | AccessRefusal:
        """Echo only existing journal confirmation; never send authentication secrets."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, AccessRefusal):
                    return reply
                if not isinstance(reply, ProfileDeletePrepared | ProfileDeleted | ProfileDeleteRefused):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                _validate_delete_reply(request, reply)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def password_reset_prepare(
        self,
        request: PasswordResetPrepare,
        *,
        deadline: float,
    ) -> PasswordResetPrepared | AccessRefusal:
        """Capture a predecessor on this exact verified connection."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, PasswordResetPrepared | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, PasswordResetPrepared) and reply.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def password_reset(
        self,
        request: PasswordReset,
        secret: bytearray,
        *,
        deadline: float,
    ) -> PasswordResetCompleted | PasswordResetRefused | AccessRefusal:
        """Consume reset credentials only after correlated secret readiness."""
        with self._exchange(deadline=deadline, secret=secret):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                _, document = delivered
                reply = document.root
                if not isinstance(reply, PasswordResetCompleted | PasswordResetRefused | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if (
                    isinstance(reply, PasswordResetCompleted | PasswordResetRefused)
                    and reply.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, PasswordResetCompleted) and reply.outcome.profile_id != str(request.profile_id):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                secret[:] = bytes(len(secret))

    def sign_in_status(self, request: SignInStatusRequest, *, deadline: float) -> SignInStatusReply | AccessRefusal:
        """Observe presence through the same correlated, credential-free exchange."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(result, SignInStatusReply | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(result, SignInStatusReply) and result.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def active_profile(self, request: ActiveProfileRequest, *, deadline: float) -> ActiveProfileReply | AccessRefusal:
        """Ask which profile is selected and signed in, through a correlated, credential-free exchange."""
        result = self._sessionless(request, request.request_id, deadline=deadline)
        if not isinstance(result, ActiveProfileReply | AccessRefusal):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result

    def login_target(self, request: LoginTargetRequest, *, deadline: float) -> LoginTargetReply | AccessRefusal:
        """Ask which profile the operator's text names, through a correlated, credential-free exchange."""
        result = self._sessionless(request, request.request_id, deadline=deadline)
        if not isinstance(result, LoginTargetReply | AccessRefusal):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result

    def _sessionless(self, request: BaseModel, request_id: UUID, *, deadline: float) -> object:
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                return self._reply(request_id, deadline=deadline).root
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _wait_login_result(
        self,
        request: ProfileLogin,
        connection_id: UUID,
        result: object,
        changed: Event,
        timeout: TimeoutDeadline,
        deadline: float,
    ) -> object:
        while isinstance(result, ProfileLoginPending):
            if (
                result.connection_id != connection_id
                or result.profile_id != request.profile_id
                or result.login_request_id != request.request_id
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            changed.clear()
            query = ProfileLoginStatusQuery(
                action="profile_login_status",
                request_id=uuid4(),
                profile_id=request.profile_id,
                login_request_id=request.request_id,
            )
            result = self._sessionless(query, query.request_id, deadline=deadline)
            if isinstance(result, ProfileLoginPending) and not changed.wait(timeout.remaining_seconds()):
                raise OrchestrationTimeoutError("orchestration_timeout")
        return result

    def login(self, request: ProfileLogin, secret: bytearray, *, deadline: float) -> ProfileStatus | AccessRefusal:
        """Consume credentials only after the exact peer accepts this login request."""
        changed = Event()
        timeout = TimeoutDeadline(deadline)

        def receive(event: ConnectionEvent) -> None:
            if (
                isinstance(event, ProfileLoginChanged)
                and event.login_request_id == request.request_id
                and event.profile_id == request.profile_id
            ):
                changed.set()

        unsubscribe: Callable[[], None] | None = None
        claimed = False
        try:
            with self._exchange(deadline=deadline, secret=secret):
                claimed = True
                unsubscribe = self.subscribe_session_events(receive, disconnected=changed.set)
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, secret, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                ready, reply_document = delivered
                result = reply_document.root
            result = self._wait_login_result(request, ready.connection_id, result, changed, timeout, deadline)
            if not isinstance(result, (ProfileStatus, AccessRefusal)) or result.connection_id != ready.connection_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return result.model_copy(update={"request_id": request.request_id})
        except OrchestrationTimeoutError as error:
            refusal = RefusalError(RefusalCode.TIMEOUT)
            self._close_after_failure(refusal)
            raise refusal from error
        except BaseException as error:
            # A login that never reached the front of the queue wrote nothing,
            # so its timeout must not end the exchange another caller holds.
            if claimed:
                self._close_after_failure(error)
            raise
        finally:
            secret[:] = bytes(len(secret))
            if unsubscribe is not None:
                unsubscribe()

    def login_status(
        self, request: ProfileLoginStatusQuery, *, deadline: float
    ) -> ProfileLoginPending | ProfileStatus | AccessRefusal:
        """Claim or cancel an exact owned attempt without re-sending its proof."""
        result = self._sessionless(request, request.request_id, deadline=deadline)
        if not isinstance(result, (ProfileLoginPending, ProfileStatus, AccessRefusal)):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if isinstance(result, ProfileLoginPending) and (
            result.login_request_id != request.login_request_id or result.profile_id != request.profile_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result
