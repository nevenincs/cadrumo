"""Shared source inventory helpers for structural pytest ratchets."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from functools import cache
from pathlib import Path

SRC_CADRUMO: Path = Path(__file__).resolve().parents[1]
"""Root of the ``src/cadrumo`` package tree."""

REPO_ROOT: Path = SRC_CADRUMO.parents[1]
"""Repository root that owns ``src/cadrumo``."""

FIXTURES_DIR: Path = SRC_CADRUMO / "tests" / "fixtures"
"""Bundled fixture tree excluded from production-test ratchets."""

CAST_RATIONALE_MARKER = "CAST-RATIONALE-"
"""Marker prefix required next to production ``cast()`` escape hatches."""

BARE_UTF8_LITERAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'encoding="utf-8"'),
    re.compile(r'\.encode\("utf-8"\)'),
    re.compile(r'\.decode\("utf-8"\)'),
)
"""Text patterns that identify bare UTF-8 literals in source inventory scans."""

UTF8_HASH_ALLOWLIST_TOKENS = frozenset({"hashlib", "hmac", "sha256", "sha1", "md5", "hasher"})
"""Line tokens that exempt hash-protocol UTF-8 literals from text-I/O ratchets."""

_TEST_MODULE_GLOBS: tuple[str, ...] = ("**/test_*.py", "**/_test_*.py")
PROJECT_TEST_ROOTS: tuple[Path, ...] = (REPO_ROOT / "dev", REPO_ROOT / "docs")
"""Project-level test roots outside the ``src/cadrumo`` package tree."""


@cache
def discover_test_modules() -> tuple[Path, ...]:
    """Return production test modules under ``src/cadrumo`` excluding fixture payloads."""
    collected: set[Path] = set()
    for glob in _TEST_MODULE_GLOBS:
        for path in SRC_CADRUMO.glob(glob):
            if path.name == "__init__.py" or _is_relative_to(path, FIXTURES_DIR):
                continue
            collected.add(path)
    return tuple(sorted(collected))


@cache
def discover_test_control_modules() -> tuple[Path, ...]:
    """Return deterministic test modules plus support/conftest files."""
    modules = set(discover_test_modules())
    for path in package_python_files():
        if path.name == "__init__.py" or _is_relative_to(path, FIXTURES_DIR):
            continue
        relative_parts = path.relative_to(SRC_CADRUMO).parts
        if path.name == "conftest.py" or "tests" in relative_parts:
            modules.add(path)
    return tuple(sorted(modules))


@cache
def project_test_modules() -> tuple[Path, ...]:
    """Return project-level ``test_*.py`` modules outside ``src/cadrumo``."""
    collected: set[Path] = set()
    for root in PROJECT_TEST_ROOTS:
        if not root.exists():
            continue
        for path in root.glob("**/test_*.py"):
            if "__pycache__" not in path.parts:
                collected.add(path)
    return tuple(sorted(collected))


@cache
def project_test_control_modules() -> tuple[Path, ...]:
    """Return project-level tests plus support/conftest modules outside ``src/cadrumo``."""
    modules = set(project_test_modules())
    for root in PROJECT_TEST_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "__init__.py":
                continue
            relative_parts = path.relative_to(root).parts
            if path.name == "conftest.py" or "tests" in relative_parts:
                modules.add(path)
    return tuple(sorted(modules))


@cache
def all_test_control_modules() -> tuple[Path, ...]:
    return tuple(sorted(set(discover_test_control_modules()) | set(project_test_control_modules())))


@cache
def package_python_files(*, include_data: bool = False) -> tuple[Path, ...]:
    """Return package ``.py`` files under ``src/cadrumo``.

    By default, the bundled ``_data`` fixture/corpus tree is excluded because it
    is not consistently importable package code. Pass ``include_data=True`` only
    for ratchets that explicitly need to inspect bundled data helpers.
    """
    return tuple(
        path
        for path in sorted(SRC_CADRUMO.rglob("*.py"))
        if "__pycache__" not in path.parts and (include_data or "_data" not in path.relative_to(SRC_CADRUMO).parts)
    )


@cache
def production_python_files() -> tuple[Path, ...]:
    """Return production ``.py`` files under ``src/cadrumo``.

    Test modules/packages, ``conftest.py`` files, and the bundled ``_data`` tree
    are excluded so structural production ratchets share one definition of their
    scan surface.
    """
    return tuple(path for path in sorted(SRC_CADRUMO.rglob("*.py")) if _is_production_python_file(path))


def non_test_package_python_files(
    *,
    include_data: bool = False,
    scan_excludes: Iterable[str] = (),
    exclude_conftest: bool = False,
) -> tuple[Path, ...]:
    """Return package files outside test modules/packages with optional rel-path excludes."""
    excluded = frozenset(scan_excludes)
    files: list[Path] = []
    for path in package_python_files(include_data=include_data):
        rel = aeat_relative(path)
        if not _is_non_test_package_python_file(path, exclude_conftest=exclude_conftest):
            continue
        if rel in excluded:
            continue
        files.append(path)
    return tuple(files)


def non_test_python_files_under(root: Path, *, include_data: bool = True) -> tuple[Path, ...]:
    """Return non-test package files below *root*, preserving a direct file input."""
    if root.is_file():
        return (root,) if _is_non_test_package_python_file(root) else ()
    return tuple(
        path
        for path in package_python_files(include_data=include_data)
        if _is_relative_to(path, root) and _is_non_test_package_python_file(path)
    )


def module_name(path: Path) -> str:
    """Return the importable aeat module name for a source file path."""
    rel = path.relative_to(SRC_CADRUMO.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def repo_path(relative: str) -> Path:
    """Return the absolute path for a repository-relative path string."""
    return REPO_ROOT / relative


def repo_relative(path: Path) -> str:
    """Return *path* relative to the repository root using POSIX separators."""
    return path.relative_to(REPO_ROOT).as_posix()


def aeat_relative(path: Path) -> str:
    """Return *path* relative to ``src/cadrumo`` using POSIX separators."""
    return path.relative_to(SRC_CADRUMO).as_posix()


def ast_for_path(path: Path, cache: Mapping[Path, ast.AST] | None = None) -> ast.AST | None:
    """Return the cached AST for *path*, or parse it once from disk.

    Structural ratchets scan many of the same modules. Accepting the shared
    ``source_tree_ast`` fixture avoids repeated parse work while preserving a
    single-file fallback for callers that inspect documented inventory entries.
    Callers that do not thread the fixture through still benefit: the fallback
    reads from the shared process-level cache primed by :func:`prime_ast_cache`.
    """
    if cache is not None and path in cache:
        return cache[path]
    return _parsed_ast_for_path(path)


_AST_CACHE: dict[Path, ast.AST | None] = {}
"""Process-level AST parse cache shared by every :func:`ast_for_path` caller
that does not supply its own cache mapping. Primed once per pytest session by
:func:`prime_ast_cache` (called from the ``source_tree_ast`` fixture in
``conftest.py``) so a ratchet that calls ``ast_for_path(path)`` without
threading the session fixture through still reuses the one full-tree parse
instead of independently re-parsing the same file from disk."""


def prime_ast_cache(entries: Mapping[Path, ast.AST]) -> None:
    """Seed the shared process-level AST cache from an externally-parsed mapping.

    Called once per pytest session by the ``source_tree_ast`` fixture so every
    :func:`ast_for_path` call made without an explicit cache argument (the
    common bypass pattern across structural ratchets that only import
    ``ast_for_path`` and never thread the session fixture through their own
    helpers) reuses the shared parse instead of re-parsing the file.
    """
    _AST_CACHE.update(entries)


def _parsed_ast_for_path(path: Path) -> ast.AST | None:
    """Return a parsed AST for *path*, cached for structural ratchets."""
    if path in _AST_CACHE:
        return _AST_CACHE[path]
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        _AST_CACHE[path] = None
        return None
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        tree = None
    _AST_CACHE[path] = tree
    return tree


def production_ast_items(cache: Mapping[Path, ast.AST] | None = None) -> tuple[tuple[Path, ast.AST], ...]:
    """Return ``(path, AST)`` pairs for the shared production source surface."""
    paths = (
        sorted(path for path in cache if _is_production_python_file(path))
        if cache is not None
        else production_python_files()
    )
    items: list[tuple[Path, ast.AST]] = []
    for path in paths:
        tree = ast_for_path(path, cache)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def package_ast_items(
    cache: Mapping[Path, ast.AST] | None = None,
    *,
    include_data: bool = False,
) -> tuple[tuple[Path, ast.AST], ...]:
    """Return ``(path, AST)`` pairs for package files, reusing cache entries."""
    paths = (
        sorted(
            path
            for path in cache
            if _is_relative_to(path, SRC_CADRUMO)
            and path.suffix == ".py"
            and "__pycache__" not in path.parts
            and (include_data or "_data" not in path.relative_to(SRC_CADRUMO).parts)
        )
        if cache is not None
        else package_python_files(include_data=include_data)
    )
    items: list[tuple[Path, ast.AST]] = []
    for path in paths:
        tree = ast_for_path(path, cache)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def qualified_name(node: ast.AST) -> str:
    """Return a dotted qualified name for simple AST call/name/attribute chains."""
    if isinstance(node, ast.Call):
        return qualified_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def leaf_name(node: ast.AST) -> str:
    name = qualified_name(node)
    return name.rsplit(".", 1)[-1] if name else ""


_ALIAS_RESOLUTION_PASSES = 4
"""Fixed-point bound for folding assignment aliases into an import binding map.

Each pass resolves one further link of an ``a = date; b = a; c = b`` rebinding
chain. Four passes cover every chain length observed in the tree while keeping
the walk bounded on a pathological source.
"""


def import_binding_map(tree: ast.AST) -> dict[str, str]:
    """Return local name -> absolute origin for every import binding in *tree*.

    Structural gates that forbid a call site must key off what a name *is*,
    not how it happens to be spelled locally: ``from datetime import date as
    _date`` binds the same class as a bare ``from datetime import date``, and a
    gate matching only the bare spelling reports green on the aliased form.
    This map is the resolution substrate for :func:`resolve_dotted_origin`.

    Every alias spelling is covered — ``import x``, ``import x as y``,
    ``import x.y`` (which binds the root ``x``), ``from x import y``, and
    ``from x import y as z`` — at module level and inside functions alike,
    since a function-local import binds a name that call sites in that
    function really use. Assignment rebindings (``D = date``) are then folded
    in to a fixed point, so a handle passed through a local variable still
    resolves to its origin.

    Relative imports are skipped: their origin depends on the importing
    module's own package position, which a single-tree walk cannot know.
    Callers needing first-party resolution must supply the consumer module's
    dotted name themselves.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = alias.name
                else:
                    root = alias.name.split(".", 1)[0]
                    bindings[root] = root
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    for _ in range(_ALIAS_RESOLUTION_PASSES):
        if not _fold_assignment_aliases(tree, bindings):
            break
    return bindings


def _fold_assignment_aliases(tree: ast.AST, bindings: dict[str, str]) -> bool:
    """Record one pass of ``target = <already-resolvable expr>`` rebindings."""
    changed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        name = qualified_name(value)
        if not name:
            continue
        origin = resolve_dotted_origin(name, bindings)
        if origin == name:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and bindings.get(target.id) != origin:
                bindings[target.id] = origin
                changed = True
    return changed


def resolve_dotted_origin(name: str, bindings: Mapping[str, str]) -> str:
    """Return *name* with its head segment resolved through import *bindings*.

    ``_date.fromisoformat`` against ``{"_date": "datetime.date"}`` resolves to
    ``datetime.date.fromisoformat``, collapsing every local spelling of one
    origin onto a single comparable string. An unbound head is returned
    unchanged, so a caller can seed defaults for the names it means to govern.
    """
    if not name:
        return name
    head, _, tail = name.partition(".")
    origin = bindings.get(head)
    if origin is None:
        return name
    return f"{origin}.{tail}" if tail else origin


def has_marker_on_line_or_adjacent_comment_block(lines: Sequence[str], lineno: int, marker: str) -> bool:
    """Return True when *marker* appears on *lineno* or its leading comment block."""
    idx = lineno - 1
    if idx < 0 or idx >= len(lines):
        return False
    if marker in lines[idx]:
        return True

    scan = idx - 1
    while scan >= 0:
        candidate = lines[scan]
        if marker in candidate:
            return True
        stripped = candidate.strip()
        if stripped == "" or stripped.startswith("#"):
            scan -= 1
            continue
        break
    return False


def cast_call_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of real ``cast()``, ``typing.cast()``, and ``t.cast()`` calls."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "cast") or (
            isinstance(func, ast.Attribute)
            and func.attr == "cast"
            and isinstance(func.value, ast.Name)
            and func.value.id in {"typing", "t"}
        ):
            yield node.lineno


def cast_rationale_violations(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[str]:
    """Return production ``cast()`` sites without an adjacent CAST-RATIONALE marker."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno in cast_call_linenos(tree):
            if not has_marker_on_line_or_adjacent_comment_block(lines, lineno, CAST_RATIONALE_MARKER):
                violations.append(f"{repo_relative(path)}:{lineno}")
    return violations


def regex_line_hits(
    files: Iterable[Path],
    pattern: re.Pattern[str],
    *,
    skip_comment_lines: bool = True,
) -> list[str]:
    """Return ``path.py:line: 'match'`` strings for regex matches in files."""
    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for match in pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            if skip_comment_lines and line_no <= len(lines) and lines[line_no - 1].lstrip().startswith("#"):
                continue
            hits.append(f"{_display_path(path)}:{line_no}: {match.group(0)!r}")
    return hits


def is_hash_protocol_site(line: str, tokens: Iterable[str] = UTF8_HASH_ALLOWLIST_TOKENS) -> bool:
    """Return True when a source line contains a hash/HMAC allowlist token."""
    token_set = frozenset(tokens)
    return any(token in line for token in token_set)


def bare_utf8_literal_violations(
    path: Path,
    *,
    hash_allowlist_tokens: Iterable[str] = UTF8_HASH_ALLOWLIST_TOKENS,
) -> list[tuple[int, str]]:
    """Return ``(lineno, stripped line)`` pairs for non-hash bare UTF-8 literals."""
    violations: list[tuple[int, str]] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return violations
    for lineno, line in enumerate(source.splitlines(), start=1):
        if is_hash_protocol_site(line, hash_allowlist_tokens):
            continue
        if any(pattern.search(line) for pattern in BARE_UTF8_LITERAL_PATTERNS):
            violations.append((lineno, line.strip()))
    return violations


def _display_path(path: Path) -> str:
    try:
        return repo_relative(path)
    except ValueError:
        return path.as_posix()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_production_python_file(path: Path) -> bool:
    if not _is_relative_to(path, SRC_CADRUMO):
        return False
    relative_parts = path.relative_to(SRC_CADRUMO).parts
    return not (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or path.name == "conftest.py"
        or "tests" in relative_parts
        or "_data" in relative_parts
    )


def _is_non_test_package_python_file(path: Path, *, exclude_conftest: bool = False) -> bool:
    if not _is_relative_to(path, SRC_CADRUMO):
        return False
    relative_parts = path.relative_to(SRC_CADRUMO).parts
    return not (
        path.name.startswith("test_")
        or path.name.startswith("_test_")
        or path.name.endswith("_test.py")
        or "tests" in relative_parts
        or (exclude_conftest and path.name == "conftest.py")
    )
