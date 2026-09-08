from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from sqlalchemy.engine import Dialect

from ...errors import StorageValidationError
from ..encrypted_columns import HashedLookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def hashed_lookup_compute_with_wrong_type() -> None:
    HashedLookup.compute(cast(str, 12345))


def hashed_lookup_bind_with_wrong_type() -> None:
    HashedLookup().process_bind_param(cast(str | bytes, 99.9), cast(Dialect, None))


@pytest.mark.parametrize(
    "call",
    (
        hashed_lookup_compute_with_wrong_type,
        hashed_lookup_bind_with_wrong_type,
    ),
)
def test_encrypted_column_type_guards_raise_storage_validation_error(call: Callable[[], object]) -> None:
    with pytest.raises(StorageValidationError) as raised:
        call()

    assert raised.type is StorageValidationError
