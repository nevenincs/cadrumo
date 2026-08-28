"""Canonical fixed-master-key fixture for storage adapter tests."""

from __future__ import annotations

import secrets

import pytest

from ..crypto.aead import KEY_SIZE


@pytest.fixture
def fixed_master_key() -> bytes:
    """Return one fresh master key shared by the consuming test's setup."""

    return secrets.token_bytes(KEY_SIZE)
