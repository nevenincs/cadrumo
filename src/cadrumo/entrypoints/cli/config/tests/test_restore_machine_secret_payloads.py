"""Canonical machine-secret payloads for the two profile-restore doors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._restore_cli import RestorePassphraseSecrets, RestoreRecoverySecrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_restore_exposes_both_strict_payload_models() -> None:
    assert tuple(RestorePassphraseSecrets.model_fields) == ("passphrase",)
    assert tuple(RestoreRecoverySecrets.model_fields) == ("recovery_secret",)


def test_passphrase_door_hard_cuts_the_legacy_password_field() -> None:
    """The retired spelling is extra input, not a compatibility alias."""
    with pytest.raises(ValidationError):
        RestorePassphraseSecrets.model_validate({"password": "retired-value"})

    parsed = RestorePassphraseSecrets.model_validate({"passphrase": "current-value"})
    assert parsed.passphrase.get_secret_value() == "current-value"


def test_recovery_door_accepts_only_the_recovery_secret() -> None:
    """Artifact presence selects a disjoint payload rather than a union."""
    with pytest.raises(ValidationError):
        RestoreRecoverySecrets.model_validate({"passphrase": "wrong-door"})

    parsed = RestoreRecoverySecrets.model_validate({"recovery_secret": "24-word-phrase"})
    assert parsed.recovery_secret.get_secret_value() == "24-word-phrase"
