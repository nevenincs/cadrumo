"""CLI logout clears selection without revoking independent runtime access."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, committed_sign_in
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.bucket_pointer import pointer_path, resolve_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_CREDENTIAL = "runtime-logout-test-passphrase"


class _KeyringError(Exception):
    """An exact test credential-store failure type."""


class _Keyring:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.entries.pop((service_name, username), None)


def _logout() -> dict[str, object]:
    result = invoke_cached_cli(("--format", "json", "config", "logout"))
    assert result.exit_code == 0, result.output
    payload = TypeAdapter(dict[str, object]).validate_json(result.stdout)
    assert payload["command"] == "config.logout"
    return payload


def test_logout_clears_only_captured_default_and_preserves_other_access(tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as patcher, isolated_profile_storage_root(tmp_path=tmp_path) as root:
        keyring = _Keyring()
        patcher.setattr(receipt, "_keyring", lambda: (keyring, _KeyringError, _KeyringError))
        with override_settings(cadrumo_output_language="en"):
            create, decode = profile_authority_contexts()
            first = register_profile_with_credentials(
                label="Default profile",
                passphrase=_PROFILE_CREDENTIAL,
                profile_create_context=create,
                profile_decode_context=decode,
            )
            second = register_profile_with_credentials(
                label="Other live profile",
                passphrase=_PROFILE_CREDENTIAL,
                profile_create_context=create,
                profile_decode_context=decode,
            )
            other_id = UUID(second.profile_id)
            active = current_active_bucket_session()
            assert active is not None and active.bucket_id == second.profile_id
            material = load_committed_profile_password_material(other_id, root=root)
            stored = receipt.mint_profile_session(
                storage_root=root,
                profile_id=other_id,
                custody_generation=material.envelope.password_generation,
                dek_epoch=material.envelope.dek_epoch,
                dek=active.dek,
                now=active.opened_at,
                idle_minutes=15,
                absolute_minutes=240,
                login_id=RECEIPT_LOGIN_ID,
                sign_in=committed_sign_in(root, other_id),
            )
            other_path = receipt.profile_session_path(storage_root=root, profile_id=other_id)
            original_receipt = other_path.read_bytes()
            account = (receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{other_id}:{stored.session_id}")
            original_key = keyring.entries[account]

            with active_profile_pointer_transaction() as pointer:
                pointer.compare_and_select(expected=pointer.read(), bucket_id=first.profile_id)
            assert resolve_active_bucket_id() == first.profile_id

            cleared = _logout()
            result = cleared["result"]
            assert isinstance(result, dict)
            assert result == {
                "logged_out_profile": CLI_PROFILE_ID_PLACEHOLDER,
                "already_logged_out": False,
                "scope": "cli_context",
                "human_receipt_revoked": False,
                "automation_revoked": False,
            }
            notices = cleared["notices"]
            assert isinstance(notices, list)
            assert "config.logout.remaining_access" in {notice["code"] for notice in notices}
            assert resolve_active_bucket_id() is None
            assert current_active_bucket_session() is active and not active.sealed
            assert other_path.read_bytes() == original_receipt
            assert keyring.entries[account] == original_key

            repeated = _logout()
            repeat = repeated["result"]
            assert isinstance(repeat, dict)
            assert repeat["already_logged_out"] is True
            assert repeat["logged_out_profile"] is None
            assert resolve_active_bucket_id() is None
            assert other_path.read_bytes() == original_receipt


def test_logout_refuses_corrupt_default_without_claiming_idempotence(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root, override_settings(cadrumo_output_language="en"):
        root.mkdir()
        corrupt = b"not = valid = toml"
        pointer_path(root).write_bytes(corrupt)
        result = invoke_cached_cli(("--format", "json", "config", "logout"))
        assert result.exit_code != 0
        assert pointer_path(root).read_bytes() == corrupt
        assert '"already_logged_out": true' not in result.output
