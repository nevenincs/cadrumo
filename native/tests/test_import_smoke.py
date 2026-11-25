"""The packaged import check imports only modules outside the first-party roots, in the packaged interpreter."""

from __future__ import annotations

import configparser
import os
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

import cadrumo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def smoke() -> dict[str, Any]:
    """Load the helper the way the packaged smoke test does."""
    return runpy.run_path(str(Path(__file__).with_name("import_smoke.py")))


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory of bundled-module stand-ins that the child interpreter, and only it, can import."""
    (tmp_path / "records_importer.py").write_text(
        "import os\nfrom pathlib import Path\nPath(__file__).with_name('importer.pid').write_text(str(os.getpid()))\n",
        encoding="utf-8",
    )
    (tmp_path / "exits_on_import.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (tmp_path / "raises_on_import.py").write_text("raise ImportError('missing native dependency')\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    return tmp_path


def test_first_party_roots_are_the_shipped_roots_of_the_import_authority(smoke: dict[str, Any]) -> None:
    """A root added to the authority must reach the check, and repository-only roots must stay out of it."""
    authority = configparser.ConfigParser()
    authority.read(_REPOSITORY / ".importlinter", encoding="utf-8")
    declared = set(authority["importlinter"]["root_packages"].split())
    if smoke["FIRST_PARTY_ROOTS"] != declared - {"dev", "docs"}:
        pytest.fail(f"First-party roots differ from the import authority: {sorted(smoke['FIRST_PARTY_ROOTS'])}")


def test_prerequisites_precede_the_module_that_needs_them(smoke: dict[str, Any]) -> None:
    """Only a module's own prerequisites are loaded ahead of it."""
    ordered = smoke["with_prerequisites"](["dde", "ssl"], {"dde": ["win32ui"], "unused": ["never"]})
    if ordered != ["win32ui", "dde", "ssl"]:
        pytest.fail(f"Unexpected import order: {ordered}")


def test_a_manifest_mixing_first_party_and_other_modules_imports_the_others_in_a_child(
    smoke: dict[str, Any], bundle: Path
) -> None:
    """The non-first-party entries are imported by another process; the first-party entry must already be loaded."""
    manifest = {"modules": ["json", "records_importer"], "smoke_modules": {"cadrumo": [cadrumo.__name__]}}
    smoke["import_bundled"](
        [*manifest["modules"], *(name for names in manifest["smoke_modules"].values() for name in names)],
        "Bundled import failed",
    )
    importer = int((bundle / "importer.pid").read_text(encoding="utf-8"))
    if importer == os.getpid() or "records_importer" in sys.modules:
        pytest.fail("A manifest module was imported in the checking process")


@pytest.mark.parametrize("name", ["cadrumo_runtime.never_loaded_here", "cadrumo_agent_service.never_loaded_here"])
def test_a_first_party_module_that_nothing_loaded_is_refused_not_imported(smoke: dict[str, Any], name: str) -> None:
    """A first-party entry is checked against the loaded modules and never imported from its manifest name."""
    with pytest.raises(RuntimeError, match=f"first-party module was not loaded by the package checks: {name}"):
        smoke["import_bundled"](["json", name], "Bundled import failed")
    if name in sys.modules:
        pytest.fail("A first-party manifest name was imported")


def test_a_module_the_child_cannot_import_is_named_in_the_failure(smoke: dict[str, Any], bundle: Path) -> None:
    """The failure carries the module and its exception, and the modules after it are not reached."""
    with pytest.raises(RuntimeError, match=r"Bundled native import failed: raises_on_import: ImportError"):
        smoke["import_bundled"](["json", "raises_on_import", "records_importer"], "Bundled native import failed")
    if (bundle / "importer.pid").exists():
        pytest.fail("The probe continued past a failed import")


def test_a_module_that_does_not_exist_is_named_in_the_failure(smoke: dict[str, Any]) -> None:
    """A manifest entry the bundle cannot supply fails the check."""
    with pytest.raises(RuntimeError, match=r"Bundled import failed: absent_bundle_module: ModuleNotFoundError"):
        smoke["import_bundled"](["absent_bundle_module"], "Bundled import failed")


def test_a_module_that_exits_during_import_cannot_end_the_check_successfully(
    smoke: dict[str, Any], bundle: Path
) -> None:
    """A clean exit raised by an import does not stand in for importing the remaining modules."""
    with pytest.raises(RuntimeError, match="Bundled import failed: exits_on_import: SystemExit"):
        smoke["import_bundled"](["exits_on_import", "records_importer"], "Bundled import failed")
    if (bundle / "importer.pid").exists():
        pytest.fail("The probe continued past a module that exited")
