"""Real behavior and ownership proofs for the canonical TUI devtools."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ..fixture import workspace
from ..frame import Frame
from ..journal import Session, read_session, write_session
from ..replay import replay, screenshot
from ..surfaces import Surface

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_DEVTOOLS_ROOT = Path(__file__).parents[1]
_PRIVATE_MODULES = {"_fixture", "_frame", "_journal", "_replay", "_surfaces"}
_PUBLIC_MODULES = {"fixture", "frame", "journal", "replay", "surfaces"}


def _definition_sites(root: Path, symbol: str) -> tuple[Path, ...]:
    sites: list[Path] = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
            for node in ast.walk(tree)
        ):
            sites.append(path)
    return tuple(sites)


def test_public_devtool_homes_are_single_defining_modules_with_inert_initializer() -> None:
    """Public devtool modules own their symbols without private or facade imports."""
    for old_name in _PRIVATE_MODULES:
        assert not (_DEVTOOLS_ROOT / f"{old_name}.py").exists()
    for public_name in _PUBLIC_MODULES:
        assert (_DEVTOOLS_ROOT / f"{public_name}.py").is_file()

    for path in _DEVTOOLS_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            assert node.module not in _PRIVATE_MODULES
            if node.level == 1:
                assert node.module is not None, f"{path} imports through the devtools package facade"
            assert not (node.module or "").startswith("cadrumo.entrypoints.tui.devtools._")

    representatives = (
        ("fixture", "workspace", workspace),
        ("frame", "Frame", Frame),
        ("journal", "Session", Session),
        ("replay", "replay", replay),
        ("surfaces", "Surface", Surface),
    )
    for module_name, symbol_name, symbol in representatives:
        module = importlib.import_module(f"cadrumo.entrypoints.tui.devtools.{module_name}")
        assert symbol.__module__ == module.__name__
        assert _definition_sites(_DEVTOOLS_ROOT, symbol_name) == (_DEVTOOLS_ROOT / f"{module_name}.py",)

    initializer = importlib.import_module("cadrumo.entrypoints.tui.devtools")
    assert initializer.__all__ == ()
    initializer_tree = ast.parse(
        (_DEVTOOLS_ROOT / "__init__.py").read_text(encoding="utf-8"),
        filename=str(_DEVTOOLS_ROOT / "__init__.py"),
    )
    assert not [
        node
        for node in ast.walk(initializer_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]


def test_public_journal_and_replay_modules_render_the_live_registration_surface(tmp_path: Path) -> None:
    """Persist, replay, and export one real compositor frame through public homes."""
    session = Session(surface="registration", width=100, height=30, theme="dark", locale="en")
    journal_path = tmp_path / "session.jsonl"
    write_session(journal_path, session)

    restored = read_session(journal_path)
    assert restored == session

    frame = replay(restored)
    assert frame.surface == session.surface
    assert frame.width == session.width
    assert frame.height == session.height
    assert frame.text
    assert frame.chain

    screenshot_path = tmp_path / "frame.svg"
    assert screenshot(restored, str(screenshot_path)) == str(screenshot_path)
    assert "<svg" in screenshot_path.read_text(encoding="utf-8")
