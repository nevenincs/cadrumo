"""Profile admission and management over one verified runtime transport."""

from __future__ import annotations

from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.extension_records import ExtensionRecordReply, ExtensionRecordRequest
from ..contracts.model_runs import ModelRunCompleted, ModelRunCompleteRequest, ModelRunFetched, ModelRunFetchRequest
from ..contracts.profile_access import (
    AccessRefusal,
    SecretReady,
)
from ..contracts.service_access import (
    ServiceAdmission,
    ServiceAdmissionPending,
    ServiceAdmissionStatusQuery,
    ServiceConnect,
    ServiceConnected,
)
from .frame_io import read_secret, write_document, write_secret
from .model_run_frames import read_secret_chunks, write_secret_chunks
from .verified_transport import VerifiedTransport


class ProfileServiceTransport(VerifiedTransport):
    """Exchange service, model-run and extension records on verified transport."""

    def service_access(
        self, request: ServiceConnect | ServiceAdmission | ServiceAdmissionStatusQuery, *, deadline: float
    ) -> ServiceConnected | ServiceAdmissionPending | AccessRefusal:
        """Submit a typed service-admission request over this verified connection."""
        with self._exchange(deadline=deadline):
            try:
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ServiceConnected | ServiceAdmissionPending | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def model_run_fetch(
        self, request: ModelRunFetchRequest, *, deadline: float
    ) -> tuple[ModelRunFetched | AccessRefusal, bytearray]:
        """Fetch one waiting worker model run; a run's body follows its reply on secret frames."""
        body = bytearray()
        with self._exchange(deadline=deadline):
            try:
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ModelRunFetched | AccessRefusal) or (
                    isinstance(reply, ModelRunFetched) and reply.run_id != request.run_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ModelRunFetched):
                    body = read_secret_chunks(self._channel, reply.body_byte_count, deadline=deadline)
                return reply, body
            except BaseException as error:
                body[:] = bytes(len(body))
                self._close_after_failure(error)
                raise

    def model_run_complete(
        self, request: ModelRunCompleteRequest, text: bytearray, *, deadline: float
    ) -> ModelRunCompleted | AccessRefusal:
        """Answer one fetched model run; served reply text follows once the runtime is ready for it."""
        with self._exchange(deadline=deadline):
            try:
                if len(text) != request.outcome.text_byte_count:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, SecretReady):
                    write_secret_chunks(self._channel, text, deadline=deadline)
                    reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ModelRunCompleted | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return reply
            except BaseException as error:
                self._close_after_failure(error)
                raise
            finally:
                text[:] = bytes(len(text))

    def extension_record(
        self, request: ExtensionRecordRequest, payload: bytearray | None = None, *, deadline: float
    ) -> tuple[ExtensionRecordReply | AccessRefusal, bytearray]:
        """Exchange one lease-bound extension-record request and payload."""
        material = bytearray()
        with self._exchange(deadline=deadline):
            try:
                write_document(self._channel, request, deadline=deadline)
                reply = self._reply(request.request_id, deadline=deadline).root
                if isinstance(reply, SecretReady):
                    if payload is None or len(payload) != request.byte_count:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    write_secret(self._channel, payload, deadline=deadline)
                    reply = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(reply, ExtensionRecordReply | AccessRefusal):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                if isinstance(reply, ExtensionRecordReply) and reply.byte_count:
                    with read_secret(self._channel, deadline=deadline) as incoming:
                        if len(incoming) != reply.byte_count:
                            raise RefusalError(RefusalCode.INVALID_FRAME)
                        material.extend(incoming)
                return reply, material
            except BaseException as error:
                material[:] = bytes(len(material))
                self._close_after_failure(error)
                raise
