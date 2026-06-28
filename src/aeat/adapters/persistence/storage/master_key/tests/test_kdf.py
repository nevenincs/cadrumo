"""Tests for `derive_kek` against captured Argon2id reference output.

The known-answer vector below was captured from a one-time live
invocation of `argon2.low_level.hash_secret_raw` at the OWASP 2024
baseline parameters with the fixed inputs documented in
`_REFERENCE_VECTOR`. The expected hex is upstream-library output, not a
re-derivation of `derive_kek` against itself; a future regression in
the substrate's KDF routing produces a different output and the test
fails.

The reference capture command (re-runnable to refresh the vector after a
deliberate parameter change):

    uv run python -c "
    from argon2.low_level import Type, hash_secret_raw
    from sys import stdout
    out = hash_secret_raw(
        secret=b'correct horse battery staple',
        salt=b'\\x00' * 16,
        time_cost=2,
        memory_cost=19*1024,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )
    stdout.write(out.hex())
    "
"""

from __future__ import annotations

import pytest
from argon2.exceptions import HashingError

from ......core.errors import build_error_envelope
from ...bucket._manifest import ManifestKdfParams
from ...errors import KeyDerivationError
from .._kdf import derive_kek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_REFERENCE_PASSPHRASE = b"correct horse battery staple"
_REFERENCE_SALT = b"\x00" * 16
_REFERENCE_PARAMS = ManifestKdfParams(
    algorithm="argon2id",
    version=19,
    memory_cost=19 * 1024,
    time_cost=2,
    parallelism=1,
    salt=_REFERENCE_SALT,
    output_length=32,
)
_REFERENCE_OUTPUT_HEX = "bcaf6fd0e5aaa31b272240c38067653313e9f7802fc226ccf8416cf7bcf9e644"


def test_derive_kek_matches_upstream_reference_vector() -> None:
    """Known-answer: production routing produces upstream argon2-cffi output."""

    result = derive_kek(_REFERENCE_PASSPHRASE, _REFERENCE_PARAMS)

    assert result.hex() == _REFERENCE_OUTPUT_HEX
    assert len(result) == 32


def test_derive_kek_output_length_is_thirty_two_bytes() -> None:
    params = _REFERENCE_PARAMS.model_copy(update={"salt": b"\x01" * 16})

    result = derive_kek(b"another-passphrase", params)

    assert len(result) == 32


def test_derive_kek_differs_for_different_salts() -> None:
    """Property: changing the salt yields a different KEK."""

    other_params = _REFERENCE_PARAMS.model_copy(update={"salt": b"\x01" * 16})

    a = derive_kek(_REFERENCE_PASSPHRASE, _REFERENCE_PARAMS)
    b = derive_kek(_REFERENCE_PASSPHRASE, other_params)

    assert a != b


def test_derive_kek_differs_for_different_passphrases() -> None:
    """Property: changing the passphrase yields a different KEK."""

    a = derive_kek(_REFERENCE_PASSPHRASE, _REFERENCE_PARAMS)
    b = derive_kek(b"different passphrase entirely", _REFERENCE_PARAMS)

    assert a != b


def test_derive_kek_rejects_non_argon2id_algorithm() -> None:
    bad_params = ManifestKdfParams(
        algorithm="bcrypt",
        version=19,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt=_REFERENCE_SALT,
        output_length=32,
    )

    with pytest.raises(KeyDerivationError, match="unsupported KDF algorithm") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, bad_params)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"
    envelope = build_error_envelope(exc_info.value)
    assert envelope.message
    assert "correct horse battery staple" not in envelope.model_dump_json()


def test_derive_kek_rejects_non_thirty_two_output_length() -> None:
    bad_params = ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt=_REFERENCE_SALT,
        output_length=16,
    )

    with pytest.raises(KeyDerivationError, match="unsupported KDF output_length") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, bad_params)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_derive_kek_wraps_argon2_parameter_failure() -> None:
    """Argon2 rejects too-low memory cost as a typed localized storage error."""

    bad_params = ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=1,
        time_cost=2,
        parallelism=1,
        salt=_REFERENCE_SALT,
        output_length=32,
    )

    with pytest.raises(KeyDerivationError, match="Argon2id KEK derivation failed") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, bad_params)

    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"
    assert isinstance(exc_info.value.__cause__, HashingError)
