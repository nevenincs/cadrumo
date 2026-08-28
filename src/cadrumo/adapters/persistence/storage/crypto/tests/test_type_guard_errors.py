from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from sqlalchemy.engine import Dialect

from ...errors import StorageValidationError
from ..encrypted_columns import EncryptedBytes, EncryptedString, HashedLookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def encrypted_string_with_wrong_type() -> None:
    EncryptedString().process_bind_param(cast(str, 12345), cast(Dialect, None))


def encrypted_bytes_with_wrong_type() -> None:
    EncryptedBytes().process_bind_param(cast(bytes, "not-bytes"), cast(Dialect, None))


def hashed_lookup_compute_with_wrong_type() -> None:
    HashedLookup.compute(cast(str, 12345))


def hashed_lookup_bind_with_wrong_type() -> None:
    HashedLookup().process_bind_param(cast(str | bytes, 99.9), cast(Dialect, None))


@pytest.mark.parametrize(
    "call",
    (
        encrypted_string_with_wrong_type,
        encrypted_bytes_with_wrong_type,
        hashed_lookup_compute_with_wrong_type,
        hashed_lookup_bind_with_wrong_type,
    ),
)
def test_encrypted_column_type_guards_raise_storage_validation_error(call: Callable[[], object]) -> None:
    with pytest.raises(StorageValidationError) as raised:
        call()

    assert raised.type is StorageValidationError
