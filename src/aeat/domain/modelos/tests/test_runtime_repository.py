"""Tests for modelo domain runtime repository helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from .._repository import WorkUnitPersistenceError
from .._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path):
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def test_resolve_modelo_repository_bucket_id_accepts_explicit_bucket() -> None:
    assert (
        resolve_modelo_repository_bucket_id(
            "  modelo-bucket  ",
            error_type=WorkUnitPersistenceError,
        )
        == "modelo-bucket"
    )


def test_resolve_modelo_repository_bucket_id_rejects_blank_explicit_bucket() -> None:
    with pytest.raises(WorkUnitPersistenceError) as raised:
        resolve_modelo_repository_bucket_id("  ", error_type=WorkUnitPersistenceError)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": "blank_explicit_bucket_id"}


def test_resolve_modelo_repository_bucket_id_uses_active_profile_setting(tmp_path: Path) -> None:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="active-modelo-bucket"):
        assert (
            resolve_modelo_repository_bucket_id(
                None,
                error_type=WorkUnitPersistenceError,
            )
            == "active-modelo-bucket"
        )


def test_resolve_modelo_repository_bucket_id_rejects_missing_active_profile(tmp_path: Path) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None),
        pytest.raises(WorkUnitPersistenceError) as raised,
    ):
        resolve_modelo_repository_bucket_id(None, error_type=WorkUnitPersistenceError)

    assert raised.value.translated_message == "application.workflow.errors.no_active_profile_bucket"
    assert raised.value.context == {"reason": "missing_active_profile_bucket"}


def test_secure_objects_for_modelo_bucket_refuses_unready_runtime(tmp_path: Path) -> None:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        pytest.raises(
            StorageValidationError,
            match=r"storage runtime is not ready|no active bucket session|route does not match",
        ),
    ):
        secure_objects_for_modelo_bucket("bucket-a")
