"""Real encrypted-profile worker support for app diagnostics CLI tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo.tests.cli_fixture_ports import CliInvocation

from .config.runtime_cli import invoke_runtime_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

_ACTIVE_PROFILE: ContextVar[NativeCliProfileFixture | None] = ContextVar("diagnostics_native_profile", default=None)


@pytest.fixture
def diagnostics_native_profile(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[NativeCliProfileFixture]:
    """Register one synthetic encrypted profile and serve it through a native worker."""
    with native_cli_profile_scope(tmp_path) as profile:
        label = f"diagnostics-{request.node.name[:24]}"
        profile.register(label=label, facts={})
        token = _ACTIVE_PROFILE.set(profile)
        try:
            yield profile
        finally:
            _ACTIVE_PROFILE.reset(token)


def invoke_diagnostics_cli(
    args: list[str],
    *,
    profile: NativeCliProfileFixture | None = None,
    invoke_cli: CliInvocation = invoke_runtime_cli,
) -> Result:
    """Run the supplied command graph through exact-profile native admission."""
    profile = profile or _ACTIVE_PROFILE.get()
    if profile is None:
        return invoke_cli(args)
    if profile.label is None:
        raise AssertionError("native diagnostics profile was not registered")
    close_active_bucket_session()
    with override_settings(cadrumo_output_language="en"):
        result = invoke_cli(
            ("--profile", profile.label, "--profile-secrets-stdin", *args),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    if profile.passphrase in result.output:
        pytest.fail("profile passphrase appeared in app diagnostics CLI output", pytrace=False)
    return result


__all__ = ["diagnostics_native_profile", "invoke_diagnostics_cli"]
