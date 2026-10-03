"""Local Google configuration conformance without contacting a provider."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime

from pydantic import BaseModel

from ...adapters.outbound.google.records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken
from ...adapters.outbound.google.session_store import (
    load_client,
    load_credential_source_selection,
    load_drive_config,
    load_metadata,
    load_token,
    save_client,
    save_drive_config,
    save_metadata,
    save_token,
)
from ...application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
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
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ...core.google_credential_source import GoogleCredentialSourceKind
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
_CLIENT = OAuthClient(
    client_id="synthetic-conformance-client",
    client_secret=secrets.token_hex(16),
    project_id="synthetic-project",
    auth_uri="https://accounts.google.com/o/oauth2/auth",
    token_uri=_OAUTH_ENDPOINT,
    auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
    redirect_uris=("http://localhost",),
)
_TIME = datetime(2026, 4, 1, tzinfo=UTC)
_METADATA = OAuthMetadata(
    account_email="conformance@example.invalid", granted_scopes=REQUIRED_SCOPES, issued_at=_TIME, last_refresh_at=_TIME
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    operation_id = context.definition.definition_id
    request: BaseModel
    result: BaseModel | None = None
    secret: bytes | None = None
    match operation_id:
        case "config.google.credential-source.set":
            request = GoogleCredentialSourceSetRequest(
                profile_id=context.profile_id, kind=GoogleCredentialSourceKind.OAUTH_DESKTOP
            )
            result = GoogleCredentialSourceSetProjection(
                profile_id=context.profile_id, kind=GoogleCredentialSourceKind.OAUTH_DESKTOP
            )
        case "config.google.credential-source.view":
            request = GoogleCredentialSourceViewRequest(profile_id=context.profile_id)
            result = GoogleCredentialSourceViewProjection(
                profile_id=context.profile_id, kind=GoogleCredentialSourceKind.OAUTH_DESKTOP, configured=False
            )
        case "config.google.folder.set":
            request = GoogleFolderSetRequest(
                profile_id=context.profile_id, folder_id="  synthetic-conformance-folder  "
            )
            result = GoogleFolderSetProjection(
                profile_id=context.profile_id, root_folder_id="synthetic-conformance-folder"
            )
        case "config.google.folder.view":
            save_drive_config(profile, DriveConfig(root_folder_id="synthetic-existing-folder"))
            request = GoogleFolderViewRequest(profile_id=context.profile_id)
            result = GoogleFolderViewProjection(
                profile_id=context.profile_id, configured=True, root_folder_id="synthetic-existing-folder"
            )
        case "config.google.login" | "config.google.logout" | "config.google.status":
            save_client(profile, _CLIENT)
            save_metadata(profile, _METADATA)
            save_token(profile, OAuthToken(refresh_token=secrets.token_hex(16), token_uri=_CLIENT.token_uri))
            if operation_id.endswith("login"):
                request = GoogleLoginRequest(profile_id=context.profile_id, refresh_only=True)
                result = GoogleLoginProjection(
                    profile_id=context.profile_id, mode="refresh-only", account_email=_METADATA.account_email
                )
            elif operation_id.endswith("logout"):
                request = GoogleLogoutRequest(profile_id=context.profile_id)
                result = GoogleLogoutProjection(
                    profile_id=context.profile_id, token_removed=True, metadata_removed=True
                )
            else:
                request = GoogleStatusRequest(profile_id=context.profile_id)
                result = GoogleStatusProjection(
                    profile_id=context.profile_id,
                    client_registered=True,
                    client_id=_CLIENT.client_id,
                    session_present=True,
                    account_email=_METADATA.account_email,
                    granted_scopes=REQUIRED_SCOPES,
                    issued_at=_TIME.isoformat(),
                    last_refresh_at=_TIME.isoformat(),
                    reauth_required=False,
                )
        case "config.google.register":
            secret = json.dumps({"installed": _CLIENT.model_dump(mode="json")}).encode("utf-8")
            path = context.input_root / "synthetic-client.json"
            path.write_bytes(secret)
            request = GoogleRegisterRequest(
                profile_id=context.profile_id, client_json_path=str(path), client_json_sha256=sha256_hex(secret)
            )
            result = GoogleRegisterProjection(
                profile_id=context.profile_id, client_id=_CLIENT.client_id, project_id=_CLIENT.project_id
            )
        case "config.google.probe":
            # No registered client: refusal is reached before token acquisition or HTTP.
            request = GoogleProbeRequest(profile_id=context.profile_id, read_only=True)
        case _:
            raise AssertionError(operation_id)

    def verify(outcome: ConformanceOutcome) -> None:
        if operation_id.endswith("credential-source.set"):
            selection = load_credential_source_selection(profile)
            assert selection is not None and selection.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP
        elif operation_id.endswith("folder.set"):
            assert load_drive_config(profile) == DriveConfig(root_folder_id="synthetic-conformance-folder")
        elif operation_id.endswith("register"):
            assert load_client(profile) == _CLIENT
        elif operation_id.endswith("logout"):
            assert load_metadata(profile) is None and load_token(profile) is None
            assert load_client(profile) == _CLIENT
        elif operation_id.endswith("probe"):
            actual = outcome.resolve_result(GoogleConfigurationOutcome)
            assert actual.outcome == "refused" and actual.refusal is not None
            assert actual.refusal.provider_code == "REFUSED_OUTBOUND_STORAGE_VALIDATION"
            assert actual.refusal.message_key == "adapters.outbound.storage._factory.errors.google_client_missing"
            assert load_client(profile) is None and load_token(profile) is None

    expected = (
        GoogleConfigurationOutcome(profile_id=context.profile_id, outcome="succeeded", result=result)
        if result is not None
        else None
    )
    return ConformancePreparation(
        profile_operation_subject(profile), request, secret=secret, expected_result=expected, verify=verify
    )


GOOGLE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            "config.google." + suffix,
            OperationTerminalCondition.REFUSED if suffix == "probe" else OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED
            if suffix in {"credential-source.set", "folder.set", "register", "logout"}
            else OperationEffect.NONE,
            ("config.google." + suffix,),
            "REFUSED_GOOGLE_CONFIGURATION" if suffix == "probe" else None,
        )
        for suffix in (
            "credential-source.set",
            "credential-source.view",
            "folder.set",
            "folder.view",
            "login",
            "logout",
            "probe",
            "register",
            "status",
        )
    ),
    prepare=_prepare,
)
