"""Profile output directories stay private while shared test-host locations retain their pins.

The canonical CLI isolation fixture relocates profile storage dynamically from
the taxonomy. The repository bootstrap separately pins browser assets, diagnostic logs and
process temporary files before application imports. Pytest scratch stays under
the pinned temporary root. This
gate verifies both lifetimes so a new output field cannot escape unnoticed.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_cli_backend
from cadrumo.core.config import load_settings
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import ROOT_DERIVED_STORAGE_FIELDS, storage_location

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_isolated_cli_backend_covers_every_state_root_derived_dir(
    isolated_cli_backend: Path,
    tmp_path: Path,
) -> None:
    """Check profile-derived paths and the bootstrap's shared locations independently.

    Profile paths, including the independently provisioned secret-store sibling,
    must stay under this test's ``tmp_path``. Browser assets, logs and temporary
    files retain their exact host pins. The temporary root must also contain
    pytest's own per-test scratch.
    """

    storage_root = isolated_cli_backend
    settings = load_settings()

    assert settings.cadrumo_local_storage_root == storage_root

    assert ROOT_DERIVED_STORAGE_FIELDS, "the root-derived member set must not be empty"
    shared_pins: dict[str, Path] = {}
    for category, variable in (
        (StorageCategory.TEMPORARY_FILES, "CADRUMO_TEMP_DIR"),
        (StorageCategory.PLAYWRIGHT_BROWSERS, "CADRUMO_PLAYWRIGHT_BROWSERS_DIR"),
        (StorageCategory.LOGS, "CADRUMO_LOG_DIR"),
    ):
        field = storage_location(category).settings_field
        assert field is not None and field in ROOT_DERIVED_STORAGE_FIELDS
        pinned = Path(os.environ[variable])
        assert pinned.is_absolute(), variable
        shared_pins[field] = pinned
    assert Path(os.environ["CADRUMO_PLAYWRIGHT_BROWSERS_DIR"]) == Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    run_temporary_root = Path(tempfile.gettempdir())
    assert run_temporary_root == Path(os.environ["TEMP"])
    assert run_temporary_root.is_relative_to(Path(os.environ["CADRUMO_TEMP_DIR"]))
    assert tmp_path.is_relative_to(run_temporary_root)
    for field_name in ROOT_DERIVED_STORAGE_FIELDS:
        value = getattr(settings, field_name)
        assert value is not None, field_name
        if field_name in shared_pins:
            assert value == shared_pins[field_name], field_name
            continue
        assert value == tmp_path or tmp_path in value.parents, (
            f"{field_name} did not relocate under the test's isolated tmp_path; "
            f"got {value!r}, expected it under {tmp_path!r}"
        )


def test_isolated_cli_backend_yields_a_directory_under_tmp_path(isolated_cli_backend: Path, tmp_path: Path) -> None:
    """The fixture's yielded root lives under the test's own ``tmp_path``,
    confirming isolation from any shared or ambient storage root."""

    assert tmp_path in isolated_cli_backend.parents or isolated_cli_backend == tmp_path
