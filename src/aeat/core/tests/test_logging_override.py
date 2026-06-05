"""Verify default_log_file_path observes ``override_settings``.

Pinning the override flow at the call site documents that the logging
helper picks up the override exactly the way it used to pick up
``AEAT_LOG_DIR`` env writes. No env-var manipulation here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..config import override_settings
from ..logging import default_log_file_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_default_log_file_path_observes_override(tmp_path: Path) -> None:
    target = tmp_path / "logs"
    with override_settings(aeat_log_dir=target):
        resolved = default_log_file_path()
    assert resolved.parent == target


def test_default_log_file_path_falls_back_to_default_without_override() -> None:
    """When no override is active the helper returns the storage-root-
    derived default path (``<aeat_local_storage_root>/logs/aeat.log``),
    so the diagnostic log stays isolated per workspace."""

    resolved = default_log_file_path()
    assert resolved.name == "aeat.log"
    assert resolved.parent.name == "logs"
