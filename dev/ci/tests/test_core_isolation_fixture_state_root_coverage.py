"""The isolation fixture relocates the one storage root; shared test-host locations keep their pins.

The canonical CLI isolation fixture replaces the storage root, the single
control over where the product stores anything, so every member resolves beneath
the test's own ``tmp_path``. The repository bootstrap separately pins the
process temporary directories and the shared browser assets before application
imports, and neither is a product storage member. This gate verifies both
lifetimes so a new member cannot escape the fixture unnoticed.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend
from cadrumo.core.config import load_settings
from cadrumo.core.storage_environment import STORAGE_ROOT, TEMPORARY_VARIABLES
from cadrumo.core.storage_taxonomy import StorageCategory, StorageScope
from cadrumo.core.storage_taxonomy_locations import (
    STORAGE_TAXONOMY,
    storage_location,
    storage_path,
    uses_external_transport,
)

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_isolated_cli_backend_relocates_every_root_member_under_tmp_path(
    isolated_cli_backend: Path,
    tmp_path: Path,
) -> None:
    """Every root-scoped member resolves beneath the fixture's root, which sits under ``tmp_path``.

    The fixture pins the root in the environment as well as in the settings, so
    a child process started from the test inherits the same single control.
    """
    storage_root = isolated_cli_backend
    settings = load_settings()

    assert settings.cadrumo_storage_root == storage_root
    assert os.environ[STORAGE_ROOT.variable] == str(storage_root)
    assert storage_root.is_relative_to(tmp_path)

    members = [
        location
        for location in STORAGE_TAXONOMY.values()
        if location.scope is StorageScope.ROOT and not uses_external_transport(location)
    ]
    assert members, "the root-scoped member set must not be empty"
    for location in members:
        resolved = storage_path(location.category, settings=settings)
        assert resolved == storage_root / location.relative_path(), (
            f"{location.category.value} did not relocate with the fixture's root; "
            f"got {resolved!r}, expected it at {storage_root / location.relative_path()!r}"
        )
        assert resolved.is_relative_to(tmp_path), location.category


def test_shared_test_host_pins_are_not_product_storage(isolated_cli_backend: Path, tmp_path: Path) -> None:
    """Process temporary files and browser assets keep the bootstrap's pins, outside the isolated root.

    The temporary variables agree with the interpreter's temporary directory and
    contain pytest's own per-test scratch. The browser assets are the operator's
    shared install: the process-wide pin names the browser member's relative
    location under a root other than the fixture's, so isolated profiles reuse
    one download while the product member itself relocates with the root.
    """
    storage_root = isolated_cli_backend

    temporary = {name: Path(os.environ[name]) for name in TEMPORARY_VARIABLES}
    assert all(pinned.is_absolute() for pinned in temporary.values()), temporary
    assert len(set(temporary.values())) == 1, "TEMP, TMP and TMPDIR must name one directory"
    run_temporary_root = Path(tempfile.gettempdir())
    assert run_temporary_root == temporary["TEMP"]
    assert tmp_path.is_relative_to(run_temporary_root)

    browsers = storage_location(StorageCategory.PLAYWRIGHT_BROWSERS)
    shared_browsers = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    assert shared_browsers.is_absolute()
    assert shared_browsers.parts[-len(browsers.relative_path().parts) :] == browsers.relative_path().parts
    assert not shared_browsers.is_relative_to(storage_root), "the shared browser install must outlive the fixture"
    assert storage_path(StorageCategory.PLAYWRIGHT_BROWSERS) == storage_root / browsers.relative_path()


def test_isolated_cli_backend_yields_a_directory_under_tmp_path(isolated_cli_backend: Path, tmp_path: Path) -> None:
    """The fixture's yielded root lives under the test's own ``tmp_path``,
    confirming isolation from any shared or ambient storage root."""

    assert tmp_path in isolated_cli_backend.parents or isolated_cli_backend == tmp_path
