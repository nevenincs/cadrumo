"""A launcher tells each child the folder of the one profile it starts it for, and nothing reads it back."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..config import Settings
from ..profile_root_environment import PROFILE_ROOT_VARIABLE, profile_root, profile_root_environment
from ..storage_environment import STORAGE_ROOT, ChildEnvironmentProfile, child_environment
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import bucket_scoped_storage_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_A = "2a0c6b1e-5d4f-4e3a-9b8c-7d6e5f4a3b2c"
_PROFILE_B = "3b1d7c2f-6e5a-4f4b-8c9d-8e7f6a5b4c3d"


def test_the_folder_is_the_profiles_bucket_the_storage_layer_resolves(tmp_path: Path) -> None:
    settings = Settings(cadrumo_storage_root=tmp_path)
    database = bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE_FILE, _PROFILE_A, settings=settings)

    folder = profile_root(tmp_path, _PROFILE_A)

    assert database.is_relative_to(folder)
    assert folder.parent == profile_root(tmp_path, _PROFILE_B).parent
    assert folder != profile_root(tmp_path, _PROFILE_B)


@pytest.mark.parametrize("identity", ["", "..", "a/b", "not-a-profile"])
def test_a_value_that_is_not_a_profile_identity_names_no_folder(tmp_path: Path, identity: str) -> None:
    with pytest.raises(ValueError, match="canonical profile identity"):
        profile_root(tmp_path, identity)


def test_no_profile_served_means_no_variable(tmp_path: Path) -> None:
    assert profile_root_environment(tmp_path, None) == {}


@pytest.mark.parametrize("profile", [ChildEnvironmentProfile.STRICT, ChildEnvironmentProfile.OPERATOR])
def test_a_child_is_told_its_own_profiles_folder_and_never_a_received_one(
    tmp_path: Path, profile: ChildEnvironmentProfile
) -> None:
    root = tmp_path / "state"
    stale = {PROFILE_ROOT_VARIABLE: str(profile_root(root, _PROFILE_B))}

    for_a = child_environment(profile, root, received=stale, sys_platform="win32", profile_id=_PROFILE_A)
    for_none = child_environment(profile, root, received=stale, sys_platform="win32")

    assert for_a[PROFILE_ROOT_VARIABLE] == str(profile_root(Path(for_a[STORAGE_ROOT.variable]), _PROFILE_A))
    assert PROFILE_ROOT_VARIABLE not in for_none


def test_the_variable_selects_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PROFILE_ROOT_VARIABLE, str(profile_root(tmp_path, _PROFILE_A)))

    settings = Settings(cadrumo_storage_root=tmp_path)

    assert not (settings.cadrumo_active_profile or "").strip()
