"""Installation admission keeps checking live paths while avoiding repeat walks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..installation import member

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("relative", ["", ".", "..", "../outside", "a/../../outside", "/outside", "C:/outside", "a\\b"])
def test_member_refuses_nonlocal_names(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError, match="Unsafe installation member"):
        member(tmp_path, relative)


@pytest.mark.skipif(os.name != "nt", reason="Win32 path alias semantics")
@pytest.mark.parametrize("relative", [".. /outside", ".../outside", "NUL", "sub/CON.txt", "file.", "file "])
def test_member_refuses_windows_normalization_and_device_aliases(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError, match="Unsafe installation member"):
        member(tmp_path, relative)


def test_member_can_name_a_new_nested_output(tmp_path: Path) -> None:
    assert member(tmp_path / "future-root", "new/directory/file") == tmp_path / "future-root/new/directory/file"


def test_member_accepts_long_unicode_paths(tmp_path: Path) -> None:
    relative = "/".join(["información " + "x" * 65] * 4) + "/receipt.txt"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"receipt")
    assert member(tmp_path, relative).read_bytes() == b"receipt"


def _redirect(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = run_command(
            [
                str(Path(os.environ["SYSTEMROOT"]) / "System32/cmd.exe"),
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            cwd=link.parent,
        )
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("above_root", [False, True])
@pytest.mark.parametrize("dangling", [False, True])
def test_member_refuses_redirects_even_above_root_and_before_output_exists(
    tmp_path: Path, above_root: bool, dangling: bool
) -> None:
    target = tmp_path / "outside"
    target.mkdir()
    link = tmp_path / "redirect"
    _redirect(link, target)
    if dangling:
        target.rmdir()
    root, relative = (link / "nested", "new/file") if above_root else (tmp_path, "redirect/new/file")
    with pytest.raises(ValueError, match="redirects through a link"):
        member(root, relative)


def test_a_prior_admission_does_not_hide_a_replaced_parent(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    assert member(tmp_path, "parent/new/file") == parent / "new/file"
    parent.rename(tmp_path / "original")
    outside = tmp_path / "outside"
    outside.mkdir()
    _redirect(parent, outside)
    with pytest.raises(ValueError, match="redirects through a link"):
        member(tmp_path, "parent/new/file")
