"""Shared invocation and encrypted-state access for native profile CLI tests."""

from __future__ import annotations

import json

from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.login_session import authenticate_profile_for_invocation
from ....core.config import override_settings
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture

__all__ = ["invoke_native_cli", "reauthenticate_native_profile"]


def reauthenticate_native_profile(
    profile: NativeCliProfileFixture,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> str:
    """Unlock the encrypted profile using its held authority decode context."""
    assert profile.label is not None
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    return login.bucket_id


def invoke_native_cli(
    profile: NativeCliProfileFixture,
    *command: str,
    output_format: str | None = "json",
) -> Result:
    """Invoke a real CLI command through the registered native profile worker."""
    assert profile.label is not None
    close_active_bucket_session()
    arguments = ["--language", "en"]
    if output_format is not None:
        arguments.extend(("--format", output_format))
    arguments.extend(("--profile", profile.label, "--profile-secrets-stdin", *command))
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            arguments,
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result
