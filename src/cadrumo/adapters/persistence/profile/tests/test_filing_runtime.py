"""Tests for filing persistence-adapter runtime repository helpers.

The suite pins explicit bucket-id resolution, active-profile fallback, typed
refusal context, and runtime-readiness failure for filing repositories that bind
to secure-object storage through the bucket runtime.

See Also:
    :mod:`~adapters.persistence.profile._filing_runtime`
        Adapter-layer resolver and secure-object factory under test.
    :func:`~core.bucket_pointer.resolve_repository_bucket_id`
        Shared explicit-or-active bucket resolver used by filing and modelo
        repositories.
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`
        Runtime storage factory that refuses unready bucket sessions.

The secure-storage architecture requires this fail-closed runtime readiness
gate: an unready bucket session must refuse rather than silently degrade.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....domain.filing.errors import ModeloDraftError
from .....tests.secure_sql import isolated_storage_root as _isolated_storage  # noqa: F401 - autouse fixture
from ...storage import StorageRuntimeReadinessCode, StorageValidationError, secure_object_repository_for_bucket
from .._filing_runtime import resolve_filing_repository_bucket_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_EXPLICIT_BUCKET_ID = "2f85f149-2df7-41b7-b569-aae0b3d0998d"
_ACTIVE_BUCKET_ID = "34245238-a76d-4ebf-a515-8e5af83cfc0c"


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
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile):
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
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile),
        pytest.raises(ModeloDraftError) as raised,
    ):
        resolve_filing_repository_bucket_id(bucket_id)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": expected_reason}


def test_secure_objects_for_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    # Asserted on the TYPED readiness code, not on prose. The refusal is
    # deliberately locale-neutral -- the operator sentence comes from a
    # translation key and the codes travel as structured context -- so a regex
    # over the message matches the key rather than any rendered English, and
    # would pass just as readily on an unrelated storage refusal.
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(StorageValidationError) as raised,
    ):
        secure_object_repository_for_bucket(_ACTIVE_BUCKET_ID)

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert raised.value.context is not None
    assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.NO_ACTIVE_SESSION.value
