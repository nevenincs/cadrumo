"""The packaged desktop health run receives a disposable root and no inherited registry authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT, authority_root_setting_names

from ..package_launch_smoke import health_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_health_run_keeps_an_exported_authority_root_away_from_the_desktop(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    received = {name: str(tmp_path / "developer-authority") for name in authority_root_setting_names()}
    received["PATH"] = str(tmp_path)
    environment = health_environment(root, received)
    assert environment[STORAGE_ROOT.variable] == str(root)
    folded = {name.upper() for name in environment}
    assert authority_root_setting_names()
    assert not folded & authority_root_setting_names()


def test_a_lower_case_spelling_of_the_authority_root_is_kept_away_too(tmp_path: Path) -> None:
    received = {name.lower(): str(tmp_path / "developer-authority") for name in authority_root_setting_names()}
    environment = health_environment(tmp_path / "storage", received)
    assert not {name.upper() for name in environment} & authority_root_setting_names()
