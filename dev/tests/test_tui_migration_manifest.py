"""Independent fixed-point proof that the retired TUI cannot re-enter the tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    PKG_ROOT,
    REPO_ROOT,
    RETIRED_TUI_PACKAGE,
    RETIRED_TUI_ROOT,
    TuiRetirementRemnant,
    TuiRetirementRemnantKind,
    TuiRetirementScanError,
    find_retired_tui_remnants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _synthetic_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    src_root = tmp_path / "src"
    package_root = src_root / "cadrumo"
    retired_root = package_root.joinpath(*RETIRED_TUI_PACKAGE.split(".")[1:])
    package_root.mkdir(parents=True)
    return src_root, package_root, retired_root


def _remnants(
    tmp_path: Path,
    src_root: Path,
    package_root: Path,
    retired_root: Path,
) -> tuple[TuiRetirementRemnant, ...]:
    return find_retired_tui_remnants(
        repo_root=tmp_path,
        src_root=src_root,
        package_root=package_root,
        retired_root=retired_root,
        development_root=tmp_path / "dev",
    )


def test_live_tree_is_the_zero_remnant_fixed_point() -> None:
    """The retired path is physically absent, with no source import or string reach."""
    # Both claims are satisfied by a scan that reached nothing. Unlike every
    # sibling here, this one runs on the scanner's DEFAULT roots, and if those
    # resolve to a tree that does not exist the walk returns () without
    # inspecting a single file, while the absence below holds over a directory
    # that was never there. Anchored on the roots the scan actually consults.
    assert RETIRED_TUI_ROOT.parent.is_dir(), (
        f"{RETIRED_TUI_ROOT.parent} is gone, so the retired path's absence proves nothing"
    )
    assert (REPO_ROOT / "dev").is_dir(), "the development root the scan consults is gone"
    package_modules = sum(1 for _ in PKG_ROOT.rglob("*.py"))
    # A floor, not a pinned count: live the package holds 5,857 modules.
    assert package_modules > 3000, (
        f"the scan's package root holds only {package_modules} modules, so an empty "
        "remnant result would mean it read almost nothing"
    )

    assert not RETIRED_TUI_ROOT.exists()
    assert find_retired_tui_remnants() == ()


def test_recreated_retired_module_is_reported_from_direct_filesystem_facts(tmp_path: Path) -> None:
    """A module cannot re-enter merely because it has no consumer yet."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    module = retired_root / "_screen.py"
    module.parent.mkdir(parents=True)
    module.write_text("class Screen: pass\n", encoding="utf-8")
    module_path = module.relative_to(tmp_path).as_posix()

    remnants = _remnants(tmp_path, src_root, package_root, retired_root)

    assert [(item.kind, item.importer_path, item.target) for item in remnants] == [
        (
            TuiRetirementRemnantKind.MODULE,
            module_path,
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


@pytest.mark.parametrize("separator", ("/", "\\"))
def test_recreated_retired_repository_path_is_reported_for_both_separators(tmp_path: Path, separator: str) -> None:
    """Repository paths are a reach too, regardless of the host separator."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    retired_path = retired_root.relative_to(tmp_path).as_posix()
    consumer = package_root / "consumer.py"
    source_separator = separator if separator == "/" else "\\\\"
    consumer.write_text(f"artifact = '{retired_path.replace('/', source_separator)}/_screen.py'\n", encoding="utf-8")

    remnants = _remnants(tmp_path, src_root, package_root, retired_root)

    assert [(item.kind, item.importer_mod, item.target) for item in remnants] == [
        (TuiRetirementRemnantKind.REFERENCE, "cadrumo.consumer", retired_path)
    ]


def test_detector_module_only_ignores_its_exact_package_declaration(tmp_path: Path) -> None:
    """A second retired reference in the detector itself remains visible to the fixed point."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    detector = tmp_path / "dev/quality/import_hygiene_scan.py"
    detector.parent.mkdir(parents=True)
    detector.write_text(
        f"RETIRED_TUI_PACKAGE: str = '{RETIRED_TUI_PACKAGE}'\nroute = '{RETIRED_TUI_PACKAGE}._screen'\n",
        encoding="utf-8",
    )

    remnants = find_retired_tui_remnants(
        repo_root=tmp_path,
        src_root=src_root,
        package_root=package_root,
        retired_root=retired_root,
        development_root=tmp_path / "dev",
        detector_path=detector,
    )

    assert [(item.kind, item.importer_path, item.target) for item in remnants] == [
        (TuiRetirementRemnantKind.REFERENCE, "dev/quality/import_hygiene_scan.py", f"{RETIRED_TUI_PACKAGE}._screen")
    ]


def test_unreadable_fixed_point_input_refuses_instead_of_disappearing(tmp_path: Path) -> None:
    """A syntax failure in the scan population cannot mute a possible remnant."""
    src_root, package_root, retired_root = _synthetic_tree(tmp_path)
    (package_root / "broken.py").write_text("from = broken\n", encoding="utf-8")

    with pytest.raises(TuiRetirementScanError, match=r"cannot parse TUI retirement fixed-point input.*broken"):
        _remnants(tmp_path, src_root, package_root, retired_root)
