"""Automatic receipt borrowing is an interactive default, never a pipe credential."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .. import runtime_profile_admission as admission
from .._profile_authentication_contract import ProfileAuthenticationMethod
from ..config import custody, secure_input
from ..config.secure_input import ProfileSecretChannel, ProfileSecretSelection
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ReceiptClient:
    def __init__(self) -> None:
        self.profile_id = uuid4()
        self.resumes = 0

    def resume_receipt(self) -> None:
        self.resumes += 1


@pytest.mark.parametrize("interactive", [False, True])
def test_automatic_resume_requires_interactive_input(monkeypatch: pytest.MonkeyPatch, interactive: bool) -> None:
    client = _ReceiptClient()
    monkeypatch.setattr(admission, "terminal_can_prompt_for_secrets", lambda: interactive)
    context = typer.Context(typer.main.TyperCommand("test"))
    if interactive:
        admission._authenticate(
            context,
            cast(RuntimeFrontendClient, client),
            root_selection=None,
            profile_label=None,
            method=ProfileAuthenticationMethod.PASSWORD,
        )
    else:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            admission._authenticate(
                context,
                cast(RuntimeFrontendClient, client),
                root_selection=None,
                profile_label=None,
                method=ProfileAuthenticationMethod.PASSWORD,
            )
        assert refused.value.translated_message == "cli.config.custody.errors.profile_passphrase_channel_absent"
    assert client.resumes == int(interactive)


def test_explicit_password_never_borrows_a_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _ReceiptClient()
    selected = ProfileSecretSelection(ProfileSecretChannel.STDIN)
    channels: list[ProfileSecretSelection | None] = []

    def password(_client: RuntimeFrontendClient, *, selection: ProfileSecretSelection | None) -> None:
        channels.append(selection)

    monkeypatch.setattr(admission, "_password", password)
    monkeypatch.setattr(admission, "terminal_can_prompt_for_secrets", lambda: False)
    admission._authenticate(
        typer.Context(typer.main.TyperCommand("test")),
        cast(RuntimeFrontendClient, client),
        root_selection=selected,
        profile_label=None,
        method=ProfileAuthenticationMethod.PASSWORD,
    )
    assert client.resumes == 0
    assert channels == [selected]


def test_config_login_without_channel_refuses_before_target_or_runtime_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secure_input, "terminal_can_prompt_for_secrets", lambda: False)
    with pytest.raises(CliRefusedBoundaryError):
        custody._login_through_the_prompt(
            typer.Context(typer.main.TyperCommand("test")), name="synthetic-nonexistent-profile", machine_secret=None
        )
