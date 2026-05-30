"""Real-behavior envelope round-trip tests for every bucket cluster error.

Asserts:
- Each error class is registered in ERROR_REGISTRY with a distinct code.
- build_error_envelope produces a valid ErrorEnvelope from each class.
- The envelope round-trips through JSON (model_dump_json / model_validate_json).
- BucketValidationError satisfies the ValueError / BucketError dual-inheritance
  contract required by pydantic field validators.
"""

from __future__ import annotations

import pytest

from .....core.errors import ERROR_REGISTRY, build_error_envelope, get_registered_error_code
from .....core.errors._registry import ErrorEnvelope
from ._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    BucketValidationError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

# ---------------------------------------------------------------------------
# Fixtures — concrete instances for each class in the cluster
# ---------------------------------------------------------------------------

_CLUSTER_INSTANCES: list[BucketError] = [
    BucketError(),
    BucketValidationError("salt must be exactly 16 bytes"),
    NoActiveBucketError(detail="no pointer file found"),
    BucketBusyError(bucket_id="bucket-001", holding_pid=9999),
    BucketAlreadyPresentError(bucket_id="bucket-001"),
    BucketLockedError(bucket_id="bucket-001"),
    RecoveryUnavailableError(bucket_id="bucket-001"),
    RecoveryVerificationError(detail="wrong 24-word entry"),
]

_CLUSTER_CLASSES: list[type[BucketError]] = [type(e) for e in _CLUSTER_INSTANCES]


# ---------------------------------------------------------------------------
# Registry membership
# ---------------------------------------------------------------------------


def test_every_cluster_class_has_a_distinct_code_in_error_registry() -> None:
    codes = set()
    for cls in _CLUSTER_CLASSES:
        code = get_registered_error_code(cls)
        assert code.code in ERROR_REGISTRY, f"{cls.__name__} code {code.code!r} not in ERROR_REGISTRY"
        codes.add(code.code)
    assert len(codes) == len(_CLUSTER_CLASSES), "duplicate code across bucket cluster classes"


# ---------------------------------------------------------------------------
# Envelope construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("error", _CLUSTER_INSTANCES, ids=[type(e).__name__ for e in _CLUSTER_INSTANCES])
def test_build_error_envelope_produces_valid_envelope(error: BucketError) -> None:
    envelope = build_error_envelope(error)
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.code in ERROR_REGISTRY
    assert envelope.schema_version == "1"
    assert envelope.category != ""
    assert envelope.message != ""


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("error", _CLUSTER_INSTANCES, ids=[type(e).__name__ for e in _CLUSTER_INSTANCES])
def test_error_envelope_round_trips_json(error: BucketError) -> None:
    envelope = build_error_envelope(error)
    json_text = envelope.model_dump_json()
    revived = ErrorEnvelope.model_validate_json(json_text)
    assert revived == envelope


# ---------------------------------------------------------------------------
# BucketValidationError dual-inheritance contract
# ---------------------------------------------------------------------------


def test_bucket_validation_error_is_value_error() -> None:
    """BucketValidationError must satisfy ValueError so pydantic validators accept it."""
    err = BucketValidationError("bad salt length")
    assert isinstance(err, ValueError)
    assert isinstance(err, BucketError)


def test_bucket_validation_error_caught_as_value_error() -> None:
    """Confirm the dual-inheritance is live at runtime — not just a class attribute."""
    with pytest.raises(ValueError, match="bad salt length"):
        raise BucketValidationError("bad salt length")


def test_bucket_validation_error_caught_as_bucket_error() -> None:
    with pytest.raises(BucketError, match="bad salt length"):
        raise BucketValidationError("bad salt length")


# ---------------------------------------------------------------------------
# Anti-tautology: mutating the JSON payload breaks equality
# ---------------------------------------------------------------------------


def test_mutated_envelope_json_is_not_equal_to_original() -> None:
    error = BucketBusyError(bucket_id="bucket-001", holding_pid=1234)
    envelope = build_error_envelope(error)
    import json

    payload = json.loads(envelope.model_dump_json())
    payload["code"] = "BOGUS_CODE_THAT_DOES_NOT_EXIST"
    # Reviving with a code not in the registry still parses (the envelope is
    # a data record, not a registry-validated object), but the result must
    # differ from the original.
    revived = ErrorEnvelope.model_validate(payload)
    assert revived != envelope
