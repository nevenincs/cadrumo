"""Complete workstation check report through the encrypted profile worker."""

from __future__ import annotations

import json
import sys
from uuid import UUID

import pytest

from .....application.user_profile.login_session import resolve_login_target
from .....core.capabilities import ServiceCapability
from .....core.config import override_settings
from .....tests.cli_envelope import unwrap_cli_result
from ...tests.diagnostics_native_support import (
    diagnostics_native_profile as diagnostics_native_profile,
)
from ...tests.diagnostics_native_support import (
    invoke_diagnostics_cli,
)
from ...tests.runtime_profile_cli_fixture import NativeCliProfileFixture
from ..check_payloads import ConfigCheckResult

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]
__all__ = ["diagnostics_native_profile"]


def test_config_check_preserves_the_full_worker_report_and_text_rows(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """The authenticated read retains complete rows, typed actions, and exit behavior."""
    assert diagnostics_native_profile.label is not None
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        json_result = invoke_diagnostics_cli(["--format", "json", "config", "check"])
    assert json_result.exit_code in (0, 2), json_result.output
    payload = unwrap_cli_result(json_result)
    ConfigCheckResult.model_validate_json(json.dumps(payload))

    profile_id = UUID(str(payload["profile_id"]))
    assert str(profile_id) == payload["profile_id"]
    assert str(profile_id) == resolve_login_target(diagnostics_native_profile.label).bucket_id
    assert set(row["capability"] for row in payload["capabilities"]) == {
        capability.value for capability in ServiceCapability
    }
    dependency_rows = {row["service"]: row for row in payload["dependencies"]}
    assert {"local-inference-hardware", "local-inference-contention"} <= set(dependency_rows)
    assert "local-reader:vision_transcription" in dependency_rows
    assert "model-runtime-hardware-floor" in dependency_rows
    assert "playwright-chromium" in dependency_rows
    assert {"extra:google", "extra:browser", "extra:anthropic"} <= set(dependency_rows)

    preflight_rows = {row["check"]: row for row in payload["preflight"]}
    assert {
        "auth-provider:certificate",
        "auth-provider:clave_movil",
        "storage:local-root",
        "corpus:normatives",
        "corpus:manuals",
        "env:configuration",
    } <= set(preflight_rows)
    for row in payload["preflight"]:
        assert set(row) == {"check", "healthy", "severity", "facts", "precondition_action"}
        if row["healthy"]:
            assert row["precondition_action"] is None
        else:
            assert row["precondition_action"] is not None
    assert json_result.exit_code == (0 if payload["ok"] else 2)
    assert all("storage:" not in str(issue) and "registry:" not in str(issue) for issue in payload["issues"])

    text_result = invoke_diagnostics_cli(["--format", "text", "config", "check"])
    assert text_result.exit_code in (0, 2), text_result.output
    assert "profile\t<profile-id>" in text_result.output
    assert "Capability\t" in text_result.output
    assert "Dependency\t" in text_result.output
    assert all(f"\t{row['check']}\t" in text_result.output for row in payload["preflight"])
