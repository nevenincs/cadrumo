"""Native iteration retains unchanged dependencies and machine tool bindings."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import tool_storage_environment
from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..assemble import installed_distributions
from ..cmake_build import _sync_base_dependencies

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_tool_storage_does_not_override_uv_configuration() -> None:
    assert not any(name.startswith("UV_") for name in tool_storage_environment())


def test_dev_paths_import_preserves_machine_caches_and_temporary_paths(tmp_path: Path) -> None:
    environment = dict(os.environ)
    names = ("UV_CACHE_DIR", "UV_TOOL_DIR", "UV_PYTHON_INSTALL_DIR", "TEMP", "TMP", "TMPDIR")
    environment.update({name: str(tmp_path / name) for name in names})
    program = (
        "import os,sys; "
        f"sys.path.insert(0,{str(REPO_ROOT)!r}); "
        f"names={names!r}; before={{name:os.environ[name] for name in names}}; "
        "import dev._paths; assert before == {name:os.environ[name] for name in names}"
    )
    result = run_command([sys.executable, "-I", "-B", "-c", program], environment=environment, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_base_closure_refresh_preserves_unchanged_and_other_owners(tmp_path: Path) -> None:
    source = tmp_path / "base"
    source.mkdir()
    (source / "kept.py").write_text("original", encoding="utf-8")
    (source / "obsolete.py").write_text("old", encoding="utf-8")
    product = tmp_path / "product"
    product.mkdir()
    _sync_base_dependencies(source, product)
    installed = product / "dependencies/kept.py"
    stamp = installed.stat().st_mtime_ns
    (product / "dependencies/app.py").write_text("separately owned", encoding="utf-8")
    (source / "obsolete.py").unlink()
    (source / "new.py").write_text("new", encoding="utf-8")
    _sync_base_dependencies(source, product)
    assert installed.stat().st_mtime_ns == stamp
    assert not (product / "dependencies/obsolete.py").exists()
    assert (product / "dependencies/new.py").read_text(encoding="utf-8") == "new"
    assert (product / "dependencies/app.py").read_text(encoding="utf-8") == "separately owned"
    installed.write_text("tampered", encoding="utf-8")
    _sync_base_dependencies(source, product)
    assert installed.read_text(encoding="utf-8") == "original"


def _licensed_wheel(directory: Path, version: str) -> Path:
    """Write a small wheel whose dist-info carries a ``licenses`` folder, as modern wheels do."""
    directory.mkdir(parents=True, exist_ok=True)
    info = f"sample-{version}.dist-info"
    wheel = directory / f"sample-{version}-py3-none-any.whl"
    members = {
        "sample/__init__.py": f"VERSION = {version!r}\n",
        f"{info}/METADATA": f"Metadata-Version: 2.4\nName: sample\nVersion: {version}\nLicense-File: LICENSE\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/licenses/LICENSE": "fixture license\n",
    }
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
        archive.writestr(f"{info}/RECORD", "".join(f"{name},,\n" for name in members) + f"{info}/RECORD,,\n")
    return wheel


def _install(wheel: Path, target: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--target",
            str(target),
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr


def test_replacing_a_distribution_leaves_no_stale_metadata_directory(tmp_path: Path) -> None:
    """A newer version replaces the older one completely, so assembly's metadata walk names only the new set."""
    product = tmp_path / "product"
    product.mkdir()
    for version in ("1.0", "2.0"):
        base = tmp_path / f"base-{version}"
        _install(_licensed_wheel(tmp_path / "wheels", version), base)
        _sync_base_dependencies(base, product)
    dependencies = product / "dependencies"
    assert sorted(path.name for path in dependencies.glob("*.dist-info")) == ["sample-2.0.dist-info"]
    assert not any("1.0" in path.as_posix() for path in dependencies.rglob("*"))
    assert [(item.metadata["Name"], item.version) for item in installed_distributions(dependencies)] == [
        ("sample", "2.0")
    ]


def test_metadata_walk_names_a_distribution_directory_without_metadata(tmp_path: Path) -> None:
    """An inconsistent closure is refused with the broken directory named, not an attribute error."""
    _install(_licensed_wheel(tmp_path / "wheels", "2.0"), tmp_path / "dependencies")
    (tmp_path / "dependencies/sample-1.0.dist-info/licenses").mkdir(parents=True)
    with pytest.raises(ValueError, match=r"without METADATA: sample-1\.0\.dist-info"):
        installed_distributions(tmp_path / "dependencies")


def test_base_closure_refuses_tampered_obsolete_members(tmp_path: Path) -> None:
    source = tmp_path / "base"
    source.mkdir()
    (source / "obsolete.py").write_text("owned", encoding="utf-8")
    product = tmp_path / "product"
    product.mkdir()
    _sync_base_dependencies(source, product)
    receipt = (product / "base-dependencies.json").read_bytes()
    (source / "obsolete.py").unlink()
    (product / "dependencies/obsolete.py").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="Obsolete base dependency changed"):
        _sync_base_dependencies(source, product)
    assert (product / "base-dependencies.json").read_bytes() == receipt
