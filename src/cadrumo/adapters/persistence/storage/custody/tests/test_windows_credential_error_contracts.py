"""Native credential failures have distinct registered boundary classifications."""

from __future__ import annotations

import pytest

from ......core.errors.error_codes import ErrorCategory, get_registered_error_code
from ..automation_secret_store import _InvalidWindowsCredentialError, _WindowsCredentialError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_native_failure_retains_status_mapping_without_claiming_retryability() -> None:
    """Win32 status evidence survives registration for the exact adapter catch."""
    error = _WindowsCredentialError(1168)

    registered = get_registered_error_code(error)

    assert error.winerror == 1168
    assert registered.code == "ERROR_WINDOWS_CREDENTIAL_API"
    assert registered.category is ErrorCategory.ERROR
    assert registered.retryable is False


def test_malformed_native_record_is_an_integrity_failure() -> None:
    """Invalid secret storage is distinct from native facility unavailability."""
    registered = get_registered_error_code(_InvalidWindowsCredentialError())

    assert registered.code == "INTEGRITY_WINDOWS_CREDENTIAL_RECORD"
    assert registered.category is ErrorCategory.INTEGRITY
    assert registered.retryable is False
