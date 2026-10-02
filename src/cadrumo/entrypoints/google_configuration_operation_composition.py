"""Compose the existing Google configuration owners for an immutable worker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from ..adapters.outbound.google import errors as google_errors
from ..adapters.outbound.google.errors import (
    GoogleAuthClientNotRegisteredError,
    GoogleAuthError,
    GoogleAuthExpiredError,
)
from ..adapters.outbound.google.google_configuration_inputs import (
    decode_google_client_json,
    google_credential_source_selection,
)
from ..adapters.outbound.google.google_configuration_refusal import GOOGLE_CONFIGURATION_ERROR_TYPES
from ..adapters.outbound.google.impersonation import GoogleCredentialSourceSelection
from ..adapters.outbound.google.oauth_flow import require_resolvable_profile_record, run_login_flow
from ..adapters.outbound.google.records import DriveConfig
from ..adapters.outbound.google.session_store import (
    delete_session,
    load_client,
    load_credential_source_selection,
    load_drive_config,
    load_metadata,
    save_client,
    save_credential_source_selection,
    save_drive_config,
    save_metadata,
    save_token,
)
from ..adapters.outbound.storage.errors import OutboundStorageError
from ..adapters.outbound.storage.factory import get_storage_provider
from ..application.operator_actions.projection import PreconditionVerdictSnapshot
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.capabilities import resolve_capability
from ..application.user_profile.capsule_record import ProfileRecordStore
from ..application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationExportDisabledError,
    GoogleConfigurationProjection,
    GoogleConfigurationRequest,
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ..application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
    GoogleConfigurationOperationPorts,
)
from ..application.user_profile.google_configuration_operation_refusal import (
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
    GoogleConfigurationRefusedError,
)
from ..application.user_profile.profile_record_repository import require_profile_record_session
from ..core.bucket_pointer import require_active_bucket_id
from ..core.capabilities import ServiceCapability
from ..core.config import load_settings
from ..core.google_credential_source import GoogleCredentialSourceKind
from ..core.hashing import sha256_hex
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


class _SelectionFields(TypedDict):
    profile_id: UUID
    kind: GoogleCredentialSourceKind
    target_principal: str | None
    target_scopes: tuple[str, ...]
    delegates: tuple[str, ...]
    subject: str | None
    lifetime_s: int | None


@dataclass(slots=True)
class _LocalFacts:
    audience: str | None = None
    target_principal: str | None = None
    vault_folder_name: str | None = None


def _closed_refusal(
    error: GoogleAuthError | OutboundStorageError | GoogleConfigurationExportDisabledError,
    request: GoogleConfigurationRequest,
    local: _LocalFacts,
    secret: memoryview | None,
) -> GoogleConfigurationRefusalProjection | None:
    if type(error) not in GOOGLE_CONFIGURATION_ERROR_TYPES:
        return None
    key = error.translated_message or error.code.message_key
    facts = GoogleConfigurationPresentationFacts(profile=request.profile_id)
    updates: dict[str, object] = {}
    if isinstance(request, GoogleRegisterRequest) and key.startswith("cli.config.google.detail.client_json_"):
        updates["path"] = request.client_json_path
        if key.endswith("unreadable"):
            updates["error_type"] = "UnicodeDecodeError"
        elif key.endswith("schema_invalid"):
            updates["error_type"] = "ValidationError"
        elif key.endswith("invalid"):
            updates["error_type"] = (
                "SourceDigestMismatch"
                if secret is not None and sha256_hex(bytes(secret)) != request.client_json_sha256
                else "JSONDecodeError"
            )
    if isinstance(request, GoogleCredentialSourceSetRequest):
        updates["kind"] = request.kind.value
        if key.endswith("impersonation_config_invalid"):
            updates["error_type"] = "ValidationError"
    if local.target_principal is not None:
        updates["target_principal"] = local.target_principal
    if local.vault_folder_name is not None and key.endswith("former_vault_folder"):
        updates["vault_folder_name"] = local.vault_folder_name
    if local.audience is not None and (
        key.startswith("adapters.google.oauth_flow.errors.id_token") or key.endswith("email_claim_missing")
    ):
        updates["audience"] = local.audience
    verdict = (
        error.terminal_precondition_verdict if isinstance(error, (GoogleAuthError, OutboundStorageError)) else None
    )
    if key.endswith("profile_state_unresolved") and verdict is not None:
        if verdict.failed_condition_id == "google.auth.profile_identity.resolved":
            updates["reason"] = "profile_bucket_pointer_missing"
        elif verdict.failed_condition_id == "google.auth.profile_record_session.available":
            updates["bucket_id"] = request.profile_id
            updates["reason"] = "profile_record_session_unavailable"
    if key.endswith("non_interactive"):
        updates["reason"] = "stdin_not_tty"
    if key.endswith("google_auth_import_failed"):
        updates["dependency"] = "google-auth"
    if key.endswith("scope_missing"):
        if not isinstance(error, google_errors.GoogleAuthScopeInsufficientError) or error.scope_failure is None:
            return None
        updates["missing_scopes"] = error.scope_failure.missing_scopes
        updates["account_email"] = error.scope_failure.account_email
    facts = GoogleConfigurationPresentationFacts.model_validate(
        {**facts.model_dump(mode="python"), **updates}, strict=True
    )
    try:
        return GoogleConfigurationRefusalProjection.model_validate(
            {
                "profile_id": request.profile_id,
                "provider_code": error.code.code,
                "message_key": key,
                "facts": facts,
                "verdict": PreconditionVerdictSnapshot.from_verdict(verdict) if verdict is not None else None,
            },
            strict=True,
        )
    except ValueError:
        # An unrecognized canonical producer retains its original coded failure.
        return None


def _selection_fields(profile_id: UUID, selection: GoogleCredentialSourceSelection) -> _SelectionFields:
    impersonation = selection.impersonation
    return {
        "profile_id": profile_id,
        "kind": selection.kind,
        "target_principal": impersonation.target_principal if impersonation is not None else None,
        "target_scopes": impersonation.target_scopes if impersonation is not None else (),
        "delegates": impersonation.delegates if impersonation is not None else (),
        "subject": impersonation.subject if impersonation is not None else None,
        "lifetime_s": impersonation.lifetime_s if impersonation is not None else None,
    }


def build_google_configuration_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> GoogleConfigurationOperationPorts:
    """Bind canonical persistence and provider flows; acquire no credentials here."""
    profile = str(profile_id)

    def require_profile() -> None:
        if require_active_bucket_id() != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    require_profile()

    def prepare_consent() -> None:
        require_profile()
        request = GoogleLoginRequest(profile_id=profile_id)
        try:
            if load_client(profile) is None:
                raise GoogleAuthClientNotRegisteredError(
                    translated_message="cli.config.google.detail.client_unregistered", context={"profile": profile}
                )
            require_resolvable_profile_record(profile, operation=operation)
        except GoogleAuthError as error:
            refusal = _closed_refusal(error, request, _LocalFacts(), None)
            if refusal is None:
                raise
            raise GoogleConfigurationRefusedError(refusal) from None

    def dispatch(
        request: GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
        local: _LocalFacts,
    ) -> GoogleConfigurationProjection:
        require_profile()
        if request.profile_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if isinstance(request, GoogleCredentialSourceSetRequest):
            selected_source = google_credential_source_selection(
                kind=request.kind,
                target_principal=request.target_principal,
                scopes=request.scopes,
                delegates=request.delegates,
                subject=request.subject,
                lifetime_seconds=request.lifetime_seconds,
            )
            commit(lambda: save_credential_source_selection(profile, selected_source), changed=lambda _result: True)
            return GoogleCredentialSourceSetProjection(**_selection_fields(profile_id, selected_source))
        if isinstance(request, GoogleCredentialSourceViewRequest):
            selection = load_credential_source_selection(profile)
            return GoogleCredentialSourceViewProjection(
                **_selection_fields(
                    profile_id, selection if selection is not None else GoogleCredentialSourceSelection()
                ),
                configured=selection is not None,
            )
        if isinstance(request, GoogleFolderSetRequest):
            selected_folder = DriveConfig(root_folder_id=request.folder_id.strip())
            commit(lambda: save_drive_config(profile, selected_folder), changed=lambda _result: True)
            return GoogleFolderSetProjection(profile_id=profile_id, root_folder_id=selected_folder.root_folder_id)
        if isinstance(request, GoogleFolderViewRequest):
            config = load_drive_config(profile)
            return GoogleFolderViewProjection(
                profile_id=profile_id,
                configured=config is not None,
                root_folder_id=config.root_folder_id if config is not None else None,
            )
        if isinstance(request, GoogleRegisterRequest):
            if secret is None:
                raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
            registered_client = decode_google_client_json(
                secret, source=Path(request.client_json_path), expected_sha256=request.client_json_sha256
            )
            commit(lambda: save_client(profile, registered_client), changed=lambda _result: True)
            return GoogleRegisterProjection(
                profile_id=profile_id, client_id=registered_client.client_id, project_id=registered_client.project_id
            )
        if isinstance(request, GoogleLoginRequest):
            # The terminal callback validates the consumed exact proposal before
            # any browser launch. Credential acquisition receives fresh admission.
            if not request.refresh_only:
                if terminal_admission is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
                terminal_admission()
            before_handoff("google.oauth-client-acquisition")
            client = load_client(profile)
            acknowledged("google.oauth-client-acquisition")
            if client is None:
                raise GoogleAuthClientNotRegisteredError(
                    translated_message="cli.config.google.detail.client_unregistered", context={"profile": profile}
                )
            local.audience = client.client_id
            if request.refresh_only:
                metadata = load_metadata(profile)
                if metadata is None:
                    raise GoogleAuthExpiredError(
                        translated_message="cli.config.google.detail.no_metadata_for_refresh",
                        context={"profile": profile},
                    )
                return GoogleLoginProjection(
                    profile_id=profile_id, mode="refresh-only", account_email=metadata.account_email
                )
            consent_token, consent_metadata = run_login_flow(
                client,
                profile,
                operation=operation,
                terminal_admission=terminal_admission,
                before_handoff=before_handoff,
                acknowledged=acknowledged,
            )
            commit(lambda: save_token(profile, consent_token), changed=lambda _result: True)
            commit(lambda: save_metadata(profile, consent_metadata), changed=lambda _result: True)
            return GoogleLoginProjection(
                profile_id=profile_id,
                mode="consent",
                account_email=consent_metadata.account_email,
                granted_scopes=consent_metadata.granted_scopes,
            )
        if isinstance(request, GoogleLogoutRequest):
            token_removed, metadata_removed = commit(lambda: delete_session(profile), changed=lambda flags: any(flags))
            return GoogleLogoutProjection(
                profile_id=profile_id, token_removed=token_removed, metadata_removed=metadata_removed
            )
        if isinstance(request, GoogleStatusRequest):
            client = load_client(profile)
            metadata = load_metadata(profile)
            return GoogleStatusProjection(
                profile_id=profile_id,
                client_registered=client is not None,
                client_id=client.client_id if client is not None else None,
                session_present=metadata is not None,
                account_email=metadata.account_email if metadata is not None else None,
                granted_scopes=metadata.granted_scopes if metadata is not None else (),
                issued_at=metadata.issued_at.isoformat() if metadata is not None else None,
                last_refresh_at=metadata.last_refresh_at.isoformat() if metadata is not None else None,
                reauth_required=metadata.reauth_required if metadata is not None else None,
            )
        if isinstance(request, GoogleProbeRequest):
            settings = load_settings().model_copy(update={"cadrumo_storage_provider_kind": "google_drive"})
            local.vault_folder_name = settings.cadrumo_google_drive_vault_folder_name.strip()
            if not request.read_only:
                session = require_profile_record_session(
                    profile_id, profile_decode_context=operation.profile_decode_context()
                )
                record = ProfileRecordStore(session=session).load().record
                if not resolve_capability(
                    ServiceCapability.GOOGLE_EXPORT, profile_record=record, settings=settings
                ).enabled:
                    raise GoogleConfigurationExportDisabledError(
                        translated_message="cli.config.google.export_capability_disabled"
                    )
            selection = load_credential_source_selection(profile)
            if selection is not None and selection.impersonation is not None:
                local.target_principal = selection.impersonation.target_principal
            provider = get_storage_provider(
                settings=settings, profile=profile, before_handoff=before_handoff, acknowledged=acknowledged
            )
            report = provider.probe(read_only=request.read_only)
            return GoogleProbeProjection(
                profile_id=profile_id,
                reachable=report.reachable,
                writable=report.writable,
                read_only=report.read_only,
                root_folder_present=report.root_folder_present,
                root_folder_id=getattr(provider, "root_folder_id", ""),
                detail=report.detail,
            )
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def run(
        request: GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> GoogleConfigurationProjection:
        local = _LocalFacts()
        try:
            return dispatch(
                request,
                secret=secret,
                commit=commit,
                before_handoff=before_handoff,
                acknowledged=acknowledged,
                terminal_admission=terminal_admission,
                local=local,
            )
        except (GoogleAuthError, OutboundStorageError, GoogleConfigurationExportDisabledError) as error:
            refusal = _closed_refusal(error, request, local, secret)
            if refusal is None:
                raise
            raise GoogleConfigurationRefusedError(refusal) from None

    return GoogleConfigurationOperationPorts(
        profile_id=profile_id, operation=operation, run=run, prepare_consent=prepare_consent
    )


__all__ = ["build_google_configuration_operation_ports"]
