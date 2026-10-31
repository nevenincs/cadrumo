"""Real-wheel contract tests for the mandatory four-wheel cohort."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..lane_verification_core import (
    create_pip_venv,
    isolated_product_env,
    run_checked,
    venv_bin_dir,
    venv_cadrumo_path,
    venv_python_path,
)
from ..shared_cohort import shared_cohort
from ..smoke_split_install import _COHORT_PROBE, _install_cohort_with_pip

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


@pytest.fixture(scope="module")
def real_cohort_wheels() -> tuple[Path, tuple[Path, ...]]:
    """Return the real four-wheel cohort from the shared content-keyed build.

    The wheels are consumed READ-ONLY: each test opens them with ``zipfile``
    and hands their resolved paths to pip, so the snapshot-built cohort every
    other packaging proof reads serves here too.

    Returns:
        The root wheel and the companion data wheels.
    """
    cohort = shared_cohort()
    return cohort.wheel, cohort.companions


@pytest.fixture(scope="module")
def pip_installed_cohort(
    tmp_path_factory: pytest.TempPathFactory,
    real_cohort_wheels: tuple[Path, tuple[Path, ...]],
) -> Path:
    """Install the cohort under real ``pip`` into one venv for this module.

    Both tests installed the identical cohort into an identical fresh venv.
    Neither mutates the environment: one inspects its scripts directory and
    the other runs a probe whose product state lives in its own ``tmp_path``.

    Returns:
        The virtualenv holding the installed cohort.
    """
    wheel, companions = real_cohort_wheels
    work = tmp_path_factory.mktemp("pip-installed-cohort")
    venv = create_pip_venv(work, f"{sys.version_info.major}.{sys.version_info.minor}")
    _install_cohort_with_pip(work, wheel, companions, venv)
    return venv


def test_four_wheel_cohort_installs_only_aeat_human_script(
    real_cohort_wheels: tuple[Path, tuple[Path, ...]],
    pip_installed_cohort: Path,
) -> None:
    """The real root wheel installs ``aeat`` without a ``cadrumo`` alias."""
    _, companions = real_cohort_wheels
    assert len(companions) == 3
    venv = pip_installed_cohort

    human_alias = venv_bin_dir(venv) / ("cadrumo.exe" if os.name == "nt" else "cadrumo")
    assert venv_cadrumo_path(venv).is_file()
    assert venv_cadrumo_path(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
    assert not human_alias.exists()


def test_real_wheels_form_one_complete_authority_cohort(
    tmp_path: Path,
    real_cohort_wheels: tuple[Path, tuple[Path, ...]],
    pip_installed_cohort: Path,
) -> None:
    """The compact root artifact and all three data wheels install as one product."""
    wheel, companions = real_cohort_wheels
    assert len(companions) == 3

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

    venv = pip_installed_cohort
    run_checked(
        [str(venv_python_path(venv)), "-c", _COHORT_PROBE],
        cwd=tmp_path,
        env=isolated_product_env(tmp_path / "test-cohort-state"),
    )

    assert 'requires("cadrumo")' in _COHORT_PROBE
    assert "bundled_indexed_authority" in _COHORT_PROBE
    assert venv_cadrumo_path(venv).name == ("aeat.exe" if os.name == "nt" else "aeat")
