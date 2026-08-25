"""Tests for filing application runtime repository helpers.

The tests pin explicit-or-active bucket id resolution and the refusal path for
an unready secure-object runtime without replacing storage with fakes. This
keeps the application filing boundary honest: helper imports stay cheap at
module load time, while runtime repository construction still validates the
active bucket session before returning storage.

See Also:
    :func:`~application.filing._runtime_repository.resolve_application_filing_bucket_id`
        Helper under test for explicit bucket ids and active-profile fallback.
    :func:`~application.filing._runtime_repository.secure_objects_for_application_filing_bucket`
        Runtime storage factory wrapper whose unready-bucket refusal is covered.
    :func:`~core.bucket_pointer.resolve_repository_bucket_id`
        Shared resolver that normalizes explicit-or-active repository bucket ids.
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`
        Secure-object factory reached only when runtime storage is requested.
    :mod:`~adapters.persistence.profile._filing_runtime`
        Adapter-layer sibling helper with the same bucket-resolution shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....core.config import override_settings
from ....tests.secure_sql import isolated_storage_root as _isolated_storage  # noqa: F401 - autouse fixture
from .._runtime_repository import (
    resolve_application_filing_bucket_id,
    secure_objects_for_application_filing_bucket,
)
from ..errors import ModeloApplicationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPLICIT_BUCKET_ID = "2f85f149-2df7-41b7-b569-aae0b3d0998d"
_ACTIVE_BUCKET_ID = "34245238-a76d-4ebf-a515-8e5af83cfc0c"


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
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile):
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
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=active_profile),
        pytest.raises(ModeloApplicationError) as raised,
    ):
        resolve_application_filing_bucket_id(explicit_bucket_id)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": expected_reason}


def test_secure_objects_for_application_filing_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID),
        pytest.raises(
            StorageValidationError,
            match=r"storage runtime is not ready|no active bucket session|route does not match",
        ),
    ):
        secure_objects_for_application_filing_bucket(_ACTIVE_BUCKET_ID)
