"""Compute which test files any declared pytest lane can actually select.

A test nobody runs is worse than a missing test: it reports nothing while
looking like coverage, and its rot is invisible until somebody reads it. The
fourteen channel-generator tests sat in exactly that state long enough for two
independent breakages to accumulate, and the author of the second had no signal
at all, because no lane selected them and nothing said so.

Reachability is a two-part question and both parts must be modelled. Those tests
were excluded *twice over*: the lanes that reached ``packaging/`` did not accept
the ``serial`` marker, and the lanes that accepted it did not reach
``packaging/``. A path-only model would have declared them reachable, the gate
would have passed, and the hole would have stayed open. So a lane selects a file
only when its path scope covers the file AND its marker expression can select at
least one test in it.

Two precisions the naive version gets wrong:

*Only pytest invocations carry marker expressions.* ``-m`` is also git's message
flag, and this repository's workflows use it that way. Reading a commit subject
as a marker expression yields nonsense that happens to parse.

*A file's markers are module-level and per-test.* Collecting only
``pytestmark`` would call a file unmarked when its tests carry their own
decorators, and unmarked files match narrow expressions they should not.

See Also:
    :func:`declared_lanes`
        Every lane the repository declares, from config, recipes, and workflows.
    :func:`unreachable_test_files`
        The gate's finding: files no declared lane can select.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_UTF_8: Final[str] = "utf-8"

#: Directories that never contain runnable project tests.
_PRUNED: Final[frozenset[str]] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", "_build", ".mypy_cache", ".ruff_cache", ".pytest_cache"},
)

#: Where lane declarations live. Anything else is not a lane.
_WORKFLOW_DIR: Final[str] = ".github/workflows"


@dataclass(frozen=True, slots=True)
class Lane:
    """One declared pytest invocation: what it reaches and what it accepts."""

    source: str
    paths: tuple[str, ...]
    marker_expression: str | None

    def covers(self, relative_path: str) -> bool:
        """Return whether this lane's path scope reaches ``relative_path``."""
        if not self.paths:
            # A pathless invocation takes the configured testpaths, which the
            # caller supplies as this lane's paths. An empty scope reaches
            # nothing rather than everything: treating it as everything is how a
            # gate silently reports full coverage.
            return False
        posix = relative_path.replace("\\", "/")
        return any(posix == scope or posix.startswith(f"{scope.rstrip('/')}/") for scope in self.paths)


def _marker_expression_of(tokens: list[str]) -> str | None:
    """Return the ``-m`` value from a pytest argv, or None when absent."""
    marker_flag = "-m"  # a pytest selector, not a credential
    for index, token in enumerate(tokens):
        if token == marker_flag and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(marker_flag) and len(token) > 2:
            return token[2:]
    return None


def _paths_of(tokens: list[str]) -> tuple[str, ...]:
    """Return positional path arguments from a pytest argv."""
    paths: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in {"-m", "-k", "-n", "--timeout", "--ignore", "--durations"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        if index == 0 or token in {"pytest", "uv", "run", "python", "-m"}:
            continue
        if token.endswith(".py") or "/" in token or token.startswith("src") or token.startswith("dev"):
            paths.append(token.split("::")[0])
    return tuple(paths)


def _pytest_invocations(text: str, *, source: str, default_paths: tuple[str, ...]) -> list[Lane]:
    """Return one lane per pytest invocation in ``text``.

    Only invocations, never every ``-m`` in the file: git's message flag shares
    the spelling, and this repository uses it in the same files.
    """
    lanes: list[Lane] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "pytest" not in line or line.startswith("#"):
            continue
        # Drop shell continuations and interpolations that shlex cannot parse.
        cleaned = line.rstrip("\\").replace("${{", "").replace("}}", "")
        try:
            tokens = shlex.split(cleaned)
        except ValueError:
            continue
        if "pytest" not in tokens and not any(token.endswith("pytest") for token in tokens):
            continue
        paths = _paths_of(tokens) or default_paths
        lanes.append(Lane(source=source, paths=paths, marker_expression=_marker_expression_of(tokens)))
    return lanes


def configured_testpaths(root: Path) -> tuple[str, ...]:
    """Return the ``testpaths`` a pathless invocation inherits."""
    text = (root / "pyproject.toml").read_text(encoding=_UTF_8)
    match = re.search(r"^testpaths\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    if not match:
        return ()
    return tuple(item.strip().strip("\"'") for item in match.group(1).split(",") if item.strip())


def configured_marker_expression(root: Path) -> str | None:
    """Return the default ``-m`` expression from addopts, if any."""
    text = (root / "pyproject.toml").read_text(encoding=_UTF_8)
    match = re.search(r"^addopts\s*=\s*\"(.*?)\"", text, re.MULTILINE)
    if not match:
        return None
    inner = re.search(r"-m\s+'([^']+)'", match.group(1)) or re.search(r'-m\s+"([^"]+)"', match.group(1))
    return inner.group(1) if inner else None


def declared_lanes(root: Path) -> tuple[Lane, ...]:
    """Return every lane declared by config, recipes, and workflows."""
    testpaths = configured_testpaths(root)
    default_expression = configured_marker_expression(root)
    lanes: list[Lane] = []

    justfile = root / "justfile"
    if justfile.exists():
        lanes.extend(
            _pytest_invocations(justfile.read_text(encoding=_UTF_8), source="justfile", default_paths=testpaths)
        )

    workflow_dir = root / _WORKFLOW_DIR
    if workflow_dir.is_dir():
        for workflow in sorted(workflow_dir.glob("*.yml")):
            lanes.extend(
                _pytest_invocations(
                    workflow.read_text(encoding=_UTF_8),
                    source=f"{_WORKFLOW_DIR}/{workflow.name}",
                    default_paths=testpaths,
                ),
            )

    # A pathless invocation inherits both testpaths and the addopts expression.
    resolved: list[Lane] = []
    for lane in lanes:
        expression = lane.marker_expression if lane.marker_expression is not None else default_expression
        resolved.append(Lane(source=lane.source, paths=lane.paths, marker_expression=expression))
    return tuple(resolved)


def markers_in(path: Path) -> frozenset[str]:
    """Return every marker the file applies, module-level and per-test.

    Both are collected because a file whose tests carry their own decorators has
    no ``pytestmark``, and calling it unmarked would match it against narrow
    expressions it cannot actually satisfy.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8, errors="replace"))
    except (SyntaxError, ValueError):
        return frozenset()
    found: set[str] = set()

    def _name(node: ast.AST) -> None:
        # pytest.mark.NAME, optionally called with arguments.
        target = node.func if isinstance(node, ast.Call) else node
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "mark"
        ):
            found.add(target.attr)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            values = node.value.elts if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
            for value in values:
                _name(value)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            for decorator in node.decorator_list:
                _name(decorator)
    return frozenset(found)


def expression_selects(expression: str | None, markers: frozenset[str]) -> bool:
    """Return whether a pytest ``-m`` expression can select these markers.

    Evaluated structurally rather than by string matching: ``unit or (integration
    and not serial)`` accepts a file marked integration only when it is not also
    marked serial, and that distinction is the whole reason the generator tests
    were unreachable.
    """
    if expression is None or not expression.strip():
        return True
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        # An unparseable expression is not evidence of reachability.
        return False

    def _evaluate(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return _evaluate(node.body)
        if isinstance(node, ast.BoolOp):
            results = [_evaluate(value) for value in node.values]
            return all(results) if isinstance(node.op, ast.And) else any(results)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _evaluate(node.operand)
        if isinstance(node, ast.Name):
            return node.id in markers
        if isinstance(node, ast.Constant):
            return bool(node.value)
        # An unmodelled construct must not be read as selection.
        return False

    return _evaluate(tree)


def discover_test_files(root: Path) -> tuple[Path, ...]:
    """Return every runnable test module under ``root``."""
    found: list[Path] = []
    for path in root.rglob("test_*.py"):
        if any(part in _PRUNED for part in path.parts):
            continue
        found.append(path)
    return tuple(sorted(found))


def unreachable_test_files(root: Path, *, lanes: Iterable[Lane] | None = None) -> tuple[str, ...]:
    """Return repository-relative test files no declared lane can select."""
    resolved = tuple(lanes) if lanes is not None else declared_lanes(root)
    unreachable: list[str] = []
    for path in discover_test_files(root):
        relative = path.relative_to(root).as_posix()
        markers = markers_in(path)
        if not any(lane.covers(relative) and expression_selects(lane.marker_expression, markers) for lane in resolved):
            unreachable.append(relative)
    return tuple(unreachable)
