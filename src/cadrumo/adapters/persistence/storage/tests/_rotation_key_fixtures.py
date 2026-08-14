"""Canonical independently generated master-key pair for rotation tests."""

from dataclasses import dataclass

import pytest

from .....tests.master_key import EphemeralMasterKeyProvider


@dataclass(frozen=True)
class RotationKeys:
    old_key: EphemeralMasterKeyProvider
    new_key: EphemeralMasterKeyProvider


@pytest.fixture
def rotation_keys() -> RotationKeys:
    return RotationKeys(
        old_key=EphemeralMasterKeyProvider(),
        new_key=EphemeralMasterKeyProvider(),
    )


__all__ = ["RotationKeys", "rotation_keys"]
