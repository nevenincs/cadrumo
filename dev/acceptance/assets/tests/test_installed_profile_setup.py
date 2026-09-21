"""Focused safety checks for ASSETS-01 installed CLI profile setup."""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import pytest
from dev.acceptance.assets.installed_profile_setup import _run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_cli_command_closes_secret_pipe_and_keeps_it_out_of_the_receipt(tmp_path: Path) -> None:
    """The scripted CLI channel receives EOF while receipts retain only hashes."""
    secret = f"assets-{secrets.token_urlsafe(24)}"

    receipt = _run_command(
        command="profile_create",
        executable=Path(sys.executable),
        launcher_prefix=("-m", "dev.acceptance.assets.tests.installed_profile_setup_fixture"),
        argv=("--format", "json", "config", "profile", "create"),
        stdin_payload=json.dumps({"passphrase": secret, "passphrase_confirmation": secret}).encode("utf-8"),
        workspace_root=Path.cwd(),
        storage_root=tmp_path / "storage",
        timeout_seconds=5.0,
    )

    assert receipt.return_code == 0
    assert receipt.timed_out is False
    assert receipt.cleanup == "not_needed"
    assert receipt.response_status == "ok"
    assert receipt.setup_state == "complete"
    assert receipt.configured is True
    assert secret not in json.dumps(receipt.to_dict())
