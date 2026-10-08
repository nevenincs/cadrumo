"""CLI rotation projects the runtime completion without retaining its proofs."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import typer
from pydantic import SecretStr
from typer.core import TyperCommand

from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError
from cadrumo.application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo.entrypoints.cli.config import passphrase
from cadrumo.entrypoints.cli.config_payloads import ConfigPassphraseChangeResult
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Client:
    """Explicit transport fault port; this test does not claim native admission."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.proof: bytearray | None = None
        self.closed = False
        self.fail_close = False

    def login_password(self, secret: bytearray) -> None:
        self.proof = secret

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("synthetic close refusal")


def _context() -> typer.Context:
    return typer.Context(TyperCommand("passphrase-change"), obj={"format": "json"})


@pytest.mark.parametrize("close_fails", [False, True])
def test_runtime_change_uses_exact_target_and_wipes_all_buffers(
    monkeypatch: pytest.MonkeyPatch, close_fails: bool
) -> None:
    profile_id = uuid4()
    clients: list[_Client] = []
    captured: dict[str, object] = {}
    buffers: list[bytearray] = []

    def open_client(target: UUID, _ctx: typer.Context) -> _Client:
        assert target == profile_id
        client = _Client(target)
        if not clients:
            client.fail_close = close_fails
        clients.append(client)
        return client

    def run_rotation(
        client: _Client,
        *,
        current_passphrase: bytearray,
        new_passphrase: bytearray,
        new_passphrase_confirmation: bytearray,
        fresh_client: Callable[[], _Client],
    ) -> SimpleNamespace:
        assert client is clients[0]
        assert bytes(current_passphrase) == b"current-secret"
        assert bytes(new_passphrase) == b"replacement-secret"
        assert bytes(new_passphrase_confirmation) == b"replacement-secret"
        buffers.extend((current_passphrase, new_passphrase, new_passphrase_confirmation))
        successor = fresh_client()
        assert successor is clients[1] and successor is not client
        successor.close()
        return SimpleNamespace(
            outcome=ProfilePassphraseRotationOutcome(
                profile_id=str(profile_id),
                password_generation=2,
                dek_epoch_preserved=True,
                recovery_enrollment_retained=False,
            )
        )

    monkeypatch.setattr(passphrase, "_resolve_active_bucket_id", lambda: str(profile_id))
    monkeypatch.setattr(
        passphrase,
        "_collect_passphrases",
        lambda **_kwargs: passphrase.PassphraseChangeSecrets(
            current_passphrase=SecretStr("current-secret"),
            new_passphrase=SecretStr("replacement-secret"),
            new_passphrase_confirmation=SecretStr("replacement-secret"),
        ),
    )
    monkeypatch.setattr(passphrase, "_open_rotation_client", open_client)
    monkeypatch.setattr(passphrase, "run_profile_password_rotation", run_rotation)
    monkeypatch.setattr(passphrase, "_activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(passphrase, "emit_envelope", lambda *_args, **kwargs: captured.update(kwargs))

    if close_fails:
        with pytest.raises(OSError, match="synthetic close refusal"):
            passphrase.passphrase_change(_context())
    else:
        passphrase.passphrase_change(_context())

    assert len(clients) == 2 and all(client.closed for client in clients)
    assert clients[0].proof is not None and set(clients[0].proof) == {0}
    assert len(buffers) == 3 and all(set(buffer) == {0} for buffer in buffers)
    if close_fails:
        assert captured == {}
    else:
        assert captured["command"] == "config.passphrase.change"
        result = captured["result"]
        assert isinstance(result, ConfigPassphraseChangeResult)
        assert result.profile_id == str(profile_id)
        assert result.changed is True and result.password_generation == 2


def test_missing_active_profile_refuses_before_collecting_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passphrase, "_resolve_active_bucket_id", lambda: None)
    monkeypatch.setattr(passphrase, "_activate_subcommand_output_language", lambda *_args: None)

    def forbidden(**_kwargs: object) -> None:
        raise AssertionError("missing target consumed a secret")

    monkeypatch.setattr(passphrase, "_collect_passphrases", forbidden)
    monkeypatch.setattr(passphrase, "_open_rotation_client", lambda _target, _ctx: forbidden())
    with pytest.raises(CliRefusedBoundaryError):
        passphrase.passphrase_change(_context())


def test_post_submit_uncertainty_keeps_operation_identity_and_wipes_proofs(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    client = _Client(profile_id)
    client.fail_close = True
    buffers: list[bytearray] = []
    operation_id = "a" * 64

    def fail_rotation(_client: object, **kwargs: object) -> None:
        for name in ("current_passphrase", "new_passphrase", "new_passphrase_confirmation"):
            value = kwargs[name]
            assert isinstance(value, bytearray)
            buffers.append(value)
        raise ProfileMutationRunError(operation_id=operation_id, code="unavailable")

    monkeypatch.setattr(passphrase, "_resolve_active_bucket_id", lambda: str(profile_id))
    monkeypatch.setattr(passphrase, "_activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(passphrase, "_open_rotation_client", lambda _profile_id, _ctx: client)
    monkeypatch.setattr(
        passphrase,
        "_collect_passphrases",
        lambda **_kwargs: passphrase.PassphraseChangeSecrets(
            current_passphrase=SecretStr("current-secret"),
            new_passphrase=SecretStr("replacement-secret"),
            new_passphrase_confirmation=SecretStr("replacement-secret"),
        ),
    )
    monkeypatch.setattr(passphrase, "run_profile_password_rotation", fail_rotation)
    with pytest.raises(ProfileMutationRunError) as caught:
        passphrase.passphrase_change(_context())

    assert caught.value.operation_id == operation_id
    envelope_context = build_error_envelope(caught.value).context
    assert envelope_context is not None
    assert envelope_context["operation_id"] == operation_id
    assert envelope_context["effect"] == "unknown"
    assert envelope_context["reason"] == "unavailable"
    assert "terminal_condition" not in envelope_context
    assert client.closed and client.proof is not None and set(client.proof) == {0}
    assert len(buffers) == 3 and all(set(buffer) == {0} for buffer in buffers)
