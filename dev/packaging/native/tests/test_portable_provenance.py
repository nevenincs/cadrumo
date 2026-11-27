"""The shipped manifest and package records name no location of the machine that built them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..assembly_staging import prune_local_install_records
from ..portable_provenance import checkout_relative, host_independent, shipped_provenance

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


def test_a_tool_in_the_builders_home_is_recorded_without_the_account(tmp_path: Path) -> None:
    checkout = tmp_path / "home" / "builder" / "code" / "checkout"
    home = tmp_path / "home" / "builder"
    tool = home / ".rustup" / "toolchains" / "stable" / "bin" / "cargo.exe"
    system = tmp_path / "Program Files" / "nodejs" / "node.exe"
    provenance = {
        "build_toolchain": {
            "CADRUMO_UV": tool.as_posix(),
            "builder_files": {"rust/cargo": {"path": str(tool), "resolved": tool.as_posix(), "sha256": "0" * 64}},
            "node": str(system),
            "toolchain_file": str(checkout / "native" / "cmake" / "Toolchain.cmake"),
        }
    }

    shipped = shipped_provenance(provenance, checkout, home)

    relative = "~/.rustup/toolchains/stable/bin/cargo.exe"
    assert shipped["build_toolchain"] == {
        "CADRUMO_UV": relative,
        "builder_files": {"rust/cargo": {"path": relative, "resolved": relative, "sha256": "0" * 64}},
        # A system location names no account; it stays as the builder recorded it.
        "node": str(system),
        # The checkout wins over the home it lies in.
        "toolchain_file": "native/cmake/Toolchain.cmake",
    }


def test_a_windows_home_compares_without_case_or_separator() -> None:
    shipped = host_independent(
        {"path": "C:/Users/Builder/scoop/shims/uv.exe"}, Path("x:/code/tui"), Path(r"c:\users\builder")
    )

    assert shipped == {"path": "~/scoop/shims/uv.exe"}


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

    pruned = prune_local_install_records(packages, root)

    assert [entry["file"] for entry in pruned] == ["site-packages/cadrumo-1.0.dist-info/direct_url.json"]
    assert not (local / "direct_url.json").exists()
    assert (remote / "direct_url.json").is_file()
