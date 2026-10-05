"""Bounded byte pages of one canonical, already-authorized public projection."""

from __future__ import annotations

import base64
from typing import Annotated, Self

from pydantic import BaseModel, Field, JsonValue, model_validator

from ...core.base64_codec import b64_decode_canonical
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError

# Base64 leaves room for both runtime and worker authority envelopes within
# the 64 KiB transport frame, while reducing repeated projection work.
PROJECTION_PAGE_BYTES = 32_768
PROJECTION_DOCUMENT_MAX_BYTES = 16_777_216


class ProjectionPageRequest(BaseModel):
    """A continuation pins the complete canonical document, never a cache key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    offset: Annotated[int, Field(ge=0, lt=PROJECTION_DOCUMENT_MAX_BYTES)] = 0
    expected_digest: ContentDigest | None = None

    @model_validator(mode="after")
    def _pin_continuation(self) -> Self:
        if self.offset and self.expected_digest is None:
            raise ValueError("projection continuation requires its document digest")
        return self


class ProjectionPage(BaseModel):
    """One canonical byte range; encoded content is private projection data."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    offset: Annotated[int, Field(ge=0, lt=PROJECTION_DOCUMENT_MAX_BYTES)]
    total_bytes: Annotated[int, Field(ge=2, le=PROJECTION_DOCUMENT_MAX_BYTES)]
    document_digest: ContentDigest
    encoded: Annotated[str, Field(min_length=4, max_length=4 * ((PROJECTION_PAGE_BYTES + 2) // 3), repr=False)]

    def decode(self) -> bytes:
        """Reject malformed or noncanonical base64 and impossible byte ranges."""
        try:
            data = b64_decode_canonical(self.encoded)
        except ValueError:
            raise ValueError("invalid projection page encoding") from None
        if self.offset >= self.total_bytes or len(data) != min(PROJECTION_PAGE_BYTES, self.total_bytes - self.offset):
            raise ValueError("invalid projection page range")
        return data

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        self.decode()
        return self


def project_document_page(document: dict[str, JsonValue], request: ProjectionPageRequest) -> ProjectionPage:
    """Slice only while the operation owner retains its normal output guard."""
    encoded = canonical_json_bytes(document)
    digest = sha256_hex(encoded)
    if (
        len(encoded) > PROJECTION_DOCUMENT_MAX_BYTES
        or request.offset >= len(encoded)
        or (request.expected_digest is not None and request.expected_digest != digest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return ProjectionPage(
        offset=request.offset,
        total_bytes=len(encoded),
        document_digest=digest,
        encoded=base64.b64encode(encoded[request.offset : request.offset + PROJECTION_PAGE_BYTES]).decode("ascii"),
    )
