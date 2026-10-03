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
from ..application.operator_actions.models import PreconditionVerdict
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
        _append_google_client_json_refusal(request, key, secret, updates)
    _append_google_source_refusal(request, key, updates)
    _append_google_local_refusal(local, key, updates)
    verdict = (
        error.terminal_precondition_verdict if isinstance(error, (GoogleAuthError, OutboundStorageError)) else None
    )
    _append_google_profile_refusal(request, key, verdict, updates)
    if not _append_google_provider_refusal(error, key, updates):
        return None
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
            return _dispatch_google_configuration(
                request,
                profile=profile,
                profile_id=profile_id,
                operation=operation,
                require_profile=require_profile,
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


def _append_google_client_json_refusal(
    request: GoogleRegisterRequest, key: str, secret: memoryview | None, updates: dict[str, object]
) -> None:
    """Describe the supplied client file without disclosing its credential contents."""
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


def _append_google_source_refusal(request: GoogleConfigurationRequest, key: str, updates: dict[str, object]) -> None:
    """Preserve credential-source kind and its bounded schema-error classification."""
    if isinstance(request, GoogleCredentialSourceSetRequest):
        updates["kind"] = request.kind.value
        if key.endswith("impersonation_config_invalid"):
            updates["error_type"] = "ValidationError"


def _append_google_local_refusal(local: _LocalFacts, key: str, updates: dict[str, object]) -> None:
    """Copy only the local facts applicable to the current refusal producer."""
    if local.target_principal is not None:
        updates["target_principal"] = local.target_principal
    if local.vault_folder_name is not None and key.endswith("former_vault_folder"):
        updates["vault_folder_name"] = local.vault_folder_name
    if local.audience is not None and (
        key.startswith("adapters.google.oauth_flow.errors.id_token") or key.endswith("email_claim_missing")
    ):
        updates["audience"] = local.audience


def _append_google_profile_refusal(
    request: GoogleConfigurationRequest, key: str, verdict: PreconditionVerdict | None, updates: dict[str, object]
) -> None:
    """Keep pointer and record-session refusal reasons bound to their original verdict."""
    if key.endswith("profile_state_unresolved") and verdict is not None:
        if verdict.failed_condition_id == "google.auth.profile_identity.resolved":
            updates["reason"] = "profile_bucket_pointer_missing"
        elif verdict.failed_condition_id == "google.auth.profile_record_session.available":
            updates["bucket_id"] = request.profile_id
            updates["reason"] = "profile_record_session_unavailable"


def _append_google_provider_refusal(
    error: GoogleAuthError | OutboundStorageError | GoogleConfigurationExportDisabledError,
    key: str,
    updates: dict[str, object],
) -> bool:
    """Require a grounded scope failure before copying its public scope metadata."""
    if key.endswith("non_interactive"):
        updates["reason"] = "stdin_not_tty"
    if key.endswith("google_auth_import_failed"):
        updates["dependency"] = "google-auth"
    if key.endswith("scope_missing"):
        if not isinstance(error, google_errors.GoogleAuthScopeInsufficientError) or error.scope_failure is None:
            return False
        updates["missing_scopes"] = error.scope_failure.missing_scopes
        updates["account_email"] = error.scope_failure.account_email
    return True


def _dispatch_google_credential_source_set(
    request: GoogleCredentialSourceSetRequest, profile: str, profile_id: UUID, commit: GoogleConfigurationCommit
) -> GoogleCredentialSourceSetProjection:
    """Run the existing GoogleCredentialSourceSet branch in its original effect order."""
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


def _dispatch_google_credential_source_view(
    request: GoogleCredentialSourceViewRequest, profile: str, profile_id: UUID
) -> GoogleCredentialSourceViewProjection:
    """Run the existing GoogleCredentialSourceView branch in its original effect order."""
    selection = load_credential_source_selection(profile)
    return GoogleCredentialSourceViewProjection(
        **_selection_fields(profile_id, selection if selection is not None else GoogleCredentialSourceSelection()),
        configured=selection is not None,
    )


def _dispatch_google_folder_set(
    request: GoogleFolderSetRequest, profile: str, profile_id: UUID, commit: GoogleConfigurationCommit
) -> GoogleFolderSetProjection:
    """Run the existing GoogleFolderSet branch in its original effect order."""
    selected_folder = DriveConfig(root_folder_id=request.folder_id.strip())
    commit(lambda: save_drive_config(profile, selected_folder), changed=lambda _result: True)
    return GoogleFolderSetProjection(profile_id=profile_id, root_folder_id=selected_folder.root_folder_id)


def _dispatch_google_folder_view(
    request: GoogleFolderViewRequest, profile: str, profile_id: UUID
) -> GoogleFolderViewProjection:
    """Run the existing GoogleFolderView branch in its original effect order."""
    config = load_drive_config(profile)
    return GoogleFolderViewProjection(
        profile_id=profile_id,
        configured=config is not None,
        root_folder_id=config.root_folder_id if config is not None else None,
    )


def _dispatch_google_register(
    request: GoogleRegisterRequest,
    profile: str,
    profile_id: UUID,
    secret: memoryview | None,
    commit: GoogleConfigurationCommit,
) -> GoogleRegisterProjection:
    """Run the existing GoogleRegister branch in its original effect order."""
    if secret is None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    registered_client = decode_google_client_json(
        secret, source=Path(request.client_json_path), expected_sha256=request.client_json_sha256
    )
    commit(lambda: save_client(profile, registered_client), changed=lambda _result: True)
    return GoogleRegisterProjection(
        profile_id=profile_id, client_id=registered_client.client_id, project_id=registered_client.project_id
    )


def _dispatch_google_login(
    request: GoogleLoginRequest,
    profile: str,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    commit: GoogleConfigurationCommit,
    before_handoff: GoogleConfigurationHandoff,
    acknowledged: GoogleConfigurationAcknowledgement,
    terminal_admission: Callable[[], None] | None,
    local: _LocalFacts,
) -> GoogleLoginProjection:
    """Run the existing GoogleLogin branch in its original effect order."""
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
        return GoogleLoginProjection(profile_id=profile_id, mode="refresh-only", account_email=metadata.account_email)
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


def _dispatch_google_logout(
    request: GoogleLogoutRequest, profile: str, profile_id: UUID, commit: GoogleConfigurationCommit
) -> GoogleLogoutProjection:
    """Run the existing GoogleLogout branch in its original effect order."""
    token_removed, metadata_removed = commit(lambda: delete_session(profile), changed=lambda flags: any(flags))
    return GoogleLogoutProjection(profile_id=profile_id, token_removed=token_removed, metadata_removed=metadata_removed)


def _dispatch_google_status(request: GoogleStatusRequest, profile: str, profile_id: UUID) -> GoogleStatusProjection:
    """Run the existing GoogleStatus branch in its original effect order."""
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


def _dispatch_google_probe(
    request: GoogleProbeRequest,
    profile: str,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    before_handoff: GoogleConfigurationHandoff,
    acknowledged: GoogleConfigurationAcknowledgement,
    local: _LocalFacts,
) -> GoogleProbeProjection:
    """Run the existing GoogleProbe branch in its original effect order."""
    settings = load_settings().model_copy(update={"cadrumo_storage_provider_kind": "google_drive"})
    local.vault_folder_name = settings.cadrumo_google_drive_vault_folder_name.strip()
    if not request.read_only:
        session = require_profile_record_session(profile_id, profile_decode_context=operation.profile_decode_context())
        record = ProfileRecordStore(session=session).load().record
        if not resolve_capability(ServiceCapability.GOOGLE_EXPORT, profile_record=record, settings=settings).enabled:
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


def _require_google_request_profile(
    request: GoogleConfigurationRequest, profile_id: UUID, require_profile: Callable[[], None]
) -> None:
    """Require both the live selected profile and the submitted request identity."""
    require_profile()
    if request.profile_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _dispatch_google_configuration(
    request: GoogleConfigurationRequest,
    *,
    profile: str,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    require_profile: Callable[[], None],
    secret: memoryview | None,
    commit: GoogleConfigurationCommit,
    before_handoff: GoogleConfigurationHandoff,
    acknowledged: GoogleConfigurationAcknowledgement,
    terminal_admission: Callable[[], None] | None,
    local: _LocalFacts,
) -> GoogleConfigurationProjection:
    """Dispatch one admitted request to its typed owner without changing branch priority."""
    _require_google_request_profile(request, profile_id, require_profile)
    if isinstance(request, GoogleCredentialSourceSetRequest):
        return _dispatch_google_credential_source_set(request, profile, profile_id, commit)
    if isinstance(request, GoogleCredentialSourceViewRequest):
        return _dispatch_google_credential_source_view(request, profile, profile_id)
    if isinstance(request, GoogleFolderSetRequest):
        return _dispatch_google_folder_set(request, profile, profile_id, commit)
    if isinstance(request, GoogleFolderViewRequest):
        return _dispatch_google_folder_view(request, profile, profile_id)
    if isinstance(request, GoogleRegisterRequest):
        return _dispatch_google_register(request, profile, profile_id, secret, commit)
    if isinstance(request, GoogleLoginRequest):
        # The terminal callback validates the consumed exact proposal before
        # any browser launch. Credential acquisition receives fresh admission.
        return _dispatch_google_login(
            request, profile, profile_id, operation, commit, before_handoff, acknowledged, terminal_admission, local
        )
    if isinstance(request, GoogleLogoutRequest):
        return _dispatch_google_logout(request, profile, profile_id, commit)
    if isinstance(request, GoogleStatusRequest):
        return _dispatch_google_status(request, profile, profile_id)
    if isinstance(request, GoogleProbeRequest):
        return _dispatch_google_probe(request, profile, profile_id, operation, before_handoff, acknowledged, local)
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
