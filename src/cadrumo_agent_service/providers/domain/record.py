"""The strict, versioned per-provider settings record.

One record per provider per profile. It carries two independent axes:

* ``assistant_auth`` -- how the assistant authenticates with this provider:
  the stored direct credential, the provider's own CLI sign-in, or not at all.
* ``credential_state`` -- whether a direct credential is stored, deliberately
  removed (``disabled``), or not set.

Choosing provider sign-in for the assistant never erases a stored key, because
extraction always needs a direct key. An absent record means "unset" on both
axes; that state is never persisted.

The secret travels as :class:`~pydantic.SecretStr`. Every ordinary dump, repr
and string rendering masks it. Only :func:`provider_settings_record_document`
reveals it, for the one caller that encrypts the record at rest.

A separate per-profile record, kept in a record capability of its own, holds
the person's model choice per role: a lane and a model for each role they
configured. It holds no secret, and a role it does not name has no selection.
"""

from __future__ import annotations

import json
import secrets
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    FieldSerializationInfo,
    SecretStr,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from cadrumo.core.errors.hierarchy import pydantic_validation_boundary
from cadrumo.core.hex import Hex64Str
from cadrumo.core.model_roles import ModelRole
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG as _STRICT_FROZEN_HIDDEN_INPUT
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.model_runs import MODEL_RUN_MODEL_ID_PATTERN

from .catalog import BASE_URL_MAX_LENGTH, LaneId, validate_https_base_url

PROVIDER_SETTINGS_RECORD_SCHEMA_VERSION: Final[Literal[1]] = 1
CREDENTIAL_SECRET_MIN_LENGTH: Final[int] = 8
CREDENTIAL_SECRET_MAX_LENGTH: Final[int] = 4096

_MASK_CHARACTERS: Final[frozenset[str]] = frozenset("*•●…")
"""Characters a masked display uses; a value containing one is never a new secret."""

_REVEAL: Final[object] = object()
"""Serialization context token that alone makes a record dump its secret."""


class AssistantAuth(StrEnum):
    """How the assistant authenticates with one provider."""

    DIRECT_API = "direct_api"
    PROVIDER_SIGN_IN = "provider_sign_in"
    DISABLED = "disabled"


class CredentialState(StrEnum):
    """Whether a direct credential is stored for one provider."""

    UNSET = "unset"
    CONFIGURED = "configured"
    DISABLED = "disabled"


class CredentialKind(StrEnum):
    """The kind of direct credential material stored."""

    API_KEY = "api_key"
    OAUTH = "oauth_token"


class CredentialSecretRefusal(StrEnum):
    """Why a candidate secret is not accepted as a new credential."""

    EMPTY = "empty"
    LENGTH = "length"
    WHITESPACE_OR_CONTROL = "whitespace_or_control"
    MASKED_PLACEHOLDER = "masked_placeholder"


def credential_secret_refusal(candidate: str) -> CredentialSecretRefusal | None:
    """Return why ``candidate`` cannot be stored as a credential, or ``None``.

    A key is one opaque token: no whitespace and no control characters, inside
    a sane length bound. A value carrying a masking character or an ellipsis is
    what a masked status display shows, never a real key, so it is refused
    rather than stored over the real one.
    """
    if not candidate:
        return CredentialSecretRefusal.EMPTY
    if not CREDENTIAL_SECRET_MIN_LENGTH <= len(candidate) <= CREDENTIAL_SECRET_MAX_LENGTH:
        return CredentialSecretRefusal.LENGTH
    if any(character.isspace() or not character.isprintable() for character in candidate):
        return CredentialSecretRefusal.WHITESPACE_OR_CONTROL
    if "..." in candidate or any(character in _MASK_CHARACTERS for character in candidate):
        return CredentialSecretRefusal.MASKED_PLACEHOLDER
    return None


def new_settings_generation() -> str:
    """Return a fresh opaque generation, random and never derived from a secret."""
    return secrets.token_hex(32)


class ProviderCredential(BaseModel):
    """One stored direct credential and its optional gateway URL."""

    model_config = _STRICT_FROZEN_HIDDEN_INPUT

    kind: CredentialKind
    secret: SecretStr
    base_url: str | None = Field(default=None, max_length=BASE_URL_MAX_LENGTH)

    @field_validator("secret")
    @classmethod
    @pydantic_validation_boundary
    def _secret_is_acceptable(cls, value: SecretStr) -> SecretStr:
        if credential_secret_refusal(value.get_secret_value()) is not None:
            raise ValueError("credential secret is not an acceptable opaque token")
        return value

    @field_validator("base_url")
    @classmethod
    @pydantic_validation_boundary
    def _base_url_is_https(cls, value: str | None) -> str | None:
        return None if value is None else validate_https_base_url(value)

    @field_serializer("secret")
    def _serialize_secret(self, value: SecretStr, info: FieldSerializationInfo) -> str:
        context = info.context
        if isinstance(context, dict) and "reveal" in context and context["reveal"] is _REVEAL:
            return value.get_secret_value()
        return str(value)


class ProviderPreferences(BaseModel):
    """Validated non-secret preferences; deliberately empty in schema version 1."""

    model_config = _STRICT_FROZEN


class ProviderSettingsRecord(BaseModel):
    """One profile's settings for one provider."""

    model_config = _STRICT_FROZEN_HIDDEN_INPUT

    schema_version: Literal[1]
    provider: LaneId
    assistant_auth: AssistantAuth
    credential_state: CredentialState
    credential: ProviderCredential | None = None
    preferences: ProviderPreferences = Field(default_factory=ProviderPreferences)
    generation: Hex64Str
    updated_at: UtcInstant

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _credential_matches_state(self) -> Self:
        configured = self.credential_state is CredentialState.CONFIGURED
        if configured != (self.credential is not None):
            raise ValueError("credential material is present exactly when the credential state is configured")
        return self


MODEL_ROLE_SELECTIONS_RECORD_SCHEMA_VERSION: Final[Literal[1]] = 1

ModelId = Annotated[str, StringConstraints(pattern=MODEL_RUN_MODEL_ID_PATTERN)]
"""A model id exactly as the lane's catalogue entry names it, under the catalogue's own id rule."""


class ModelRoleSelection(BaseModel):
    """The lane and model the person chose for one role; nothing here is secret."""

    model_config = _STRICT_FROZEN

    role: ModelRole
    lane: LaneId
    """The catalogue lane id, never the provider identity alone."""
    model: ModelId


class ModelRoleSelectionsRecord(BaseModel):
    """One profile's per-role model selections, at most one per role.

    A role missing from ``selections`` has no selection. Nothing stands in for
    it: there is no default, no recommended entry and no other role's choice.
    """

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    selections: tuple[ModelRoleSelection, ...] = Field(max_length=len(ModelRole))
    generation: Hex64Str
    updated_at: UtcInstant

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_selection_per_role(self) -> Self:
        roles = [selection.role for selection in self.selections]
        if len(roles) != len(set(roles)):
            raise ValueError("a role carries at most one selection")
        return self

    def selection(self, role: ModelRole) -> ModelRoleSelection | None:
        """Return the person's selection for ``role``, or ``None`` when there is none."""
        return next((selection for selection in self.selections if selection.role is role), None)


def model_role_selections_record_document(record: ModelRoleSelectionsRecord) -> bytes:
    """Return the selections record's at-rest JSON; it carries no secret."""
    document = record.model_dump(mode="json")
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_model_role_selections_record(payload: bytes) -> ModelRoleSelectionsRecord:
    """Parse at-rest JSON back into a selections record.

    Raises:
        pydantic.ValidationError: When the payload is not a valid record.
        UnicodeDecodeError: When the payload is not UTF-8.
    """
    return ModelRoleSelectionsRecord.model_validate_json(payload.decode("utf-8"))


def provider_settings_record_document(record: ProviderSettingsRecord) -> bytes:
    """Return the record's at-rest JSON, secret included, for encryption only."""
    document = record.model_dump(mode="json", context={"reveal": _REVEAL})
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_provider_settings_record(payload: bytes) -> ProviderSettingsRecord:
    """Parse at-rest JSON back into a record.

    Raises:
        pydantic.ValidationError: When the payload is not a valid record. Input
            values are hidden from the error, so the secret cannot reach it.
        UnicodeDecodeError: When the payload is not UTF-8.
    """
    return ProviderSettingsRecord.model_validate_json(payload.decode("utf-8"))


__all__ = [
    "CREDENTIAL_SECRET_MAX_LENGTH",
    "CREDENTIAL_SECRET_MIN_LENGTH",
    "MODEL_ROLE_SELECTIONS_RECORD_SCHEMA_VERSION",
    "PROVIDER_SETTINGS_RECORD_SCHEMA_VERSION",
    "AssistantAuth",
    "CredentialKind",
    "CredentialSecretRefusal",
    "CredentialState",
    "ModelId",
    "ModelRoleSelection",
    "ModelRoleSelectionsRecord",
    "ProviderCredential",
    "ProviderPreferences",
    "ProviderSettingsRecord",
    "credential_secret_refusal",
    "model_role_selections_record_document",
    "new_settings_generation",
    "parse_model_role_selections_record",
    "parse_provider_settings_record",
    "provider_settings_record_document",
]
