"""Native iteration retains unchanged dependencies and machine tool bindings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import tool_storage_environment
from dev._paths import REPO_ROOT

from ...command_execution import run_command
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
