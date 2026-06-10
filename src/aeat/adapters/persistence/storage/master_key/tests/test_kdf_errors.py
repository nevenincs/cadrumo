"""Real-behavior tests for KeyDerivationError at every migrated raise in _kdf.py (contract).

Asserts that:
- `derive_kek` raises `KeyDerivationError` (not bare ValueError) for each
  invalid parameter path.
- `KeyDerivationError` has a bound `ErrorCode` and round-trips through
  `build_error_envelope`.
"""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from ...bucket._manifest import ManifestKdfParams
from ...errors import KeyDerivationError
from .._kdf import derive_kek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_SALT = b"\x00" * 16
_PASSPHRASE = b"correct horse battery staple"


def test_derive_kek_raises_key_derivation_error_for_unsupported_algorithm() -> None:
    """_kdf.py:44 — unsupported algorithm must raise KeyDerivationError, not ValueError."""

    bad_params = ManifestKdfParams(
        algorithm="bcrypt",
        version=19,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt=_VALID_SALT,
        output_length=32,
    )

    with pytest.raises(KeyDerivationError, match="unsupported KDF algorithm") as exc_info:
        derive_kek(_PASSPHRASE, bad_params)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_derive_kek_raises_key_derivation_error_for_unsupported_output_length() -> None:
    """_kdf.py:48 — unsupported output_length must raise KeyDerivationError, not ValueError."""

    bad_params = ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt=_VALID_SALT,
        output_length=16,
    )

    with pytest.raises(KeyDerivationError, match="unsupported KDF output_length") as exc_info:
        derive_kek(_PASSPHRASE, bad_params)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_key_derivation_error_is_registered() -> None:
    """KeyDerivationError must have a bound ErrorCode in ERROR_REGISTRY."""

    err = KeyDerivationError("test")
    code = err.code

    assert code.code in ERROR_REGISTRY


def test_key_derivation_error_envelope_round_trip() -> None:
    """build_error_envelope produces a well-formed envelope from KeyDerivationError."""

    err = KeyDerivationError("unsupported KDF algorithm 'bcrypt'; expected 'argon2id'")
    envelope = build_error_envelope(err)

    assert envelope.code in ERROR_REGISTRY
    assert envelope.retryable is False
    assert envelope.message
