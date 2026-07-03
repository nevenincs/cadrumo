"""Tests for the filing persistence-adapter runtime repository helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....domain.filing import ModeloDraftError
from ...storage import StorageValidationError, dispose_engine
from .._filing_runtime import resolve_filing_repository_bucket_id, secure_objects_for_filing_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

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


def test_resolve_filing_repository_bucket_id_accepts_explicit_or_active_bucket(tmp_path: Path) -> None:
    cases = (
        ("explicit", f"  {_EXPLICIT_BUCKET_ID}  ", _ACTIVE_BUCKET_ID, _EXPLICIT_BUCKET_ID),
        ("active", None, _ACTIVE_BUCKET_ID, _ACTIVE_BUCKET_ID),
    )
    for case_id, bucket_id, active_profile, expected in cases:
        with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile):
            assert resolve_filing_repository_bucket_id(bucket_id) == expected, case_id


def test_resolve_filing_repository_bucket_id_rejects_unresolved_bucket(tmp_path: Path) -> None:
    cases = (
        ("blank-explicit", "  ", _ACTIVE_BUCKET_ID, "blank_explicit_bucket_id"),
        ("missing-active", None, None, "missing_active_profile_bucket"),
    )
    for case_id, bucket_id, active_profile, expected_reason in cases:
        with (
            override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile),
            pytest.raises(ModeloDraftError) as raised,
        ):
            resolve_filing_repository_bucket_id(bucket_id)

        assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket", case_id
        assert raised.value.context == {"reason": expected_reason}, case_id


def test_secure_objects_for_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(
            StorageValidationError,
            match=r"storage runtime is not ready|no active bucket session|route does not match",
        ),
    ):
        secure_objects_for_filing_bucket(_ACTIVE_BUCKET_ID)
