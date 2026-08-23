"""Focused contract tests for the canonical ``config login`` secret door."""

from __future__ import annotations

from typing import cast

import click
import pytest
import typer

from .._config import _secure_input
from .._config._custody import _login_through_the_prompt, _LoginSecrets
from .._errors import CliRefusedBoundaryError
from .._machine_secret_contract import registered_machine_secret_payload_models

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_login_registers_one_canonical_strict_payload_model() -> None:
    """Discovery and runtime validation share the exact command-local model."""
    assert issubclass(_LoginSecrets, _secure_input.MachineSecretPayload)
    assert registered_machine_secret_payload_models()["config.login", "passphrase"] is _LoginSecrets


def test_login_without_an_explicit_channel_or_verified_terminal_refuses_before_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured substrate secrets cannot become an implicit CLI input route."""
    from ....application import user_profile

    authentication_attempted = False

    def unexpected_login(**_kwargs: object) -> None:
        nonlocal authentication_attempted
        authentication_attempted = True

    monkeypatch.setattr(_secure_input, "terminal_can_prompt_for_secrets", lambda: False)
    monkeypatch.setattr(user_profile, "login_profile", unexpected_login)

    with pytest.raises(CliRefusedBoundaryError) as raised:
        _login_through_the_prompt(
            cast("typer.Context", click.Context(click.Command("login"))),
            name="operator",
            machine_secret=None,
        )

    assert raised.value.translated_message == "cli.config.login.passphrase_channel_absent"
    assert authentication_attempted is False
