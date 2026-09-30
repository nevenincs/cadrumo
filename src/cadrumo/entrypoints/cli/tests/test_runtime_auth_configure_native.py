"""The auth configure CLI settles against one native exact-profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.auth.operation_definitions import AUTH_CONFIGURE_OPERATION_DEFINITION_ID
from ....application.auth.provider_configure_operation_access import AuthConfigureOperationProjection
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....tests.cli_envelope import unwrap_cli_result
from ..config import runtime_auth_configure as configure_bridge
from ..runtime_registered_operation import RegisteredOperationCompletion, run_registered_operation
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, RuntimeFailureObservation, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _invoke(profile: NativeCliProfileFixture, *command: str):
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
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_cli_auth_configure_settles_and_reads_back_exact_profile_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist a synthetic certificate selection through the registered operation."""
    certificate = tmp_path / "synthetic-test-certificate.p12"
    certificate.write_bytes(b"synthetic test certificate placeholder")

    with native_cli_profile_scope(tmp_path) as profile:
        observations: list[RuntimeFailureObservation] = []
        profile.failure_observer = observations.append
        profile.register(
            label="native-auth-configure",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Auth Configure",
                "activities.description": "synthetic test profile",
            },
        )
        active_profile_id = UUID(str(resolve_active_bucket_id()))

        observed: list[tuple[str, OperationTerminalCondition, OperationEffect, str | None, BaseModel]] = []

        def observe_completion[ResultT: BaseModel](
            client: RuntimeFrontendClient,
            payload: BaseModel,
            *,
            definition_id: str,
            subject_ref: str,
            result_type: type[ResultT],
            request_version: int,
            result_version: int,
            timeout: float,
            allow_refusal_detail: bool = False,
        ) -> RegisteredOperationCompletion[ResultT]:
            completed = run_registered_operation(
                client,
                payload,
                definition_id=definition_id,
                subject_ref=subject_ref,
                result_type=result_type,
                request_version=request_version,
                result_version=result_version,
                timeout=timeout,
                allow_refusal_detail=allow_refusal_detail,
            )
            if definition_id == AUTH_CONFIGURE_OPERATION_DEFINITION_ID:
                observed.append(
                    (
                        definition_id,
                        completed.terminal_condition,
                        completed.effect,
                        completed.refusal_code,
                        completed.projection,
                    )
                )
            return completed

        monkeypatch.setattr(configure_bridge, "run_registered_operation", observe_completion)
        configured = _invoke(
            profile,
            "config",
            "auth",
            "configure",
            "--provider",
            "certificate",
            "--file",
            str(certificate),
        )
        assert configured.exit_code == 0, (configured.output, observations)
        raised = tuple(item for item in observations if item.exception_type is not None)
        assert raised == (), (configured.output, raised)
        payload = unwrap_cli_result(configured)
        assert payload["provider"] == "certificate"
        assert payload["file"] == str(certificate)
        assert payload["complete"] is True

        assert len(observed) == 1
        definition_id, condition, effect, refusal_code, projection = observed[0]
        assert definition_id == AUTH_CONFIGURE_OPERATION_DEFINITION_ID
        assert condition is OperationTerminalCondition.SUCCEEDED
        assert effect is OperationEffect.UPDATED
        assert refusal_code is None
        assert isinstance(projection, AuthConfigureOperationProjection)
        assert projection.profile_id == active_profile_id

        status = _invoke(profile, "config", "auth", "status")
        assert status.exit_code == 0, (status.output, observations)
        status_payload = unwrap_cli_result(status)
        assert status_payload["provider"] == "certificate"
        assert status_payload["certificate_path"] == str(certificate)
