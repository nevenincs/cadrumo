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


def test_every_class_inherits_from_aeat_error() -> None:
    for cls in (
        BucketError,
        BucketValidationError,
        NoActiveBucketError,
        BucketBusyError,
        BucketAlreadyPresentError,
        BucketLockedError,
        RecoveryUnavailableError,
        RecoveryVerificationError,
    ):
        assert issubclass(cls, AeatError)


def test_every_class_has_a_registered_code() -> None:
    for cls in (
        BucketError,
        BucketValidationError,
        NoActiveBucketError,
        BucketBusyError,
        BucketAlreadyPresentError,
        BucketLockedError,
        RecoveryUnavailableError,
        RecoveryVerificationError,
    ):
        code = get_registered_error_code(cls)
        assert code.code in ERROR_REGISTRY


def test_no_active_bucket_error_default_suggestion_references_list_buckets() -> None:
    code = get_registered_error_code(NoActiveBucketError)
    assert code.default_suggestion == "aeat config profile list"


def test_bucket_locked_default_suggestion_references_switch_recovery_verb() -> None:
    code = get_registered_error_code(BucketLockedError)
    assert code.default_suggestion == "aeat config switch NAME"


def test_bucket_busy_payload_carries_bucket_id_and_pid() -> None:
    error = BucketBusyError(bucket_id="bucket-001", holding_pid=4242)
    assert error.bucket_id == "bucket-001"
    assert error.holding_pid == 4242
    assert error.context == {"bucket_id": "bucket-001", "holding_pid": 4242}


def test_bucket_already_present_payload_carries_bucket_id() -> None:
    error = BucketAlreadyPresentError(bucket_id="bucket-001")
    assert error.bucket_id == "bucket-001"
    assert error.context == {"bucket_id": "bucket-001"}


def test_bucket_locked_payload_carries_bucket_id() -> None:
    error = BucketLockedError(bucket_id="bucket-001")
    assert error.bucket_id == "bucket-001"
    assert error.context == {"bucket_id": "bucket-001"}


def test_recovery_unavailable_payload_carries_bucket_id() -> None:
    error = RecoveryUnavailableError(bucket_id="bucket-001")
    assert error.bucket_id == "bucket-001"
    assert error.context == {"bucket_id": "bucket-001"}


def test_each_registry_code_is_distinct() -> None:
    codes = {
        get_registered_error_code(cls).code
        for cls in (
            BucketError,
            BucketValidationError,
            NoActiveBucketError,
            BucketBusyError,
            BucketAlreadyPresentError,
            BucketLockedError,
            RecoveryUnavailableError,
            RecoveryVerificationError,
        )
    }
    assert len(codes) == 8
