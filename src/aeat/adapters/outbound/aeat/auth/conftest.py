"""Shared test fixtures for the aeat.adapters.outbound.aeat.auth package."""

from __future__ import annotations

import pytest

from ._fixtures import SECRET_PASSPHRASE


@pytest.fixture(scope="session")
def secret_passphrase() -> str:
    """Return the canonical PKCS#12 test passphrase."""
    return SECRET_PASSPHRASE
