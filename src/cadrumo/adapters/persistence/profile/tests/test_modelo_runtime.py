"""Tests for the modelo persistence-adapter runtime repository helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import resolve_repository_bucket_id
from .....core.config import override_settings
from .....domain.modelos import WorkUnitPersistenceError
from .....tests.secure_sql import isolated_storage_root as _isolated_storage  # noqa: F401 - autouse fixture
from ...storage import StorageRuntimeReadinessCode, StorageValidationError, secure_object_repository_for_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_EXPLICIT_BUCKET_ID = "5bfb9265-6886-4067-8d27-138978e71d95"
_ACTIVE_BUCKET_ID = "9cc2d040-7e90-4f88-8f83-8d6bf63c4e65"


def test_resolve_modelo_repository_bucket_id_accepts_explicit_bucket() -> None:
    assert (
        resolve_repository_bucket_id(
            f"  {_EXPLICIT_BUCKET_ID}  ",
            error_type=WorkUnitPersistenceError,
        )
        == _EXPLICIT_BUCKET_ID
    )


def test_resolve_modelo_repository_bucket_id_rejects_blank_explicit_bucket() -> None:
    with pytest.raises(WorkUnitPersistenceError) as raised:
        resolve_repository_bucket_id("  ", error_type=WorkUnitPersistenceError)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": "blank_explicit_bucket_id"}


def test_resolve_modelo_repository_bucket_id_uses_active_profile_setting(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID):
        assert (
            resolve_repository_bucket_id(
                None,
                error_type=WorkUnitPersistenceError,
            )
            == _ACTIVE_BUCKET_ID
        )


def test_resolve_modelo_repository_bucket_id_rejects_missing_active_profile(tmp_path: Path) -> None:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None),
        pytest.raises(WorkUnitPersistenceError) as raised,
    ):
        resolve_repository_bucket_id(None, error_type=WorkUnitPersistenceError)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": "missing_active_profile_bucket"}


def test_secure_objects_for_modelo_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
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
