"""Global CLI sign-out revokes human access while preserving profile selection."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from pydantic import TypeAdapter

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend as _isolated_cli_backend
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.application.user_profile.profile_pointer import (
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)
from cadrumo.core.bucket_pointer import pointer_path
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from cadrumo_client.contracts.sign_in import HumanSignedOut, SignInPresence, SignInStatus, SignInStatusReply
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

__all__ = ["_isolated_cli_backend"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREDENTIAL_INPUT = "a-sufficiently-long-operator-passphrase"


class _Client:
    """Controlled transport boundary; selection and CLI projection remain real."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.calls: list[str] = []
        self.on_logout: Callable[[], None] | None = None
        self.receipt_refusal: Exception | None = None
        self.signed_in = False
        self.proofs: list[bytes] = []

    def human_sign_out(self) -> HumanSignedOut:
        self.calls.append("sign_out")
        if not self.signed_in and self.receipt_refusal is not None:
            # As the real client does: with no session it resumes the stored sign-in, and none resumes.
            raise self.receipt_refusal
        if self.on_logout is not None:
            self.on_logout()
        return HumanSignedOut(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=self.profile_id,
            session_ids=(),
            receipt_removed=True,
            keychain_removed=True,
            automation_enabled=True,
            automation_access_remains=False,
        )

    def resume_receipt(self) -> None:
        self.calls.append("resume")
        if self.receipt_refusal is not None:
            raise self.receipt_refusal
        self.signed_in = True

    def login_password(self, secret: bytearray, *, persist_receipt: bool) -> None:
        assert not persist_receipt
        self.calls.append("password")
        self.proofs.append(bytes(secret))
        self.signed_in = True

    def sign_in_status(self) -> SignInStatusReply:
        self.calls.append("status")
        return SignInStatusReply(
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

    monkeypatch.setattr("cadrumo_client.transport.installed_client.open_installed_client", open_client)


def _logout(run_cadrumo_cli: Callable[..., Result]) -> dict[str, object]:
    result = run_cadrumo_cli(("--format", "json", "config", "logout"))
    assert result.exit_code == 0, result.output
    payload = TypeAdapter(dict[str, object]).validate_json(result.stdout)
    assert payload["command"] == "config.logout"
    return payload


def test_logout_retains_selection(monkeypatch: pytest.MonkeyPatch, run_cadrumo_cli: Callable[..., Result]) -> None:
    profile_id = UUID(register_cli_profile(label="Selected profile", log_in=False))
    client = _Client(profile_id)
    _install_client(monkeypatch, client)
    captured = observe_active_profile_pointer()
    payload = _logout(run_cadrumo_cli)
    assert payload["result"] == {
        "logged_out_profile": CLI_PROFILE_ID_PLACEHOLDER,
        "already_logged_out": False,
        "scope": "profile_human_access",
        "human_receipt_revoked": True,
        "receipt_removed": True,
        "keychain_removed": True,
        "automation_enabled": True,
        "automation_access_remains": False,
        "automation_revoked": False,
    }
    assert observe_active_profile_pointer() == captured
    assert client.calls == ["sign_out", "close"]


def test_logout_does_not_overwrite_concurrent_selection(
    monkeypatch: pytest.MonkeyPatch, run_cadrumo_cli: Callable[..., Result]
) -> None:
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
    assert _logout(run_cadrumo_cli)["result"] is not None
    assert observe_active_profile_pointer().bucket_id == second
    assert client.calls == ["sign_out", "close"]


def test_logout_missing_human_proof_refuses_and_keeps_selection(
    monkeypatch: pytest.MonkeyPatch, run_cadrumo_cli: Callable[..., Result]
) -> None:
    profile_id = UUID(register_cli_profile(label="No human proof", log_in=False))
    client = _Client(profile_id)
    _install_client(monkeypatch, client)
    captured = observe_active_profile_pointer()

    def refuse() -> None:
        raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)

    client.on_logout = refuse
    result = run_cadrumo_cli(("--format", "json", "config", "logout"))
    assert result.exit_code != 0
    assert observe_active_profile_pointer() == captured
    assert client.calls == ["sign_out", "close"]
    assert '"already_logged_out": true' not in result.output
    with override_settings(cadrumo_output_language=OutputLanguage.EN):
        expected = tr("cli.config.errors.profile_session_logout_unproven", locale="en")
    assert expected in result.output


def test_logout_refuses_corrupt_default_without_claiming_idempotence(
    _isolated_cli_backend: Path, run_cadrumo_cli: Callable[..., Result]
) -> None:
    root = _isolated_cli_backend
    root.mkdir(exist_ok=True)
    corrupt = b"not = valid = toml"
    pointer_path(root).write_bytes(corrupt)
    result = run_cadrumo_cli(("--format", "json", "config", "logout"))
    assert result.exit_code != 0
    assert pointer_path(root).read_bytes() == corrupt
    assert '"already_logged_out": true' not in result.output


@pytest.mark.parametrize(
    "refusal",
    [
        None,
        ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT),
        # A denial the receipt refusals do not name still leaves the password to prove the person.
        FrontendRefusedError("operation_denied"),
    ],
    ids=["receipt_resumes", "no_receipt", "unmapped_refusal"],
)
def test_logout_proves_the_person_by_a_stored_sign_in_before_the_password(
    monkeypatch: pytest.MonkeyPatch, run_cadrumo_cli: Callable[..., Result], refusal: Exception | None
) -> None:
    """The password is the fallback proof: it signs in only when no stored sign-in resumes."""
    profile_id = UUID(register_cli_profile(label="Held sign-in", log_in=False))
    client = _Client(profile_id)
    client.receipt_refusal = refusal
    _install_client(monkeypatch, client)
    result = run_cadrumo_cli(
        ("--format", "json", "config", "logout", "--secrets-stdin"),
        input=json.dumps({"passphrase": _CREDENTIAL_INPUT}),
    )
    assert result.exit_code == 0, result.output
    assert _CREDENTIAL_INPUT not in result.output
    if refusal is None:
        assert client.calls == ["resume", "sign_out", "close"]
        assert client.proofs == []
    else:
        assert client.calls == ["resume", "password", "sign_out", "close"]
        assert client.proofs == [_CREDENTIAL_INPUT.encode()]
