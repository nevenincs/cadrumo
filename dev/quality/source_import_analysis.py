"""Shared source-import analysis primitives for development scanners.

READ-ONLY. This module owns the parsing vocabulary several ``dev/`` scanners
need in common -- module-name resolution, relative-import resolution, the
``TYPE_CHECKING`` guard set, the import-site walk, the shipped/unshipped
partition read from the packaging config, and docstring/comment extraction.
It declares no boundary rules of its own.

The one-way ``src/`` -> ``dev/`` import boundary is no longer re-implemented
here. It is declared as the ``no-dev-in-shipped`` contract in ``.importlinter``
and evaluated by Import Linter against the live import graph, so the rule is a
contract rather than a second copy of the import reader.
"""

from __future__ import annotations

import ast
import fnmatch
import io
import tokenize
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8

SRC_ROOT = REPO_ROOT / "src"
_UTF_8: Final[str] = UTF_8


# ---------------------------------------------------------------------------
# Module path helpers
# ---------------------------------------------------------------------------


def module_name_for(path: Path, *, src_root: Path = SRC_ROOT) -> str:
    """Return the dotted module name for a file under ``src_root``.

    Args:
        path: The module file to name.
        src_root: Source root the name is taken relative to. Injectable so a
            caller can resolve names inside a synthetic tree; defaults to the
            repository's real ``src/``.
    """
    rel = path.relative_to(src_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def is_test_module(mod: str, path: Path) -> bool:
    """True if the module is a test module (under ``tests/`` or ``test_*``)."""
    parts = path.parts
    if "tests" in parts:
        return True
    last = mod.rsplit(".", 1)[-1]
    return last.startswith("test_") or last == "conftest"


def resolve_relative_import(
    importer_mod: str, importer_is_pkg: bool, level: int, node_module: str | None
) -> str | None:
    """Resolve a (possibly relative) ``from`` import target to an absolute name.

    Mirrors Python's import-system semantics for relative ``from`` imports.
    """
    if level == 0:
        return node_module

    importer_parts = importer_mod.split(".")
    # For a package (__init__.py), "its own package" is itself; the base for
    # relative resolution starts at the package itself for level=1.
    base_parts = importer_parts if importer_is_pkg else importer_parts[:-1]

    # level=1 means "current package" (base_parts as-is); each extra level
    # strips one more component.
    strip = level - 1
    if strip > 0:
        if strip > len(base_parts):
            return None
        base_parts = base_parts[: len(base_parts) - strip]

    if node_module:
        return ".".join(base_parts + node_module.split("."))
    return ".".join(base_parts) if base_parts else None


# Import extraction
# ---------------------------------------------------------------------------


@dataclass
class ImportSite:
    """A single ``import`` / ``from`` statement resolved to its target module."""

    importer_mod: str
    importer_path: Path
    lineno: int
    target_mod: str
    imported_names: list[str]
    is_test: bool
    in_type_checking: bool


def type_checking_guarded_nodes(tree: ast.Module) -> set[int]:
    """Return the ``id()`` of every node under an ``if TYPE_CHECKING:`` guard.

    The one canonical answer to "is this statement type-only?", shared by the
    import walk and the wrapper-binding map so the two cannot disagree about
    what the guard covers.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_guard = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if is_guard:
            guarded.update(id(child) for child in ast.walk(node))
    return guarded


def walk_module_imports(path: Path, *, src_root: Path = SRC_ROOT) -> list[ImportSite]:
    """Parse a module and return every resolved import site it contains.

    Args:
        path: The module file to parse.
        src_root: Source root the importer's dotted name is taken relative to.
    """
    try:
        src = path.read_text(encoding=_UTF_8)
        tree = ast.parse(src, filename=str(path))
    except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
        return []

    mod = module_name_for(path, src_root=src_root)
    is_pkg = path.name == "__init__.py"
    sites: list[ImportSite] = []
    test_flag = is_test_module(mod, path)

    type_checking_nodes = type_checking_guarded_nodes(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(mod, is_pkg, node.level, node.module)
            if target is None:
                continue
            names = [alias.name for alias in node.names]
            sites.append(
                ImportSite(
                    importer_mod=mod,
                    importer_path=path,
                    lineno=node.lineno,
                    target_mod=target,
                    imported_names=names,
                    is_test=test_flag,
                    in_type_checking=id(node) in type_checking_nodes,
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                sites.append(
                    ImportSite(
                        importer_mod=mod,
                        importer_path=path,
                        lineno=node.lineno,
                        target_mod=alias.name,
                        imported_names=[],
                        is_test=test_flag,
                        in_type_checking=id(node) in type_checking_nodes,
                    )
                )
    return sites


DEV_TOOLING_ROOT: Final[str] = "dev"

PYPROJECT_PATH: Final[Path] = REPO_ROOT / "pyproject.toml"


def wheel_exclude_globs(pyproject_path: Path = PYPROJECT_PATH) -> tuple[str, ...]:
    """Return the wheel target's exclude globs, read from the packaging config.

    Read rather than restated so the shipped/unshipped boundary this module
    reasons about stays true if the packaging excludes change. A missing table
    raises: silently defaulting to "nothing is excluded" would make every
    module look shipped, and defaulting to "everything" would mute the gate.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding=_UTF_8))
    excludes = data["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    return tuple(str(glob) for glob in excludes)


def is_shipped_module(
    path: Path,
    *,
    src_root: Path = SRC_ROOT,
    exclude_globs: tuple[str, ...] | None = None,
) -> bool:
    """True if ``path`` lands in the installed wheel.

    A module is shipped unless the packaging config excludes it. Note this is
    NOT the same partition as :func:`is_test_module`: a package-root
    ``conftest.py`` carries no ``tests/`` path component, so it ships and is
    treated as shipped here even though it is test infrastructure by name.

    Args:
        path: Module file to classify.
        src_root: Source root ``path`` is relative to.
        exclude_globs: Wheel exclude globs; read from the packaging config when
            omitted.
    """
    globs = wheel_exclude_globs() if exclude_globs is None else exclude_globs
    rel = "src/" + path.relative_to(src_root).as_posix()
    for glob in globs:
        # A bare directory glob ("src/cadrumo/tests") excludes the tree under it;
        # fnmatch's '*' spans '/', so the recursive forms match as written.
        if fnmatch.fnmatchcase(rel, glob) or rel.startswith(glob.rstrip("*").rstrip("/") + "/"):
            return False
    return True


def _docstring_constant_ids(tree: ast.Module) -> set[int]:
    """Return the node ids of every module, class, and function docstring.

    A docstring is documentation, never a runtime path read. Several shipped
    modules legitimately name ``dev/`` tooling in their prose (the terminology
    handbook authoring tool, the corpus extractor), and that prose must not be
    read as a dependency.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


def _comment_lines(source: str) -> list[tuple[int, str]]:
    """Return every ``(lineno, text)`` COMMENT line in ``source``."""
    lines: list[tuple[int, str]] = []
    try:
        stream = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(stream):
            if tok.type == tokenize.COMMENT:
                lines.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, UnicodeDecodeError):
        pass
    return lines


def _prose_string_lines(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every docstring and multi-line string line.

    Docstrings are prose by definition and are swept regardless of length --
    the former Family 6 skip made a one-line docstring naming the dev tree
    invisible. A multi-line NON-docstring string is prose too and is swept;
    single-line non-docstring strings stay Family 6's jurisdiction, so no line
    is reported by two families.
    """
    docstring_ids = _docstring_constant_ids(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        is_doc = id(node) in docstring_ids
        if not is_doc and "\n" not in node.value:
            continue
        for offset, line in enumerate(node.value.splitlines()):
            out.append((node.lineno + offset, line))
    return out
