"""Canonical machine-secret payload for the profile-restore door."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..restore_cli import RestorePassphraseSecrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_restore_exposes_exactly_the_passphrase_payload_model() -> None:
    assert tuple(RestorePassphraseSecrets.model_fields) == ("passphrase",)


def test_passphrase_door_hard_cuts_the_legacy_password_field() -> None:
    """The retired spelling is extra input, not a compatibility alias."""
    with pytest.raises(ValidationError):
        RestorePassphraseSecrets.model_validate({"password": "retired-value"})

    parsed = RestorePassphraseSecrets.model_validate({"passphrase": "current-value"})
    assert parsed.passphrase.get_secret_value() == "current-value"


def test_passphrase_door_refuses_a_recovery_secret() -> None:
    """A restore proves the passphrase only; recovery is enrolled afterwards by its own verb."""
    with pytest.raises(ValidationError):
        RestorePassphraseSecrets.model_validate({"recovery_code": "AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA"})
    with pytest.raises(ValidationError):
        RestorePassphraseSecrets.model_validate({"recovery_secret": "retired-door"})
