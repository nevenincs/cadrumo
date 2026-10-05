"""Closed Google configuration refusals retained in encrypted operation results."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.error_codes import get_registered_error_code_by_code
from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operator_actions.projection import PreconditionVerdictSnapshot

GOOGLE_CONFIGURATION_REFUSAL_CODE = "REFUSED_GOOGLE_CONFIGURATION"

type GoogleConfigurationProviderCode = Literal[
    "AUTH_GOOGLE",
    "REFUSED_GOOGLE_VALIDATION",
    "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE",
    "AUTH_GOOGLE_CLIENT_REVOKED",
    "REFUSED_GOOGLE_SIGN_IN_REQUIRED",
    "AUTH_GOOGLE_SCOPE_INSUFFICIENT",
    "FAIL_GOOGLE_NETWORK",
    "FAIL_GOOGLE_LOOPBACK_BIND",
    "FAIL_GOOGLE_BROWSER_OPEN",
    "REFUSED_GOOGLE_NON_INTERACTIVE",
    "LOCKED_GOOGLE_KEYCHAIN",
    "REFUSED_GOOGLE_PROFILE_UNBOUND",
    "REFUSED_OUTBOUND_STORAGE_VALIDATION",
    "AUTH_OUTBOUND_STORAGE_PERMISSION",
    "FAIL_OUTBOUND_STORAGE_UNAVAILABLE",
    "FAIL_OUTBOUND_STORAGE",
    "ERROR_OUTBOUND_STORAGE_NOT_FOUND",
    "REFUSED_OUTBOUND_STORAGE_CONFLICT",
    "ERROR_OUTBOUND_STORAGE_PATH_TOO_LONG",
    "REFUSED_OUTBOUND_STORAGE_QUOTA",
    "FAIL_OUTBOUND_STORAGE_NETWORK",
    "INTEGRITY_OUTBOUND_STORAGE",
    "REFUSED_GOOGLE_CONFIGURATION_EXPORT_DISABLED",
]

type GoogleConfigurationMessageKey = Literal[
    "errors.auth.auth_google",
    "errors.refused.refused_google_validation",
    "errors.refused.refused_google_client_metadata_unavailable",
    "errors.auth.auth_google_client_revoked",
    "errors.refused.refused_google_sign_in_required",
    "errors.auth.auth_google_scope_insufficient",
    "errors.fail.fail_google_network",
    "errors.fail.fail_google_loopback_bind",
    "errors.fail.fail_google_browser_open",
    "errors.refused.refused_google_non_interactive",
    "errors.locked.locked_google_keychain",
    "errors.refused.refused_google_profile_unbound",
    "errors.refused.refused_outbound_storage_validation",
    "errors.auth.auth_outbound_storage_permission",
    "errors.fail.fail_outbound_storage_unavailable",
    "cli.config.google.export_capability_disabled",
    "errors.fail.fail_outbound_storage",
    "errors.error.error_outbound_storage_not_found",
    "errors.refused.refused_outbound_storage_conflict",
    "errors.error.error_outbound_storage_path_too_long",
    "errors.refused.refused_outbound_storage_quota",
    "errors.fail.fail_outbound_storage_network",
    "errors.integrity.integrity_outbound_storage",
    "adapters.google.installation_client.errors.client_metadata_invalid",
    "adapters.google.oauth_flow.errors.non_interactive",
    "adapters.google.oauth_flow.errors.profile_state_unresolved",
    "adapters.google.oauth_flow.errors.scope_missing",
    "adapters.google.oauth_flow.errors.refresh_token_missing",
    "adapters.google.oauth_flow.errors.oauthlib_not_importable",
    "adapters.google.oauth_flow.errors.client_config_refused",
    "adapters.google.oauth_flow.errors.loopback_bind_failed",
    "adapters.google.oauth_flow.errors.browser_launcher_refused",
    "adapters.google.oauth_flow.errors.endpoint_unreachable",
    "adapters.google.oauth_flow.errors.id_token_missing",
    "adapters.google.oauth_flow.errors.id_token_module_not_importable",
    "adapters.google.oauth_flow.errors.id_token_verification_failed",
    "adapters.google.oauth_flow.errors.email_claim_missing",
    "adapters.outbound.storage._factory.errors.google_token_missing",
    "adapters.outbound.storage._factory.errors.google_auth_import_failed",
    "adapters.outbound.storage._factory.errors.drive_root_missing",
    "adapters.outbound.storage.google_drive.errors.root_folder_id_blank",
    "adapters.outbound.storage.google_drive.errors.vault_folder_name_blank",
    "adapters.outbound.storage.google_drive.errors.former_vault_folder",
]

_Text = Annotated[str, Field(max_length=65_536)]

_DYNAMIC_CODES: dict[str, frozenset[str]] = {
    "adapters.google.installation_client.errors.client_metadata_invalid": frozenset(
        {"REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"}
    ),
    "adapters.google.oauth_flow.errors.non_interactive": frozenset({"REFUSED_GOOGLE_NON_INTERACTIVE"}),
    "adapters.google.oauth_flow.errors.refresh_token_missing": frozenset({"REFUSED_GOOGLE_VALIDATION"}),
    "adapters.google.oauth_flow.errors.profile_state_unresolved": frozenset({"REFUSED_GOOGLE_PROFILE_UNBOUND"}),
    **{
        f"adapters.google.oauth_flow.errors.{key}": frozenset({"AUTH_GOOGLE_SCOPE_INSUFFICIENT"})
        for key in (
            "scope_missing",
            "id_token_missing",
            "email_claim_missing",
        )
    },
    **{
        f"adapters.google.oauth_flow.errors.{key}": frozenset({"FAIL_GOOGLE_NETWORK"})
        for key in (
            "oauthlib_not_importable",
            "client_config_refused",
            "endpoint_unreachable",
            "id_token_module_not_importable",
            "id_token_verification_failed",
        )
    },
    "adapters.google.oauth_flow.errors.loopback_bind_failed": frozenset({"FAIL_GOOGLE_LOOPBACK_BIND"}),
    "adapters.google.oauth_flow.errors.browser_launcher_refused": frozenset({"FAIL_GOOGLE_BROWSER_OPEN"}),
    **{
        f"adapters.outbound.storage._factory.errors.{key}": frozenset({"REFUSED_OUTBOUND_STORAGE_VALIDATION"})
        for key in (
            "google_token_missing",
            "drive_root_missing",
        )
    },
    "adapters.outbound.storage._factory.errors.google_auth_import_failed": frozenset({"FAIL_OUTBOUND_STORAGE"}),
    **{
        f"adapters.outbound.storage.google_drive.errors.{key}": frozenset({"REFUSED_OUTBOUND_STORAGE_VALIDATION"})
        for key in (
            "root_folder_id_blank",
            "vault_folder_name_blank",
            "former_vault_folder",
        )
    },
}


class GoogleConfigurationPresentationFacts(BaseModel):
    """Known interpolation fields copied only from typed requests and owning local facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile: UUID
    vault_folder_name: _Text | None = None
    audience: _Text | None = None
    dependency: Literal["google-auth"] | None = None
    missing_scopes: Annotated[tuple[_Text, ...], Field(max_length=64)] = ()
    account_email: _Text | None = None
    bucket_id: UUID | None = None
    reason: Literal["stdin_not_tty", "profile_bucket_pointer_missing", "profile_record_session_unavailable"] | None = (
        None
    )

    def presentation_context(self) -> dict[str, object]:
        """Restore only the closed original interpolation names from validated fields."""
        values: dict[str, object] = {"profile": str(self.profile)}
        for field in (
            "vault_folder_name",
            "audience",
            "dependency",
            "account_email",
            "reason",
        ):
            value = getattr(self, field)
            if value is not None:
                values[field] = value
        if self.bucket_id is not None:
            values["bucket_id"] = str(self.bucket_id)
        if self.missing_scopes:
            values["missing_scopes"] = list(self.missing_scopes)
        return values


class GoogleConfigurationRefusalProjection(BaseModel):
    """Original declared human failure and lossless canonical action evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    provider_code: GoogleConfigurationProviderCode
    message_key: GoogleConfigurationMessageKey
    facts: GoogleConfigurationPresentationFacts
    verdict: PreconditionVerdictSnapshot | None = None

    @model_validator(mode="after")
    def _same_profile(self) -> Self:
        if self.facts.profile != self.profile_id:
            raise ValueError("Google refusal facts belong to a different profile")
        descriptor = get_registered_error_code_by_code(self.provider_code)
        if self.message_key != descriptor.message_key and self.provider_code not in _DYNAMIC_CODES.get(
            self.message_key, frozenset()
        ):
            raise ValueError("Google refusal message is not declared for its original code")
        return self


class GoogleConfigurationRefusedError(CadrumoError):
    """Registered REFUSED carrier for encrypted original-provider detail."""

    def __init__(self, projection: GoogleConfigurationRefusalProjection) -> None:
        """Keep only the strict immutable projection from recognized canonical producers."""
        self._projection = GoogleConfigurationRefusalProjection.model_validate(
            projection.model_dump(mode="python"), strict=True
        )
        super().__init__()

    @property
    def projection(self) -> GoogleConfigurationRefusalProjection:
        """Expose only the immutable validated owning-provider refusal facts."""
        return self._projection


__all__ = [
    "GOOGLE_CONFIGURATION_REFUSAL_CODE",
    "GoogleConfigurationMessageKey",
    "GoogleConfigurationPresentationFacts",
    "GoogleConfigurationProviderCode",
    "GoogleConfigurationRefusalProjection",
    "GoogleConfigurationRefusedError",
]
