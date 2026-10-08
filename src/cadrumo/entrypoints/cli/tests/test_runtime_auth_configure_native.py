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
from ....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....tests.cli_envelope import unwrap_cli_result
from ..config import runtime_auth_configure as configure_bridge
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..runtime_registered_operation import run_registered_operation
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, RuntimeFailureObservation, native_cli_profile_scope

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
        assert payload["changed"] is True
        assert payload["certificate_file_provided"] is True
        assert payload["complete"] is True
        # The public result never carries the private certificate location.
        assert "file" not in payload
        assert str(certificate) not in configured.stdout
        assert certificate.name not in configured.stdout

        assert len(observed) == 1
        definition_id, condition, effect, refusal_code, projection = observed[0]
        assert definition_id == AUTH_CONFIGURE_OPERATION_DEFINITION_ID
        assert condition is OperationTerminalCondition.SUCCEEDED
        assert effect is OperationEffect.UPDATED
        assert refusal_code is None
        assert isinstance(projection, AuthConfigurePublicResultV2)
        assert projection.profile_id == active_profile_id

        # Selecting the configuration already recorded writes nothing.
        repeated = _invoke(
            profile,
            "config",
            "auth",
            "configure",
            "--provider",
            "certificate",
            "--file",
            str(certificate),
        )
        assert repeated.exit_code == 0, (repeated.output, observations)
        assert unwrap_cli_result(repeated)["changed"] is False
        assert observed[-1][2] is OperationEffect.NONE

        status = _invoke(profile, "config", "auth", "status")
        assert status.exit_code == 0, (status.output, observations)
        status_payload = unwrap_cli_result(status)
        assert status_payload["provider"] == "certificate"
        assert status_payload["certificate_path"] == str(certificate)


def test_native_cli_auth_configure_records_the_clave_movil_route_and_refuses_unknown_choices(tmp_path: Path) -> None:
    """A route is saved with its provider, and an invalid choice is refused without being echoed."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-auth-route",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Auth Route",
                "identity.tax_id": "12345678Z",
                "auth.dni_nie": "87654321X",
                "activities.description": "synthetic test profile",
            },
        )
        invalid = "secret-auth-choice-must-not-appear"
        refused = _invoke(profile, "config", "auth", "configure", "--provider", invalid)
        assert refused.exit_code != 0
        assert invalid not in refused.output

        configured = _invoke(
            profile, "config", "auth", "configure", "--provider", "clave_movil", "--clave-movil-route", "qr"
        )
        assert configured.exit_code == 0, configured.output
        payload = unwrap_cli_result(configured)
        assert payload["provider"] == "clave_movil"
        # The two identities disagree; the result says so without naming either.
        assert payload["identity_alignment"] == "mismatch"
        assert payload["complete"] is False
        assert payload["precondition_action"]["failed_condition_id"] == "auth.clave_movil.identity_aligned"
        assert "12345678Z" not in configured.stdout
        assert "87654321X" not in configured.stdout

        status = _invoke(profile, "config", "auth", "status")
        assert status.exit_code == 0, status.output
        assert unwrap_cli_result(status)["provider"] == "clave_movil"
