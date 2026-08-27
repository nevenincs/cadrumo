"""Real behavior and ownership proofs for the canonical TUI devtools."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from ..fixture import workspace
from ..frame import Frame
from ..journal import Session, read_session, write_session
from ..replay import replay, screenshot
from ..surfaces import Surface

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_DEVTOOLS_ROOT = Path(__file__).parents[1]
_REPO_ROOT = Path(__file__).parents[6]
_SRC_ROOT = _REPO_ROOT / "src"
_SOURCE_ROOTS = (
    _REPO_ROOT / "src" / "cadrumo",
    _REPO_ROOT / "dev",
    _REPO_ROOT / "packaging",
)
_PRIVATE_MODULES = {"_fixture", "_frame", "_journal", "_replay", "_surfaces"}
_PUBLIC_EXPORTS = (
    (
        "fixture",
        (
            "PASSPHRASE_ENV_VAR",
            "PROFILE_LABEL",
            "STATE_DIR",
            "WORKSPACE_ENV_VAR",
            "ensure_profile",
            "ensure_session",
            "harness_storage",
            "passphrase",
            "registration_attempt",
            "workspace",
        ),
    ),
    (
        "frame",
        ("Frame", "capture", "engine_band", "focus_band", "geometry_band", "key_band", "screen_text"),
    ),
    (
        "journal",
        ("Click", "Fill", "Gesture", "Press", "Session", "Type", "describe", "read_session", "write_session"),
    ),
    ("replay", ("replay", "screenshot")),
    ("surfaces", ("SURFACES", "Surface", "resolve")),
)
_PUBLIC_MODULES = {module_name for module_name, _ in _PUBLIC_EXPORTS}
_CANONICAL_MODULES = _PUBLIC_MODULES | {"modelo_work_wizard"}
_DEVTOOLS_PACKAGE = "cadrumo.entrypoints.tui.devtools"


def _repo_path(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _source_trees() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple(
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for root in _SOURCE_ROOTS
        if root.is_dir()
        for path in sorted(root.rglob("*.py"))
    )


def _module_name(path: Path) -> str | None:
    """Return the importable module for a file under the source root."""
    try:
        relative = path.relative_to(_SRC_ROOT).with_suffix("")
    except ValueError:
        return None
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_target(path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve a relative import from any module under ``src/cadrumo``."""
    module = _module_name(path)
    if module is None:
        return None
    package = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
    base_length = len(package) - node.level + 1
    if base_length <= 0:
        return None
    base = package[:base_length]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _import_from_targets(path: Path, node: ast.ImportFrom) -> tuple[str, ...]:
    base = _relative_target(path, node) if node.level else node.module
    if not base:
        return tuple(alias.name for alias in node.names if alias.name != "*")
    return (base, *(f"{base}.{alias.name}" for alias in node.names if alias.name != "*"))


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and all(isinstance(value, ast.Constant) for value in node.values):
        return "".join(str(value.value) for value in node.values if isinstance(value, ast.Constant))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _dynamic_import_targets(tree: ast.Module) -> tuple[str, ...]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_dynamic_import = (isinstance(function, ast.Name) and function.id in {"__import__", "import_module"}) or (
            isinstance(function, ast.Attribute) and function.attr == "import_module"
        )
        if is_dynamic_import and node.args:
            target = _constant_string(node.args[0])
            if target is not None:
                targets.append(target)
    return tuple(targets)


def _edge_signature(path: Path, node: ast.AST) -> tuple[object, ...]:
    if isinstance(node, ast.Import):
        return (_repo_path(path), "import", tuple((alias.name, alias.asname) for alias in node.names))
    if isinstance(node, ast.ImportFrom):
        return (
            _repo_path(path),
            "from",
            node.level,
            node.module or "",
            tuple((alias.name, alias.asname) for alias in node.names),
        )
    raise TypeError(f"unsupported import node: {type(node)!r}")


def _expected_from(path: str, level: int, module: str, names: tuple[str, ...]) -> tuple[object, ...]:
    return (path, "from", level, module, tuple((name, None) for name in names))


_EXPECTED_CANONICAL_EDGES = tuple(
    sorted(
        (
            _expected_from("src/cadrumo/entrypoints/tui/devtools/__main__.py", 1, "fixture", ("workspace",)),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/__main__.py",
                1,
                "journal",
                ("Click", "Fill", "Press", "Session", "Type", "describe", "read_session", "write_session"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/__main__.py",
                1,
                "replay",
                ("replay", "screenshot"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/__main__.py",
                1,
                "surfaces",
                ("SURFACES", "resolve"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/modelo_work_wizard.py",
                1,
                "fixture",
                ("harness_storage", "passphrase"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/replay.py",
                1,
                "fixture",
                ("ensure_profile", "ensure_session", "harness_storage"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/replay.py",
                1,
                "frame",
                ("Frame", "capture"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/replay.py",
                1,
                "journal",
                ("Click", "Fill", "Press", "Session", "Type"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/replay.py",
                1,
                "surfaces",
                ("resolve",),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/surfaces.py",
                1,
                "fixture",
                ("registration_attempt",),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/surfaces.py",
                1,
                "modelo_work_wizard",
                ("build_modelo_work_wizard", "provision_modelo_work_wizard"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/tests/test_public_homes.py",
                2,
                "fixture",
                ("workspace",),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/tests/test_public_homes.py",
                2,
                "frame",
                ("Frame",),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/tests/test_public_homes.py",
                2,
                "journal",
                ("Session", "read_session", "write_session"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/tests/test_public_homes.py",
                2,
                "replay",
                ("replay", "screenshot"),
            ),
            _expected_from(
                "src/cadrumo/entrypoints/tui/devtools/tests/test_public_homes.py",
                2,
                "surfaces",
                ("Surface",),
            ),
        ),
        key=repr,
    )
)


def _module_kind(target: str) -> str | None:
    if target == _DEVTOOLS_PACKAGE:
        return "facade"
    prefix = f"{_DEVTOOLS_PACKAGE}."
    if not target.startswith(prefix):
        return None
    suffix = target.removeprefix(prefix)
    if suffix.startswith("_"):
        return "private"
    if suffix in _CANONICAL_MODULES:
        return "canonical"
    return "unknown"


def _definition_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def _definition_sites(trees: tuple[tuple[Path, ast.Module], ...], symbol: str) -> tuple[Path, ...]:
    return tuple(path for path, tree in trees if path.parent == _DEVTOOLS_ROOT and symbol in _definition_names(tree))


def test_public_devtool_homes_are_single_defining_modules_with_inert_initializer() -> None:
    """Public devtool modules own their symbols without private or facade imports."""
    assert not (_REPO_ROOT / "dev" / "tui").exists()
    for old_name in _PRIVATE_MODULES:
        assert not (_DEVTOOLS_ROOT / f"{old_name}.py").exists()
    for public_name, _ in _PUBLIC_EXPORTS:
        assert (_DEVTOOLS_ROOT / f"{public_name}.py").is_file()

    trees = _source_trees()
    canonical_edges: list[tuple[object, ...]] = []
    forbidden_edges: list[tuple[str, str, str]] = []
    dynamic_edges: list[tuple[str, str, str]] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    kind = _module_kind(alias.name)
                    if kind == "canonical":
                        canonical_edges.append(_edge_signature(path, node))
                    elif kind is not None:
                        forbidden_edges.append((_repo_path(path), kind, alias.name))
            elif isinstance(node, ast.ImportFrom):
                base = _relative_target(path, node) if node.level else node.module
                base_kind = _module_kind(base) if base else None
                if base_kind == "canonical":
                    canonical_edges.append(_edge_signature(path, node))
                elif base_kind is not None:
                    forbidden_edges.append((_repo_path(path), base_kind, base or ""))
                else:
                    for target in _import_from_targets(path, node):
                        kind = _module_kind(target)
                        if kind is not None:
                            forbidden_edges.append((_repo_path(path), kind, target))
        for target in _dynamic_import_targets(tree):
            kind = _module_kind(target)
            if kind is not None:
                dynamic_edges.append((_repo_path(path), kind, target))

    assert tuple(sorted(canonical_edges, key=repr)) == _EXPECTED_CANONICAL_EDGES
    assert not forbidden_edges
    assert not dynamic_edges

    representatives = (
        ("fixture", "workspace", workspace),
        ("frame", "Frame", Frame),
        ("journal", "Session", Session),
        ("replay", "replay", replay),
        ("surfaces", "Surface", Surface),
    )
    for module_name, symbol_name, symbol in representatives:
        module = importlib.import_module(f"{_DEVTOOLS_PACKAGE}.{module_name}")
        assert getattr(module, symbol_name) is symbol

    for module_name, expected_exports in _PUBLIC_EXPORTS:
        module = importlib.import_module(f"{_DEVTOOLS_PACKAGE}.{module_name}")
        assert tuple(module.__all__) == expected_exports
        module_path = _DEVTOOLS_ROOT / f"{module_name}.py"
        for symbol_name in expected_exports:
            symbol = getattr(module, symbol_name)
            if inspect.isclass(symbol) or inspect.isfunction(symbol):
                assert symbol.__module__ == module.__name__
            assert _definition_sites(trees, symbol_name) == (module_path,)

    initializer = importlib.import_module(_DEVTOOLS_PACKAGE)
    assert initializer.__all__ == ()
    initializer_tree = ast.parse(
        (_DEVTOOLS_ROOT / "__init__.py").read_text(encoding="utf-8"),
        filename=str(_DEVTOOLS_ROOT / "__init__.py"),
    )
    assert not [
        node
        for node in ast.walk(initializer_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
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
