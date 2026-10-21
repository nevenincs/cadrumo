"""Plain members are inventoried without resolving them; links and junctions are still resolved and contained."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from ...command_execution import run_command
from ..build_toolchain import sysroot_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree(root: Path) -> dict[str, str]:
    members = {
        "include/target.h": b"public SDK ABI",
        "lib/site/module.py": b"value = 1\n",
        "lib/site/data/table.json": b"{}\n",
        "README": b"sdk\n",
    }
    for name, content in members.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return {name: hashlib.sha256(content).hexdigest() for name, content in sorted(members.items())}


def test_a_tree_of_plain_members_is_inventoried_whole(tmp_path: Path) -> None:
    expected = _tree(tmp_path / "sdk")
    inventory = sysroot_inventory(tmp_path / "sdk")
    assert inventory["files"] == expected
    assert inventory["links"] == {}
    assert sysroot_inventory(tmp_path / "sdk", excluded=frozenset({"README"}))["files"] == {
        name: value for name, value in expected.items() if name != "README"
    }


def _junction(link: Path, target: Path) -> None:
    created = run_command(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)], cwd=target.parent)
    assert created.returncode == 0, created.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Junctions are a Windows reparse point")
def test_a_junction_is_resolved_and_must_stay_inside_the_sdk(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    _tree(sdk)
    alias = sdk / "headers"
    _junction(alias, sdk / "include")
    inventory = sysroot_inventory(sdk)
    assert inventory["links"]["headers"]["target"] == "include"
    assert inventory["links"]["headers"]["kind"] == "directory"
    assert "headers/target.h" not in inventory["files"]
    os.rmdir(alias)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.h").write_bytes(b"not the SDK's")
    _junction(alias, outside)
    with pytest.raises(ValueError, match="escapes the selected SDK"):
        sysroot_inventory(sdk)
