"""Phone-state reporting through the registered encrypted-profile worker."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from cadrumo.application.auth.diagnostics import AuthDiagnosticPhoneState
from cadrumo.core.config import Settings
from cadrumo.core.hashing import canonical_json_bytes

from ...tests.diagnostics_native_support import diagnostics_native_profile, invoke_diagnostics_cli
from ...tests.runtime_profile_cli_fixture import NativeCliProfileFixture
from .runtime_cli import unwrap_cli_result

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]

__all__ = ["diagnostics_native_profile"]


def test_report_updates_only_the_bound_profiles_encrypted_diagnostic(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    diagnostic_id = "native-report-001"
    captured_at = datetime.now(UTC)
    external = Settings.external_constants().aeat
    url = external.clave_movil.selector_access_url_template.format(
        target=f"{external.domains.sede}{external.sede_paths.expedientes_resumen}",
    )
    payload = canonical_json_bytes(
        {
            "diagnostic_id": diagnostic_id,
            "reason": "native-worker-report-test",
            "url": url,
            "captured_at": captured_at.isoformat(),
        },
    )
    build_auth_diagnostic_persistence().save_record(diagnostic_id, payload, written_at=captured_at)

    reported = invoke_diagnostics_cli(
        [
            "--format",
            "json",
            "config",
            "auth",
            "diagnostics",
            "report",
            diagnostic_id,
            "--phone-state",
            AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value,
        ],
    )
    assert reported.exit_code == 0, reported.output
    result = unwrap_cli_result(reported)
    assert result["diagnostic_id"] == diagnostic_id
    assert result["phone_state"] == AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value
    reported_at_value = result["reported_at"]
    assert isinstance(reported_at_value, str)
    reported_at = datetime.fromisoformat(reported_at_value)
    assert reported_at.tzinfo is not None

    shown = invoke_diagnostics_cli(
        ["--format", "json", "config", "auth", "diagnostics", "view", diagnostic_id],
    )
    assert shown.exit_code == 0, shown.output
    detail = unwrap_cli_result(shown)
    assert detail["diagnostic_id"] == diagnostic_id
    assert detail["phone_state"] == AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value
    assert detail["phone_state_source"] == "operator_report"
    reported_at_detail = detail["phone_state_reported_at"]
    assert isinstance(reported_at_detail, str)
    assert datetime.fromisoformat(reported_at_detail) == reported_at

    missing = invoke_diagnostics_cli(
        [
            "config",
            "auth",
            "diagnostics",
            "report",
            "missing-native-report",
            "--phone-state",
            AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value,
        ],
    )
    assert missing.exit_code != 0, missing.output
    assert "Auth diagnostic not found" in missing.output, missing.output
    assert "Traceback" not in missing.output
