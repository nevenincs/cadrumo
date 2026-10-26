"""The Modelo 360 commands sign in through the runtime, as every other profile command does, and run in its worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo.tests.cli_envelope import require_error_document, unwrap_cli_result
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    native_cli_profile_scope,
)

from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(profile: NativeCliProfileFixture, passphrase: str, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
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
            input=json.dumps({"profile_passphrase": passphrase}),
        )
    assert passphrase not in result.output
    return result


def test_m360_commands_sign_in_through_the_runtime_and_refuse_a_wrong_password(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-m360-operation", facts={})

        listed = unwrap_cli_result(_invoke(profile, profile.passphrase, "app", "modelo", "m360", "list"))
        absent = _invoke(profile, profile.passphrase, "app", "modelo", "m360", "remove", "2025")
        refused = _invoke(profile, "not-the-passphrase-of-this-profile", "app", "modelo", "m360", "list")

    assert listed["solicitudes"] == []
    # The worker refused to remove a solicitud that was never declared, with its registered refusal.
    absent_error = require_error_document(absent.output)["error"]
    assert absent_error["code"] == "REFUSED_MODELO_360_SOLICITUD"
    assert absent_error["context"]["terminal_condition"] == "refused"
    # The runtime refused the password: the sign-in refusal set's own reason reaches the command line.
    error = require_error_document(refused.output)["error"]
    assert error["context"]["reason"] == "credential_rejected"
    assert error["context"]["sign_in_reason"] == "credential_rejected"
