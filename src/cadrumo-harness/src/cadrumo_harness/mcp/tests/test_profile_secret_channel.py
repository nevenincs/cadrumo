"""Security gates for the MCP server's one-shot local profile-secret channel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .._profile_secret_channel import (
    clear_profile_secret,
    load_profile_secret_file,
    profile_secret_stdin_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _clear_channel() -> None:
    clear_profile_secret()


def test_channel_consumes_unlinks_and_frames_the_commandspec_fields(tmp_path: Path) -> None:
    channel = tmp_path / "profile-secret.json"
    channel.write_text(json.dumps({"profile_passphrase": "local-only"}), encoding="utf-8")
    load_profile_secret_file(channel)
    assert not channel.exists()
    assert json.loads(profile_secret_stdin_payload() or "null") == {"profile_passphrase": "local-only"}


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"not-json",
        b"{}",
        b'{"profile_passphrase":"ok","extra":"forbidden"}',
        b'{"profile_passphrase":7}',
    ),
)
def test_channel_fails_closed_on_malformed_or_unexpected_payloads(tmp_path: Path, payload: bytes) -> None:
    channel = tmp_path / "profile-secret.json"
    channel.write_bytes(payload)
    with pytest.raises(RuntimeError):
        load_profile_secret_file(channel)
    assert not channel.exists()
    assert profile_secret_stdin_payload() is None
