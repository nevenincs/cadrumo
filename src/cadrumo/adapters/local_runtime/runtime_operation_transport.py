"""Registered operation exchanges and bounded private payload submission."""

from __future__ import annotations

from ...application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContractReply,
    RuntimeOperationFinancialInput,
    RuntimeOperationManaged,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationPayloadReady,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSecret,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitPayload,
    RuntimeOperationSubmitted,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
)
from ...application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SUBMISSION_PAYLOAD_MAX_BYTES,
    FinancialOperandInputDescriptor,
    SubmissionPayloadDescriptor,
)
from ...core.hashing import canonical_json_bytes, sha256_hex
from .runtime_enrollment_transport import RuntimeEnrollmentTransport
from .runtime_frame_io import (
    MAXIMUM_FRAME_BYTES,
    write_document,
    write_secret,
)


class RuntimeOperationTransport(RuntimeEnrollmentTransport):
    """Registered operation exchanges and bounded private payload submission."""

    def operation(
        self, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply | RuntimeAccessRefusal:
        """Use only registered operation doors bound to this live profile connection."""
        if isinstance(request, RuntimeOperationSecret | RuntimeOperationSubmitPayload):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        with self._exchange(deadline=deadline):
            try:
                if self._closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                if isinstance(request, RuntimeOperationFinancialInput):
                    return self._submit_payload(request, deadline=deadline)
                if isinstance(request, RuntimeOperationSubmit):
                    try:
                        streamed = len(canonical_json_bytes(request.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES
                    except (UnicodeError, ValueError):
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
                    if streamed:
                        return self._submit_payload(request, deadline=deadline)
                write_document(self._channel, request, deadline=deadline)
                result = self._reply(request.request_id, deadline=deadline).root
                if not isinstance(
                    result,
                    RuntimeOperationSubmitted
                    | RuntimeOperationAcknowledged
                    | RuntimeOperationObserved
                    | RuntimeOperationContractReply
                    | RuntimeOperationProjected
                    | RuntimeOperationPage
                    | RuntimeOperationManaged
                    | RuntimeAccessRefusal,
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                return result
            except BaseException as error:
                self._close_after_failure(error)
                raise

    def _submit_payload(
        self, request: RuntimeOperationSubmit | RuntimeOperationFinancialInput, *, deadline: float
    ) -> RuntimeOperationSubmitted | RuntimeAccessRefusal:
        """Stream private UTF-8 under the existing exchange lock and exact readiness."""
        try:
            content = bytearray(request.payload_json, "utf-8")
        except UnicodeError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        try:
            if not 2 <= len(content) <= SUBMISSION_PAYLOAD_MAX_BYTES:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            descriptor = (
                FinancialOperandInputDescriptor(byte_count=len(content))
                if isinstance(request, RuntimeOperationFinancialInput)
                else SubmissionPayloadDescriptor(byte_count=len(content), payload_digest=sha256_hex(bytes(content)))
            )
            begin = RuntimeOperationSubmitPayload(
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
            if isinstance(ready, RuntimeAccessRefusal):
                return ready
            if not isinstance(ready, RuntimeOperationPayloadReady) or ready.descriptor != descriptor:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            for offset in range(0, len(content), SUBMISSION_PAYLOAD_CHUNK_BYTES):
                write_secret(
                    self._channel, content[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES], deadline=deadline
                )
            submitted = self._reply(request.request_id, deadline=deadline).root
            if not isinstance(submitted, RuntimeOperationSubmitted | RuntimeAccessRefusal):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return submitted
        finally:
            content[:] = bytes(len(content))
