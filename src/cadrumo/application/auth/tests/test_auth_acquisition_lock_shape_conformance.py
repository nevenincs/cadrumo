"""The real auth-acquisition lock file matches its declared grammar shape.

Unlike the LLM usage/telemetry/cache logical paths, ``auth_acquisition_lock``
is a real filesystem write: :func:`acquire_auth_acquisition_lock` opens the
lock file with ``os.open(..., O_CREAT | O_EXCL | O_WRONLY)``. This drives that
real writer and asserts the real resulting path against the declared grammar.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.auth_provider import AuthProviderKind
from ....core.storage_taxonomy_locations import storage_location
from ....core.storage_taxonomy import StorageCategory
from ....core.config import Settings, override_settings
from ....tests import assert_path_matches_grammar
from ..acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _active_profile() -> Iterator[None]:
    with override_settings(cadrumo_active_profile="operator"):
        yield


def test_the_real_lock_file_matches_its_declared_shape(tmp_path: Path) -> None:
    root = tmp_path
    settings = Settings(cadrumo_local_storage_root=root)

    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ) as record:
        path = auth_acquisition_lock_path(settings, AuthProviderKind.CLAVE_MOVIL)
        assert path.is_file()
        assert_path_matches_grammar(key="auth_acquisition_lock", root=root, produced=path)
        assert record.provider_kind is AuthProviderKind.CLAVE_MOVIL


def test_a_non_conforming_lock_filename_is_rejected_by_the_grammar(tmp_path: Path) -> None:
    """Positive control: the matcher can still fail."""
    malformed = tmp_path / storage_location(StorageCategory.TOKENS).subpath / "not-shaped-like-a-lock-file.txt"
    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="auth_acquisition_lock", root=tmp_path, produced=malformed)
