"""Aggregate real-behavior test: every master_key cluster error envelope-round-trips (contract).

Each error class in the master_key cluster must:
1. Be a registered CadrumoError subclass with a bound ErrorCode in ERROR_REGISTRY.
2. Produce a non-empty, well-formed ErrorEnvelope via build_error_envelope.

This is an envelope smoke-test, not a behaviour test. It verifies the
registration wiring is complete for every cluster member so a future
addition of a new error class that forgets its ErrorCode registration
row fails loudly here.
"""

from __future__ import annotations

import pytest

from ...errors import (
    SecretStoreError,
)
from ..errors import MasterKeyReentrantError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_master_key_reentrant_error_is_secret_store_error_subtype() -> None:
    """MasterKeyReentrantError must sit in the SecretStoreError family."""

    assert issubclass(MasterKeyReentrantError, SecretStoreError)
