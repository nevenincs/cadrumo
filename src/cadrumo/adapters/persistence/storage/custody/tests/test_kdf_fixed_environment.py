"""KDF readiness accepts only caller names plus package-declared fixed names."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from .._kdf_process import _environment_keys
from .._kdf_worker_identity import _validate_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_native_fixed_names_are_attested_without_admitting_other_ambient_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "cadrumo_build", {"fixed_environment_names": ("PACKAGE_IDENTITY",)}, raising=False)
    expected = _environment_keys({"env": {"HOME": "/neutral"}})
    assert expected == frozenset({"HOME", "PACKAGE_IDENTITY"})
    directory = tempfile.TemporaryDirectory()
    with directory as name:
        # The identity value belongs to the native host; the readiness frame
        # discloses only names, and must still reject every undeclared name.
        payload: dict[str, object] = {
            "cwd": str(Path(name).resolve()),
            "environment_keys": ["HOME", "PACKAGE_IDENTITY"],
        }
        _validate_environment(payload, neutral_directory=directory, environment_keys=expected)
        for keys in (["HOME"], ["HOME", "PACKAGE_IDENTITY", "UNDECLARED"]):
            payload["environment_keys"] = keys
            with pytest.raises(ValueError, match="environment is not allowlisted"):
                _validate_environment(payload, neutral_directory=directory, environment_keys=expected)


def test_unpackaged_launch_does_not_admit_fixed_names_from_the_ambient_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "cadrumo_build", raising=False)
    monkeypatch.setenv("PACKAGE_IDENTITY", "ambient")
    assert _environment_keys({"env": {"HOME": "/neutral"}}) == frozenset({"HOME"})


@pytest.mark.skipif(sys.platform == "win32", reason="directory symlinks need a privilege on Windows")
def test_neutral_directory_is_compared_by_identity_across_a_symlinked_temporary_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    (real_root / "other").mkdir(parents=True)
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)
    directory = tempfile.TemporaryDirectory(dir=linked_root)
    expected = frozenset({"HOME"})
    with directory as name:
        assert Path(name).parent == linked_root
        # A kernel-reported working directory is the link-free spelling.
        payload: dict[str, object] = {"cwd": str(Path(name).resolve()), "environment_keys": ["HOME"]}
        _validate_environment(payload, neutral_directory=directory, environment_keys=expected)
        for other in (str(real_root / "other"), str(Path(name) / "missing"), "", 7):
            payload["cwd"] = other
            with pytest.raises(ValueError, match="cwd is not neutral"):
                _validate_environment(payload, neutral_directory=directory, environment_keys=expected)
