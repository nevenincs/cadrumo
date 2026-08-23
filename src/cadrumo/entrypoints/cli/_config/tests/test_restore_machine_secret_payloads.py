"""Canonical machine-secret payloads for the two profile-restore doors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..._machine_secret_contract import registered_machine_secret_payload_models
from .._restore_cli import _RestorePassphraseSecrets, _RestoreRecoverySecrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_restore_registers_both_conditional_payload_models() -> None:
    """The inventory and the live restore validators cannot drift apart."""
    registered = registered_machine_secret_payload_models()

    assert registered[("config.profile.restore", "passphrase")] is _RestorePassphraseSecrets
    assert registered[("config.profile.restore", "recovery")] is _RestoreRecoverySecrets


def test_passphrase_door_hard_cuts_the_legacy_password_field() -> None:
    """The retired spelling is extra input, not a compatibility alias."""
    with pytest.raises(ValidationError):
        _RestorePassphraseSecrets.model_validate({"password": "retired-value"})

    parsed = _RestorePassphraseSecrets.model_validate({"passphrase": "current-value"})
    assert parsed.passphrase.get_secret_value() == "current-value"


def test_recovery_door_accepts_only_the_recovery_secret() -> None:
    """Artifact presence selects a disjoint payload rather than a union."""
    with pytest.raises(ValidationError):
        _RestoreRecoverySecrets.model_validate({"passphrase": "wrong-door"})

    parsed = _RestoreRecoverySecrets.model_validate({"recovery_secret": "24-word-phrase"})
    assert parsed.recovery_secret.get_secret_value() == "24-word-phrase"
