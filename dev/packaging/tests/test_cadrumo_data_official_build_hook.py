"""Compatibility contract for the official companion's Hatchling build hook."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Generic, TypeVar

import pytest

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files

from .._distribution_limits import PYPI_FILE_CAP_BYTES
from ..hashing import sha256_path
from ..lane_verification_core import run_checked

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _hook_module(companion: str) -> ModuleType:
    path = REPO_ROOT / "packaging" / companion / "hatch_build.py"
    spec = importlib.util.spec_from_file_location(f"{companion}_hatch_build_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("companion", ("cadrumo_data_official", "cadrumo_data_normatives"))
def test_hook_module_loads_with_one_parameter_nongeneric_hatchling_contract(
    monkeypatch: pytest.MonkeyPatch,
    companion: str,
) -> None:
    """The admitted newer isolated backend exposes a reduced generic contract."""
    import hatchling.builders.config as builder_config_module
    import hatchling.builders.hooks.plugin.interface as hook_interface_module

    class CurrentBuilderConfig:
        """Model Hatchling's concrete current configuration type."""

    CurrentBuilderConfigType = TypeVar("CurrentBuilderConfigType")

    class CurrentBuildHookInterface(Generic[CurrentBuilderConfigType]):
        """Model Hatchling's one-parameter current build-hook interface."""

    monkeypatch.setattr(builder_config_module, "BuilderConfig", CurrentBuilderConfig)
    monkeypatch.setattr(hook_interface_module, "BuildHookInterface", CurrentBuildHookInterface)

    hook = _hook_module(companion)

    assert hook.CustomBuildHook.__orig_bases__ == (CurrentBuildHookInterface[CurrentBuilderConfig],)


def test_normatives_sdist_rebuild_preserves_source_binary_payload(tmp_path: Path) -> None:
    """An isolated sdist build must preserve all normative bytes without a checkout."""
    uv = shutil.which("uv")
    assert uv is not None
    direct = tmp_path / "direct"
    run_checked(
        [uv, "build", "--wheel", "--sdist", "--out-dir", str(direct)],
        cwd=REPO_ROOT / "packaging" / "cadrumo_data_normatives",
    )
    original = next(direct.glob("cadrumo_data_normatives-*.whl"))
    sdist = next(direct.glob("cadrumo_data_normatives-*.tar.gz"))
    rebuilt = tmp_path / "rebuilt"
    run_checked([uv, "build", "--wheel", "--out-dir", str(rebuilt), str(sdist)], cwd=tmp_path)
    wheel = next(rebuilt.glob("cadrumo_data_normatives-*.whl"))
    assert max(original.stat().st_size, sdist.stat().st_size, wheel.stat().st_size) < PYPI_FILE_CAP_BYTES
    source_prefix = "src/cadrumo/_data/corpus/"
    expected = {
        f"cadrumo_data/_data/corpus/{path.removeprefix(source_prefix)}": sha256_path(REPO_ROOT / path)
        for path in repository_files(REPO_ROOT, under=(f"{source_prefix}normatives",))
        if Path(path).suffix.lower() in {".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"} and "/tests/" not in path
    }
    assert expected
    with zipfile.ZipFile(original) as first, zipfile.ZipFile(wheel) as second:
        assert set(first.namelist()) == set(second.namelist())
        assert "cadrumo_data/__init__.py" not in second.namelist()
        assert {name for name in second.namelist() if name.startswith("cadrumo_data/")} == set(expected)
        for name in first.namelist():
            assert first.read(name) == second.read(name), name
        for name, digest in expected.items():
            assert hashlib.sha256(second.read(name)).hexdigest() == digest, name
