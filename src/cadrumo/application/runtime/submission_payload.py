"""Strict, bounded assembly of one protected operation-submission payload."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ...core.base64_codec import b64_decode_canonical
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

SUBMISSION_PAYLOAD_CHUNK_BYTES = 16_384
SUBMISSION_PAYLOAD_MAX_BYTES = 16_777_216
SUBMISSION_PAYLOAD_TIMEOUT_SECONDS = 30

_MAX_ENCODED_CHUNK_CHARS = 4 * ((SUBMISSION_PAYLOAD_CHUNK_BYTES + 2) // 3)


class SubmissionPayloadDescriptor(BaseModel):
    """Declare the exact UTF-8 byte count and digest before any chunk arrives."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    byte_count: Annotated[int, Field(ge=2, le=SUBMISSION_PAYLOAD_MAX_BYTES)]
    payload_digest: ContentDigest


class FinancialOperandInputDescriptor(BaseModel):
    """Bounded volatile operator input, deliberately without an input digest."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["financial_operand_input"] = "financial_operand_input"
    byte_count: Annotated[int, Field(ge=2, le=SUBMISSION_PAYLOAD_MAX_BYTES)]


class SubmissionPayloadChunk(BaseModel):
    """One bounded, ordered byte range without exposing its contents in repr."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    offset: Annotated[int, Field(ge=0)]
    encoded: Annotated[str, Field(min_length=4, max_length=_MAX_ENCODED_CHUNK_CHARS, repr=False)]

    def decode(self) -> bytes:
        """Reject noncanonical base64, empty data and oversized chunks."""
        try:
            data = b64_decode_canonical(self.encoded)
        except ValueError:
            raise ValueError("invalid submission payload chunk") from None
        if not 0 < len(data) <= SUBMISSION_PAYLOAD_CHUNK_BYTES:
            raise ValueError("invalid submission payload chunk")
        return data


class SubmissionPayloadBuffer:
    """Assemble a single finite submission, then wipe its mutable byte storage."""

    def __init__(self, descriptor: SubmissionPayloadDescriptor | FinancialOperandInputDescriptor) -> None:
        """Retain only bounded metadata and an initially empty mutable buffer."""
        self._descriptor = descriptor
        self._content = bytearray()
        self._closed = False

    def append(self, chunk: SubmissionPayloadChunk) -> None:
        """Accept exactly the next full chunk, except for the final remainder."""
        if self._closed:
            raise ValueError("submission payload buffer is closed")
        try:
            remaining = self._descriptor.byte_count - len(self._content)
            expected = min(SUBMISSION_PAYLOAD_CHUNK_BYTES, remaining)
            data = chunk.decode()
            if chunk.offset != len(self._content) or len(data) != expected:
                raise ValueError("submission payload chunk has an invalid range")
            self._content.extend(data)
        except BaseException:
            self.close()
            raise

    def finish(self) -> str:
        """Verify complete bytes and strict UTF-8, closing even on refusal."""
        if self._closed:
            raise ValueError("submission payload buffer is closed")
        try:
            if len(self._content) != self._descriptor.byte_count:
                raise ValueError("submission payload is incomplete")
            if (
                isinstance(self._descriptor, SubmissionPayloadDescriptor)
                and sha256_hex(bytes(self._content)) != self._descriptor.payload_digest
            ):
                raise ValueError("submission payload digest does not match")
            try:
                return self._content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise ValueError("submission payload is not UTF-8") from None
        finally:
            self.close()

    def close(self) -> None:
        """Wipe mutable storage once; a closed upload cannot be resumed."""
        if not self._closed:
            self._closed = True
            self._content[:] = bytes(len(self._content))
            self._content.clear()


__all__ = [
    "SUBMISSION_PAYLOAD_CHUNK_BYTES",
    "SUBMISSION_PAYLOAD_MAX_BYTES",
    "SUBMISSION_PAYLOAD_TIMEOUT_SECONDS",
    "SubmissionPayloadBuffer",
    "SubmissionPayloadChunk",
    "SubmissionPayloadDescriptor",
]
