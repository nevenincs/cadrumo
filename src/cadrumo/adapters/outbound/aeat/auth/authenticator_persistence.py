"""Certificate-auth persisted-session metadata and redacted diagnostics.

:class:`adapters.outbound.aeat.auth.AeatAuthenticator` writes
:class:`PersistedSessionMetadata` into the encrypted
:class:`adapters.outbound.aeat.auth.session_store.PersistedBrowserSession`
metadata mapping after capturing Playwright storage state. Resume paths use
the metadata to validate the storage-state fingerprint, idle deadline,
certificate thumbprint, and certificate subject before rebuilding the session.

The reason-code helpers reduce detailed invalidation causes to stable,
non-sensitive strings carried through :class:`AeatLoginAssertionError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG
from .....core.config import AEAT_CERTIFICATE_PROTECTED_URL, assert_canonical_protected_resource
from .....core.errors import AeatLoginAssertionError
from .....core.identity import ContentDigest
from .....core.time import validate_utc_aware

AEAT_STORAGE_STATE_SCHEMA_VERSION: Final[int] = 2
"""Schema version for certificate-auth :class:`PersistedSessionMetadata` records."""


class PersistedSessionMetadata(BaseModel):
    """Certificate-auth metadata stored inside the encrypted session envelope.

    The fields bind a captured Playwright storage state to the certificate
    identity that produced it. ``protected_resource_url`` records the sole
    successful browser proof, while ``storage_state_sha256`` lets resume checks
    reject metadata that no longer matches the encrypted storage-state payload.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[2] = AEAT_STORAGE_STATE_SCHEMA_VERSION
    certificate_thumbprint: str = Field(min_length=1)
    certificate_subject: str = Field(min_length=1)
    certificate_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: ContentDigest
    protected_resource_url: str = AEAT_CERTIFICATE_PROTECTED_URL

    @field_validator("authenticated_at", "idle_deadline")
    @classmethod
    def _instants_are_utc(cls, value: datetime) -> datetime:
        """Reject a session instant that is naive or not UTC.

        The metadata is persisted inside the encrypted session envelope as
        JSON, which preserves the offset, so the canonical contract holds at
        this boundary. Both fields are compared against the clock on resume:
        a naive value would be read as UTC and could extend or expire an idle
        deadline by the local offset.
        """
        return validate_utc_aware(value)

    @field_validator("protected_resource_url")
    @classmethod
    def _protected_resource_is_canonical(cls, value: str) -> str:
        return assert_canonical_protected_resource(value, subject="persisted certificate proof")


# Ordered (substring, reason-code) rules for persisted-session refusals. The
# declaration order is specificity order: the first substring found in the
# lowered reason wins, mirroring the original if-ladder exactly.
_REASON_CODE_RULES: Final[tuple[tuple[str, str], ...]] = (
    ("hash does not match", "storage_hash_mismatch"),
    ("past its idle deadline", "idle_deadline_expired"),
    ("different certificate thumbprint", "certificate_thumbprint_mismatch"),
    ("different certificate subject", "certificate_subject_mismatch"),
    ("different certificate nif", "certificate_nif_mismatch"),
    ("failed live verification", "live_verification_failed"),
    ("could not be resumed", "resume_failed"),
    ("storage_state missing", "storage_state_missing"),
    ("storage_state is malformed", "storage_state_malformed"),
    ("storage_state root", "storage_state_root_invalid"),
    ("cookies array", "storage_state_cookies_missing"),
    ("origins array", "storage_state_origins_missing"),
    ("metadata is malformed", "metadata_malformed"),
    ("schema version", "schema_version_unsupported"),
)


def persisted_session_reason_code(reason: str) -> str:
    """Map a detailed persisted-session refusal reason to a non-sensitive code.

    The mapping mirrors the certificate-auth resume gates and storage-state
    parsing checks so callers can log or translate the outcome without exposing
    certificate subjects, logical storage paths, or browser-session contents.
    """
    reason_lower = reason.lower()
    for needle, code in _REASON_CODE_RULES:
        if needle in reason_lower:
            return code
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


__all__ = [
    "PersistedSessionMetadata",
    "persisted_session_reason_code",
    "persisted_session_reason_from_error",
]

