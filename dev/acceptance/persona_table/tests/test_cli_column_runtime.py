"""The CLI column's teardown removes only a disposable root it owns and follows no link; secrets stay in one child."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import pytest

from dev.runtime_lifecycle.caller_owned_root import AcceptanceError

from ..cli_column.hygiene import OAUTH_CLIENT_ENV
from ..cli_column.runtime import (
    RuntimeSetupError,
    build_environment,
    child_environment,
    remove_snapshot,
    snapshot_path,
    teardown_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _root_name() -> str:
    return f"cadrumo-e2e-{secrets.token_hex(16)}"


def _link(link: Path, target: Path) -> None:
    """A directory link without privilege: a junction on Windows, a symbolic link elsewhere."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def test_a_disposable_root_is_removed_with_everything_in_it(tmp_path: Path) -> None:
    root = tmp_path / _root_name()
    (root / "runtime" / "deep").mkdir(parents=True)
    (root / "runtime" / "deep" / "file.txt").write_text("held", encoding="utf-8")

    left = teardown_root(root, tmp_path)

    assert left == []
    assert not root.exists()


def test_a_path_outside_the_disposable_root_naming_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "profile-data"
    other.mkdir()
    (other / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(AcceptanceError, match="not named like a disposable root"):
        teardown_root(other, tmp_path)

    assert (other / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_a_root_that_is_not_directly_below_the_parent_is_refused(tmp_path: Path) -> None:
    nested = tmp_path / "inner" / _root_name()
    nested.mkdir(parents=True)

    with pytest.raises(AcceptanceError, match="not directly below"):
        teardown_root(nested, tmp_path)

    assert nested.is_dir()


def test_a_link_named_like_a_root_is_refused_and_its_target_stays(tmp_path: Path) -> None:
    target = tmp_path / "somewhere-else"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / _root_name()
    _link(link, target)

    with pytest.raises(AcceptanceError, match="it is a link"):
        teardown_root(link, tmp_path)

    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_a_link_inside_the_root_is_removed_without_following_it(tmp_path: Path) -> None:
    target = tmp_path / "outside"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    root = tmp_path / _root_name()
    root.mkdir()
    _link(root / "pointer", target)

    left = teardown_root(root, tmp_path)

    assert left == []
    assert not root.exists()
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_a_missing_root_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AcceptanceError, match="not a directory"):
        teardown_root(tmp_path / _root_name(), tmp_path)


def test_a_snapshot_is_removed_only_when_it_is_named_and_shaped_like_one(tmp_path: Path) -> None:
    snapshot = tmp_path / "snap-abc"
    (snapshot / "src").mkdir(parents=True)
    (snapshot / "src" / "locked.txt").write_text("x", encoding="utf-8")
    (snapshot / "src" / "locked.txt").chmod(0o444)

    assert remove_snapshot(snapshot) == []
    assert not snapshot.exists()


def test_a_directory_not_named_like_a_snapshot_or_holding_git_is_not_removed(tmp_path: Path) -> None:
    other = tmp_path / "checkout"
    other.mkdir()
    repository = tmp_path / "snap-with-git"
    (repository / ".git").mkdir(parents=True)

    with pytest.raises(RuntimeSetupError, match="not a snapshot directory"):
        remove_snapshot(other)
    with pytest.raises(RuntimeSetupError, match=r"holds a \.git entry"):
        remove_snapshot(repository)

    assert other.is_dir()
    assert repository.is_dir()


def test_a_link_named_like_a_snapshot_is_not_removed(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "snap-link"
    _link(link, target)

    with pytest.raises(RuntimeSetupError, match="not a snapshot directory"):
        remove_snapshot(link)

    assert target.is_dir()


def test_children_never_see_a_product_setting_the_interpreter_selection_or_the_oauth_client(tmp_path: Path) -> None:
    ambient = {
        "PATH": "p",
        "CADRUMO_STORAGE_ROOT": "x",
        "cadrumo_authority_root": "y",
        OAUTH_CLIENT_ENV: "client",
        "PYTHONPATH": "elsewhere",
        "VIRTUAL_ENV": "venv",
        "AEAT_OLD": "z",
    }

    environment = child_environment(ambient, python_path=snapshot_path(tmp_path))

    assert environment == {"PATH": "p", "PYTHONPATH": os.pathsep.join([str(tmp_path / "src"), str(tmp_path)])}


def test_only_the_build_environment_carries_the_oauth_client(tmp_path: Path) -> None:
    ambient = {"PATH": "p", OAUTH_CLIENT_ENV: "ambient-client", "CADRUMO_X": "1"}

    build = build_environment(tmp_path, "build-client", ambient)

    assert build[OAUTH_CLIENT_ENV] == "build-client"
    assert "CADRUMO_X" not in build
    assert OAUTH_CLIENT_ENV not in child_environment(ambient)
