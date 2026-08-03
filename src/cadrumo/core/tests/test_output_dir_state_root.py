"""State-root derivation for every generated-output directory.

Durable state must not default under ``REPO_ROOT`` on an installed run:
every output directory derives its default from
``cadrumo_local_storage_root`` through the ``_STATE_ROOT_DERIVED_DIRS``
taxonomy, and an explicit per-field override still wins. These tests pin the
derivation for the whole table so a new output dir cannot silently reintroduce
a ``REPO_ROOT/var/...`` default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests import REPO_ROOT
from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config import _STATE_ROOT_DERIVED_DIRS, Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def test_every_derived_output_dir_roots_under_storage_root(tmp_path: Path) -> None:
    """Each entry in the derivation table resolves to ``<root>/<subpath>``."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    root = settings.cadrumo_local_storage_root
    assert root == storage_root
    for field_name, subpath in _STATE_ROOT_DERIVED_DIRS.items():
        expected = root.joinpath(*subpath.split("/"))
        assert getattr(settings, field_name) == expected, field_name


def test_no_derived_output_dir_defaults_under_project_root_var(tmp_path: Path) -> None:
    """With the root pointed away from the checkout, no derived dir escapes to
    ``REPO_ROOT/var`` — proving the effective default is root-derived, not
    the ``REPO_ROOT/var/...`` placeholder each field still carries."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    project_var = REPO_ROOT / "var"
    for field_name in _STATE_ROOT_DERIVED_DIRS:
        value = getattr(settings, field_name)
        assert value is not None, field_name
        assert storage_root in value.parents or value == storage_root, field_name
        assert project_var not in value.parents, field_name


def test_explicit_output_dir_override_wins_over_derivation(tmp_path: Path) -> None:
    """An explicit per-field env override defeats the state-root derivation."""
    storage_root = tmp_path / "state"
    explicit_runs = tmp_path / "operator-runs"

    settings = _settings_from_env(
        CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root),
        CADRUMO_RUNS_DIR=str(explicit_runs),
    )

    assert settings.cadrumo_runs_dir == explicit_runs
    # A sibling derived dir still follows the root.
    assert settings.cadrumo_drafts_dir == storage_root / "drafts"


def test_cache_dirs_share_the_cache_namespace(tmp_path: Path) -> None:
    """The regenerable caches derive under the ``cache/`` on-disk namespace."""
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    assert settings.cadrumo_llm_cache_dir == storage_root / "cache" / "llm-cache"
    assert settings.cadrumo_status_cache_dir == storage_root / "cache" / "status-cache"
