"""Focused contract tests for the canonical ``config login`` secret door."""

from __future__ import annotations

import pytest

from cadrumo_client.commands.custody import LoginSecrets
from cadrumo_client.commands.secure_input import MachineSecretPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_login_exposes_one_canonical_strict_payload_model() -> None:
    assert issubclass(LoginSecrets, MachineSecretPayload)
    assert tuple(LoginSecrets.model_fields) == ("passphrase",)
