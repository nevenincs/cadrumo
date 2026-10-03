"""Registered-executor conformance scenarios for the human Google configuration family.

Every scenario stays on the local side of the provider boundary. The local
leaves read or write synthetic records through the production secure store;
the leaves that would reach Google (login consent and the Drive probe)
refuse on a missing local precondition before any provider exchange, so no
scenario contacts the network or holds a usable credential.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from ...adapters.outbound.google.impersonation import GoogleCredentialSourceSelection, GoogleImpersonationConfig
from ...adapters.outbound.google.records import (
    DRIVE_FILE_SCOPE,
    REQUIRED_SCOPES,
    SHEETS_SCOPE,
    DriveConfig,
    OAuthClient,
    OAuthMetadata,
    OAuthToken,
)
from ...adapters.outbound.google.session_store import (
    load_client,
    load_credential_source_selection,
    load_drive_config,
    load_metadata,
    load_token,
    save_client,
    save_credential_source_selection,
    save_drive_config,
    save_metadata,
    save_token,
)
from ...application.operator_actions.preconditions import no_action_precondition_verdict
from ...application.operator_actions.projection import PreconditionVerdictSnapshot
from ...application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID,
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConfigurationProjection,
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ...application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
)
from ...core.google_credential_source import GoogleCredentialSourceKind
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_TARGET_PRINCIPAL = "conformance-export@synthetic-project.iam.gserviceaccount.com"
_ROOT_FOLDER_ID = "conformance-root-folder"
_ACCOUNT_EMAIL = "conformance-operator@example.invalid"
_CLIENT_ID = "conformance-client.apps.googleusercontent.com"
_PROJECT_ID = "conformance-synthetic-project"
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_EXCHANGE_URI = "https://oauth2.googleapis.com/token"
_CERT_URI = "https://www.googleapis.com/oauth2/v1/certs"
_SYNTHETIC_CLIENT_CREDENTIAL = "conformance-synthetic-client-credential"
_SYNTHETIC_REFRESH_CREDENTIAL = "conformance-synthetic-refresh-credential"
_REDIRECT_URI = "http://localhost"
_ISSUED_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
_REFRESHED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


# Every value is synthetic. The endpoints are the canonical hosts the record
# validators admit (records.py OAuthClient/OAuthToken); none is a usable
# credential and no scenario hands one to a provider.
def _synthetic_client() -> OAuthClient:
    return OAuthClient(
        client_id=_CLIENT_ID,
        client_secret=_SYNTHETIC_CLIENT_CREDENTIAL,
        project_id=_PROJECT_ID,
        auth_uri=_AUTH_URI,
        token_uri=_EXCHANGE_URI,
        auth_provider_x509_cert_url=_CERT_URI,
        redirect_uris=(_REDIRECT_URI,),
    )


def _synthetic_metadata() -> OAuthMetadata:
    return OAuthMetadata(
        account_email=_ACCOUNT_EMAIL,
        granted_scopes=REQUIRED_SCOPES,
        issued_at=_ISSUED_AT,
        last_refresh_at=_REFRESHED_AT,
        reauth_required=False,
    )


def _synthetic_token() -> OAuthToken:
    return OAuthToken(refresh_token=_SYNTHETIC_REFRESH_CREDENTIAL, token_uri=_EXCHANGE_URI)


def _impersonation_selection() -> GoogleCredentialSourceSelection:
    return GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=GoogleImpersonationConfig(
            target_principal=_TARGET_PRINCIPAL,
            target_scopes=(DRIVE_FILE_SCOPE, SHEETS_SCOPE),
            delegates=(),
            subject=None,
            lifetime_s=900,
        ),
    )


def _succeeded(profile_id: UUID, result: GoogleConfigurationProjection) -> GoogleConfigurationOutcome:
    return GoogleConfigurationOutcome(profile_id=profile_id, outcome="succeeded", result=result)


def _preparation(
    context: ConformanceFamilyContext,
    request: BaseModel,
    expected: GoogleConfigurationOutcome,
    *,
    secret: bytes | None = None,
    verify: Callable[[ConformanceOutcome], None] | None = None,
) -> ConformancePreparation:
    return ConformancePreparation(
        # The result projector binds the receipt to this exact subject
        # (google_configuration_result_projection.py:36).
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=request,
        secret=secret,
        expected_result=expected,
        verify=verify,
    )


def _prepare_credential_source_set(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    before = load_credential_source_selection(profile)
    request = GoogleCredentialSourceSetRequest(
        profile_id=context.profile_id,
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        # The source constructor strips the principal before validating it
        # (google_configuration_inputs.py:93).
        target_principal=f"  {_TARGET_PRINCIPAL}  ",
        scopes=(DRIVE_FILE_SCOPE,),
        lifetime_seconds=600,
    )
    expected = GoogleCredentialSourceSetProjection(
        profile_id=context.profile_id,
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        target_principal=_TARGET_PRINCIPAL,
        target_scopes=(DRIVE_FILE_SCOPE,),
        delegates=(),
        subject=None,
        lifetime_s=600,
    )

    def verify(_outcome: ConformanceOutcome) -> None:
        assert before is None
        stored = load_credential_source_selection(profile)
        assert stored is not None
        assert stored.kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION
        assert stored.impersonation is not None
        assert stored.impersonation.target_principal == _TARGET_PRINCIPAL
        assert stored.impersonation.target_scopes == (DRIVE_FILE_SCOPE,)
        assert stored.impersonation.lifetime_s == 600

    return _preparation(context, request, _succeeded(context.profile_id, expected), verify=verify)


def _prepare_credential_source_view(context: ConformanceFamilyContext) -> ConformancePreparation:
    selection = _impersonation_selection()
    save_credential_source_selection(str(context.profile_id), selection)
    impersonation = selection.impersonation
    assert impersonation is not None
    expected = GoogleCredentialSourceViewProjection(
        profile_id=context.profile_id,
        kind=selection.kind,
        target_principal=impersonation.target_principal,
        target_scopes=impersonation.target_scopes,
        delegates=impersonation.delegates,
        subject=impersonation.subject,
        lifetime_s=impersonation.lifetime_s,
        configured=True,
    )
    request = GoogleCredentialSourceViewRequest(profile_id=context.profile_id)
    return _preparation(context, request, _succeeded(context.profile_id, expected))


def _prepare_folder_set(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    before = load_drive_config(profile)
    # The folder leaf keeps the canonical whitespace normalisation
    # (google_configuration_operation_composition.py:321).
    request = GoogleFolderSetRequest(profile_id=context.profile_id, folder_id=f"  {_ROOT_FOLDER_ID}\t")
    expected = GoogleFolderSetProjection(profile_id=context.profile_id, root_folder_id=_ROOT_FOLDER_ID)

    def verify(_outcome: ConformanceOutcome) -> None:
        assert before is None
        assert load_drive_config(profile) == DriveConfig(root_folder_id=_ROOT_FOLDER_ID)

    return _preparation(context, request, _succeeded(context.profile_id, expected), verify=verify)


def _prepare_folder_view(context: ConformanceFamilyContext) -> ConformancePreparation:
    save_drive_config(str(context.profile_id), DriveConfig(root_folder_id=_ROOT_FOLDER_ID))
    expected = GoogleFolderViewProjection(
        profile_id=context.profile_id, configured=True, root_folder_id=_ROOT_FOLDER_ID
    )
    request = GoogleFolderViewRequest(profile_id=context.profile_id)
    return _preparation(context, request, _succeeded(context.profile_id, expected))


def _prepare_login(context: ConformanceFamilyContext) -> ConformancePreparation:
    # The consent leaf checks the registered client before publishing its
    # review (google_configuration_operation_composition.py:174), and the
    # isolated profile has none, so it refuses without a provider handoff.
    profile = str(context.profile_id)
    assert load_client(profile) is None
    refusal = GoogleConfigurationRefusalProjection(
        profile_id=context.profile_id,
        # Registered for GoogleAuthClientNotRegisteredError at core/errors/registry/_adapters_part2.py:233.
        provider_code="AUTH_GOOGLE_CLIENT_NOT_REGISTERED",
        message_key="cli.config.google.detail.client_unregistered",
        facts=GoogleConfigurationPresentationFacts(profile=context.profile_id),
    )

    def verify(_outcome: ConformanceOutcome) -> None:
        assert load_token(profile) is None
        assert load_metadata(profile) is None

    request = GoogleLoginRequest(profile_id=context.profile_id, refresh_only=False)
    return _preparation(
        context,
        request,
        GoogleConfigurationOutcome(profile_id=context.profile_id, outcome="refused", refusal=refusal),
        verify=verify,
    )


def _prepare_logout(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    save_client(profile, _synthetic_client())
    save_token(profile, _synthetic_token())
    save_metadata(profile, _synthetic_metadata())
    expected = GoogleLogoutProjection(profile_id=context.profile_id, token_removed=True, metadata_removed=True)

    def verify(_outcome: ConformanceOutcome) -> None:
        assert load_token(profile) is None
        assert load_metadata(profile) is None
        # Logout preserves the registered client (session_store.delete_session).
        assert load_client(profile) == _synthetic_client()

    request = GoogleLogoutRequest(profile_id=context.profile_id)
    return _preparation(context, request, _succeeded(context.profile_id, expected), verify=verify)


def _prepare_probe(context: ConformanceFamilyContext) -> ConformancePreparation:
    # A persisted root folder makes the root lookup independent of any host
    # override (storage/factory.py:243). Credential hydration then refuses on
    # the missing registered client (storage/factory.py:174-184) before any
    # Drive request is built.
    profile = str(context.profile_id)
    save_drive_config(profile, DriveConfig(root_folder_id=_ROOT_FOLDER_ID))
    verdict = no_action_precondition_verdict(
        condition_id="storage.factory.google_oauth_client.present",
        facts={"field": "google_oauth_client", "valid": False, "backend": "google_drive"},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    refusal = GoogleConfigurationRefusalProjection(
        profile_id=context.profile_id,
        # Registered for OutboundStorageValidationError at core/errors/registry/_adapters_part2.py:383.
        provider_code="REFUSED_OUTBOUND_STORAGE_VALIDATION",
        message_key="adapters.outbound.storage._factory.errors.google_client_missing",
        facts=GoogleConfigurationPresentationFacts(profile=context.profile_id),
        verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )
    request = GoogleProbeRequest(profile_id=context.profile_id, read_only=False)
    return _preparation(
        context, request, GoogleConfigurationOutcome(profile_id=context.profile_id, outcome="refused", refusal=refusal)
    )


def _prepare_register(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    before = load_client(profile)
    client_json = json.dumps(
        {
            "installed": {
                "client_id": _CLIENT_ID,
                "client_secret": _SYNTHETIC_CLIENT_CREDENTIAL,
                "project_id": _PROJECT_ID,
                "auth_uri": _AUTH_URI,
                "token_uri": _EXCHANGE_URI,
                "auth_provider_x509_cert_url": _CERT_URI,
                "redirect_uris": [_REDIRECT_URI],
            }
        }
    ).encode("utf-8")
    source = context.input_root / "client_secret.json"
    source.write_bytes(client_json)
    request = GoogleRegisterRequest(
        profile_id=context.profile_id, client_json_path=str(source), client_json_sha256=sha256_hex(client_json)
    )
    expected = GoogleRegisterProjection(profile_id=context.profile_id, client_id=_CLIENT_ID, project_id=_PROJECT_ID)

    def verify(_outcome: ConformanceOutcome) -> None:
        assert before is None
        assert load_client(profile) == _synthetic_client()

    # The registered definition declares the client JSON as its ephemeral
    # secret (google_configuration_operation.py:149-153).
    return _preparation(context, request, _succeeded(context.profile_id, expected), secret=client_json, verify=verify)


def _prepare_status(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    client = _synthetic_client()
    metadata = _synthetic_metadata()
    save_client(profile, client)
    save_metadata(profile, metadata)
    # Instants are rendered with isoformat (google_configuration_operation_composition.py:426-427).
    expected = GoogleStatusProjection(
        profile_id=context.profile_id,
        client_registered=True,
        client_id=client.client_id,
        session_present=True,
        account_email=metadata.account_email,
        granted_scopes=metadata.granted_scopes,
        issued_at=_ISSUED_AT.isoformat(),
        last_refresh_at=_REFRESHED_AT.isoformat(),
        reauth_required=False,
    )
    request = GoogleStatusRequest(profile_id=context.profile_id)
    return _preparation(context, request, _succeeded(context.profile_id, expected))


_PREPARERS: dict[str, Callable[[ConformanceFamilyContext], ConformancePreparation]] = {
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID: _prepare_credential_source_set,
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID: _prepare_credential_source_view,
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID: _prepare_folder_set,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID: _prepare_folder_view,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID: _prepare_login,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID: _prepare_logout,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID: _prepare_probe,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID: _prepare_register,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    preparer = _PREPARERS.get(context.definition.definition_id)
    if preparer is None:
        raise AssertionError(f"no Google configuration conformance scenario for {context.definition.definition_id}")
    return preparer(context)


def _case(
    definition_id: str,
    terminal: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_ref: str | None = None,
) -> RegisteredExecutorConformanceCase:
    # Each leaf declares its own id as its only phase (google_configuration_operation.py:129)
    # and publishes it before any port work (google_configuration_executor.py:184).
    return RegisteredExecutorConformanceCase(
        definition_id, terminal, effect, (definition_id,), expected_refusal_ref=refusal_ref
    )


_SUCCEEDED = OperationTerminalCondition.SUCCEEDED
_REFUSED = OperationTerminalCondition.REFUSED

GOOGLE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Local writes settle UPDATED through the tracked commit
        # (google_configuration_executor.py:151-160); reads commit nothing.
        _case(GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        _case(GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.NONE),
        _case(GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        _case(GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.NONE),
        # The consent preparation refusal is stored with effect NONE
        # (google_configuration_executor.py:202-205).
        _case(GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _REFUSED, OperationEffect.NONE, GOOGLE_CONFIGURATION_REFUSAL_CODE),
        # Logout's commit reports a change when either session record existed
        # (google_configuration_operation_composition.py:411).
        _case(GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        # The credential-acquisition handoff is admitted before hydration
        # (storage/factory.py:303-305) and never acknowledged once hydration
        # refuses, so the tracker settles the refusal UNKNOWN
        # (google_configuration_executor.py:125-127, 305-308).
        _case(
            GOOGLE_PROBE_OPERATION_DEFINITION_ID, _REFUSED, OperationEffect.UNKNOWN, GOOGLE_CONFIGURATION_REFUSAL_CODE
        ),
        _case(GOOGLE_REGISTER_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        _case(GOOGLE_STATUS_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.NONE),
    ),
    prepare=_prepare,
)
