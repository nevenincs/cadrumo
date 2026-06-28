"""Certificate-auth persisted-session metadata and redacted diagnostics.

:class:`aeat.adapters.outbound.aeat.auth.AeatAuthenticator` writes
:class:`PersistedSessionMetadata` into the encrypted
:class:`aeat.adapters.outbound.aeat.auth._session_store.PersistedBrowserSession`
metadata mapping after capturing Playwright storage state. Resume paths use
the metadata to validate the storage-state fingerprint, idle deadline,
certificate thumbprint, and certificate subject before rebuilding the session.

The reason-code helpers reduce detailed invalidation causes to stable,
non-sensitive strings carried through :class:`AeatLoginAssertionError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG
from ._errors import AeatLoginAssertionError
from .certificate import HandshakeResult

AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 1
"""Schema version for certificate-auth :class:`PersistedSessionMetadata` records."""


class PersistedSessionMetadata(BaseModel):
    """Certificate-auth metadata stored inside the encrypted session envelope.

    The fields bind a captured Playwright storage state to the certificate
    identity that produced it. :class:`HandshakeResult` preserves the verified
    AEAT handshake details, while ``storage_state_sha256`` lets resume checks
    reject metadata that no longer matches the encrypted storage-state payload.
    """

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
    """Map a detailed persisted-session refusal reason to a non-sensitive code.

    The mapping mirrors the certificate-auth resume gates and storage-state
    parsing checks so callers can log or translate the outcome without exposing
    certificate subjects, logical storage paths, or browser-session contents.
    """
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
    """Extract the redacted persisted-session reason code from an auth error.

    Returns the explicit ``context["reason"]`` value when
    :class:`AeatLoginAssertionError` carries one, otherwise falls back to the
    generic persisted-session invalidation code.
    """
    context = getattr(error, "context", None)
    if isinstance(context, Mapping):
        reason = context.get("reason")
        if isinstance(reason, str) and reason:
            return reason
    return "invalid_persisted_session"
