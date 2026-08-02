"""Real-behavior tests for KeyDerivationError at every raise in _kdf.py (contract).

Asserts that:
- `derive_kek` raises `KeyDerivationError` (not bare ValueError) for each
  invalid parameter path.
- `KeyDerivationError` has a bound `ErrorCode` and round-trips through
  `build_error_envelope`.

These parameter sets are now unreachable through ordinary construction:
`ManifestKdfParams` validates the algorithm, version, cost window, and output
length against the shared `_kdf_bounds` contract, so the record refuses them
before `derive_kek` is ever called. They are built with `model_construct`,
which skips validation, precisely to reach the backstop underneath -- the
guards must keep raising a TYPED storage error for a caller that bypasses the
record, and asserting that requires bypassing it here too.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from ...bucket import ManifestKdfParams
from ...errors import KeyDerivationError
from .._kdf import derive_kek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_SALT = b"\x00" * 16
_PASSPHRASE = b"correct horse battery staple"


def _unvalidated(**overrides: object) -> ManifestKdfParams:
    """Build a record that skips validation, to reach the backstop beneath it."""
    fields: dict[str, object] = {
        "algorithm": "argon2id",
        "version": 19,
        "memory_cost": 19 * 1024,
        "time_cost": 2,
        "parallelism": 1,
        "salt": _VALID_SALT,
        "output_length": 32,
    }
    fields.update(overrides)
    return ManifestKdfParams.model_construct(**fields)


def test_record_refuses_the_unsupported_algorithm_before_derivation() -> None:
    """The record is the authority; the backstop below is not where this is caught."""
    with pytest.raises(ValidationError):
        ManifestKdfParams(
            algorithm="bcrypt",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=_VALID_SALT,
            output_length=32,
        )


def test_record_refuses_the_unsupported_output_length_before_derivation() -> None:
    """Same authority, on the output length."""
    with pytest.raises(ValidationError):
        ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=_VALID_SALT,
            output_length=16,
        )


def test_derive_kek_raises_key_derivation_error_for_unsupported_algorithm() -> None:
    """A validation-bypassing caller still gets a typed storage error."""
    with pytest.raises(KeyDerivationError, match="unsupported KDF algorithm") as exc_info:
        derive_kek(_PASSPHRASE, _unvalidated(algorithm="bcrypt"))
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_derive_kek_raises_key_derivation_error_for_unsupported_output_length() -> None:
    """Same backstop, on the output length."""
    with pytest.raises(KeyDerivationError, match="unsupported KDF output_length") as exc_info:
        derive_kek(_PASSPHRASE, _unvalidated(output_length=16))
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_derive_kek_still_derives_under_valid_params() -> None:
    """POSITIVE CONTROL: the backstop does not refuse canonical material."""
    assert len(derive_kek(_PASSPHRASE, _unvalidated())) == 32


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
