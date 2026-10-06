"""Real Windows worker and encrypted records, without Google network traffic.

The owning native CLI fixture uses MemoryNativePort and synthetic OS-login
evidence. This journey does not establish platform secret-store acceptance or
exercise Google OAuth, browser consent, or remote provider traffic.

The worker is a separate process. This journey exercises existing session
records without starting browser consent; synthetic client validation is
covered independently at the settings and Google adapter boundaries.
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
from .....adapters.outbound.google.records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken
from .....adapters.outbound.google.session_store import (
    load_drive_config,
    load_metadata,
    load_token,
    save_drive_config,
    save_metadata,
    save_token,
)
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.runtime.operation_access import (
    RuntimeOperationObserved,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from .....application.user_profile.access_contracts import AccessDenialCode
from .....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from .....application.user_profile.login_session import login_profile, resolve_login_target
from .....core.hashing import canonical_json_bytes
from .....core.operations import OperationEffect, profile_operation_subject
from .....core.redaction.rules import redact_structured_for_cli_output
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....tests.cli_envelope import unwrap_cli_result
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


def test_native_google_configuration_installation_client_and_exact_profile_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Retain complete local state through real CLI leaves; no leaf accepts a client from the operator."""
    refresh_value = "native-refresh-" + uuid4().hex
    original_operation = RuntimeFrontendClient.operation
    original_result = RuntimeFrontendClient.read_result_document
    definitions: dict[str, str] = {}
    effects: dict[str, OperationEffect] = {}
    completions: list[tuple[str, OperationEffect, GoogleConfigurationOutcome]] = []
    foreign_refused = False
    owner_profile: UUID | None = None

    def observe_operation(
        client: RuntimeFrontendClient, request: RuntimeOperationRequest, *, deadline: float
    ) -> RuntimeOperationReply:
        encoded = request.model_dump_json()
        assert refresh_value not in encoded
        reply = original_operation(client, request, deadline=deadline)
        if isinstance(request, RuntimeOperationSubmit) and isinstance(reply, RuntimeOperationSubmitted):
            definitions[reply.receipt.operation_id] = request.definition_id
            # No Google configuration leaf opens a protected input channel.
            assert reply.receipt.secret_requirement is None
        if isinstance(reply, RuntimeOperationObserved) and isinstance(reply.observation, OperationObservationSuccessV1):
            state = reply.observation.projection
            effects[state.operation_id] = state.effect
        return reply

    def observe_result(
        client: RuntimeFrontendClient,
        result: OperationResultProjectionRequestV1,
        *,
        timeout: float = 60,
        deadline: float | None = None,
    ) -> dict[str, JsonValue]:
        nonlocal foreign_refused
        document = original_result(client, result, timeout=timeout, deadline=deadline)
        definition_id = definitions[result.operation_id]
        if not definition_id.startswith("config.google."):
            return document
        encoded = canonical_json_bytes(document)
        assert refresh_value.encode() not in encoded
        envelope = OperationResultProjectionSuccessV1[GoogleConfigurationOutcome].model_validate_json(encoded)
        assert envelope.projection.profile_id == owner_profile == client.profile_id
        completions.append((definition_id, effects[result.operation_id], envelope.projection))
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
            assert refresh_value not in reply.output
            compact = tuple(
                dict.fromkeys(
                    (item.exception_type, item.definition_id, item.phase, item.reason)
                    for item in observations
                    if item.exception_type is not None or item.reason is not None
                )
            )[-8:]
            assert reply.exit_code == 0, reply.output + "\nobservations=" + json.dumps(compact)
            return reply

        status = unwrap_cli_result(invoke("status"))
        assert status["session_present"] is False
        assert "client_registered" not in status and "client_id" not in status
        assert foreign_refused
        # The command that accepted a client from the operator no longer exists.
        removed = _invoke(profile, "register", "--client-json", str(tmp_path / "client.json"))
        assert removed.exit_code == 2, removed.output
        assert not any(definition.endswith(".register") for definition in definitions.values())
        assert unwrap_cli_result(invoke("folder", "view"))["configured"] is False
        # No command accepts a Drive folder from the operator.
        folder_id = "synthetic-native-root-folder"
        removed_folder_set = _invoke(profile, "folder", "set", folder_id)
        assert removed_folder_set.exit_code == 2, removed_folder_set.output
        assert unwrap_cli_result(invoke("folder", "view"))["configured"] is False

        close_active_bucket_session()
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            profile_id = str(owner_profile)
            assert load_drive_config(profile_id) is None
            # A sign-in is what stores the folder it created; this fixture stores one directly.
            save_drive_config(profile_id, DriveConfig(root_folder_id=folder_id))
            reopened_folder = load_drive_config(profile_id)
            instant = datetime.now(UTC)
            # Local synthetic fixture records make actual logout deletion observable;
            # they are not an OAuth or provider credential-acquisition simulation.
            save_token(
                profile_id,
                OAuthToken(
                    refresh_token=refresh_value,
                    client_id="synthetic-native-client.apps.googleusercontent.com",
                    token_uri=_OAUTH_ENDPOINT,
                ),
            )
            save_metadata(
                profile_id,
                OAuthMetadata(
                    account_email="synthetic@example.invalid",
                    granted_scopes=REQUIRED_SCOPES,
                    issued_at=instant,
                ),
            )
        finally:
            close_active_bucket_session()
        assert unwrap_cli_result(invoke("folder", "view"))["root_folder_id"] == folder_id
        linked = unwrap_cli_result(invoke("status"))
        assert linked["session_present"] is True
        definition, effect, outcome = completions[-1]
        assert definition == GOOGLE_STATUS_OPERATION_DEFINITION_ID and effect is OperationEffect.NONE
        canonical_status = outcome.result
        assert isinstance(canonical_status, GoogleStatusProjection)
        assert canonical_status.granted_scopes == REQUIRED_SCOPES
        assert canonical_status.account_email == "synthetic@example.invalid"
        assert canonical_status.issued_at == instant.isoformat()
        expected_visible = redact_structured_for_cli_output(
            {
                "account_email": canonical_status.account_email,
                "granted_scopes": list(canonical_status.granted_scopes),
                "issued_at": canonical_status.issued_at,
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
        finally:
            close_active_bucket_session()
        # The flag that claimed to refresh without consent no longer exists.
        removed_flag = _invoke(profile, "login", "--refresh-only")
        assert removed_flag.exit_code == 2, removed_flag.output
        assert unwrap_cli_result(invoke("status")) == linked
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
        assert final_status["session_present"] is False
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            assert load_token(profile_id) is None and load_metadata(profile_id) is None
            assert load_drive_config(profile_id) == reopened_folder
        finally:
            close_active_bucket_session()
