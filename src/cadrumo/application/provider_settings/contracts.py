"""Masked status, typed refusals and action results for provider settings.

These are the values every frontend may show. None of them carries a secret or
a fingerprint of one: a status entry names the provider, its catalog facts, the
person's chosen mode, whether a credential is available and from where, and the
row revision an action must send back as its guard. The revision hashes the
record's ciphertext, so it changes on every write and cannot confirm a guessed
key.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints

from ...core.hex import is_hex64
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.provider_settings.catalog import ProviderAuthKind, ProviderConsumer, ProviderId

ABSENT_REVISION: Final[str] = "absent"
"""The revision of a provider with no stored record, and the guard that creates one."""

ProviderSettingsRevision = Annotated[str, StringConstraints(pattern=r"^(absent|[0-9a-f]{64})$")]
"""A status revision: ``absent`` or the stored row's opaque revision."""


def is_provider_settings_revision(value: str) -> bool:
    """Return whether ``value`` is a well-formed revision token."""
    return value == ABSENT_REVISION or is_hex64(value)


class ProviderSettingsMode(StrEnum):
    """The person's chosen mode for one provider."""

    KEY = "key"
    OAUTH = "oauth_token"
    PROVIDER_SIGN_IN = "provider_sign_in"
    DISABLED = "disabled"
    UNSET = "unset"


class ProviderCredentialSource(StrEnum):
    """Where the credential a consumer would use comes from."""

    PROFILE = "profile"
    ENVIRONMENT = "environment"
    NONE = "none"


class ProviderReadiness(StrEnum):
    """How ready the provider is for use.

    ``ready`` is reserved for a credential a consumer has used successfully;
    storing a key alone never produces it.
    """

    READY = "ready"
    NOT_VERIFIED = "not_verified"
    MISSING = "missing"
    DISABLED = "disabled"
    SIGN_IN_REQUIRED = "sign_in_required"
    UNUSABLE = "unusable"


class ProviderStatusReason(StrEnum):
    """Why a provider is not usable; ``None`` when it is usable."""

    NOT_CONFIGURED = "not_configured"
    TURNED_OFF = "turned_off"
    SIGN_IN_WITH_PROVIDER_TOOL = "sign_in_with_provider_tool"
    RECORD_UNREADABLE = "record_unreadable"


class ProviderStatusEntry(BaseModel):
    """Masked status of one provider."""

    model_config = _STRICT_FROZEN

    id: ProviderId
    display_name: str
    auth_kind: ProviderAuthKind
    consumers: tuple[ProviderConsumer, ...]
    mode: ProviderSettingsMode
    available: bool
    source: ProviderCredentialSource
    readiness: ProviderReadiness
    reason: ProviderStatusReason | None
    base_url: str | None
    """The person's stored base URL only; never the catalog default."""
    default_base_url: str | None
    revision: ProviderSettingsRevision


class ProviderSettingsStatus(BaseModel):
    """Masked status of every catalogued provider, in catalog order."""

    model_config = _STRICT_FROZEN

    development: bool
    """Whether this is a development build, where an unset key may come from the environment."""
    providers: tuple[ProviderStatusEntry, ...] = Field(min_length=1)


class ProviderSettingsRefusalCode(StrEnum):
    """Closed refusal codes for every provider-settings read and change."""

    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    INVALID_KEY_FORMAT = "invalid_key_format"
    BASE_URL_REJECTED = "base_url_rejected"
    REVISION_CONFLICT = "revision_conflict"
    COMMITTED_READBACK_FAILED = "committed_readback_failed"
    PERSON_ACT_REQUIRED = "person_act_required"
    """Produced at dispatch for a frontend that may not change credentials, never by the service."""
    UNKNOWN = "unknown"


class ProviderSettingsRefusal(BaseModel):
    """A typed refusal carrying no secret and no storage detail."""

    model_config = _STRICT_FROZEN

    code: ProviderSettingsRefusalCode


class ProviderSettingsActionAccepted(BaseModel):
    """A committed action, with the provider's status read back after commit."""

    model_config = _STRICT_FROZEN

    entry: ProviderStatusEntry


type ProviderSettingsActionResult = ProviderSettingsActionAccepted | ProviderSettingsRefusal


__all__ = [
    "ABSENT_REVISION",
    "ProviderCredentialSource",
    "ProviderReadiness",
    "ProviderSettingsActionAccepted",
    "ProviderSettingsActionResult",
    "ProviderSettingsMode",
    "ProviderSettingsRefusal",
    "ProviderSettingsRefusalCode",
    "ProviderSettingsRevision",
    "ProviderSettingsStatus",
    "ProviderStatusEntry",
    "ProviderStatusReason",
    "is_provider_settings_revision",
]
