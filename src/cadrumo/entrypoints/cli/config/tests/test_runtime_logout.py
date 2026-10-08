"""Global CLI sign-out revokes human access while preserving profile selection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.sign_in import (
    RuntimeHumanSignedOut,
    RuntimeSignInStatusReply,
    SignInPresence,
    SignInStatus,
)
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.application.user_profile.profile_pointer import (
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)
from cadrumo.core.bucket_pointer import pointer_path
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Client:
    """Controlled transport boundary; selection and CLI projection remain real."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.calls: list[str] = []
        self.on_logout: Callable[[], None] | None = None

    def human_sign_out(self) -> RuntimeHumanSignedOut:
        self.calls.append("sign_out")
        if self.on_logout is not None:
            self.on_logout()
        return RuntimeHumanSignedOut(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=self.profile_id,
            session_ids=(),
            receipt_removed=True,
            keychain_removed=True,
            automation_enabled=True,
        )

    def sign_in_status(self) -> RuntimeSignInStatusReply:
        self.calls.append("status")
        return RuntimeSignInStatusReply(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=self.profile_id,
            status=SignInStatus(presence=SignInPresence.ABSENT),
        )

    def close(self) -> None:
        self.calls.append("close")


def _install_client(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    async def open_client(*, profile_id: UUID, frontend: OperationFrontendProjection) -> _Client:
        assert profile_id == client.profile_id
        assert frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr("cadrumo.adapters.local_runtime.runtime_client.open_installed_runtime_client", open_client)


def _logout() -> dict[str, object]:
    result = invoke_cached_cli(("--format", "json", "config", "logout"))
    assert result.exit_code == 0, result.output
    payload = TypeAdapter(dict[str, object]).validate_json(result.stdout)
    assert payload["command"] == "config.logout"
    return payload


def test_logout_retains_selection_and_status_queries_the_same_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = UUID(register_cli_profile(label="Selected profile", log_in=False))
    client = _Client(profile_id)
    _install_client(monkeypatch, client)
    captured = observe_active_profile_pointer()
    payload = _logout()
    assert payload["result"] == {
        "logged_out_profile": CLI_PROFILE_ID_PLACEHOLDER,
        "already_logged_out": False,
        "scope": "profile_human_access",
        "human_receipt_revoked": True,
        "receipt_removed": True,
        "keychain_removed": True,
        "automation_enabled": True,
        "automation_revoked": False,
    }
    assert observe_active_profile_pointer() == captured
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(("--format", "json", "config", "sign-in-status"))
    assert result.exit_code == 0, result.output
    status = TypeAdapter(dict[str, object]).validate_json(result.stdout)["result"]
    assert isinstance(status, dict)
    assert status["profile_id"] == str(profile_id)
    assert status["status"] == {"presence": "absent", "idle_deadline": None, "absolute_deadline": None}
    assert client.calls == ["sign_out", "close", "status", "close"]


def test_logout_does_not_overwrite_concurrent_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    first = register_cli_profile(label="First profile", log_in=False)
    second = register_cli_profile(label="Second profile", log_in=False)
    with active_profile_pointer_transaction() as pointer:
        pointer.compare_and_select(expected=pointer.read(), bucket_id=first)
    client = _Client(UUID(first))
    _install_client(monkeypatch, client)

    def select_other() -> None:
        with active_profile_pointer_transaction() as pointer:
            pointer.compare_and_select(expected=pointer.read(), bucket_id=second)

    client.on_logout = select_other
    assert _logout()["result"] is not None
    assert observe_active_profile_pointer().bucket_id == second
    assert client.calls == ["sign_out", "close"]


def test_logout_missing_human_proof_refuses_and_keeps_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = UUID(register_cli_profile(label="No human proof", log_in=False))
    client = _Client(profile_id)
    _install_client(monkeypatch, client)
    captured = observe_active_profile_pointer()

    def refuse() -> None:
        raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)

    client.on_logout = refuse
    result = invoke_cached_cli(("--format", "json", "config", "logout"))
    assert result.exit_code != 0
    assert observe_active_profile_pointer() == captured
    assert client.calls == ["sign_out", "close"]
    assert '"already_logged_out": true' not in result.output


def test_logout_refuses_corrupt_default_without_claiming_idempotence(_isolated_cli_backend: Path) -> None:
    root = _isolated_cli_backend
    root.mkdir(exist_ok=True)
    corrupt = b"not = valid = toml"
    pointer_path(root).write_bytes(corrupt)
    result = invoke_cached_cli(("--format", "json", "config", "logout"))
    assert result.exit_code != 0
    assert pointer_path(root).read_bytes() == corrupt
    assert '"already_logged_out": true' not in result.output
