"""Tests for filing application runtime repository helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from .._runtime_repository import (
    resolve_application_filing_bucket_id,
    secure_objects_for_application_filing_bucket,
)
from ..errors import ModeloApplicationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPLICIT_BUCKET_ID = "2f85f149-2df7-41b7-b569-aae0b3d0998d"
_ACTIVE_BUCKET_ID = "34245238-a76d-4ebf-a515-8e5af83cfc0c"


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path):
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@pytest.mark.parametrize(
    ("bucket_id", "active_profile", "expected"),
    (
        (f"  {_EXPLICIT_BUCKET_ID}  ", _ACTIVE_BUCKET_ID, _EXPLICIT_BUCKET_ID),
        (None, _ACTIVE_BUCKET_ID, _ACTIVE_BUCKET_ID),
    ),
)
def test_resolve_application_filing_bucket_id_accepts_explicit_or_active_bucket(
    tmp_path: Path,
    bucket_id: str | None,
    active_profile: str,
    expected: str,
) -> None:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile):
        assert resolve_application_filing_bucket_id(bucket_id) == expected


@pytest.mark.parametrize(
    ("explicit_bucket_id", "active_profile", "expected_reason"),
    (
        ("  ", _ACTIVE_BUCKET_ID, "blank_explicit_bucket_id"),
        (None, None, "missing_active_profile_bucket"),
    ),
)
def test_resolve_application_filing_bucket_id_rejects_missing_bucket(
    tmp_path: Path,
    explicit_bucket_id: str | None,
    active_profile: str | None,
    expected_reason: str,
) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile),
        pytest.raises(ModeloApplicationError) as raised,
    ):
        resolve_application_filing_bucket_id(explicit_bucket_id)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": expected_reason}


def test_secure_objects_for_application_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(
            StorageValidationError,
            match=r"storage runtime is not ready|no active bucket session|route does not match",
        ),
    ):
        secure_objects_for_application_filing_bucket(_ACTIVE_BUCKET_ID)
