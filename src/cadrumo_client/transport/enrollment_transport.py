"""Bound enrollment receipt and native credential delivery exchanges."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import SecretBytes

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError

from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.enrollment_access import (
    EnrollmentClientReply,
    EnrollmentCredentialBinding,
    EnrollmentDelivery,
    EnrollmentIdle,
    EnrollmentInspect,
    EnrollmentPoll,
    EnrollmentPrepare,
    EnrollmentPrepared,
    EnrollmentReconcile,
    EnrollmentRecorded,
    EnrollmentSubmit,
)
from ..contracts.profile_access import AccessRefusal
from .frame_io import read_secret, write_document
from .profile_transport import ProfileTransport


class EnrollmentTransport(ProfileTransport):
    """Bound enrollment receipt and native credential delivery exchanges."""

    def enrollment_prepare(self, request: EnrollmentPrepare, *, deadline: float) -> EnrollmentPrepared | AccessRefusal:
        """Mint a request only on this verified native connection."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, EnrollmentPrepared | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, EnrollmentPrepared) and reply.profile_binding.profile_id != request.profile_id:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_submit(
        self, request: EnrollmentSubmit, proposal: bytearray, *, deadline: float
    ) -> EnrollmentRecorded | AccessRefusal:
        """Submit proposal bytes only after one correlated secret-ready document."""
        with self._exchange(deadline=deadline, secret=proposal):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                delivered = self._deliver_secret(request, proposal, deadline=deadline)
                if isinstance(delivered, AccessRefusal):
                    return delivered
                _, reply_document = delivered
                reply = reply_document.root
                if not isinstance(reply, EnrollmentRecorded | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, EnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_inspect(
        self, request: EnrollmentInspect | EnrollmentReconcile, *, deadline: float
    ) -> EnrollmentRecorded | EnrollmentIdle | AccessRefusal:
        """Read an exact receipt through its live offer or fresh root admission."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, EnrollmentRecorded | EnrollmentIdle | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, EnrollmentRecorded) and (
                    reply.receipt.request_id != request.enrollment_request_id
                    or reply.receipt.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def enrollment_poll(
        self,
        request: EnrollmentPoll,
        *,
        store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
        possession: Callable[[EnrollmentCredentialBinding], SecretBytes | None],
        deadline: float,
    ) -> EnrollmentDelivery | EnrollmentIdle | AccessRefusal:
        """Finish one bound client command, including its secret frame and final reply."""
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, EnrollmentIdle | AccessRefusal):
                    return reply
                if not isinstance(reply, EnrollmentDelivery) or (
                    reply.credential.profile_binding.profile_id != request.profile_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                response, proof = self._enrollment_client_response(reply, store, possession, deadline)
                write_document(self._channel, response, deadline=deadline)
                if response.outcome == "present":
                    if proof is None:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    self.send_secret(bytearray(proof.get_secret_value()), deadline=deadline)
                final = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(final, EnrollmentIdle | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply if isinstance(final, EnrollmentIdle) else final
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _enrollment_client_response(
        self,
        reply: EnrollmentDelivery,
        store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
        possession: Callable[[EnrollmentCredentialBinding], SecretBytes | None],
        deadline: float,
    ) -> tuple[EnrollmentClientReply, SecretBytes | None]:
        """Finish one native store or possession command before acknowledging it."""
        if reply.action == "store":
            with read_secret(self._channel, deadline=deadline) as candidate:
                response = _store_enrollment_candidate(reply, candidate, store)
            return response, None
        try:
            proof = possession(reply.credential)
        except AutomationCustodyError as error:
            return EnrollmentClientReply(command_id=reply.command_id, outcome="refused", code=error.reason), None
        return EnrollmentClientReply(
            command_id=reply.command_id, outcome="present" if proof is not None else "missing"
        ), proof


def _store_enrollment_candidate(
    reply: EnrollmentDelivery,
    candidate: bytearray,
    store: Callable[[EnrollmentCredentialBinding, SecretBytes], None],
) -> EnrollmentClientReply:
    try:
        store(reply.credential, SecretBytes(bytes(candidate)))
    except AutomationCustodyError as error:
        return EnrollmentClientReply(command_id=reply.command_id, outcome="refused", code=error.reason)
    return EnrollmentClientReply(command_id=reply.command_id, outcome="stored")
