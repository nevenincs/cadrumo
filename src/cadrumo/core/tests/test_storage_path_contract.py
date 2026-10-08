"""Host path eligibility and preparation before filesystem effects."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..errors.hierarchy import CoreValidationError
from ..storage_environment import (
    PROCESS_ENVIRONMENT,
    STORAGE_ROOT,
    ChildEnvironmentProfile,
    StorageMode,
    StorageModeEvidence,
    StorageRootRefusal,
    child_environment,
    normalize_storage_path,
    resolve_storage_path,
    storage_root_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_host_resolution_normalizes_missing_components_without_creating_them(tmp_path: Path) -> None:
    raw = tmp_path / "missing" / ".." / "selected"
    result = storage_root_for({STORAGE_ROOT.variable: str(raw)}, StorageModeEvidence(StorageMode.INSTALLED, None))
    assert result == tmp_path / "selected"
    assert not result.exists() and not (tmp_path / "missing").exists()


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
@pytest.mark.parametrize("value", ["relative", "", "\udcff"])
def test_inherited_paths_refuse_before_root_creation(
    tmp_path: Path, profile: ChildEnvironmentProfile, value: str
) -> None:
    root = tmp_path / "root"
    name = PROCESS_ENVIRONMENT.host_inherited[0]
    with pytest.raises(CoreValidationError) as error:
        child_environment(profile, root, received={name: value})
    expected = StorageRootRefusal.INVALID_PATH_INPUT if value == "\udcff" else StorageRootRefusal.NON_ABSOLUTE_PIN
    assert error.value.context is not None
    assert error.value.context["storage_root_refusal"] == expected.value
    assert not root.exists()


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
def test_valid_inherited_path_spelling_and_opaque_values_survive(
    tmp_path: Path, profile: ChildEnvironmentProfile
) -> None:
    inherited = str(tmp_path / "missing" / ".." / "authority")
    name = PROCESS_ENVIRONMENT.host_inherited[0]
    environment = child_environment(profile, tmp_path / "root", received={name: inherited, "ORDINARY_VALUE": "\udcff"})
    assert environment[name] == inherited
    assert environment["ORDINARY_VALUE"] == "\udcff"
    assert not (tmp_path / "missing").exists()


def test_temporary_home_uses_received_mapping_and_invalid_home_has_no_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home_name = "USERPROFILE" if os.name == "nt" else "HOME"
    monkeypatch.setenv(home_name, str(tmp_path / "ambient-home"))
    supplied = tmp_path / "supplied-home"
    environment = child_environment(
        ChildEnvironmentProfile.OPERATOR,
        tmp_path / "root",
        received={home_name: str(supplied), "CADRUMO_TEMP_DIR": "~/unused/../scratch"},
    )
    assert environment[PROCESS_ENVIRONMENT.temporary_variables[0]] == str(supplied / "scratch")
    assert (supplied / "scratch").is_dir() and not (supplied / "unused").exists()
    assert not (tmp_path / "ambient-home").exists()
    root = tmp_path / "refused-root"
    with pytest.raises(CoreValidationError) as error:
        child_environment(
            ChildEnvironmentProfile.OPERATOR, root, received={home_name: "\udcff", "CADRUMO_TEMP_DIR": "~/scratch"}
        )
    assert error.value.context is not None
    assert error.value.context["storage_root_refusal"] == StorageRootRefusal.INVALID_PATH_INPUT.value
    assert not root.exists()


def test_member_expansion_refuses_named_users_and_relative_home(tmp_path: Path) -> None:
    home_name = "USERPROFILE" if os.name == "nt" else "HOME"
    for value, home, expected in [
        ("~someone/state", str(tmp_path), StorageRootRefusal.INVALID_PATH_INPUT),
        ("~/state", "relative", StorageRootRefusal.HOME_UNAVAILABLE),
    ]:
        with pytest.raises(CoreValidationError) as error:
            resolve_storage_path(value, root=tmp_path / "root", received={home_name: home})
        assert error.value.context is not None
        assert error.value.context["storage_root_refusal"] == expected.value
    assert not (tmp_path / "root").exists()


def test_filesystem_failure_stays_distinct_from_non_absolute_input(tmp_path: Path) -> None:
    file = tmp_path / "file"
    file.write_text("fixture")
    with pytest.raises(CoreValidationError) as error:
        normalize_storage_path(file / "child")
    assert error.value.context is not None
    assert error.value.context["storage_root_refusal"] == StorageRootRefusal.FILESYSTEM_PATH_REFUSED.value


@pytest.mark.skipif(os.name == "nt", reason="POSIX creation mode")
def test_creation_keeps_existing_modes_and_makes_new_intermediate_directories_private(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir(mode=0o755)
    environment = child_environment(ChildEnvironmentProfile.STRICT, existing / "new" / "root", received={})
    assert existing.stat().st_mode & 0o777 == 0o755
    for directory in [existing / "new", existing / "new/root", Path(environment["TMPDIR"])]:
        assert directory.stat().st_mode & 0o777 == STORAGE_ROOT.posix_directory_mode
