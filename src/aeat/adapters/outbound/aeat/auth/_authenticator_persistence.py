"""Persisted certificate-auth session metadata records and diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG
from ._errors import AeatLoginAssertionError
from .certificate import HandshakeResult

AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1
"""Schema version for the persisted AEAT session metadata."""


class PersistedSessionMetadata(BaseModel):
    """AEAT-specific metadata stored beside a Playwright storage-state file."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=AEAT_STORAGE_STATE_SCHEMA_VERSION, ge=1)
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    certificate_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: str = Field(min_length=64, max_length=64)
    handshake: HandshakeResult


def persisted_session_reason_code(reason: str) -> str:
    """Return a non-sensitive persisted-session invalidation reason code."""
    reason_lower = reason.lower()
    if "hash does not match" in reason_lower:
        return "storage_hash_mismatch"
    if "past its idle deadline" in reason_lower:
        return "idle_deadline_expired"
    if "different certificate thumbprint" in reason_lower:
        return "certificate_thumbprint_mismatch"
    if "different certificate subject" in reason_lower:
        return "certificate_subject_mismatch"
    if "failed live verification" in reason_lower:
        return "live_verification_failed"
    if "could not be resumed" in reason_lower:
        return "resume_failed"
    if "storage_state missing" in reason_lower:
        return "storage_state_missing"
    if "storage_state is malformed" in reason_lower:
        return "storage_state_malformed"
    if "storage_state root" in reason_lower:
        return "storage_state_root_invalid"
    if "cookies array" in reason_lower:
        return "storage_state_cookies_missing"
    if "origins array" in reason_lower:
        return "storage_state_origins_missing"
    if "metadata is malformed" in reason_lower:
        return "metadata_malformed"
    if "schema version" in reason_lower:
        return "schema_version_unsupported"
    return "invalid_persisted_session"


def persisted_session_reason_from_error(error: AeatLoginAssertionError) -> str:
    """Extract the redacted persisted-session reason code from an auth error."""
    context = getattr(error, "context", None)
    if isinstance(context, Mapping):
        reason = context.get("reason")
        if isinstance(reason, str) and reason:
            return reason
    return "invalid_persisted_session"
