"""Registered-executor conformance scenarios for the human Google configuration family.

Every scenario stays on the local side of the provider boundary. The local
leaves read or write synthetic records through the production secure store;
the leaves that would reach Google (login and the Drive probe) refuse because
the installation under test carries no Google client, before any provider
exchange, so no scenario contacts the network or holds a usable credential.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from ...adapters.outbound.google.records import (
    REQUIRED_SCOPES,
    DriveConfig,
    OAuthMetadata,
    OAuthToken,
)
from ...adapters.outbound.google.session_store import (
    load_drive_config,
    load_metadata,
    load_token,
    save_drive_config,
    save_metadata,
    save_token,
)
from ...application.operations.frontend_requests import OperationPublicEffectEventV1
from ...application.operator_actions.preconditions import no_action_precondition_verdict
from ...application.operator_actions.projection import PreconditionVerdictSnapshot
from ...application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleConfigurationProjection,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ...application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_ROOT_FOLDER_ID = "conformance-root-folder"
_ACCOUNT_EMAIL = "conformance-operator@example.invalid"
_EXCHANGE_URI = "https://oauth2.googleapis.com/token"
_SYNTHETIC_REFRESH_CREDENTIAL = "conformance-synthetic-refresh-credential"
_SYNTHETIC_CLIENT_ID = "conformance-client.apps.googleusercontent.com"
_ISSUED_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
_REFRESHED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


def _synthetic_metadata() -> OAuthMetadata:
    return OAuthMetadata(
        account_email=_ACCOUNT_EMAIL,
        granted_scopes=REQUIRED_SCOPES,
        issued_at=_ISSUED_AT,
        last_refresh_at=_REFRESHED_AT,
        reauth_required=False,
    )


def _synthetic_token() -> OAuthToken:
    return OAuthToken(
        refresh_token=_SYNTHETIC_REFRESH_CREDENTIAL, client_id=_SYNTHETIC_CLIENT_ID, token_uri=_EXCHANGE_URI
    )


def _succeeded(profile_id: UUID, result: GoogleConfigurationProjection) -> GoogleConfigurationOutcome:
    return GoogleConfigurationOutcome(profile_id=profile_id, outcome="succeeded", result=result)


def _preparation(
    context: ConformanceFamilyContext,
    request: BaseModel,
    expected: GoogleConfigurationOutcome,
    *,
    verify: Callable[[ConformanceOutcome], None] | None = None,
) -> ConformancePreparation:
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=request,
        expected_result=expected,
        verify=verify,
    )


def _prepare_folder_set(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    before = load_drive_config(profile)
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


def _client_metadata_unavailable(profile_id: UUID) -> GoogleConfigurationRefusalProjection:
    """The one refusal every leaf gives when the installation carries no client file.

    The suite keeps the installation location empty, so a conformance run
    never reads a developer's own client.
    """
    verdict = no_action_precondition_verdict(
        condition_id="google.auth.client_metadata.available",
        facts={"client_metadata_present": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )
    return GoogleConfigurationRefusalProjection(
        profile_id=profile_id,
        provider_code="REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE",
        message_key="errors.refused.refused_google_client_metadata_unavailable",
        facts=GoogleConfigurationPresentationFacts(profile=profile_id),
        verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )


def _prepare_login(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    refusal = _client_metadata_unavailable(context.profile_id)

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
    save_token(profile, _synthetic_token())
    save_metadata(profile, _synthetic_metadata())
    expected = GoogleLogoutProjection(profile_id=context.profile_id, token_removed=True, metadata_removed=True)

    def verify(_outcome: ConformanceOutcome) -> None:
        assert load_token(profile) is None
        assert load_metadata(profile) is None

    request = GoogleLogoutRequest(profile_id=context.profile_id)
    return _preparation(context, request, _succeeded(context.profile_id, expected), verify=verify)


def _prepare_probe(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    save_drive_config(profile, DriveConfig(root_folder_id=_ROOT_FOLDER_ID))
    refusal = _client_metadata_unavailable(context.profile_id)
    request = GoogleProbeRequest(profile_id=context.profile_id, read_only=False)
    return _preparation(
        context, request, GoogleConfigurationOutcome(profile_id=context.profile_id, outcome="refused", refusal=refusal)
    )


def _prepare_status(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    metadata = _synthetic_metadata()
    save_metadata(profile, metadata)
    expected = GoogleStatusProjection(
        profile_id=context.profile_id,
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
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID: _prepare_folder_set,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID: _prepare_folder_view,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID: _prepare_login,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID: _prepare_logout,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID: _prepare_probe,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID: _prepare_status,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    preparer = _PREPARERS.get(context.definition.definition_id)
    if preparer is None:
        raise AssertionError(f"no Google configuration conformance scenario for {context.definition.definition_id}")
    return preparer(context)


def _case(
    definition_id: str, terminal: OperationTerminalCondition, effect: OperationEffect, refusal_ref: str | None = None
) -> RegisteredExecutorConformanceCase:
    return RegisteredExecutorConformanceCase(
        definition_id, terminal, effect, (definition_id,), expected_refusal_ref=refusal_ref
    )


_SUCCEEDED = OperationTerminalCondition.SUCCEEDED
_REFUSED = OperationTerminalCondition.REFUSED
GOOGLE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        _case(GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        _case(GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.NONE),
        _case(GOOGLE_LOGIN_OPERATION_DEFINITION_ID, _REFUSED, OperationEffect.NONE, GOOGLE_CONFIGURATION_REFUSAL_CODE),
        _case(GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.UPDATED),
        _case(
            GOOGLE_PROBE_OPERATION_DEFINITION_ID, _REFUSED, OperationEffect.UNKNOWN, GOOGLE_CONFIGURATION_REFUSAL_CODE
        ),
        _case(GOOGLE_STATUS_OPERATION_DEFINITION_ID, _SUCCEEDED, OperationEffect.NONE),
    ),
    prepare=_prepare,
)
_RETAINED_GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
_RETAINED_GOOGLE_TIME = datetime(2026, 4, 1, tzinfo=UTC)
_RETAINED_GOOGLE_METADATA = OAuthMetadata(
    account_email="conformance@example.invalid",
    granted_scopes=REQUIRED_SCOPES,
    issued_at=_RETAINED_GOOGLE_TIME,
    last_refresh_at=_RETAINED_GOOGLE_TIME,
)


def _retained_google_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    operation_id = context.definition.definition_id
    request: BaseModel
    result: GoogleConfigurationProjection | None = None
    refused: GoogleConfigurationRefusalProjection | None = None
    match operation_id:
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
            save_metadata(profile, _RETAINED_GOOGLE_METADATA)
            save_token(
                profile,
                OAuthToken(
                    refresh_token=secrets.token_hex(16),
                    client_id=_SYNTHETIC_CLIENT_ID,
                    token_uri=_RETAINED_GOOGLE_OAUTH_ENDPOINT,
                ),
            )
            if operation_id.endswith("login"):
                # A stored session cannot be refreshed without the client it was minted for.
                request = GoogleLoginRequest(profile_id=context.profile_id, refresh_only=True)
                refused = _client_metadata_unavailable(context.profile_id)
            elif operation_id.endswith("logout"):
                request = GoogleLogoutRequest(profile_id=context.profile_id)
                result = GoogleLogoutProjection(
                    profile_id=context.profile_id, token_removed=True, metadata_removed=True
                )
            else:
                request = GoogleStatusRequest(profile_id=context.profile_id)
                result = GoogleStatusProjection(
                    profile_id=context.profile_id,
                    session_present=True,
                    account_email=_RETAINED_GOOGLE_METADATA.account_email,
                    granted_scopes=REQUIRED_SCOPES,
                    issued_at=_RETAINED_GOOGLE_TIME.isoformat(),
                    last_refresh_at=_RETAINED_GOOGLE_TIME.isoformat(),
                    reauth_required=False,
                )
        case "config.google.probe":
            save_drive_config(profile, DriveConfig(root_folder_id="synthetic-conformance-folder"))
            request = GoogleProbeRequest(profile_id=context.profile_id, read_only=True)
        case _:
            raise AssertionError(operation_id)

    def verify(outcome: ConformanceOutcome) -> None:
        if operation_id.endswith("folder.set"):
            assert load_drive_config(profile) == DriveConfig(root_folder_id="synthetic-conformance-folder")
        elif operation_id.endswith("login"):
            assert load_metadata(profile) == _RETAINED_GOOGLE_METADATA and load_token(profile) is not None
        elif operation_id.endswith("logout"):
            assert load_metadata(profile) is None and load_token(profile) is None
        elif operation_id.endswith("probe"):
            actual = outcome.resolve_result(GoogleConfigurationOutcome)
            assert actual.outcome == "refused" and actual.refusal is not None
            assert actual.refusal == _client_metadata_unavailable(context.profile_id)
            assert load_drive_config(profile) == DriveConfig(root_folder_id="synthetic-conformance-folder")
            assert load_token(profile) is None
            assert tuple(
                event.effect
                for event in outcome.observed.event_page.events
                if isinstance(event, OperationPublicEffectEventV1)
            ) == (OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UNKNOWN)

    expected: GoogleConfigurationOutcome | None = None
    if result is not None:
        expected = _succeeded(context.profile_id, result)
    elif refused is not None:
        expected = GoogleConfigurationOutcome(profile_id=context.profile_id, outcome="refused", refusal=refused)
    return ConformancePreparation(profile_operation_subject(profile), request, expected_result=expected, verify=verify)


GOOGLE_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            "config.google." + suffix,
            OperationTerminalCondition.REFUSED
            if suffix in {"login", "probe"}
            else OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED
            if suffix in {"folder.set", "logout"}
            else OperationEffect.UNKNOWN
            if suffix == "probe"
            else OperationEffect.NONE,
            ("config.google." + suffix,),
            "REFUSED_GOOGLE_CONFIGURATION" if suffix in {"login", "probe"} else None,
        )
        for suffix in (
            "folder.set",
            "folder.view",
            "login",
            "logout",
            "probe",
            "status",
        )
    ),
    prepare=_retained_google_prepare,
)
