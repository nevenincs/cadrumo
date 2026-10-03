"""Closed human Google configuration requests, results and consent proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError
from ...core.google_credential_source import GoogleCredentialSourceKind
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.interactions import OperationResponseIntentValue
from ..operations.models import OperationIdentity, OperationRevision
from ..operations.registry import OperationSchemaBindingV1
from .google_configuration_operation_refusal import GoogleConfigurationRefusalProjection

GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID = "config.google.credential-source.set"
GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID = "config.google.credential-source.view"
GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID = "config.google.folder.set"
GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID = "config.google.folder.view"
GOOGLE_LOGIN_OPERATION_DEFINITION_ID = "config.google.login"
GOOGLE_LOGOUT_OPERATION_DEFINITION_ID = "config.google.logout"
GOOGLE_PROBE_OPERATION_DEFINITION_ID = "config.google.probe"
GOOGLE_REGISTER_OPERATION_DEFINITION_ID = "config.google.register"
GOOGLE_STATUS_OPERATION_DEFINITION_ID = "config.google.status"
GOOGLE_REGISTER_INPUT_KIND = "google.oauth-client-json"
GOOGLE_CONSENT_PRESENTATION_CODE = "google.consent.terminal-required"
GOOGLE_CONFIGURATION_EXPORT_DISABLED_CODE = "REFUSED_GOOGLE_CONFIGURATION_EXPORT_DISABLED"
_Text = Annotated[str, Field(max_length=65_536)]
_Input = Annotated[str, Field(max_length=16_384)]


class GoogleConfigurationExportDisabledError(CadrumoError):
    """Canonical Google-export capability refusal for the write-enabled probe."""


class GoogleProfileRequest(BaseModel):
    """Immutable target; never inferred from an ambient profile selection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class GoogleCredentialSourceSetRequest(GoogleProfileRequest):
    """Original options, validated by the existing credential-source constructor."""

    kind: GoogleCredentialSourceKind
    target_principal: _Input | None = None
    scopes: tuple[_Input, ...] = ()
    delegates: tuple[_Input, ...] = ()
    subject: _Input | None = None
    lifetime_seconds: int | None = None


class GoogleCredentialSourceViewRequest(GoogleProfileRequest):
    """Read persisted selection with the canonical OAuth Desktop default."""


class GoogleFolderSetRequest(GoogleProfileRequest):
    """Original root-folder text, retaining canonical whitespace normalization."""

    folder_id: _Input


class GoogleFolderViewRequest(GoogleProfileRequest):
    """Read persisted root-folder configuration."""


class GoogleLoginRequest(GoogleProfileRequest):
    """Consent or the current metadata-only refresh inspection."""

    refresh_only: bool = False


class GoogleLogoutRequest(GoogleProfileRequest):
    """Delete the session while preserving client and folder configuration."""


class GoogleProbeRequest(GoogleProfileRequest):
    """Run the canonical provider probe with its existing sentinel election."""

    read_only: bool = False


class GoogleRegisterRequest(GoogleProfileRequest):
    """Source provenance and digest; JSON bytes use the protected secret channel."""

    client_json_path: Annotated[str, Field(min_length=1, max_length=4096)]
    client_json_sha256: ContentDigest

    @model_validator(mode="after")
    def _absolute_source(self) -> Self:
        if not Path(self.client_json_path).is_absolute():
            raise ValueError("Google client JSON source must be absolute")
        return self


class GoogleStatusRequest(GoogleProfileRequest):
    """Inspect registered client and non-secret session metadata."""


type GoogleConfigurationRequest = (
    GoogleCredentialSourceSetRequest
    | GoogleCredentialSourceViewRequest
    | GoogleFolderSetRequest
    | GoogleFolderViewRequest
    | GoogleLoginRequest
    | GoogleLogoutRequest
    | GoogleProbeRequest
    | GoogleRegisterRequest
    | GoogleStatusRequest
)


class GoogleCredentialSourceProjection(BaseModel):
    """Complete non-secret source configuration used by the existing human output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: GoogleCredentialSourceKind
    target_principal: _Text | None = None
    target_scopes: tuple[_Text, ...] = ()
    delegates: tuple[_Text, ...] = ()
    subject: _Text | None = None
    lifetime_s: int | None = None


class GoogleCredentialSourceSetProjection(GoogleCredentialSourceProjection):
    """Saved selection without ADC discovery or token exchange."""


class GoogleCredentialSourceViewProjection(GoogleCredentialSourceProjection):
    """Persisted/default selection plus its configuration-presence fact."""

    configured: bool


class GoogleFolderSetProjection(BaseModel):
    """Acknowledged canonical root-folder configuration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    root_folder_id: _Text


class GoogleFolderViewProjection(BaseModel):
    """Persisted root-folder presence and complete orientation value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    configured: bool
    root_folder_id: _Text | None = None


class GoogleLoginProjection(BaseModel):
    """Canonical linked account and scopes; tokens have no public field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    mode: Literal["consent", "refresh-only"]
    account_email: _Text
    granted_scopes: tuple[_Text, ...] = ()


class GoogleLogoutProjection(BaseModel):
    """Actual atomic deletion acknowledgement, including idempotent absence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    token_removed: bool
    metadata_removed: bool
    client_preserved: Literal[True] = True


class GoogleProbeProjection(BaseModel):
    """Complete current probe report with the provider's resolved root folder."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    provider_kind: Literal["google_drive"] = "google_drive"
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    root_folder_id: _Text
    detail: _Text = ""


class GoogleRegisterProjection(BaseModel):
    """Only the client/project orientation fields from the registered secret."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    client_id: _Text
    project_id: _Text


class GoogleStatusProjection(BaseModel):
    """Whole current client/session inspection without credential material."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    client_registered: bool
    client_id: _Text | None = None
    session_present: bool
    account_email: _Text | None = None
    granted_scopes: tuple[_Text, ...] = ()
    issued_at: _Text | None = None
    last_refresh_at: _Text | None = None
    reauth_required: bool | None = None


type GoogleConfigurationProjection = (
    GoogleCredentialSourceSetProjection
    | GoogleCredentialSourceViewProjection
    | GoogleFolderSetProjection
    | GoogleFolderViewProjection
    | GoogleLoginProjection
    | GoogleLogoutProjection
    | GoogleProbeProjection
    | GoogleRegisterProjection
    | GoogleStatusProjection
)


class GoogleConfigurationOutcome(BaseModel):
    """One complete success or original-provider refusal for the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    outcome: Literal["succeeded", "refused"]
    result: GoogleConfigurationProjection | None = None
    refusal: GoogleConfigurationRefusalProjection | None = None

    @model_validator(mode="after")
    def _one_outcome(self) -> Self:
        if self.outcome == "succeeded":
            if self.result is None or self.refusal is not None or self.result.profile_id != self.profile_id:
                raise ValueError("Google success requires its exact complete profile result")
        elif self.refusal is None or self.result is not None or self.refusal.profile_id != self.profile_id:
            raise ValueError("Google refusal requires its exact closed profile detail")
        return self


GOOGLE_CONFIGURATION_CONTRACTS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID: (
        GoogleCredentialSourceSetRequest,
        GoogleCredentialSourceSetProjection,
    ),
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID: (
        GoogleCredentialSourceViewRequest,
        GoogleCredentialSourceViewProjection,
    ),
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID: (GoogleFolderSetRequest, GoogleFolderSetProjection),
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID: (GoogleFolderViewRequest, GoogleFolderViewProjection),
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID: (GoogleLoginRequest, GoogleLoginProjection),
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID: (GoogleLogoutRequest, GoogleLogoutProjection),
    GOOGLE_PROBE_OPERATION_DEFINITION_ID: (GoogleProbeRequest, GoogleProbeProjection),
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID: (GoogleRegisterRequest, GoogleRegisterProjection),
    GOOGLE_STATUS_OPERATION_DEFINITION_ID: (GoogleStatusRequest, GoogleStatusProjection),
}
GOOGLE_CONFIGURATION_REQUEST_TYPES = (
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetRequest,
    GoogleFolderViewRequest,
    GoogleLoginRequest,
    GoogleLogoutRequest,
    GoogleProbeRequest,
    GoogleRegisterRequest,
    GoogleStatusRequest,
)


class GoogleConfigurationExecutionResult(BaseModel):
    """Encrypted complete result bound to the actual invocation and effect."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    projection: GoogleConfigurationOutcome
    effect: Literal["none", "updated", "partial", "unknown"]


class GoogleConsentProposal(BaseModel):
    """Exact revision and request whose human terminal presence is acknowledged."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    revision: OperationRevision
    request: GoogleLoginRequest

    @property
    def digest(self) -> ContentDigest:
        """Bind acknowledgement to the complete immutable proposal."""
        from ...core.hashing import content_hash_hex

        return content_hash_hex(self.model_dump(mode="json"))


class GoogleConsentReviewProjection(BaseModel):
    """Credential-free facts inspected by the human terminal before consent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    revision: OperationRevision
    profile_id: UUID
    reviewed_proposal_digest: ContentDigest


class GoogleConsentResponse(BaseModel):
    """Decision only; authority is bound by the runtime's revision/control token."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    response_version: Literal[1] = 1
    intent: OperationResponseIntentValue


GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".review",
    schema_version=1,
    model_type=GoogleConsentReviewProjection,
)
GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_LOGIN_OPERATION_DEFINITION_ID + ".response",
    schema_version=1,
    model_type=GoogleConsentResponse,
)


__all__ = [
    "GOOGLE_CONFIGURATION_CONTRACTS",
    "GOOGLE_CONFIGURATION_EXPORT_DISABLED_CODE",
    "GOOGLE_CONFIGURATION_REQUEST_TYPES",
    "GOOGLE_CONSENT_PRESENTATION_CODE",
    "GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING",
    "GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING",
    "GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID",
    "GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID",
    "GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID",
    "GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID",
    "GOOGLE_LOGIN_OPERATION_DEFINITION_ID",
    "GOOGLE_LOGOUT_OPERATION_DEFINITION_ID",
    "GOOGLE_PROBE_OPERATION_DEFINITION_ID",
    "GOOGLE_REGISTER_INPUT_KIND",
    "GOOGLE_REGISTER_OPERATION_DEFINITION_ID",
    "GOOGLE_STATUS_OPERATION_DEFINITION_ID",
    "GoogleConfigurationExecutionResult",
    "GoogleConfigurationExportDisabledError",
    "GoogleConfigurationOutcome",
    "GoogleConfigurationProjection",
    "GoogleConfigurationRequest",
    "GoogleConsentProposal",
    "GoogleConsentResponse",
    "GoogleConsentReviewProjection",
    "GoogleCredentialSourceProjection",
    "GoogleCredentialSourceSetProjection",
    "GoogleCredentialSourceSetRequest",
    "GoogleCredentialSourceViewProjection",
    "GoogleCredentialSourceViewRequest",
    "GoogleFolderSetProjection",
    "GoogleFolderSetRequest",
    "GoogleFolderViewProjection",
    "GoogleFolderViewRequest",
    "GoogleLoginProjection",
    "GoogleLoginRequest",
    "GoogleLogoutProjection",
    "GoogleLogoutRequest",
    "GoogleProbeProjection",
    "GoogleProbeRequest",
    "GoogleProfileRequest",
    "GoogleRegisterProjection",
    "GoogleRegisterRequest",
    "GoogleStatusProjection",
    "GoogleStatusRequest",
]
