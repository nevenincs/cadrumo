"""Verify default_log_file_path observes ``override_settings``.

Pinning the override flow at the call site documents that the logging
helper picks up the override exactly the way it picks up
``CADRUMO_STORAGE_ROOT`` env writes. No env-var manipulation here.

``test_default_log_file_path_observes_override`` uses a fictional
``"probe-root"`` override target: the value is arbitrary, since the test's
subject is override propagation, not any real location.
``test_default_log_file_path_falls_back_to_default_without_override`` keeps
the real ``"logs"`` literal -- it asserts the genuine, unoverridden DEFAULT
derivation, not a `/`-join site (a name-equality check, not a taxonomy
census target).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from ..config import Settings, override_settings, settings_override
from ..logging import default_log_file_path
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_default_log_file_path_observes_override(tmp_path: Path) -> None:
    storage_root = tmp_path / "probe-root"
    with override_settings(cadrumo_storage_root=storage_root):
        resolved = default_log_file_path()
    assert resolved.parent == storage_root / storage_location(StorageCategory.LOGS).relative_path()


def test_default_log_file_path_falls_back_to_default_without_override() -> None:
    """When no override is active the helper returns the storage-root-
    derived default path (``<cadrumo_storage_root>/logs/cadrumo.log``),
    so the diagnostic log stays isolated per workspace."""

    with isolated_aeat_env():
        token = settings_override.set(Settings())
        try:
            resolved = default_log_file_path()
        finally:
            settings_override.reset(token)
    assert resolved.name == "cadrumo.log"
    assert resolved.parent.name == "logs"
