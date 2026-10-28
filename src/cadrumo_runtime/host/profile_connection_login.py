"""Retained connection-bound login attempts, settled by cues and exact claims."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.errors.failure_report import log_boundary_failure
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    OrchestrationTimeoutError,
    TimeoutDeadline,
)
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileLogin,
    ProfileLoginPending,
    ProfileLoginStatusQuery,
    ProfileStatus,
    SecretReady,
)
from cadrumo_client.contracts.session_events import ProfileLoginChanged
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document

from ..application.session_authority_contracts import HumanAdmissionControl
from .profile_host import ProfileConnection, RuntimeProfileHost

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections

_LOGGER = get_logger(__name__)


@dataclass
class PendingProfileLogin:
    """One retained proof owner; only its original connection can claim it."""

    context: ConnectionContext
    request: ProfileLogin
    connection: ProfileConnection
    host: RuntimeProfileHost
    secret: bytearray = field(repr=False)
    deadline: TimeoutDeadline = field(default_factory=DEFAULT_TIMEOUT_POLICY.deadline)
    control: HumanAdmissionControl = field(default_factory=HumanAdmissionControl)
    finished: Event = field(default_factory=Event)
    result: ProfileStatus | AccessRefusal | None = None
    failure: BaseException | None = field(default=None, repr=False)
    thread: Thread | None = field(default=None, repr=False)

    def retained_cleanup(self) -> AsyncResourceCleanupError | None:
        """The original failed cleanup owner, never replaced by a retry attempt."""
        if self.failure is None:
            return None
        for key in ("async_cleanup_error", "cleanup_error"):
            cleanup = self.failure.__dict__.get(key)
            if isinstance(cleanup, AsyncResourceCleanupError):
                return cleanup
        return None


class ProfileConnectionLoginMixin:
    """Keep the sole connection reader available during an owned login proof."""

    def _login(
        self: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request: ProfileLogin
    ) -> ProfileLoginPending | ProfileStatus | AccessDenied:
        with self._guard:
            prior = self._pending_logins.get(context.connection_id)
            if prior is not None and (not prior.finished.is_set() or prior.retained_cleanup() is not None):
                return AccessDenied(code=AccessDenialCode.SUBJECT_BUSY)
            if prior is None and len(self._pending_logins) >= 32:
                return AccessDenied(code=AccessDenialCode.SUBJECT_BUSY)
            if not self._login_slots.acquire(blocking=False):
                return AccessDenied(code=AccessDenialCode.SUBJECT_BUSY)
        pending: PendingProfileLogin | None = None
        timeout = DEFAULT_TIMEOUT_POLICY.deadline()
        try:
            connection, host = self._prepare(context, channel, request)
            write_document(
                channel,
                SecretReady(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                ),
                deadline=timeout.instant,
            )
            with read_secret(channel, deadline=timeout.instant) as secret:
                pending = PendingProfileLogin(context, request, connection, host, bytearray(secret), deadline=timeout)
            if request.method == "api_key":
                return self._login_proof(
                    connection, host, context, request, pending.secret, pending.control, pending.deadline
                )
            with host.guard, self._guard:
                if (
                    self._closed
                    or self._connections.get(context.connection_id) is not connection
                    or connection.disconnecting
                ):
                    return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
                self._pending_logins[context.connection_id] = pending
            pending.thread = Thread(target=self._run_login, args=(pending,), name="profile-login", daemon=True)
            pending.thread.start()
            return self._login_pending(pending, request.request_id)
        except BaseException:
            if pending is not None:
                pending.secret[:] = bytes(len(pending.secret))
                with self._guard:
                    if self._pending_logins.get(context.connection_id) is pending:
                        self._pending_logins.pop(context.connection_id)
            raise
        finally:
            if pending is None or pending.thread is None or pending.thread.ident is None:
                if pending is not None:
                    pending.secret[:] = bytes(len(pending.secret))
                self._login_slots.release()

    def _run_login(self: RuntimeProfileConnections, pending: PendingProfileLogin) -> None:
        request, context = pending.request, pending.context
        try:
            result = self._login_proof(
                pending.connection, pending.host, context, request, pending.secret, pending.control, pending.deadline
            )
            if isinstance(result, AccessDenied):
                result = AccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=result.code,
                    sign_in=result.sign_in,
                    recovery_remaining_seconds=result.recovery_remaining_seconds,
                )
        except BaseException as error:
            pending.failure = error
            log_boundary_failure(_LOGGER, "profile_login_attempt_failed", error, level=logging.WARNING)
            code = (
                error.reason
                if isinstance(error, (AutomationCustodyError, ProfileAccessRefusedError, RefusalError))
                else RefusalCode.UNAVAILABLE
            )
            if isinstance(error, OrchestrationTimeoutError):
                code = RefusalCode.TIMEOUT
            sign_in = error.sign_in if isinstance(error, ProfileAccessRefusedError) else None
            if sign_in is not None and sign_in.reason == "credential_rejected":
                code = AutomationCustodyCode.CREDENTIAL_REJECTED
            result = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=code,
                sign_in=sign_in,
            )
        finally:
            pending.secret[:] = bytes(len(pending.secret))
            self._login_slots.release()
        with self._guard:
            pending.result = result
            pending.finished.set()
            if (
                self._connections.get(context.connection_id) is not pending.connection
                and pending.retained_cleanup() is None
            ):
                self._pending_logins.pop(context.connection_id, None)
        self._events.publish(
            ProfileLoginChanged(
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                profile_id=request.profile_id,
                login_request_id=request.request_id,
            )
        )
        self._sign_in_changed()
        self.lifecycle_changed()

    def _login_pending(
        self: RuntimeProfileConnections, pending: PendingProfileLogin, request_id: UUID
    ) -> ProfileLoginPending:
        return ProfileLoginPending(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=pending.context.connection_id,
            profile_id=pending.request.profile_id,
            login_request_id=pending.request.request_id,
        )

    def _login_status(
        self: RuntimeProfileConnections, context: ConnectionContext, request: ProfileLoginStatusQuery
    ) -> ProfileLoginPending | ProfileStatus | AccessRefusal | AccessDenied:
        with self._guard:
            pending = self._pending_logins.get(context.connection_id)
        if (
            pending is None
            or pending.context != context
            or pending.request.profile_id != request.profile_id
            or pending.request.request_id != request.login_request_id
        ):
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with pending.host.guard:
            if request.action == "profile_login_cancel":
                pending.control.cancel()
            if pending.finished.is_set():
                result = pending.result
                if result is None:
                    return AccessDenied(code=AccessDenialCode.AUTHORITY_UNAVAILABLE)
                if isinstance(result, ProfileStatus) and result.status.session_id is not None:
                    current = self._status(
                        pending.connection, pending.host, request.request_id, result.status.session_id
                    )
                    if isinstance(current, AccessDenied):
                        return current
                    return result.model_copy(update={"request_id": request.request_id, "status": current.status})
                return result.model_copy(update={"request_id": request.request_id})
        return self._login_pending(pending, request.request_id)

    def _cancel_connection_login(self: RuntimeProfileConnections, context: ConnectionContext) -> None:
        with self._guard:
            pending = self._pending_logins.get(context.connection_id)
        if pending is not None:
            with pending.host.guard:
                pending.control.cancel()
            if pending.finished.is_set() and pending.retained_cleanup() is None:
                with self._guard:
                    if self._pending_logins.get(context.connection_id) is pending:
                        self._pending_logins.pop(context.connection_id)

    def _settle_pending_logins(self: RuntimeProfileConnections, *, deadline: float) -> tuple[UUID, ...]:
        """Keep original proof threads and failed cleanup owners until shutdown settles them."""
        with self._guard:
            pending = tuple(self._pending_logins.values())
        unsettled: set[UUID] = set()
        for attempt in pending:
            if attempt.host.guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
                try:
                    attempt.control.cancel()
                finally:
                    attempt.host.guard.release()
            else:
                unsettled.add(attempt.request.profile_id)
            if attempt.thread is not None and attempt.thread.ident is not None:
                attempt.thread.join(timeout=max(0.0, deadline - time.monotonic()))
            if not attempt.finished.is_set() or (attempt.thread is not None and attempt.thread.is_alive()):
                unsettled.add(attempt.request.profile_id)
                continue
            cleanup = attempt.retained_cleanup()
            if isinstance(cleanup, AsyncResourceCleanupError):
                try:
                    asyncio.run(cleanup.retry_cleanup())
                except BaseException:
                    unsettled.add(attempt.request.profile_id)
                    continue
                attempt.failure = None
            with self._guard:
                if self._pending_logins.get(attempt.context.connection_id) is attempt:
                    self._pending_logins.pop(attempt.context.connection_id)
        return tuple(sorted(unsettled))
