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

from typing import TypedDict

import pytest
from argon2.exceptions import HashingError
from pydantic import ValidationError

from ......core.errors import build_error_envelope
from ...bucket import ManifestKdfParams
from ...errors import KeyDerivationError
from .._kdf import derive_kek
from .._kdf_params import KdfParams

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


class _UnvalidatedManifestKdfFields(TypedDict):
    algorithm: str
    version: int
    memory_cost: int
    time_cost: int
    parallelism: int
    salt: bytes
    output_length: int


def _unvalidated(
    *,
    algorithm: str = "argon2id",
    memory_cost: int = 19 * 1024,
    output_length: int = 32,
) -> ManifestKdfParams:
    """Build a record that skips validation, to reach the backstop beneath it.

    Every parameter set below is now refused by ``ManifestKdfParams`` itself
    against the shared ``_kdf_bounds`` window, so ordinary construction can no
    longer produce one. ``model_construct`` bypasses that on purpose: the
    guards inside ``derive_kek`` must keep raising a TYPED storage error for a
    caller that bypasses the record, and proving that requires bypassing it.
    """
    fields: _UnvalidatedManifestKdfFields = {
        "algorithm": algorithm,
        "version": 19,
        "memory_cost": memory_cost,
        "time_cost": 2,
        "parallelism": 1,
        "salt": _REFERENCE_SALT,
        "output_length": output_length,
    }
    return ManifestKdfParams.model_construct(**fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"algorithm": "bcrypt"},
        {"version": 1},
        {"memory_cost": 1},
        {"memory_cost": 8},
        {"time_cost": 1},
        {"parallelism": 0},
        {"output_length": 16},
    ],
)
def test_manifest_record_refuses_what_the_enrollment_record_refuses(overrides: dict[str, object]) -> None:
    """The two KDF records accept the same value set, from the same constants.

    DISCRIMINATING on the divergence this closes: every one of these was
    accepted by ``ManifestKdfParams`` and refused by ``KdfParams``, so the
    manifest-side unlock contract admitted parameter sets enrollment would
    never mint -- including an 8 KiB, single-iteration Argon2 configuration.
    """
    fields: dict[str, object] = {
        "algorithm": "argon2id",
        "version": 19,
        "memory_cost": 19 * 1024,
        "time_cost": 2,
        "parallelism": 1,
        "salt": _REFERENCE_SALT,
        "output_length": 32,
    }
    fields.update(overrides)

    with pytest.raises(ValidationError):
        ManifestKdfParams.model_validate(fields)
    with pytest.raises(ValidationError):
        KdfParams.model_validate(fields)


def test_canonical_params_project_into_an_accepted_manifest_record() -> None:
    """POSITIVE CONTROL: the enrollment record's own output still validates.

    Without this, the parametrized refusals above are equally satisfied by a
    manifest record that refuses everything, which would break every bucket.
    """
    manifest_params = KdfParams.default().to_manifest_params()

    assert manifest_params.algorithm == "argon2id"
    assert manifest_params.output_length == 32
    assert len(derive_kek(_REFERENCE_PASSPHRASE, manifest_params)) == 32


def test_derive_kek_rejects_non_argon2id_algorithm() -> None:
    with pytest.raises(KeyDerivationError, match="unsupported KDF algorithm") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, _unvalidated(algorithm="bcrypt"))
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"
    envelope = build_error_envelope(exc_info.value)
    assert envelope.message
    assert "correct horse battery staple" not in envelope.model_dump_json()


def test_derive_kek_rejects_non_thirty_two_output_length() -> None:
    with pytest.raises(KeyDerivationError, match="unsupported KDF output_length") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, _unvalidated(output_length=16))
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"


def test_derive_kek_wraps_argon2_parameter_failure() -> None:
    """Argon2 rejects too-low memory cost as a typed localized storage error."""

    with pytest.raises(KeyDerivationError, match="Argon2id KEK derivation failed") as exc_info:
        derive_kek(_REFERENCE_PASSPHRASE, _unvalidated(memory_cost=1))

    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_key_derivation"
    assert isinstance(exc_info.value.__cause__, HashingError)
