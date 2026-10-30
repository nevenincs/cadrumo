"""The shipped manifest and package records name no location of the machine that built them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..assembly_staging import _prune_local_install_records
from ..portable_provenance import checkout_relative, shipped_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_paths_inside_the_checkout_become_checkout_relative_in_either_spelling(tmp_path: Path) -> None:
    checkout = tmp_path / "Source Tree"
    inside = checkout / "native" / "cmake" / "Toolchain.cmake"
    provenance = {
        "toolchain": {
            "path": str(inside),
            "resolved": inside.as_posix(),
            "other": [str(inside), "https://example.invalid"],
        },
        "tool": str(tmp_path / "elsewhere" / "tool.exe"),
        "count": 3,
    }

    shipped = checkout_relative(provenance, checkout)

    assert shipped["toolchain"] == {
        "path": "native/cmake/Toolchain.cmake",
        "resolved": "native/cmake/Toolchain.cmake",
        "other": ["native/cmake/Toolchain.cmake", "https://example.invalid"],
    }
    # A location outside the checkout is not a checkout fact; it is left as the builder recorded it.
    assert shipped["tool"] == str(tmp_path / "elsewhere" / "tool.exe")
    assert shipped["count"] == 3


def test_windows_paths_compare_without_case() -> None:
    shipped = checkout_relative({"path": r"Y:\Code\Tui\native\file.toml"}, Path("y:/code/tui"))

    assert shipped == {"path": "native/file.toml"}


def test_the_agent_projects_location_is_not_recorded(tmp_path: Path) -> None:
    provenance = {"agent": {"source": str(tmp_path / "agent"), "version": "1.0"}, "runtime": {"target": "linux"}}

    shipped = shipped_provenance(provenance, tmp_path / "checkout")

    assert shipped == {"agent": {"version": "1.0"}, "runtime": {"target": "linux"}}


def test_installer_records_of_build_host_wheels_are_dropped_and_listed(tmp_path: Path) -> None:
    root = tmp_path / "app"
    packages = root / "site-packages"
    local = packages / "cadrumo-1.0.dist-info"
    remote = packages / "attrs-1.0.dist-info"
    for directory, url in (
        (local, "file:///build/product/wheels/cadrumo-1.0-py3-none-any.whl"),
        (remote, "https://files.invalid/attrs.whl"),
    ):
        directory.mkdir(parents=True)
        (directory / "direct_url.json").write_text(json.dumps({"url": url}), encoding="utf-8")

    pruned = _prune_local_install_records(packages, root)

    assert [entry["file"] for entry in pruned] == ["site-packages/cadrumo-1.0.dist-info/direct_url.json"]
    assert not (local / "direct_url.json").exists()
    assert (remote / "direct_url.json").is_file()
