"""Tests for filing persistence-adapter runtime repository helpers.

The suite pins explicit bucket-id resolution, active-profile fallback, typed
refusal context, and runtime-readiness failure for filing repositories that bind
to secure-object storage through the bucket runtime.

See Also:
    :mod:`~adapters.persistence.profile._filing_runtime`
        Adapter-layer resolver and secure-object factory under test.
    :func:`~core.resolve_repository_bucket_id`
        Shared explicit-or-active bucket resolver used by filing and modelo
        repositories.
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`
        Runtime storage factory that refuses unready bucket sessions.
    Governing vault records
        ``2026-06-04-secure-storage-production-hardening-w12-p26-s210-review-audit``
        closes the filing runtime helper as runtime-default; the secure-storage
        production-hardening architecture ADR requires this fail-closed runtime
        readiness gate.
"""

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


@pytest.mark.parametrize(
    ("bucket_id", "active_profile", "expected"),
    (
        pytest.param(f"  {_EXPLICIT_BUCKET_ID}  ", _ACTIVE_BUCKET_ID, _EXPLICIT_BUCKET_ID, id="explicit"),
        pytest.param(None, _ACTIVE_BUCKET_ID, _ACTIVE_BUCKET_ID, id="active"),
    ),
)
def test_resolve_filing_repository_bucket_id_accepts_explicit_or_active_bucket(
    tmp_path: Path,
    bucket_id: str | None,
    active_profile: str,
    expected: str,
) -> None:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile):
        assert resolve_filing_repository_bucket_id(bucket_id) == expected


@pytest.mark.parametrize(
    ("bucket_id", "active_profile", "expected_reason"),
    (
        pytest.param("  ", _ACTIVE_BUCKET_ID, "blank_explicit_bucket_id", id="blank-explicit"),
        pytest.param(None, None, "missing_active_profile_bucket", id="missing-active"),
    ),
)
def test_resolve_filing_repository_bucket_id_rejects_unresolved_bucket(
    tmp_path: Path,
    bucket_id: str | None,
    active_profile: str | None,
    expected_reason: str,
) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=active_profile),
        pytest.raises(ModeloDraftError) as raised,
    ):
        resolve_filing_repository_bucket_id(bucket_id)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": expected_reason}


def test_secure_objects_for_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(
            StorageValidationError,
            match=r"storage runtime is not ready|no active bucket session|route does not match",
        ),
    ):
        secure_objects_for_filing_bucket(_ACTIVE_BUCKET_ID)
