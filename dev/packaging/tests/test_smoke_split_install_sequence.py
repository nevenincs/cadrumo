"""Real-wheel contract tests for the mandatory three-wheel cohort."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from .._smoke_common import (
    build_companion_wheels,
    build_wheel,
    create_pip_venv,
    isolated_product_env,
    run_checked,
    venv_bin_dir,
    venv_cadrumo_path,
    venv_python_path,
)
from ..smoke_split_install import _COHORT_PROBE, _install_cohort_with_pip

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_three_wheel_cohort_installs_only_aeat_human_script(tmp_path: Path) -> None:
    """The real root wheel installs ``aeat`` without a ``cadrumo`` alias."""
    uv = shutil.which("uv")
    assert uv is not None

    wheel = build_wheel(_REPO_ROOT, tmp_path, uv, build_root=_REPO_ROOT)
    companions = build_companion_wheels(tmp_path, uv, build_root=_REPO_ROOT)
    venv = create_pip_venv(tmp_path, f"{sys.version_info.major}.{sys.version_info.minor}")
    _install_cohort_with_pip(tmp_path, wheel, companions, venv)

    human_alias = venv_bin_dir(venv) / ("cadrumo.exe" if os.name == "nt" else "cadrumo")
    assert venv_cadrumo_path(venv).is_file()
    assert venv_cadrumo_path(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
    assert not human_alias.exists()


def test_real_wheels_form_one_complete_authority_cohort(tmp_path: Path) -> None:
    """The compact root artifact and both data wheels install as one product."""
    uv = shutil.which("uv")
    assert uv is not None

    wheel = build_wheel(_REPO_ROOT, tmp_path, uv, build_root=_REPO_ROOT)
    companions = build_companion_wheels(tmp_path, uv, build_root=_REPO_ROOT)

    with zipfile.ZipFile(wheel) as archive:
        assert not any(
            name.startswith("cadrumo/_data/corpus/")
            and name.lower().endswith((".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"))
            for name in archive.namelist()
        )
    with zipfile.ZipFile(companions[1]) as archive:
        official = set(archive.namelist())
    assert any(name.endswith(".docx") for name in official)
    assert any(name.endswith(".zip") for name in official)

    venv = create_pip_venv(tmp_path, f"{sys.version_info.major}.{sys.version_info.minor}")
    _install_cohort_with_pip(tmp_path, wheel, companions, venv)
    run_checked(
        [str(venv_python_path(venv)), "-c", _COHORT_PROBE],
        cwd=tmp_path,
        env=isolated_product_env(tmp_path / "test-cohort-state"),
    )

    assert 'requires("cadrumo")' in _COHORT_PROBE
    assert "bundled_authority" in _COHORT_PROBE
    assert venv_cadrumo_path(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
