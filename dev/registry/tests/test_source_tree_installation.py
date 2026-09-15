"""Safety tests for proven registry source installation."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ..source_tree_installation import fingerprint, install_proven_tree

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
