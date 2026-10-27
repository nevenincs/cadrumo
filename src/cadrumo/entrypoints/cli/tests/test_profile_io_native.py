"""Isolated native profile read/write/read benchmark journey with synthetic facts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(profile: RegisteredCliProfile, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_joined_cli(
        ["--language", "en", "--profile", profile.label, "--profile-secrets-stdin", "--format", "json", *command],
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    assert result.exit_code == 0, type(result.exception).__name__
    return result


def test_native_profile_read_write_read(tmp_path: Path) -> None:
    """Each CLI invocation reauthenticates; final read verifies durable replacement."""
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(
            label="benchmark-profile-io",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Profile Benchmark",
                "activities.description": "synthetic benchmark",
                "contact.postcode": "08001",
            },
        )
        before = _invoke(profile, "config", "profile", "view")
        assert "08001" in before.output
        _invoke(profile, "config", "profile", "edit", "--quiet", "--address-postcode", "28010")
        after = _invoke(profile, "config", "profile", "view")
        assert "28010" in after.output
        assert "08001" not in after.output
