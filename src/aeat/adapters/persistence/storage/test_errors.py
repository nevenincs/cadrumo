"""Contract tests for the secure-storage exception hierarchy."""

from __future__ import annotations

import pytest

from ....core.errors import AeatError, get_registered_error_code, resolve_error_message
from .bucket import BucketError
from .errors import (
    DecryptionError,
    PersistenceError,
    RepositoryError,
    SecretStoreError,
    SecureObjectUnreadableError,
    SecureStorageError,
    StorageError,
)
from .master_key._active_session import NoActiveBucketSessionError

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_secure_storage_base_reuses_central_aeat_error_registry() -> None:
    assert issubclass(SecureStorageError, AeatError)
    assert issubclass(StorageError, SecureStorageError)
    assert issubclass(RepositoryError, SecureStorageError)
    assert issubclass(PersistenceError, SecureStorageError)
    assert issubclass(SecretStoreError, SecureStorageError)
    assert issubclass(BucketError, SecureStorageError)
    assert get_registered_error_code(SecureStorageError).code == "FAIL_SECURE_STORAGE"


def test_secure_object_unreadable_uses_locale_registry_message() -> None:
    error = SecureObjectUnreadableError("calculation-observations", 42)
    code = get_registered_error_code(SecureObjectUnreadableError)

    assert isinstance(error, DecryptionError)
    assert error.args == ()
    assert error.translated_message == code.message_key
    assert error.context == {"namespace": "calculation-observations", "row_id": 42}
    assert "calculation-observations/#42" not in resolve_error_message(error)


def test_no_active_bucket_session_error_uses_locale_registry_message() -> None:
    error = NoActiveBucketSessionError("legacy active-session detail")
    code = get_registered_error_code(NoActiveBucketSessionError)

    assert error.args == ()
    assert error.translated_message == code.message_key
    assert resolve_error_message(error) != "legacy active-session detail"
