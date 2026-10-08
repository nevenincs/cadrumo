"""A test-owned native worker and encrypted profile for export acceptance."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope


@pytest.fixture
def native_review_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Register an isolated synthetic profile and its owned native runtime."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="Synthetic saved export acceptance", facts={})
        yield profile


def invoke_native_review(profile: NativeCliProfileFixture, command: Sequence[str]) -> Result:
    """Authenticate through the CLI's protected channel and run the actual parser."""
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            ["--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command],
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result
