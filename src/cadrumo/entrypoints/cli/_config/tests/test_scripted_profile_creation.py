"""Real-behaviour tests for non-interactive ``config profile create``.

The scripted arm of ``create`` had no creation path: it fell through to the
setup flow, whose ``create`` mode refuses because the flow is not a creation
authority. These drive the real verb against a real storage root, through the
real registration door, and assert a real encrypted profile exists afterwards.
No mocks, no stubs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "a-sufficiently-long-operator-passphrase"


def _storage_overrides(tmp_path: Path, *, passphrase: str | None) -> dict[str, object]:
    return {
        "cadrumo_local_storage_root": tmp_path / "cadrumo-storage",
        "cadrumo_secret_passphrase": passphrase,
    }


def test_scripted_create_registers_a_real_profile(tmp_path: Path) -> None:
    """``create NAME --quiet`` brings a real, listable profile into existence."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created = invoke_cached_cli(("--format", "json", "config", "profile", "create", "Scripted Operator", "--quiet"))

        assert created.exit_code == 0, created.output
        document = json.loads(created.stdout)
        assert document["result"]["profile_name"] == "Scripted Operator"
        assert document["result"]["status"] == "created"

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert listed.exit_code == 0, listed.output
    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Scripted Operator"]
    assert profiles[0]["active"] is True
    # The bucket identifier is the profile UUID, and it reaches the operator
    # surface through the envelope's redaction funnel rather than raw.
    assert profiles[0]["bucket_id"] == "<bucket-id>"


def test_a_scripted_profile_warns_that_recovery_was_not_enrolled(tmp_path: Path) -> None:
    """A run with no terminal enrolls no recovery, and SAYS so.

    Recovery can only be installed while the capsule is being published, so an
    operator who is not told at creation is never told at all -- they would
    hold a profile whose passphrase is the single point of failure and believe
    otherwise. The warning is the whole protection, and the 24 words must not
    appear anywhere in the machine output.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        created = invoke_cached_cli(("--format", "json", "config", "profile", "create", "No Terminal", "--quiet"))

    assert created.exit_code == 0, created.output
    document = json.loads(created.stdout)
    codes = [notice["code"] for notice in document["notices"]]
    assert "PROFILE_RECOVERY_NOT_ENROLLED" in codes
    # The envelope must never be the transport for recovery material, whether
    # or not a wrapper was minted.
    assert "mnemonic" not in created.stdout.lower()


def test_scripted_create_refuses_when_no_passphrase_channel_is_available(tmp_path: Path) -> None:
    """With no console and no configured secret, creation refuses rather than inventing one.

    The refusal is the whole protection: a profile created under a passphrase
    the operator never chose is unopenable by them and indistinguishable from
    one they did choose.
    """
    with override_settings(**_storage_overrides(tmp_path, passphrase=None)):
        result = invoke_cached_cli(("config", "profile", "create", "No Channel", "--quiet"))

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_refuses_a_blank_name(tmp_path: Path) -> None:
    """A blank subject is refused before any credential is consumed."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        result = invoke_cached_cli(("config", "profile", "create", "   ", "--quiet"))

        assert result.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert json.loads(listed.stdout)["result"]["profiles"] == []


def test_scripted_create_is_refused_for_a_duplicate_label(tmp_path: Path) -> None:
    """The second create under one label refuses and leaves the first intact."""
    with override_settings(**_storage_overrides(tmp_path, passphrase=_PASSPHRASE)):
        first = invoke_cached_cli(("config", "profile", "create", "Only One", "--quiet"))
        assert first.exit_code == 0, first.output

        second = invoke_cached_cli(("config", "profile", "create", "Only One", "--quiet"))
        assert second.exit_code != 0

        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    profiles = json.loads(listed.stdout)["result"]["profiles"]
    assert [profile["name"] for profile in profiles] == ["Only One"]
