"""Contract tests for the secure-storage exception hierarchy."""

from __future__ import annotations

import pytest

from .....core.errors import CadrumoError, get_registered_error_code, resolve_error_message
from ..bucket import BucketError
from ..errors import (
    DecryptionError,
    PersistenceError,
    RepositoryError,
    SecretStoreError,
    SecureObjectUnreadableError,
    SecureStorageError,
    StorageError,
)
from ..master_key import NoActiveBucketSessionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_secure_storage_errors_reuse_central_cadrumo_error_registry() -> None:
    for error_type in (
        SecureStorageError,
        StorageError,
        RepositoryError,
        PersistenceError,
        SecretStoreError,
        DecryptionError,
        BucketError,
        NoActiveBucketSessionError,
    ):
        assert issubclass(error_type, CadrumoError), error_type.__name__
        assert issubclass(error_type, SecureStorageError), error_type.__name__


def test_secure_storage_base_error_is_registered() -> None:
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
