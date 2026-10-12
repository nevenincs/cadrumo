"""A live sign-in admits every CLI invocation; a supplied secret never borrows it."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.user_profile.login_session import ProfileReceiptRefusedError
from ....core.profile_session import ProfileSessionRefusalReason
from .. import runtime_profile_admission as admission
from .._profile_authentication_contract import ProfileAuthenticationMethod
from .._profile_session_gate import session_refusal_translation_key
from ..config.secure_input import ProfileSecretChannel, ProfileSecretSelection
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ReceiptClient:
    def __init__(self, refusal: ProfileSessionRefusalReason | None = None) -> None:
        self.profile_id = uuid4()
        self.resumes = 0
        self.refusal = refusal

    def resume_receipt(self) -> None:
        self.resumes += 1
        if self.refusal is not None:
            raise ProfileReceiptRefusedError(self.refusal)


def _authenticate(client: _ReceiptClient) -> None:
    admission._authenticate(
        typer.Context(typer.main.TyperCommand("test")),
        cast(RuntimeFrontendClient, client),
        root_selection=None,
        profile_label=None,
        method=ProfileAuthenticationMethod.PASSWORD,
    )


@pytest.mark.parametrize("interactive", [False, True])
def test_a_live_sign_in_admits_with_or_without_a_terminal(monkeypatch: pytest.MonkeyPatch, interactive: bool) -> None:
    client = _ReceiptClient()
    monkeypatch.setattr(admission, "terminal_can_prompt_for_secrets", lambda: interactive)
    monkeypatch.setattr(admission, "_password", lambda *_args, **_kwargs: pytest.fail("asked for a password"))

    _authenticate(client)

    assert client.resumes == 1


def test_no_live_sign_in_refuses_with_the_login_action_without_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _ReceiptClient(ProfileSessionRefusalReason.ABSENT)
    monkeypatch.setattr(admission, "terminal_can_prompt_for_secrets", lambda: False)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _authenticate(client)

    assert client.resumes == 1
    assert refused.value.translated_message == session_refusal_translation_key(ProfileSessionRefusalReason.ABSENT, None)


@pytest.mark.parametrize("interactive", [False, True])
def test_a_keychainless_logon_asks_for_the_password_only_at_a_terminal(
    monkeypatch: pytest.MonkeyPatch, interactive: bool
) -> None:
    client = _ReceiptClient(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)
    prompted: list[ProfileSecretSelection | None] = []

    def password(_client: RuntimeFrontendClient, *, selection: ProfileSecretSelection | None) -> None:
        prompted.append(selection)

    monkeypatch.setattr(admission, "_password", password)
    monkeypatch.setattr(admission, "terminal_can_prompt_for_secrets", lambda: interactive)
    if interactive:
        _authenticate(client)
        assert prompted == [None]
    else:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            _authenticate(client)
        assert refused.value.translated_message == "cli.config.custody.errors.profile_passphrase_channel_absent"
        assert prompted == []


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
