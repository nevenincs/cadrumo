"""Independent fixed-point proof that the retired TUI cannot re-enter the tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    RETIRED_TUI_PACKAGE,
    RETIRED_TUI_ROOT,
    TuiRetirementRemnantKind,
    TuiRetirementScanError,
    find_retired_tui_remnants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _synthetic_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    src_root = tmp_path / "src"
    package_root = src_root / "cadrumo"
    retired_root = package_root / "adapters/inbound/tui"
    package_root.mkdir(parents=True)
    return src_root, package_root, retired_root


def _remnants(tmp_path: Path, src_root: Path, package_root: Path, retired_root: Path):
    return find_retired_tui_remnants(
        repo_root=tmp_path,
        src_root=src_root,
        package_root=package_root,
        retired_root=retired_root,
        development_root=tmp_path / "dev",
    )


def test_live_tree_is_the_zero_remnant_fixed_point() -> None:
    """The retired path is physically absent, with no source import or string reach."""
    assert not RETIRED_TUI_ROOT.exists()
    assert find_retired_tui_remnants() == ()


def test_recreated_retired_module_is_reported_from_direct_filesystem_facts(tmp_path: Path) -> None:
    """A module cannot re-enter merely because it has no consumer yet."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    module = retired_root / "_screen.py"
    module.parent.mkdir(parents=True)
    module.write_text("class Screen: pass\n", encoding="utf-8")

    remnants = _remnants(tmp_path, src_root, package_root, retired_root)

    assert [(item.kind, item.importer_path, item.target) for item in remnants] == [
        (
            TuiRetirementRemnantKind.MODULE,
            "src/cadrumo/adapters/inbound/tui/_screen.py",
            f"{RETIRED_TUI_PACKAGE}._screen",
        )
    ]


def test_recreated_retired_import_is_reported_without_a_historical_baseline(tmp_path: Path) -> None:
    """Any direct import is a current violation; there is no accepted import inventory."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    consumer = package_root / "consumer.py"
    consumer.write_text(f"from {RETIRED_TUI_PACKAGE}._screen import Screen\n", encoding="utf-8")

    remnants = _remnants(tmp_path, src_root, package_root, retired_root)

    assert [(item.kind, item.importer_mod, item.target) for item in remnants] == [
        (TuiRetirementRemnantKind.IMPORT, "cadrumo.consumer", f"{RETIRED_TUI_PACKAGE}._screen")
    ]


def test_recreated_qualified_reference_is_reported_without_an_import(tmp_path: Path) -> None:
    """Strings used for dynamic routes or registration cannot hide a retired reach."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    consumer = package_root / "consumer.py"
    consumer.write_text(f"route = '{RETIRED_TUI_PACKAGE}._screen.Screen'\n", encoding="utf-8")

    remnants = _remnants(tmp_path, src_root, package_root, retired_root)

    assert [(item.kind, item.importer_mod, item.target) for item in remnants] == [
        (TuiRetirementRemnantKind.REFERENCE, "cadrumo.consumer", f"{RETIRED_TUI_PACKAGE}._screen.Screen")
    ]


def test_unreadable_fixed_point_input_refuses_instead_of_disappearing(tmp_path: Path) -> None:
    """A syntax failure in the scan population cannot mute a possible remnant."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    (package_root / "broken.py").write_text("from = broken\n", encoding="utf-8")

    with pytest.raises(TuiRetirementScanError, match=r"cannot parse TUI retirement fixed-point input.*broken"):
        _remnants(tmp_path, src_root, package_root, retired_root)
