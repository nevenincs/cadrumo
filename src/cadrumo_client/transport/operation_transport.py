"""Registered operation exchanges and bounded private payload submission."""

from __future__ import annotations

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.operation_access import (
    OperationAcknowledged,
    OperationContractReply,
    OperationFinancialInput,
    OperationManaged,
    OperationObserved,
    OperationPage,
    OperationPayloadReady,
    OperationProjected,
    OperationReply,
    OperationRequest,
    OperationSecret,
    OperationSubmit,
    OperationSubmitPayload,
    OperationSubmitted,
)
from ..contracts.profile_access import AccessRefusal
from ..contracts.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SUBMISSION_PAYLOAD_MAX_BYTES,
    FinancialOperandInputDescriptor,
    SubmissionPayloadDescriptor,
)
from .enrollment_transport import EnrollmentTransport
from .frame_io import MAXIMUM_FRAME_BYTES, write_document, write_secret


class OperationTransport(EnrollmentTransport):
    """Registered operation exchanges and bounded private payload submission."""

    def operation(self, request: OperationRequest, *, deadline: float) -> OperationReply | AccessRefusal:
        """Use only registered operation doors bound to this live profile connection."""
        if isinstance(request, OperationSecret | OperationSubmitPayload):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                if isinstance(request, OperationFinancialInput):
                    return self._submit_payload(request, deadline=deadline)
                if isinstance(request, OperationSubmit):
                    try:
                        streamed = len(canonical_json_bytes(request.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES
                    except (UnicodeError, ValueError):
                        raise RefusalError(RefusalCode.INVALID_FRAME) from None
                    if streamed:
                        return self._submit_payload(request, deadline=deadline)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(
                    result,
                    OperationSubmitted
                    | OperationAcknowledged
                    | OperationObserved
                    | OperationContractReply
                    | OperationProjected
                    | OperationPage
                    | OperationManaged
                    | AccessRefusal,
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _submit_payload(
        self, request: OperationSubmit | OperationFinancialInput, *, deadline: float
    ) -> OperationSubmitted | AccessRefusal:
        """Stream private UTF-8 under the existing exchange lock and exact readiness."""
        try:
            content = bytearray(request.payload_json, "utf-8")
        except UnicodeError:
            raise RefusalError(RefusalCode.INVALID_FRAME) from None
        try:
            if not 2 <= len(content) <= SUBMISSION_PAYLOAD_MAX_BYTES:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            descriptor = (
                FinancialOperandInputDescriptor(byte_count=len(content))
                if isinstance(request, OperationFinancialInput)
                else SubmissionPayloadDescriptor(byte_count=len(content), payload_digest=sha256_hex(bytes(content)))
            )
            begin = OperationSubmitPayload(
                request_id=request.request_id,
                profile_id=request.profile_id,
                session_id=request.session_id,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
                idempotency_key=request.idempotency_key,
                descriptor=descriptor,
            )
            write_document(self._channel, begin, deadline=deadline)
            ready = self._reply(request.request_id, deadline=deadline).root
            if isinstance(ready, AccessRefusal):
                return ready
            if not isinstance(ready, OperationPayloadReady) or ready.descriptor != descriptor:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            for offset in range(0, len(content), SUBMISSION_PAYLOAD_CHUNK_BYTES):
                write_secret(
                    self._channel, content[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES], deadline=deadline
                )
            submitted = self._reply(request.request_id, deadline=deadline).root
            if not isinstance(submitted, OperationSubmitted | AccessRefusal):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return submitted
        finally:
            content[:] = bytes(len(content))
