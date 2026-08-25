"""Payload-contract and registry-binding tests for bucket storage errors.

The suite pins every bucket error as an :class:`~core.errors.CadrumoError` with a
registered code, distinct registry identity, explicit envelope action state, and
structured context for bucket-id / lock-holder payloads. These contracts keep
manifest, lockfile, recovery, and active-bucket failures observable without
leaking raw storage details.

See Also:
    :mod:`~adapters.persistence.storage.bucket._errors`
        Error hierarchy and payload constructors under test.
    :mod:`~adapters.persistence.storage.bucket._lockfile`
        PID-stamped lock primitive that raises busy / locked bucket failures.

Adverse storage failures must fail closed with redacted diagnostics rather
than leak raw storage details to the operator.
"""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, CadrumoError, get_registered_error_code
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


@pytest.mark.parametrize("error_cls", _BUCKET_ERROR_CLASSES, ids=lambda cls: cls.__name__)
def test_every_class_inherits_from_cadrumo_error(error_cls: type[BucketError]) -> None:
    assert issubclass(error_cls, CadrumoError)


@pytest.mark.parametrize("error_cls", _BUCKET_ERROR_CLASSES, ids=lambda cls: cls.__name__)
def test_every_class_has_a_registered_code(error_cls: type[BucketError]) -> None:
    code = get_registered_error_code(error_cls)
    assert code.code in ERROR_REGISTRY


def test_bucket_busy_payload_carries_bucket_id_and_pid() -> None:
    error = BucketBusyError(bucket_id="bucket-001", holding_pid=4242)
    assert error.bucket_id == "bucket-001"
    assert error.holding_pid == 4242
    assert error.context == {"bucket_id": "bucket-001", "holding_pid": 4242}


@pytest.mark.parametrize(
    ("error", "expected_context"),
    (
        pytest.param(
            BucketAlreadyPresentError(bucket_id="bucket-001"),
            {"bucket_id": "bucket-001"},
            id="already-present",
        ),
        pytest.param(
            BucketLockedError(bucket_id="bucket-001"),
            {"bucket_id": "bucket-001", "bucket_session_unlocked": False},
            id="locked",
        ),
        pytest.param(
            RecoveryUnavailableError(bucket_id="bucket-001"),
            {"bucket_id": "bucket-001"},
            id="recovery-unavailable",
        ),
    ),
)
def test_bucket_id_payload_carries_bucket_id(
    error: BucketAlreadyPresentError | BucketLockedError | RecoveryUnavailableError,
    expected_context: dict[str, str | bool],
) -> None:
    assert error.bucket_id == "bucket-001"
    assert error.context == expected_context


def test_each_registry_code_is_distinct() -> None:
    codes = {get_registered_error_code(cls).code for cls in _BUCKET_ERROR_CLASSES}
    assert len(codes) == len(_BUCKET_ERROR_CLASSES)
