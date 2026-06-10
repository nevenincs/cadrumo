"""Aggregate real-behavior test: every master_key cluster error envelope-round-trips (contract).

Each error class in the master_key cluster must:
1. Be a registered AeatError subclass with a bound ErrorCode in ERROR_REGISTRY.
2. Produce a non-empty, well-formed ErrorEnvelope via build_error_envelope.

This is an envelope smoke-test, not a behaviour test. It verifies the
registration wiring is complete for every cluster member so a future
addition of a new error class that forgets its ErrorCode registration
row fails loudly here.
"""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, AeatError, build_error_envelope
from ...errors import (
    EncryptionError,
    KeyDerivationError,
    SecretStoreError,
    StorageValidationError,
)
from .._errors import (
    MasterKeyReentrantError,
    MasterKeyTypeError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _envelope_round_trip(err: AeatError) -> None:
    """Assert `err` round-trips through build_error_envelope to a valid envelope."""

    code = err.code
    assert code.code in ERROR_REGISTRY, f"{type(err).__name__}.code={code.code!r} not found in ERROR_REGISTRY"

    envelope = build_error_envelope(err)
    assert envelope.code == code.code
    assert envelope.category != "", f"{type(err).__name__} produced empty envelope.category"
    assert envelope.message, f"{type(err).__name__} produced empty envelope.message"


@pytest.mark.parametrize(
    "error_instance",
    [
        MasterKeyReentrantError("SomeProvider"),
        MasterKeyTypeError("wrong type"),
        KeyDerivationError("unsupported KDF algorithm 'bcrypt'"),
        EncryptionError("kek must be exactly 32 bytes"),
        StorageValidationError("bucket_id must be non-empty"),
        SecretStoreError("generic secret store failure"),
    ],
    ids=[
        "MasterKeyReentrantError",
        "MasterKeyTypeError",
        "KeyDerivationError",
        "EncryptionError",
        "StorageValidationError",
        "SecretStoreError",
    ],
)
def test_cluster_error_envelope_round_trips(error_instance: AeatError) -> None:
    """Every master_key cluster error round-trips through the error envelope."""

    _envelope_round_trip(error_instance)


def test_master_key_reentrant_error_is_secret_store_error_subtype() -> None:
    """MasterKeyReentrantError must sit in the SecretStoreError family."""

    assert issubclass(MasterKeyReentrantError, SecretStoreError)


def test_master_key_type_error_is_storage_error_and_type_error() -> None:
    """MasterKeyTypeError must be catchable as both StorageError and TypeError."""

    from ...errors import StorageError

    assert issubclass(MasterKeyTypeError, StorageError)
    assert issubclass(MasterKeyTypeError, TypeError)
