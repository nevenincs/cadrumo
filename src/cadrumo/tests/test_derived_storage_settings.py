"""A repointed storage root takes the log and temporary categories with it.

The runner pins explicit category paths for its own output. An explicit path
outranks the root, so a test that only repoints the root keeps reading and
writing the runner's directories. :func:`derived_storage_settings` is the
isolation for tests that must not; these tests measure it through the resolver
production reads, with a positive control showing the pin is real.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ..core.config import Settings, override_settings, settings_override
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_path
from .env_scope import derived_storage_settings, isolated_aeat_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PINNED_CATEGORIES = (StorageCategory.LOGS, StorageCategory.TEMPORARY_FILES)


def _runner_pins(runner_root: Path) -> dict[StorageCategory, Path]:
    return {
        StorageCategory.LOGS: runner_root / "product-logs",
        StorageCategory.TEMPORARY_FILES: runner_root / "scratch",
    }


def _pinned_environment(pins: dict[StorageCategory, Path]) -> dict[str, str]:
    return {
        "CADRUMO_LOG_DIR": str(pins[StorageCategory.LOGS]),
        "CADRUMO_TEMP_DIR": str(pins[StorageCategory.TEMPORARY_FILES]),
    }


def test_an_explicit_category_path_outranks_a_repointed_root(tmp_path: Path) -> None:
    """Positive control: without the helper the pinned paths escape the new root."""
    pins = _runner_pins(tmp_path / "runner")

    with isolated_aeat_env(**_pinned_environment(pins)):
        token = settings_override.set(Settings(cadrumo_profile_kdf_measure_calibration=False))
        try:
            with override_settings(cadrumo_local_storage_root=tmp_path / "repointed"):
                for category in _PINNED_CATEGORIES:
                    assert storage_path(category) == pins[category]
        finally:
            settings_override.reset(token)


def test_derived_storage_settings_keeps_pinned_categories_under_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pins = _runner_pins(tmp_path / "runner")
    for name, value in _pinned_environment(pins).items():
        monkeypatch.setenv(name, value)
    root = tmp_path / "repointed"

    with derived_storage_settings(tmp_path / "ambient"), override_settings(cadrumo_local_storage_root=root):
        for category in _PINNED_CATEGORIES:
            resolved = storage_path(category)
            assert resolved.is_relative_to(root), (category, resolved)
            assert not resolved.is_relative_to(pins[category]), (category, resolved)


def test_derived_storage_settings_hands_the_runner_pins_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = _pinned_environment(_runner_pins(tmp_path / "runner"))
    for name, value in pinned.items():
        monkeypatch.setenv(name, value)

    with derived_storage_settings(tmp_path / "ambient"):
        assert not set(pinned) & set(os.environ)

    assert {name: os.environ.get(name) for name in pinned} == pinned
