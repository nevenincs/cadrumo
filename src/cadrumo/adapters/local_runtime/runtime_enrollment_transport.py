"""Bound enrollment receipt and native credential delivery exchanges."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import SecretBytes

from ...application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.enrollment_access import (
    EnrollmentCredentialBinding,
    RuntimeEnrollmentClientReply,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentSubmit,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
)
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from .runtime_frame_io import (
    read_secret,
    write_document,
)
from .runtime_profile_transport import RuntimeProfileTransport


class RuntimeEnrollmentTransport(RuntimeProfileTransport):
    """Bound enrollment receipt and native credential delivery exchanges."""

    def enrollment_prepare(
        self, request: RuntimeEnrollmentPrepare, *, deadline: float
    ) -> RuntimeEnrollmentPrepared | RuntimeAccessRefusal:
        """Mint a request only on this verified native connection."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeEnrollmentPrepared | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if (
                    isinstance(reply, RuntimeEnrollmentPrepared)
                    and reply.profile_binding.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_submit(
        self, request: RuntimeEnrollmentSubmit, proposal: bytearray, *, deadline: float
    ) -> RuntimeEnrollmentRecorded | RuntimeAccessRefusal:
        """Submit proposal bytes only after one correlated secret-ready document."""
        with self._exchange(deadline=deadline, secret=proposal):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, proposal, deadline=deadline)
                if isinstance(delivered, RuntimeAccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, RuntimeEnrollmentRecorded | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeEnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_inspect(
        self, request: RuntimeEnrollmentInspect | RuntimeEnrollmentReconcile, *, deadline: float
    ) -> RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeAccessRefusal:
        """Read an exact receipt through its live offer or fresh root admission."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if isinstance(reply, RuntimeEnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_poll(
        self,
        request: RuntimeEnrollmentPoll,
        *,
        store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
        possession: Callable[[EnrollmentCredentialBinding], SecretBytes | None],
        deadline: float,
    ) -> RuntimeEnrollmentDelivery | RuntimeEnrollmentIdle | RuntimeAccessRefusal:
        """Finish one bound client command, including its secret frame and final reply."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    return reply
                if not isinstance(reply, RuntimeEnrollmentDelivery) or (
                    reply.credential.profile_binding.profile_id != request.profile_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                response, proof = self._enrollment_client_response(reply, store, possession, deadline)
                write_document(self._channel, response, deadline=deadline)
                if response.outcome == "present":
                    if proof is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                    self.send_secret(bytearray(proof.get_secret_value()), deadline=deadline)
                final = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(final, RuntimeEnrollmentIdle | RuntimeAccessRefusal):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return reply if isinstance(final, RuntimeEnrollmentIdle) else final
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _enrollment_client_response(
        self,
        reply: RuntimeEnrollmentDelivery,
        store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
        possession: Callable[[EnrollmentCredentialBinding], SecretBytes | None],
        deadline: float,
    ) -> tuple[RuntimeEnrollmentClientReply, SecretBytes | None]:
        """Finish one native store or possession command before acknowledging it."""
        if reply.action == "store":
            with read_secret(self._channel, deadline=deadline) as candidate:
                response = _store_enrollment_candidate(reply, candidate, store)
            return response, None
        try:
            proof = possession(reply.credential)
        except AutomationCustodyError as error:
            return RuntimeEnrollmentClientReply(command_id=reply.command_id, outcome="refused", code=error.reason), None
        return RuntimeEnrollmentClientReply(
            command_id=reply.command_id, outcome="present" if proof is not None else "missing"
        ), proof


def _store_enrollment_candidate(
    reply: RuntimeEnrollmentDelivery,
    candidate: bytearray,
    store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
) -> RuntimeEnrollmentClientReply:
    try:
        store(reply.credential, SecretBytes(bytes(candidate)))
    except AutomationCustodyError as error:
        return RuntimeEnrollmentClientReply(command_id=reply.command_id, outcome="refused", code=error.reason)
    return RuntimeEnrollmentClientReply(command_id=reply.command_id, outcome="stored")
