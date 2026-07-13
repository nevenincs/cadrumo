"""Real-wheel contract tests for the split-install smoke sequence."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from dev.packaging.smoke_core import _run, _venv_bin, _venv_python
from dev.packaging.smoke_pip_core import _create_pip_venv, _install_target_with_pip
from dev.packaging.smoke_split_install import (
    _ADVISORY_PROBE,
    _CLEAN_PROBE,
    _build_data_wheels,
    _build_slim_wheel,
    _runtime_env,
    _venv_cadrumo,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_slim_wheel_installs_only_aeat_human_script(tmp_path: Path) -> None:
    """The real root wheel installs ``aeat`` without a ``cadrumo`` alias."""
    uv = shutil.which("uv")
    assert uv is not None

    wheel = _build_slim_wheel(_REPO_ROOT, tmp_path, uv)
    venv = _create_pip_venv(tmp_path, f"{sys.version_info.major}.{sys.version_info.minor}")
    _install_target_with_pip(tmp_path, str(wheel.resolve()), venv)

    human_alias = _venv_bin(venv) / ("cadrumo.exe" if os.name == "nt" else "cadrumo")
    assert _venv_cadrumo(venv).is_file()
    assert _venv_cadrumo(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
    assert not human_alias.exists()


def test_real_wheels_match_the_deferred_authority_sequence(tmp_path: Path) -> None:
    """Slim absence is inspected before full authority runs with both companions."""
    uv = shutil.which("uv")
    assert uv is not None

    wheel = _build_slim_wheel(_REPO_ROOT, tmp_path, uv)
    companions = _build_data_wheels(_REPO_ROOT, tmp_path, uv)

    with zipfile.ZipFile(wheel) as archive:
        assert not any(
            name.startswith("cadrumo/_data/corpus/")
            and name.lower().endswith((".docx", ".pdf", ".xls", ".xlsx", ".zip"))
            for name in archive.namelist()
        )
    with zipfile.ZipFile(companions[1]) as archive:
        official = set(archive.namelist())
    assert any(name.endswith(".docx") for name in official)
    assert any(name.endswith(".zip") for name in official)

    venv = _create_pip_venv(tmp_path, f"{sys.version_info.major}.{sys.version_info.minor}")
    _install_target_with_pip(tmp_path, str(wheel.resolve()), venv)
    _run(
        [str(_venv_python(venv)), "-c", _ADVISORY_PROBE],
        cwd=tmp_path,
        env=_runtime_env(tmp_path, "test-advisory-state"),
    )
    for companion in companions:
        _install_target_with_pip(tmp_path, str(companion.resolve()), venv)
    _run(
        [str(_venv_python(venv)), "-c", _CLEAN_PROBE],
        cwd=tmp_path,
        env=_runtime_env(tmp_path, "test-clean-state"),
    )

    assert "bundled_authority" not in _ADVISORY_PROBE
    assert "load_registry_tree" in _ADVISORY_PROBE
    assert "bundled_authority" in _CLEAN_PROBE
    assert _venv_cadrumo(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
