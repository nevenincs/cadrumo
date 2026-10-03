"""Real Windows worker and encrypted records, without Google network traffic.

The owning native CLI fixture uses MemoryNativePort and synthetic OS-login
evidence. This journey does not establish platform secret-store acceptance or
exercise Google OAuth, ADC, IAM, browser consent, or remote provider traffic.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from pydantic import JsonValue

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from .....adapters.outbound.google.records import REQUIRED_SCOPES, OAuthMetadata, OAuthToken
from .....adapters.outbound.google.session_store import (
    load_client,
    load_credential_source_selection,
    load_drive_config,
    load_metadata,
    load_token,
    save_metadata,
    save_token,
)
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.operations.secret_submission import OperationSecretRequirement
from .....application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from .....application.user_profile.access_contracts import AccessDenialCode
from .....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_INPUT_KIND,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from .....application.user_profile.google_configuration_operation_refusal import GOOGLE_CONFIGURATION_REFUSAL_CODE
from .....application.user_profile.login_session import login_profile, resolve_login_target
from .....core.hashing import canonical_json_bytes
from .....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .....core.redaction.rules import redact_structured_for_cli_output
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...runtime_registered_operation import run_registered_operation
from ...tests.cli_runner import invoke_cached_cli
from ...tests.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            "config",
            "google",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_google_configuration_protected_registration_and_exact_profile_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Consume one protected source and retain complete local state through real CLI leaves."""
    client_value = "native-client-" + uuid4().hex
    refresh_value = "native-refresh-" + uuid4().hex
    client_json = tmp_path / "desktop-client.json"
    client_json.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "synthetic-native-client.apps.googleusercontent.com",
                    "client_secret": client_value,
                    "project_id": "synthetic-native-project",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )
    original_operation = RuntimeFrontendClient.operation
    original_secret = RuntimeFrontendClient.submit_secret
    original_result = RuntimeFrontendClient.read_result_document
    definitions: dict[str, str] = {}
    requirements: dict[str, OperationSecretRequirement] = {}
    effects: dict[str, OperationEffect] = {}
    completions: list[tuple[str, OperationEffect, GoogleConfigurationOutcome]] = []
    submitted_lengths: list[int] = []
    replay_refused = False
    foreign_refused = False
    owner_profile: UUID | None = None

    def observe_operation(
        client: RuntimeFrontendClient, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply:
        encoded = request.model_dump_json()
        assert client_value not in encoded and refresh_value not in encoded
        reply = original_operation(client, request, deadline=deadline)
        if isinstance(request, RuntimeOperationSubmit) and isinstance(reply, RuntimeOperationSubmitted):
            definitions[reply.receipt.operation_id] = request.definition_id
            if reply.receipt.secret_requirement is not None:
                requirements[reply.receipt.operation_id] = reply.receipt.secret_requirement
        if isinstance(reply, RuntimeOperationObserved) and isinstance(reply.observation, OperationObservationSuccessV1):
            state = reply.observation.projection
            effects[state.operation_id] = state.effect
        return reply

    def observe_secret(
        client: RuntimeFrontendClient,
        requirement: OperationSecretRequirement,
        secret: bytearray,
        *,
        timeout: float = 20,
    ) -> RuntimeOperationAcknowledged:
        assert requirement.secret_kind == GOOGLE_REGISTER_INPUT_KIND
        assert requirement.identity.definition_id == GOOGLE_REGISTER_OPERATION_DEFINITION_ID
        submitted_lengths.append(len(secret))
        try:
            return original_secret(client, requirement, secret, timeout=timeout)
        finally:
            assert secret == bytearray(len(secret))

    def observe_result(
        client: RuntimeFrontendClient,
        result: OperationResultProjectionRequestV1,
        *,
        timeout: float = 60,
        deadline: float | None = None,
    ) -> dict[str, JsonValue]:
        nonlocal replay_refused, foreign_refused
        document = original_result(client, result, timeout=timeout, deadline=deadline)
        definition_id = definitions[result.operation_id]
        if not definition_id.startswith("config.google."):
            return document
        encoded = canonical_json_bytes(document)
        assert client_value.encode() not in encoded and refresh_value.encode() not in encoded
        envelope = OperationResultProjectionSuccessV1[GoogleConfigurationOutcome].model_validate_json(encoded)
        assert envelope.projection.profile_id == owner_profile == client.profile_id
        completions.append((definition_id, effects[result.operation_id], envelope.projection))
        if definition_id == GOOGLE_REGISTER_OPERATION_DEFINITION_ID:
            replacement = bytearray(b"one-use replay must be denied before delivery")
            with pytest.raises(RuntimeFrontendRefusedError):
                original_secret(client, requirements[result.operation_id], replacement)
            assert replacement == bytearray(len(replacement))
            assert client.status().status.connected
            replay_refused = True
        if definition_id == GOOGLE_STATUS_OPERATION_DEFINITION_ID and not foreign_refused:
            with pytest.raises(RuntimeFrontendRefusedError) as denied:
                run_registered_operation(
                    client,
                    GoogleStatusRequest(profile_id=uuid4()),
                    definition_id=GOOGLE_STATUS_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(client.profile_id)),
                    result_type=GoogleConfigurationOutcome,
                    request_version=1,
                    result_version=1,
                    timeout=30,
                    allow_refusal_detail=True,
                )
            assert denied.value.reason == AccessDenialCode.PROFILE_MISMATCH.value
            assert client.status().status.connected
            foreign_refused = True
        return document

    monkeypatch.setattr(RuntimeFrontendClient, "operation", observe_operation)
    monkeypatch.setattr(RuntimeFrontendClient, "submit_secret", observe_secret)
    monkeypatch.setattr(RuntimeFrontendClient, "read_result_document", observe_result)
    with native_cli_profile_scope(tmp_path) as profile:
        observations: list[RuntimeFailureObservation] = []
        profile.failure_observer = observations.append
        profile.register(
            label="native-google-local",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Google Local",
                "activities.description": "synthetic test profile",
            },
        )
        assert profile.label is not None
        owner_profile = UUID(resolve_login_target(profile.label).bucket_id)

        def invoke(*command: str) -> Result:
            reply = _invoke(profile, *command)
            assert client_value not in reply.output and refresh_value not in reply.output
            compact = tuple(
                dict.fromkeys(
                    (item.exception_type, item.definition_id, item.phase, item.reason)
                    for item in observations
                    if item.exception_type is not None or item.reason is not None
                )
            )[-8:]
            assert reply.exit_code == 0, reply.output + "\nobservations=" + json.dumps(compact)
            return reply

        registered = unwrap_cli_result(invoke("register", "--client-json", str(client_json)))
        assert registered["client_id"] == "synthetic-native-client.apps.googleusercontent.com"
        assert registered["project_id"] == "synthetic-native-project"
        assert submitted_lengths == [client_json.stat().st_size]
        assert replay_refused
        status = unwrap_cli_result(invoke("status"))
        assert status["client_registered"] is True and status["session_present"] is False
        assert foreign_refused
        source_default = unwrap_cli_result(invoke("credential-source", "view"))
        assert source_default["configured"] is False and source_default["kind"] == "oauth_desktop"

        def assert_source_refusal(*arguments: str, message_key: str) -> None:
            refused = _invoke(profile, "credential-source", "set", *arguments)
            assert client_value not in refused.output and refresh_value not in refused.output
            assert refused.exit_code == 3, (refused.output, observations)
            error = require_error_document(refused.output)["error"]
            assert error["code"] == "AUTH_GOOGLE" and error["category"] == "AUTH"
            context = error["context"]
            assert isinstance(context, dict)
            assert context["refusal_code"] == GOOGLE_CONFIGURATION_REFUSAL_CODE
            assert context["terminal_condition"] == OperationTerminalCondition.REFUSED.value
            assert context["effect"] == OperationEffect.NONE.value
            definition, effect, outcome = completions[-1]
            assert definition == GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID
            assert effect is OperationEffect.NONE and outcome.outcome == "refused"
            assert outcome.result is None and outcome.refusal is not None
            assert outcome.refusal.provider_code == "AUTH_GOOGLE"
            assert outcome.refusal.message_key == message_key
            assert unwrap_cli_result(invoke("credential-source", "view")) == source_default

        assert_source_refusal(
            "--kind",
            "service_account_impersonation",
            message_key="cli.config.google.credential_source.detail.target_principal_required",
        )
        assert_source_refusal(
            "--kind",
            "oauth_desktop",
            "--target-principal",
            "synthetic@synthetic.iam.gserviceaccount.com",
            message_key="cli.config.google.credential_source.detail.oauth_desktop_rejects_impersonation_options",
        )
        assert unwrap_cli_result(invoke("folder", "view"))["configured"] is False
        principal = "native-target@synthetic.iam.gserviceaccount.com"
        delegate = "native-delegate@synthetic.iam.gserviceaccount.com"
        source = unwrap_cli_result(
            invoke(
                "credential-source",
                "set",
                "--kind",
                "service_account_impersonation",
                "--target-principal",
                principal,
                "--scope",
                REQUIRED_SCOPES[-1],
                "--delegate",
                delegate,
                "--subject",
                "synthetic@example.invalid",
                "--lifetime-seconds",
                "1800",
            )
        )
        viewed = unwrap_cli_result(invoke("credential-source", "view"))
        for key in ("kind", "target_principal", "target_scopes", "delegates", "subject", "lifetime_s"):
            assert viewed[key] == source[key]
        assert viewed["configured"] is True
        folder_id = "synthetic-native-root-folder"
        assert unwrap_cli_result(invoke("folder", "set", folder_id))["root_folder_id"] == folder_id
        assert unwrap_cli_result(invoke("folder", "view"))["root_folder_id"] == folder_id

        close_active_bucket_session()
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            profile_id = str(owner_profile)
            reopened_client = load_client(profile_id)
            assert reopened_client is not None and reopened_client.client_secret == client_value
            reopened_source = load_credential_source_selection(profile_id)
            assert reopened_source is not None and reopened_source.impersonation is not None
            assert reopened_source.impersonation.target_principal == principal
            assert reopened_source.impersonation.target_scopes == (REQUIRED_SCOPES[-1],)
            assert reopened_source.impersonation.delegates == (delegate,)
            assert reopened_source.impersonation.subject == "synthetic@example.invalid"
            assert reopened_source.impersonation.lifetime_s == 1800
            reopened_folder = load_drive_config(profile_id)
            assert reopened_folder is not None and reopened_folder.root_folder_id == folder_id
            instant = datetime.now(UTC)
            # Local synthetic fixture records make actual logout deletion observable;
            # they are not an OAuth or provider credential-acquisition simulation.
            save_token(profile_id, OAuthToken(refresh_token=refresh_value, token_uri=_OAUTH_ENDPOINT))
            save_metadata(
                profile_id,
                OAuthMetadata(
                    account_email="synthetic@example.invalid",
                    granted_scopes=REQUIRED_SCOPES,
                    issued_at=instant,
                    last_refresh_at=instant,
                    reauth_required=False,
                ),
            )
        finally:
            close_active_bucket_session()
        linked = unwrap_cli_result(invoke("status"))
        assert linked["session_present"] is True
        definition, effect, outcome = completions[-1]
        assert definition == GOOGLE_STATUS_OPERATION_DEFINITION_ID and effect is OperationEffect.NONE
        canonical_status = outcome.result
        assert isinstance(canonical_status, GoogleStatusProjection)
        assert canonical_status.granted_scopes == REQUIRED_SCOPES
        assert canonical_status.account_email == "synthetic@example.invalid"
        assert canonical_status.issued_at == instant.isoformat() == canonical_status.last_refresh_at
        assert canonical_status.reauth_required is False
        expected_visible = redact_structured_for_cli_output(
            {
                "account_email": canonical_status.account_email,
                "granted_scopes": list(canonical_status.granted_scopes),
                "issued_at": canonical_status.issued_at,
                "last_refresh_at": canonical_status.last_refresh_at,
                "reauth_required": canonical_status.reauth_required,
            }
        )
        for field, expected in expected_visible.items():
            assert linked[field] == expected
        close_active_bucket_session()
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            reopened_metadata = load_metadata(profile_id)
            assert reopened_metadata is not None
            assert reopened_metadata.granted_scopes == canonical_status.granted_scopes == REQUIRED_SCOPES
            assert reopened_metadata.account_email == canonical_status.account_email
            assert reopened_metadata.issued_at.isoformat() == canonical_status.issued_at
            assert reopened_metadata.last_refresh_at.isoformat() == canonical_status.last_refresh_at
            assert reopened_metadata.reauth_required is canonical_status.reauth_required
        finally:
            close_active_bucket_session()
        refreshed = unwrap_cli_result(invoke("login", "--refresh-only"))
        assert refreshed["mode"] == "refresh-only" and refreshed["account_email"] == linked["account_email"]
        first_logout = unwrap_cli_result(invoke("logout"))
        assert first_logout["token_removed"] is True and first_logout["metadata_removed"] is True
        second_logout = unwrap_cli_result(invoke("logout"))
        assert second_logout["token_removed"] is False and second_logout["metadata_removed"] is False
        logout_effects = [
            effect
            for definition, effect, _outcome in completions
            if definition == GOOGLE_LOGOUT_OPERATION_DEFINITION_ID
        ]
        assert logout_effects == [OperationEffect.UPDATED, OperationEffect.NONE]
        final_status = unwrap_cli_result(invoke("status"))
        assert final_status["client_registered"] is True and final_status["session_present"] is False
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            assert load_token(profile_id) is None and load_metadata(profile_id) is None
            assert load_client(profile_id) == reopened_client
            assert load_credential_source_selection(profile_id) == reopened_source
            assert load_drive_config(profile_id) == reopened_folder
        finally:
            close_active_bucket_session()
