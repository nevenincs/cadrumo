"""Payload-contract and registry-binding tests for the bucket error hierarchy."""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, AeatError, get_registered_error_code
from .._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    BucketValidationError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ERROR_CLASSES: tuple[type[BucketError], ...] = (
    BucketError,
    BucketValidationError,
    NoActiveBucketError,
    BucketBusyError,
    BucketAlreadyPresentError,
    BucketLockedError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)


def test_every_class_inherits_from_aeat_error() -> None:
    for error_cls in _BUCKET_ERROR_CLASSES:
        assert issubclass(error_cls, AeatError), error_cls.__name__


def test_every_class_has_a_registered_code() -> None:
    for error_cls in _BUCKET_ERROR_CLASSES:
        code = get_registered_error_code(error_cls)
        assert code.code in ERROR_REGISTRY, error_cls.__name__


def test_default_suggestions_reference_operator_commands() -> None:
    cases = (
        (NoActiveBucketError, "aeat config profile list"),
        (BucketLockedError, "aeat config switch NAME"),
    )
    for error_cls, expected_suggestion in cases:
        code = get_registered_error_code(error_cls)
        assert code.default_suggestion == expected_suggestion, error_cls.__name__


def test_bucket_busy_payload_carries_bucket_id_and_pid() -> None:
    error = BucketBusyError(bucket_id="bucket-001", holding_pid=4242)
    assert error.bucket_id == "bucket-001"
    assert error.holding_pid == 4242
    assert error.context == {"bucket_id": "bucket-001", "holding_pid": 4242}


def test_bucket_id_payload_carries_bucket_id() -> None:
    for error in (
        BucketAlreadyPresentError(bucket_id="bucket-001"),
        BucketLockedError(bucket_id="bucket-001"),
        RecoveryUnavailableError(bucket_id="bucket-001"),
    ):
        assert error.bucket_id == "bucket-001", type(error).__name__
        assert error.context == {"bucket_id": "bucket-001"}


def test_each_registry_code_is_distinct() -> None:
    codes = {get_registered_error_code(cls).code for cls in _BUCKET_ERROR_CLASSES}
    assert len(codes) == len(_BUCKET_ERROR_CLASSES)
