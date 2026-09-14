"""Tests for filing persistence-adapter runtime helpers.

These tests belong with the adapter that resolves bucket-scoped secure storage.
The application layer consumes ports and does not own runtime repository
construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile._filing_runtime import resolve_filing_repository_bucket_id
from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_storage_root as _isolated_storage,  # noqa: F401 - autouse fixture
)
from cadrumo.core.config import override_settings
from cadrumo.domain.filing.errors import ModeloDraftError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_EXPLICIT_BUCKET_ID = "2f85f149-2df7-41b7-b569-aae0b3d0998d"
_ACTIVE_BUCKET_ID = "34245238-a76d-4ebf-a515-8e5af83cfc0c"


@pytest.mark.parametrize(
    ("bucket_id", "active_profile", "expected"),
    (
        (f"  {_EXPLICIT_BUCKET_ID}  ", _ACTIVE_BUCKET_ID, _EXPLICIT_BUCKET_ID),
        (None, _ACTIVE_BUCKET_ID, _ACTIVE_BUCKET_ID),
    ),
)
def test_resolve_filing_repository_bucket_id_accepts_explicit_or_active_bucket(
    tmp_path: Path,
    bucket_id: str | None,
    active_profile: str,
    expected: str,
) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile):
        assert resolve_filing_repository_bucket_id(bucket_id) == expected


@pytest.mark.parametrize(
    ("explicit_bucket_id", "active_profile", "expected_reason"),
    (
        ("  ", _ACTIVE_BUCKET_ID, "blank_explicit_bucket_id"),
        (None, None, "missing_active_profile_bucket"),
    ),
)
def test_resolve_filing_repository_bucket_id_rejects_missing_bucket(
    tmp_path: Path,
    explicit_bucket_id: str | None,
    active_profile: str | None,
    expected_reason: str,
) -> None:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile),
        pytest.raises(ModeloDraftError) as raised,
    ):
        resolve_filing_repository_bucket_id(explicit_bucket_id)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": expected_reason}


def test_secure_objects_for_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(StorageValidationError) as refusal,
    ):
        secure_object_repository_for_bucket(_ACTIVE_BUCKET_ID)

    assert refusal.value.translated_message == "errors.storage.runtime.not_ready"
