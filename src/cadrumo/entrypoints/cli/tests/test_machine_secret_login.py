"""Focused contract tests for the canonical ``config login`` secret door."""

from __future__ import annotations

import pytest

from ..config import secure_input
from ..config.custody import LoginSecrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_login_exposes_one_canonical_strict_payload_model() -> None:
    assert issubclass(LoginSecrets, secure_input.MachineSecretPayload)
    assert tuple(LoginSecrets.model_fields) == ("passphrase",)
