"""Safety tests for proven registry source installation."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from ..source_tree_installation import fingerprint, install_proven_tree, replace_file_if_unchanged

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _trees(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    live = tmp_path / "live"
    live.mkdir()
    (live / "revision.toml").write_text("before\n", encoding="utf-8")
    original = shutil.copytree(live, tmp_path / "original")
    staged = shutil.copytree(live, tmp_path / "staged")
    (staged / "revision.toml").write_text("after\n", encoding="utf-8")
    return live, staged, original, fingerprint(original)


def test_install_proven_tree_applies_exact_proven_bytes(tmp_path: Path) -> None:
    live, staged, original, before = _trees(tmp_path)

    install_proven_tree(live, staged, original, before)

    assert fingerprint(live) == fingerprint(staged)


def test_install_proven_tree_refuses_a_concurrent_edit_before_writing(tmp_path: Path) -> None:
    live, staged, original, before = _trees(tmp_path)
    (live / "revision.toml").write_text("concurrent\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source changed before installation"):
        install_proven_tree(live, staged, original, before)

    assert (live / "revision.toml").read_text(encoding="utf-8") == "concurrent\n"


def test_install_proven_tree_rolls_back_its_writes_when_final_verification_refuses(tmp_path: Path) -> None:
    live, staged, original, before = _trees(tmp_path)
    # A directory the live tree never gains fails the post-write directory-set check.
    (staged / "casillas").mkdir()

    with pytest.raises(ValueError, match=r"source directory set changed during installation.*rolled back"):
        install_proven_tree(live, staged, original, before)

    assert (live / "revision.toml").read_text(encoding="utf-8") == "before\n"
    assert fingerprint(live) == before


def test_replace_captures_a_concurrent_edit_instead_of_overwriting_it(tmp_path: Path) -> None:
    target = tmp_path / "revision.toml"
    replacement = tmp_path / "replacement.toml"
    target.write_text("before\n", encoding="utf-8")
    replacement.write_text("after\n", encoding="utf-8")
    hashed_before_the_edit = hashlib.sha256(b"before\n").hexdigest()
    # The installer hashed the file, then another writer changed it before replacement.
    target.write_text("concurrent\n", encoding="utf-8")

    with pytest.raises(ValueError, match="concurrent edit captured"):
        replace_file_if_unchanged(target, replacement, hashed_before_the_edit)

    assert target.read_text(encoding="utf-8") == "concurrent\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["replacement.toml", "revision.toml"]
