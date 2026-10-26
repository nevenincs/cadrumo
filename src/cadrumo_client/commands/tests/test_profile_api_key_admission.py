"""Shared-client admission proofs, independent of tax command parsing."""

from __future__ import annotations

from typing import cast

import pytest
import typer

from cadrumo_client.commands import profile_admission as admission
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_authentication import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
    ProfileSecretSourceOptions,
)
from cadrumo_client.commands.secure_input import ProfileSecretChannel, ProfileSecretSelection
from cadrumo_client.transport.frontend_client import FrontendClient

from .runtime_target_double import answer_login_targets_locally

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _runtime_answers_login_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runtime client here is a double, so the runtime's login-target answer is given as it would give it."""
    answer_login_targets_locally(monkeypatch)


def _context(source: ProfileSecretSourceOptions) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    context = typer.Context(typer.main.get_command(app))
    cast("dict[str, object]", context.ensure_object(dict))["profile_secret_source"] = source
    return context


class _LoginWitness:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.secret: bytearray | None = None

    def resume_receipt(self) -> None:
        self.calls.append("receipt")
        raise AssertionError("API authentication must not attempt a human receipt")

    def login_password(self, _secret: bytearray) -> None:
        self.calls.append("password")
        raise AssertionError("API authentication must not attempt password login")

    def login_api_key(self, secret: bytearray) -> None:
        self.calls.append("api_key")
        self.secret = secret
        assert bytes(secret) == b"synthetic-api-key"


def test_api_login_consumes_once_and_wipes_the_mutable_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    witness = _LoginWitness()
    monkeypatch.setattr(
        admission,
        "read_profile_secret_payload",
        lambda _model, *, selection: ProfileAuthenticationSecrets.model_validate({"api_key": "synthetic-api-key"}),
    )
    admission.authenticate_profile_client(
        cast(FrontendClient, witness),
        root_selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
        profile_label=None,
        method=ProfileAuthenticationMethod.API_KEY,
    )
    assert witness.calls == ["api_key"]
    assert witness.secret == bytearray(len(b"synthetic-api-key"))


@pytest.mark.parametrize(
    ("method", "field"),
    (
        (ProfileAuthenticationMethod.PASSWORD, "api_key"),
        (ProfileAuthenticationMethod.API_KEY, "profile_passphrase"),
    ),
)
def test_selected_method_refuses_the_other_valid_payload(
    monkeypatch: pytest.MonkeyPatch,
    method: ProfileAuthenticationMethod,
    field: str,
) -> None:
    witness = _LoginWitness()
    monkeypatch.setattr(
        admission,
        "read_profile_secret_payload",
        lambda _model, *, selection: ProfileAuthenticationSecrets.model_validate({field: "synthetic-secret"}),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        if method is ProfileAuthenticationMethod.API_KEY:
            admission.authenticate_profile_client(
                cast(FrontendClient, witness),
                root_selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
                profile_label=None,
                method=method,
            )
        else:
            admission._password(
                cast(FrontendClient, witness),
                selection=ProfileSecretSelection(ProfileSecretChannel.STDIN),
                not_persisted=lambda: pytest.fail("a refused secret signed nothing in"),
            )
    assert refused.value.translated_message is not None
    assert refused.value.translated_message.endswith("profile_secrets_method_mismatch")
    assert witness.calls == []
