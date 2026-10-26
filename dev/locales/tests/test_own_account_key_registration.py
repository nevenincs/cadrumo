"""Authored command keys are registered as their values, with account lifecycle copy."""

import pytest

from ..fstring_registry import _own_account_registrations

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_account_keys_are_locale_values_and_include_the_closing_date() -> None:
    keys = {
        registration.key_factory(value)
        for registration in _own_account_registrations()
        for value in registration.values
    }
    assert {
        "cli.app.ledger.account.add_help",
        "cli.app.modelo.m360.declare_help",
        "cli.config.custody.secrets_stdin_help",
        "tui.ledger.own_accounts.field_name.closed_on",
    } <= keys
    assert not any(key.startswith("TranslationKey(") for key in keys)
