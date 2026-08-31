"""Tests for the canonical :class:`KdfParams` Argon2id record."""

from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from ..kdf_params import KdfParams

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_default_pins_owasp_baseline_constants() -> None:
    """Pin-test the OWASP 2024 KDF parameters verbatim."""

    params = KdfParams.default()
    assert params.algorithm == "argon2id"
    assert params.version == 19
    assert params.memory_cost == 19 * 1024
    assert params.time_cost == 2
    assert params.parallelism == 1
    assert params.output_length == 32
    assert len(params.salt) == 16


def test_default_emits_distinct_salts() -> None:
    a = KdfParams.default()
    b = KdfParams.default()
    assert a.salt != b.salt


def test_rejects_memory_cost_zero() -> None:
    with pytest.raises(ValidationError):
        KdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=0,
            time_cost=2,
            parallelism=1,
            salt=secrets.token_bytes(16),
            output_length=32,
        )


def test_rejects_time_cost_zero() -> None:
    invalid_time_cost: int = 0
    with pytest.raises(ValidationError):
        KdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19 * 1024,
            time_cost=invalid_time_cost,
            parallelism=1,
            salt=secrets.token_bytes(16),
            output_length=32,
        )


def test_rejects_wrong_salt_length() -> None:
    with pytest.raises(ValidationError):
        KdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=secrets.token_bytes(15),
            output_length=32,
        )


def test_rejects_unknown_algorithm() -> None:
    with pytest.raises(ValidationError):
        KdfParams.model_validate(
            {
                "algorithm": "scrypt",
                "version": 19,
                "memory_cost": 19 * 1024,
                "time_cost": 2,
                "parallelism": 1,
                "salt": secrets.token_bytes(16),
                "output_length": 32,
            },
        )


def test_json_round_trip_preserves_salt() -> None:
    params = KdfParams.default()
    blob = params.model_dump_json()
    revived = KdfParams.model_validate_json(blob)
    assert revived.salt == params.salt
    assert revived == params


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        KdfParams.model_validate(
            {
                "algorithm": "argon2id",
                "version": 19,
                "memory_cost": 19 * 1024,
                "time_cost": 2,
                "parallelism": 1,
                "salt": secrets.token_bytes(16),
                "output_length": 32,
                "unexpected": 1,
            },
        )
