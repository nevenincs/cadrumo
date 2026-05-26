"""Payload-contract and registry-binding tests for the bucket error hierarchy."""

from __future__ import annotations

import pytest

from .....core.errors import ERROR_REGISTRY, AeatError, get_registered_error_code, resolve_error_message
from ..errors import SecureStorageError
from ._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_every_class_inherits_from_aeat_error() -> None:
    for cls in (
        BucketError,
        NoActiveBucketError,
        BucketBusyError,
        BucketAlreadyPresentError,
        BucketLockedError,
        RecoveryUnavailableError,
        RecoveryVerificationError,
    ):
        assert issubclass(cls, AeatError)
        assert issubclass(cls, SecureStorageError)


def test_every_class_has_a_registered_code() -> None:
    for cls in (
        BucketError,
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


def test_bucket_locked_default_suggestion_references_unlock() -> None:
    code = get_registered_error_code(BucketLockedError)
    assert code.default_suggestion == "aeat config profile switch NAME"


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


@pytest.mark.parametrize(
    "error",
    [
        NoActiveBucketError("legacy detail must not become the operator-facing message"),
        BucketBusyError(bucket_id="bucket-001", holding_pid=4242),
        BucketAlreadyPresentError(bucket_id="bucket-001"),
        BucketLockedError(bucket_id="bucket-001"),
        RecoveryUnavailableError(bucket_id="bucket-001"),
        RecoveryVerificationError("recovery detail must not echo into stderr"),
    ],
)
def test_bucket_errors_render_from_registry_translation(error: BucketError) -> None:
    code = get_registered_error_code(error)
    assert error.args == ()
    assert error.translated_message == code.message_key
    assert resolve_error_message(error) != "legacy detail must not become the operator-facing message"
    assert resolve_error_message(error) != "recovery detail must not echo into stderr"


def test_each_registry_code_is_distinct() -> None:
    codes = {
        get_registered_error_code(cls).code
        for cls in (
            BucketError,
            NoActiveBucketError,
            BucketBusyError,
            BucketAlreadyPresentError,
            BucketLockedError,
            RecoveryUnavailableError,
            RecoveryVerificationError,
        )
    }
    assert len(codes) == 7
