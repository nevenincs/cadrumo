"""Run one CLI command for a native profile fixture through the profile password channel."""

from __future__ import annotations

import json

from click.testing import Result

from cadrumo.core.config import override_settings

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture
from .cli_runner import invoke_cached_cli


def invoke_native_profile_cli(fixture: NativeCliProfileFixture, *command: str) -> Result:
    """Run ``command`` as the fixture's profile with identifiers hidden, refusing a password in the output."""
    assert fixture.label is not None
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            ("--format", "json", "--profile", fixture.label, "--profile-secrets-stdin", *command),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result
