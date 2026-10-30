"""The docs build's per-process log directory starts from the resolved storage root."""

from __future__ import annotations

import os

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import STORAGE_ROOT, storage_root_override

from ..build import private_log_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_a_relative_root_pin_yields_the_log_directory_the_settings_layer_keeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The sample environment file pins the root with a relative spelling.
    monkeypatch.setenv(STORAGE_ROOT.variable, "var/storage")
    monkeypatch.delenv("CADRUMO_LOG_DIR", raising=False)

    directory = private_log_directory()

    root = storage_root_override("var/storage")
    assert root.is_absolute()
    assert os.environ[STORAGE_ROOT.variable] == str(root)
    assert directory == root / "logs" / f"pid-{os.getpid()}"
    # A relative log directory would be anchored beneath the root a second time.
    monkeypatch.setenv("CADRUMO_LOG_DIR", str(directory))
    assert Settings().cadrumo_log_dir == directory
