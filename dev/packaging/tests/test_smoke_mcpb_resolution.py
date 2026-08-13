r"""Tests for the MCPB smoke's npx shim-to-interpreter resolution.

A Windows ``npx.cmd`` can come from two different layouts: a native Node
install / setup-node tool cache (``node.exe`` and npm's ``npx-cli.js`` beside
the shim) or an npm-global-prefix directory (shims only — the interpreter
lives with the Node installation). The claude lane's pin fix points
``CADRUMO_CLAUDE_EXECUTABLE`` at the npm prefix, which surfaced the
beside-only assumption as "could not resolve node+npx-cli beside ...npm\\npx.cmd".
These tests build both layouts as real files and drive the real resolver;
PATH is really re-pointed (and restored) rather than mocked.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ..smoke_mcpb import _npx_argv

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _write_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub interpreter\n", encoding="utf-8")
    if not sys.platform.startswith("win"):
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _node_name() -> str:
    return "node.exe" if sys.platform.startswith("win") else "node"


@contextmanager
def _real_path(*directories: Path) -> Iterator[None]:
    """Point the process PATH at exactly these directories, then restore it."""
    original = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join(str(directory) for directory in directories)
    try:
        yield
    finally:
        os.environ["PATH"] = original


def _native_install(root: Path) -> tuple[Path, Path, Path]:
    """Materialise a native-layout Node install: shim, node, and npx-cli.js together."""
    npx = _write_executable(root / "npx.cmd")
    node = _write_executable(root / _node_name())
    cli = root / "node_modules" / "npm" / "bin" / "npx-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// npx cli\n", encoding="utf-8")
    return npx, node, cli


def test_posix_npx_is_directly_executable(tmp_path: Path) -> None:
    """A non-shim npx (POSIX layout) is returned as-is."""
    npx = _write_executable(tmp_path / "npx")
    assert _npx_argv(npx) == [str(npx)]


def test_native_layout_resolves_beside_the_shim(tmp_path: Path) -> None:
    """The native install keeps node and npx-cli.js beside the shim.

    On Windows the beside probe answers before PATH is even consulted; the
    POSIX run of this test resolves through PATH to the same installation.
    """
    npx, node, cli = _native_install(tmp_path / "nodejs")
    with _real_path(node.parent):
        assert _npx_argv(npx) == [str(node), str(cli)]


def test_npm_prefix_shim_falls_back_to_the_path_resolved_node(tmp_path: Path) -> None:
    """An npm-prefix shim (no node beside it) resolves via the real installation."""
    prefix = tmp_path / "Roaming" / "npm"
    shim = _write_executable(prefix / "npx.cmd")
    _install_npx, node, cli = _native_install(tmp_path / "nodejs")
    with _real_path(node.parent):
        # Path comparison: shutil.which may report a PATHEXT-cased suffix
        # (node.EXE) that is the same file on the case-insensitive filesystem.
        assert [Path(part) for part in _npx_argv(shim)] == [node, cli]


def test_unresolvable_shim_refuses_naming_every_probed_path(tmp_path: Path) -> None:
    """No interpreter anywhere: the refusal enumerates what was probed."""
    prefix = tmp_path / "Roaming" / "npm"
    shim = _write_executable(prefix / "npx.cmd")
    empty = tmp_path / "empty"
    empty.mkdir()
    with _real_path(empty), pytest.raises(SystemExit) as excinfo:
        _npx_argv(shim)
    message = str(excinfo.value)
    assert "probed:" in message
    assert str(prefix / "node.exe") in message
    assert str(shim) in message
