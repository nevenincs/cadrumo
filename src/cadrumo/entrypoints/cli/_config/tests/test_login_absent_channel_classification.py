"""Login channel absence never launders operational storage failures."""

from __future__ import annotations

from types import SimpleNamespace

import click
import pytest

from .....adapters.persistence.storage import KeyringUnavailableError
from .....adapters.persistence.storage.custody import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from .....application import user_profile
from .....core import config as config_module
from ..._errors import CliRefusedBoundaryError
from .. import _custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "fault",
    (
        KeyringUnavailableError("keyring unavailable"),
        ProfileCustodyRecordError("corrupt custody record"),
        ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE),
    ),
)
def test_callback_free_login_preserves_operational_fault_identity(
    monkeypatch: pytest.MonkeyPatch,
    fault: BaseException,
) -> None:
    """No configured channel is not evidence that an operational fault means absence."""
    _arrange_callback_free_login(monkeypatch, fault)

    with pytest.raises(type(fault)) as captured:
        _custody._login_through_the_prompt(
            click.Context(click.Command("login")),
            name="profile",
            secrets_stdin=False,
            secrets_fd=None,
        )

    assert captured.value is fault
    assert getattr(captured.value, "translated_message", None) != "cli.config.login.passphrase_channel_absent"


def test_genuine_absent_channel_keeps_specific_cli_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact custody absence signal retains its instructive CLI refusal."""
    _arrange_callback_free_login(
        monkeypatch,
        ProfileCustodyPasswordError("profile login requires an explicit password channel"),
    )

    with pytest.raises(CliRefusedBoundaryError) as captured:
        _custody._login_through_the_prompt(
            click.Context(click.Command("login")),
            name="profile",
            secrets_stdin=False,
            secrets_fd=None,
        )

    assert captured.value.translated_message == "cli.config.login.passphrase_channel_absent"


def _arrange_callback_free_login(monkeypatch: pytest.MonkeyPatch, fault: BaseException) -> None:
    def raise_fault(**_kwargs: object) -> None:
        raise fault

    monkeypatch.setattr(user_profile, "login_profile", raise_fault)
    monkeypatch.setattr(config_module, "load_settings", lambda: SimpleNamespace(cadrumo_secret_passphrase=None))
    monkeypatch.setattr(
        "cadrumo.entrypoints.cli._headless_secret_channel_active",
        lambda: True,
    )
