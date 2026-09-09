"""Import-hygiene scanner for top-level-export centralisation.

Discovery-phase tool: builds an inventory of cross-package private imports and
the ``src/`` -> ``dev/`` boundary breaches across ``src/cadrumo``. READ-ONLY:
it does not modify production code.

It is the SINGLE AUTHORITY for the one-way ``src/`` -> ``dev/`` boundary.
The boundary is absolute, by operator ruling: no module under ``src/`` --
shipped or test, ``cadrumo`` or ``cadrumo_harness`` -- may have ANY awareness of
the ``dev/`` tree. Family 5 detects an IMPORT of ``dev.*`` (static or dynamic),
Family 6 detects a module building a PATH into the ``dev/`` tree at runtime,
and Family 10 detects PROSE awareness -- a comment, docstring or multi-line
string that names the dev tree. The three are one rule with three syntaxes,
and they live together here so a fix to one cannot silently leave the other
behind. Consumers assert against these functions rather than re-implementing
them; the boundary gate under ``dev/quality/tests`` is one such consumer. The
former shipped-only scope was widened by ruling, never by drift: a
wheel-excluded test importing ``dev.*`` is no installed-user defect, but the
ruling targets absolute awareness, not installed-user breakage.

Families 8 and 9 are the two ends of one broken edge, and they live together
for the same reason. A deletion that lands without its consumer sweep leaves
either a consumer pointing at something gone (family 8) or a module nothing
points at any more (family 9); a check that sees only one end reports the split
as clean half the time. Both are whole-tree questions by construction -- no
per-commit or per-file gate can answer either -- so both are computed over the
complete first-party census rather than a changed-file subset.

Re-run with:

    python -m dev.quality.import_hygiene_scan [--json OUT.json] [--top N]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import io
import json
import sys
import tokenize
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8
from .unread_inputs import report_unread

SRC_ROOT = REPO_ROOT / "src"
PKG_ROOT = SRC_ROOT / "cadrumo"
_UTF_8: Final[str] = UTF_8

CANONICAL_TUI_PACKAGE: Final[str] = "cadrumo.entrypoints.tui"

_LIVE_INVENTORY_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {".git", ".vault", "_build", "build", "dist", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)


def tracked_live_files() -> tuple[Path, ...]:
    """Return tracked repository files, excluding only archive/generated trees."""
    import subprocess

    output = subprocess.check_output(("git", "ls-files", "-z"), cwd=REPO_ROOT, text=False)  # noqa: S607
    return tuple(
        sorted(
            {
                (REPO_ROOT / raw.decode(_UTF_8)).resolve()
                for raw in output.split(b"\0")
                if raw
                and (REPO_ROOT / raw.decode(_UTF_8)).is_file()
                and not any(part in _LIVE_INVENTORY_EXCLUDED_DIRS for part in (REPO_ROOT / raw.decode(_UTF_8)).parts)
            },
            key=lambda path: path.as_posix(),
        )
    )


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


def has_private_component(mod: str) -> bool:
    """True if any dotted component (other than a dunder) starts with '_'."""
    return any(part.startswith("_") and not (part.startswith("__") and part.endswith("__")) for part in mod.split("."))


def is_underscore_named(name: str) -> bool:
    """True if ``name`` is a private-convention identifier (leading '_', not a dunder).

    Mirrors the private-component test above but for a single bare identifier
    (an ``__all__`` entry), not a dotted module path.
    """
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def owning_package(mod: str) -> str:
    """Return the package that owns a private module.

    Ownership rule: for a private module ``A.B._C...`` (first private
    component at index k), the owning package is ``A.B`` -- everything
    strictly before the first private component. If the module itself has
    no private component, it owns itself (not expected to be called in that
    case).
    """
    parts = mod.split(".")
    for i, part in enumerate(parts):
        if part.startswith("_") and not (part.startswith("__") and part.endswith("__")):
            return ".".join(parts[:i])
    return mod


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


# ---------------------------------------------------------------------------
# Facade boundary discovery
# ---------------------------------------------------------------------------


@dataclass
class FacadeInfo:
    """A package __init__.py and the ``__all__`` export surface it declares."""

    package: str
    path: Path
    all_names: list[str] = field(default_factory=list)
    has_real_all: bool = False


def dunder_all_assignment_value(node: ast.stmt) -> ast.expr | None:
    """Return the assigned value expression if ``node`` assigns ``__all__``.

    Handles both the plain form (``__all__ = [...]``, :class:`ast.Assign`) and
    the annotated form (``__all__: list[str] = [...]``, :class:`ast.AnnAssign`).
    An annotated declaration with no value (``__all__: list[str]``) yields
    ``None``, same as any other statement that is not an ``__all__`` binding.
    """
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
        return node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
        return node.value
    return None


def discover_facades() -> dict[str, FacadeInfo]:
    """Enumerate every __init__.py carrying a real ``__all__`` literal.

    A "real" ``__all__`` is a non-empty list/tuple/set of string constants,
    assigned via either the plain (``__all__ = [...]``) or annotated
    (``__all__: list[str] = [...]``) form.
    """
    facades: dict[str, FacadeInfo] = {}
    for init_path in scan_directory(
        PKG_ROOT, pattern="__init__.py", recursive=True, prune_directories=("__pycache__",)
    ):
        mod = module_name_for(init_path)
        try:
            src = init_path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(init_path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        all_names: list[str] = []
        has_real_all = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.stmt):
                continue
            value = dunder_all_assignment_value(node)
            if value is None or not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                continue
            names = [elt.value for elt in value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
            if names:
                all_names.extend(names)
                has_real_all = True
        facades[mod] = FacadeInfo(package=mod, path=init_path, all_names=all_names, has_real_all=has_real_all)
    return facades


# ---------------------------------------------------------------------------
# Violation family 4: underscore-named entries in a public ``__all__``
# ---------------------------------------------------------------------------


@dataclass
class UnderscoreInAllViolation:
    """A private-named symbol (leading '_', not a dunder) exported in a facade's ``__all__``.

    A public facade exporting a private-named symbol contradicts the
    single-canonical-source policy: the leading underscore signals "not part
    of the public contract" everywhere else in the codebase, but listing the
    name in ``__all__`` advertises it as exactly that. Every hit needs a
    per-symbol disposition -- promote to a public name (rename + sweep every
    consumer) or drop it from the facade (it stays importable intra-package,
    just not on the public surface).
    """

    package: str
    path: str
    name: str


def find_underscore_in_all_violations(facades: dict[str, FacadeInfo]) -> list[UnderscoreInAllViolation]:
    """Return every ``__all__`` entry across all facades that is underscore-named."""
    violations: list[UnderscoreInAllViolation] = []
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        for name in info.all_names:
            if is_underscore_named(name):
                violations.append(
                    UnderscoreInAllViolation(
                        package=pkg,
                        path=str(info.path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        name=name,
                    )
                )
    return violations


# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Violation family 1: cross-package private import
# ---------------------------------------------------------------------------


@dataclass
class PrivateImportViolation:
    """A cross-package import that reaches into another package's private module."""

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    owning_package: str
    imported_names: list[str]
    is_test: bool
    in_type_checking: bool


def defining_package(mod: str) -> str:
    """Return the package that owns a private NAME defined in ``mod``.

    A private symbol belongs to the module that defines it, and that module's
    own package is the boundary it is private within: siblings may use it,
    anything outside must go through a public name. This is the same ownership
    question :func:`owning_package` answers for a private module path, asked on
    the other axis.
    """
    parts = mod.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else mod


def _reaches_outside(importer: str, owner: str) -> bool:
    """True when ``importer`` sits outside the package that owns the target."""
    return not (importer == owner or importer.startswith(owner + "."))


def find_private_import_violations(all_sites: list[ImportSite]) -> list[PrivateImportViolation]:
    """Return every import site that reaches into a foreign package's privates.

    Two shapes count, because either one alone can be renamed away while the
    coupling survives. A private MODULE path is the familiar shape. A private
    NAME imported from a public module is the other: promoting a private module
    to a public name would otherwise clear every private-symbol reach into it
    from this scanner without changing a single import, so a rename would
    launder a live reach past the gate.
    """
    violations: list[PrivateImportViolation] = []
    for site in all_sites:
        if not site.target_mod.startswith("cadrumo"):
            continue
        importer = site.importer_mod
        if has_private_component(site.target_mod):
            # Legitimate: importer is under the owning package (sibling/descendant),
            # OR importer *is* the owning package's own __init__ building its facade.
            owner = owning_package(site.target_mod)
            reached_names = site.imported_names
        else:
            owner = defining_package(site.target_mod)
            reached_names = [name for name in site.imported_names if is_underscore_named(name)]
            if not reached_names:
                continue
        if not _reaches_outside(importer, owner):
            continue
        violations.append(
            PrivateImportViolation(
                importer_mod=importer,
                importer_path=str(site.importer_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                lineno=site.lineno,
                target_mod=site.target_mod,
                owning_package=owner,
                imported_names=reached_names,
                is_test=site.is_test,
                in_type_checking=site.in_type_checking,
            )
        )
    return violations


class TuiBoundaryViolationKind(StrEnum):
    """Static syntax families that can bypass the dedicated TUI boundary."""

    STATIC_IMPORT = "static_import"
    TYPE_ONLY_IMPORT = "type_only_import"
    REEXPORT = "reexport"
    DYNAMIC_IMPORT = "dynamic_import"
    ANNOTATION = "annotation"
    REGISTRATION = "registration"
    TEXTUAL_LOCATION = "textual_location"
    PRIVATE_FACADE = "private_facade"


@dataclass(frozen=True)
class TuiBoundaryViolation:
    """One exact AST reach that violates D11's TUI dependency direction."""

    importer_mod: str
    importer_path: str
    lineno: int
    target: str
    kind: TuiBoundaryViolationKind


def _targets_module(value: str, module: str) -> bool:
    return value == module or value.startswith(module + ".") or value.startswith(module + ":")


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _expression_reference(node: ast.expr, aliases: dict[str, str]) -> str | None:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    root = aliases.get(current.id, current.id)
    return ".".join((root, *reversed(parts)))


def _annotation_references(tree: ast.Module, aliases: dict[str, str]) -> tuple[tuple[int, str], ...]:
    annotations: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.extend(arg.annotation for arg in (*node.args.posonlyargs, *node.args.args) if arg.annotation)
            annotations.extend(arg.annotation for arg in (*node.args.kwonlyargs,) if arg.annotation)
            if node.args.vararg and node.args.vararg.annotation:
                annotations.append(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation:
                annotations.append(node.args.kwarg.annotation)
            if node.returns:
                annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    found: set[tuple[int, str]] = set()
    for annotation in annotations:
        for node in ast.walk(annotation):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add((node.lineno, node.value))
            elif isinstance(node, (ast.Name, ast.Attribute)) and (target := _expression_reference(node, aliases)):
                found.add((node.lineno, target))
    return tuple(
        sorted(
            (line, target)
            for line, target in found
            if not any(other_line == line and other.startswith(target + ".") for other_line, other in found)
        )
    )


def _registration_references(tree: ast.Module, aliases: dict[str, str]) -> tuple[tuple[int, str], ...]:
    """Return TUI-shaped values passed through any call boundary.

    Registration APIs have no stable verb vocabulary: decorators, registries,
    plugin managers and dependency containers all accept the same module or
    object reference under arbitrary method names.  The semantic fact is the
    TUI reference crossing a call boundary, so resolve every argument rather
    than maintaining registrar spellings.
    """
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = _called_function_name(node.func)
        if called in _DYNAMIC_IMPORT_CALLABLES:
            continue
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if _targets_module(value.value, CANONICAL_TUI_PACKAGE):
                    found.add((value.lineno, value.value))
            elif (target := _expression_reference(value, aliases)) and _targets_module(target, CANONICAL_TUI_PACKAGE):
                found.add((value.lineno, target))
    return tuple(sorted(found))


def find_tui_boundary_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[TuiBoundaryViolation]:
    """Reject every statically visible bypass of the canonical TUI boundary."""
    violations: list[TuiBoundaryViolation] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        aliases = _import_aliases(tree)
        importer = module_name_for(path, src_root=src_root)
        relative = path.relative_to(src_root).as_posix()
        inside_tui = importer == CANONICAL_TUI_PACKAGE or importer.startswith(CANONICAL_TUI_PACKAGE + ".")

        for site in walk_module_imports(path, src_root=src_root):
            target = site.target_mod
            if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                kind = (
                    TuiBoundaryViolationKind.TYPE_ONLY_IMPORT
                    if site.in_type_checking
                    else TuiBoundaryViolationKind.STATIC_IMPORT
                )
                if path.name == "__init__.py":
                    kind = TuiBoundaryViolationKind.REEXPORT
                violations.append(TuiBoundaryViolation(importer, relative, site.lineno, target, kind))
            if (
                inside_tui
                and target.startswith("cadrumo.")
                and any(is_underscore_named(name) for name in site.imported_names)
            ):
                private_target = next(name for name in site.imported_names if is_underscore_named(name))
                violations.append(
                    TuiBoundaryViolation(
                        importer,
                        relative,
                        site.lineno,
                        f"{target}.{private_target}",
                        TuiBoundaryViolationKind.PRIVATE_FACADE,
                    )
                )
            if (target == "textual" or target.startswith("textual.")) and not inside_tui:
                violations.append(
                    TuiBoundaryViolation(
                        importer, relative, site.lineno, target, TuiBoundaryViolationKind.TEXTUAL_LOCATION
                    )
                )
            if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                owner = owning_package(target)
                if importer != owner and not importer.startswith(owner + "."):
                    violations.append(
                        TuiBoundaryViolation(
                            importer, relative, site.lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE
                        )
                    )

        for lineno, target in iter_dynamic_import_targets(path):
            if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                violations.append(
                    TuiBoundaryViolation(importer, relative, lineno, target, TuiBoundaryViolationKind.DYNAMIC_IMPORT)
                )
            if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                violations.append(
                    TuiBoundaryViolation(importer, relative, lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE)
                )

        for kind, references in (
            (TuiBoundaryViolationKind.ANNOTATION, _annotation_references(tree, aliases)),
            (TuiBoundaryViolationKind.REGISTRATION, _registration_references(tree, aliases)),
        ):
            for lineno, target in references:
                if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                    violations.append(TuiBoundaryViolation(importer, relative, lineno, target, kind))
                if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                    violations.append(
                        TuiBoundaryViolation(
                            importer, relative, lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE
                        )
                    )

    return sorted(violations, key=lambda item: (item.importer_path, item.lineno, item.kind, item.target))


# ---------------------------------------------------------------------------
# Violation family 5: shipped module importing the unshipped dev tooling
# ---------------------------------------------------------------------------

DEV_TOOLING_ROOT: Final[str] = "dev"

PYPROJECT_PATH: Final[Path] = REPO_ROOT / "pyproject.toml"

# Callables whose first string-literal argument names a module to import. A
# dynamically-built target is invisible to the AST import walk above, so a
# `dev.` reach expressed this way would otherwise slip the family entirely --
# the exact blind spot that makes a gate pass while missing what it guards.
_DYNAMIC_IMPORT_CALLABLES: Final[frozenset[str]] = frozenset({"import_module", "__import__"})


@dataclass
class DevToolingImportViolation:
    """A module under ``src/`` that imports the unshipped ``dev/`` tooling."""

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    imported_names: list[str]
    is_dynamic: bool


def targets_dev_tooling(mod: str) -> bool:
    """True if ``mod`` names the ``dev`` tooling root or anything beneath it."""
    return mod == DEV_TOOLING_ROOT or mod.startswith(DEV_TOOLING_ROOT + ".")


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


def iter_dynamic_import_targets(path: Path) -> list[tuple[int, str]]:
    """Return every ``(lineno, module)`` pair from a string-literal dynamic import.

    Only a literal first argument is resolvable by static reading; a target
    assembled from variables is out of reach here and is left to review.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
        return []

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            called = func.attr
        elif isinstance(func, ast.Name):
            called = func.id
        else:
            continue
        if called not in _DYNAMIC_IMPORT_CALLABLES:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value))
    return found


def find_dev_tooling_import_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevToolingImportViolation]:
    """Return every module under ``src_root`` that imports ``dev.``.

    Absolute by operator ruling: no module under ``src/`` -- shipped or test --
    may import the ``dev/`` tree, which ships in neither the wheel nor the
    sdist. The former shipped-only scope encoded the installed-user defect only;
    the ruling widens the boundary to all awareness, so a test that needs dev
    tooling lives under ``dev/`` itself and is swept here as a violation too.

    Args:
        py_files: Module files to scan.
        src_root: Source root importer names are resolved against.
    """
    violations: list[DevToolingImportViolation] = []
    for path in py_files:
        mod = module_name_for(path, src_root=src_root)
        rel = str(path.relative_to(src_root)).replace("\\", "/")
        for site in walk_module_imports(path, src_root=src_root):
            if targets_dev_tooling(site.target_mod):
                violations.append(
                    DevToolingImportViolation(
                        importer_mod=mod,
                        importer_path=rel,
                        lineno=site.lineno,
                        target_mod=site.target_mod,
                        imported_names=site.imported_names,
                        is_dynamic=False,
                    )
                )
        for lineno, target in iter_dynamic_import_targets(path):
            if targets_dev_tooling(target):
                violations.append(
                    DevToolingImportViolation(
                        importer_mod=mod,
                        importer_path=rel,
                        lineno=lineno,
                        target_mod=target,
                        imported_names=[],
                        is_dynamic=True,
                    )
                )
    return sorted(violations, key=lambda v: (v.importer_path, v.lineno, v.target_mod))


# ---------------------------------------------------------------------------
# Violation family 6: shipped module building a path into the unshipped dev tree
# ---------------------------------------------------------------------------

# Leading segments that carry no path identity of their own.
_RELATIVE_MARKERS: Final[frozenset[str]] = frozenset({".", ".."})

# Callables that assemble a filesystem path from separate segment arguments, so
# a bare "dev" argument names the dev directory. `join` is deliberately gated on
# an arity of two or more: `sep.join(iterable)` is a string operation with a
# single argument and must never be read as a path assembly.
_SEGMENT_JOIN_CALLABLES: Final[frozenset[str]] = frozenset({"join"})
_PATH_FACTORY_CALLABLES: Final[frozenset[str]] = frozenset(
    {
        "Path",
        "PurePath",
        "PosixPath",
        "PurePosixPath",
        "WindowsPath",
        "PureWindowsPath",
        "joinpath",
    }
)


class DevPathForm(StrEnum):
    """The syntactic shape a shipped module used to reach into ``dev/``."""

    LITERAL = "literal"
    PATH_JOIN = "path_join"
    CALL_JOIN = "call_join"
    FSTRING = "fstring"


@dataclass
class DevPathReachViolation:
    """A shipped module under ``src/`` that builds a path into the ``dev/`` tree."""

    module_path: str
    lineno: int
    form: DevPathForm
    detail: str


def _posix_segments(value: str) -> list[str]:
    r"""Split ``value`` into path segments on either separator.

    Windows and POSIX separators are folded together so ``"dev\\x.json"`` and
    ``"dev/x.json"`` are the same path to this scanner.
    """
    return value.replace("\\", "/").split("/")


def names_dev_directory(value: str) -> bool:
    """True if ``value`` is a *relative* path whose leading component is ``dev``.

    Segment-aware, never a substring test. Three discriminations carry the
    precision of this whole family:

    * An **absolute** ``/dev/...`` value is a POSIX device node, not the repo
      tree. Shipped code opens ``"/dev/tty"`` to read a secret without echo and
      is correct to do so; firing there would red the gate on sound code and
      teach the next author to weaken it. What actually delivers that silence
      today is the segment-equality rule below, not the ``startswith("/")``
      guard: an absolute value splits to a LEADING EMPTY segment, the
      relative-marker skip advances over ``.`` and ``..`` only, so the scan
      compares ``""`` against ``dev`` and stops. The explicit guard is
      defence-in-depth against exactly one future widening -- folding ``""``
      into the relative-marker skip so ``"/dev/x"`` normalises like
      ``"./dev/x"``, which would otherwise re-open the device-path false
      positive with no test naming it. Keep the guard and the marker set in
      view together; neither is redundant with the other under that change.
    * A segment must **equal** ``dev``. ``devengada``, ``devolucion``,
      ``device`` and ``dev.example.com`` are all near-misses this codebase
      really contains.
    * ``dev`` must be used as a **directory** -- something has to follow it. A
      bare ``"dev"`` string carries no path meaning on its own; it is caught by
      the join forms below, which supply the surrounding path context.

    A value containing a newline is prose (a docstring or a message), never a
    path literal, and is rejected; docstrings are skipped wholesale by
    :func:`_docstring_constant_ids`. A single-line NON-docstring string that
    begins with a dev path -- an assertion message, say -- is still reported.
    That is deliberate: narrowing further (rejecting any value containing a
    space) would let ``"dev/my baseline.json"`` through, and in a hard-zero
    boundary gate an over-fire costs a reword while an under-fire ships a
    broken wheel. A shipped module has no business naming the dev tree even in
    prose.
    """
    if not value or "\n" in value or "\r" in value:
        return False
    normalised = value.replace("\\", "/")
    if normalised.startswith("/"):
        return False
    segments = normalised.split("/")
    index = 0
    while index < len(segments) and segments[index] in _RELATIVE_MARKERS:
        index += 1
    return index + 1 < len(segments) and segments[index] == DEV_TOOLING_ROOT


def _continues_into_dev_directory(text: str) -> bool:
    """True for an f-string tail like ``"/dev/x.json"`` that follows a root interpolation.

    Read only for a constant segment PRECEDED by an interpolation, where the
    leading separator joins onto an interpolated root rather than marking an
    absolute path. That preceding-interpolation requirement is what keeps a
    plain ``f"/dev/null"`` out: with nothing interpolated before it, the value
    is an absolute device path and is judged by :func:`names_dev_directory`.

    The empty leading segment carries the other half: the tail must BEGIN with
    a separator, so ``dev`` sits directly under the interpolated root. A tail
    like ``"-sandbox/dev/notes.json"`` glues the interpolation into its own
    first segment, naming a ``dev`` directory one level below a DIFFERENT tree
    -- not this repository's.
    """
    segments = _posix_segments(text)
    return len(segments) >= 2 and segments[0] == "" and segments[1] == DEV_TOOLING_ROOT


def _is_bare_dev_segment(node: ast.expr) -> bool:
    """True if ``node`` is the string constant ``"dev"``."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == DEV_TOOLING_ROOT


def _divided_dev_segment(node: ast.BinOp) -> str | None:
    """Return a detail string if ``node`` is a ``pathlib`` join onto ``"dev"``.

    Matches ``PROJECT_ROOT / "dev"`` -- the realistic form of this violation,
    since a bare ``open("dev/x.json")`` is CWD-relative and would not survive a
    single test run from outside the repo root. ``PROJECT_ROOT`` is exported
    from ``cadrumo.core.paths``, so a shipped module can anchor a fully working
    dev-tree read this way and break only once installed as a wheel.

    Both operands are checked: ``Path.__rtruediv__`` makes ``"dev" / root`` a
    valid join too. Only the BARE ``"dev"`` segment matches here; a
    ``root / "dev/x.json"`` operand is already a dev path literal and is
    reported once, by :func:`names_dev_directory`, rather than twice.
    """
    if not isinstance(node.op, ast.Div):
        return None
    if _is_bare_dev_segment(node.right) or _is_bare_dev_segment(node.left):
        return f'{ast.unparse(node)!s} (path join onto "{DEV_TOOLING_ROOT}")'
    return None


def _called_function_name(func: ast.expr) -> str | None:
    """Return the trailing callable name of ``func``, or ``None`` if unreadable."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _call_assembled_dev_segment(node: ast.Call) -> str | None:
    """Return a detail string if ``node`` assembles a path from a ``"dev"`` segment.

    Covers ``os.path.join(root, "dev", "x.json")`` and the ``Path(root, "dev")``
    / ``root.joinpath("dev")`` factory forms. ``join`` requires two or more
    arguments so ``"".join(parts)`` -- a string operation, not a path assembly
    -- can never match.
    """
    name = _called_function_name(node.func)
    if name is None:
        return None
    if name in _SEGMENT_JOIN_CALLABLES:
        if len(node.args) < 2:
            return None
    elif name not in _PATH_FACTORY_CALLABLES:
        return None
    if any(_is_bare_dev_segment(arg) for arg in node.args):
        return f'{name}(...) with a "{DEV_TOOLING_ROOT}" path segment'
    return None


def _joined_str_dev_parts(node: ast.JoinedStr) -> list[str]:
    """Return every constant part of an f-string that reaches into ``dev/``.

    An f-string hides the reach from a constant scan: ``f"{root}/dev/x.json"``
    stores the segment as the constant ``"/dev/x.json"``, which starts with a
    separator and matches no ``dev/`` prefix.
    """
    parts: list[str] = []
    interpolated = False
    for part in node.values:
        if isinstance(part, ast.FormattedValue):
            interpolated = True
            continue
        if not isinstance(part, ast.Constant) or not isinstance(part.value, str):
            continue
        text = part.value
        if names_dev_directory(text) or (interpolated and _continues_into_dev_directory(text)):
            parts.append(text)
    return parts


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


def dev_path_hits(tree: ast.Module) -> list[tuple[int, DevPathForm, str]]:
    """Return every ``(lineno, form, detail)`` dev-tree reach in one parsed module."""
    skip = _docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values if isinstance(part, ast.Constant))

    hits: list[tuple[int, DevPathForm, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            hits.extend((node.lineno, DevPathForm.FSTRING, text) for text in _joined_str_dev_parts(node))
        elif isinstance(node, ast.BinOp):
            detail = _divided_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.PATH_JOIN, detail))
        elif isinstance(node, ast.Call):
            detail = _call_assembled_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.CALL_JOIN, detail))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and names_dev_directory(node.value)
        ):
            hits.append((node.lineno, DevPathForm.LITERAL, node.value))
    return hits


def find_dev_path_reach_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevPathReachViolation]:
    r"""Return every module under ``src_root`` that builds a ``dev/`` path.

    This is the metadata loophole an import scan alone cannot see: a module
    reading a dev artifact at runtime does not import ``dev.*`` but is just as
    broken for every installed user, because ``dev/`` ships in neither the
    wheel nor the sdist. Family 5 catches the code dependency; this family
    catches the data dependency. Absolute by operator ruling -- every module
    under ``src/``, test trees included, is swept.

    Four forms are detected, because the boundary breaks in all four and a
    scanner covering only the first is a scanner that cannot see the realistic
    case:

    * ``literal`` -- ``"dev/baseline.json"``, ``"./dev/..."``, ``"..\dev\..."``
    * ``path_join`` -- ``PROJECT_ROOT / "dev" / "baseline.json"``
    * ``call_join`` -- ``os.path.join(root, "dev", ...)``, ``Path(root, "dev")``
    * ``fstring`` -- ``f"{root}/dev/baseline.json"``

    **Construction is the trigger, not the read.** A reach is reported where
    the path is BUILT, without requiring an adjacent ``open``/``read_text``
    call. Demanding proof of a read would reopen the hole this family exists to
    close: a module constant assigned once and consumed elsewhere (exactly how
    the real baselines in the excluded test tree are written) would then pass
    while depending on a dev artifact at runtime. No module under ``src/`` has
    a legitimate reason to name the dev tree at all.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[DevPathReachViolation] = []
    unread: list[str] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            unread.append(rel)
            continue
        violations.extend(
            DevPathReachViolation(rel, lineno, form, detail) for lineno, form, detail in dev_path_hits(tree)
        )
    report_unread(
        "dev-path reach scan",
        "a development-tree reference inside one of them would not be found",
        unread,
    )
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.form, v.detail))


# ---------------------------------------------------------------------------
# Violation family 10: prose awareness of the dev tree under src/
# ---------------------------------------------------------------------------


#: Live top-level names of the dev tree, read from disk at scan time so this
#: family tracks the tree it guards without a maintained list. Only a path or
#: module reference naming a REAL dev child fires -- ``dev.example.com``,
#: ``devengada`` and another tree's ``dev`` directory stay silent.
def _dev_tree_children() -> frozenset[str]:
    """Return the dev tree's current top-level entries, refusing an unreadable tree.

    Returning an empty set on failure would be silent rather than safe. Every
    dotted token is decided by membership in this roster, so an empty roster
    answers False for all of them, and the slash channel degrades the same way,
    keeping only a bare ``dev/`` folder reference. The scan then reports clean
    over a detector that can no longer match, with nothing in the output saying
    so. Measured against this tree: with the roster live,
    ``dev.quality.import_hygiene_scan`` and ``dev/quality/foo.py`` are both
    recognised; with it empty, neither is, while the near-miss tokens the
    detector must reject stay rejected. The loss is detection only, which is
    the shape that reads as a pass.

    Refusing matters more here than in a per-file handler because this is
    resolved once at import, so a single transient failure would poison every
    scan in the process rather than one file. The sibling lane-visibility
    screen refuses a declared root that has stopped existing for the same
    reason, and this follows it.
    """
    try:
        return frozenset(
            entry.name for entry in (REPO_ROOT / DEV_TOOLING_ROOT).iterdir() if not entry.name.startswith(".")
        )
    except OSError as error:
        raise FileNotFoundError(
            "the dev tree could not be listed, so the prose scan would report clean over a "
            f"detector whose every dotted match is decided by that listing: {REPO_ROOT / DEV_TOOLING_ROOT}"
        ) from error


_DEV_TREE_CHILDREN: Final[frozenset[str]] = _dev_tree_children()


def prose_token_names_dev_tree(token: str) -> bool:
    """True if one whitespace-delimited prose token names this repo's dev tree.

    Prose tokens are comment, docstring and multi-line-string words, so the
    same three discriminations as :func:`names_dev_directory` carry the
    precision here: the token must START with ``dev`` (an absolute ``/dev/tty``
    device path and a mid-path ``-sandbox/dev/...`` segment do not), a ``dev``
    must name a REAL top-level child of the dev tree (``dev.example.com`` and
    a bare word ``dev`` do not), and the slash form accepts a trailing ``dev/``
    as a bare folder reference.
    """
    stripped = token.strip("()[]{}`'\"<>,:;")
    if not stripped.startswith(DEV_TOOLING_ROOT):
        return False
    segments = stripped.replace("\\", "/").split("/")
    if len(segments) >= 2:
        return segments[1] in _DEV_TREE_CHILDREN or segments[1] == ""
    dotted = stripped.split(".")
    return len(dotted) >= 2 and dotted[1] in _DEV_TREE_CHILDREN


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


@dataclass
class DevProseViolation:
    """A comment, docstring or multi-line string in a src module naming the dev tree."""

    module_path: str
    lineno: int
    source_kind: str  # "comment" | "string"
    detail: str


def find_dev_prose_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevProseViolation]:
    """Return every prose site under ``src_root`` that names the dev tree.

    The awareness half of the boundary, by operator ruling: even a comment or
    docstring naming ``dev/`` is forbidden under ``src/``. The precision rules
    are the same ones the path family documents -- device nodes, near-miss
    Spanish stems, and other trees' ``dev`` directories stay silent.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[DevProseViolation] = []
    unread: list[str] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            source = path.read_text(encoding=_UTF_8)
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            unread.append(rel)
            continue
        for lineno, text in _prose_string_lines(tree):
            for token in text.split():
                if prose_token_names_dev_tree(token):
                    violations.append(DevProseViolation(rel, lineno, "string", text.strip()))
                    break
        for lineno, text in _comment_lines(source):
            for token in text.split():
                if prose_token_names_dev_tree(token):
                    violations.append(DevProseViolation(rel, lineno, "comment", text.strip()))
                    break
    report_unread(
        "dev-prose scan",
        "a development-tree mention inside one of them would not be found",
        unread,
    )
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.source_kind))


# ---------------------------------------------------------------------------
# Violation family 7: production import of a demoted registry raw-loader symbol
# ---------------------------------------------------------------------------

REGISTRY_LOADER_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry.loader"
REGISTRY_LOADER_OWNER_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry"

#: Raw-loader-and-unguarded-entry-point names demoted from the registry
#: loader module's public contract: the four raw-loader names, plus
#: ``build_snapshot``, which is the same unguarded-entry-point class as the
#: raw loader family. Each had zero
#: cross-package production OR test consumers at demotion time, EXCEPT
#: ``build_snapshot``, whose only external caller at demotion time was a test
#: fixture (confirmed by an AST scan over ``walk_module_imports``, not a text
#: grep -- a multi-line ``from ... import (...)`` block hides a name from a
#: per-line regex, which is exactly how ``collect_registry_tree_fingerprints``
#: was nearly misclassified here). Test callers of a demoted name are never
#: gated below (``site.is_test`` short-circuits); ``build_snapshot`` has since
#: gained more of them, routed through the ``domain.calculations.registry.tests``
#: facade rather than this package directly. The eight raw-loader siblings that stayed
#: exported (``load_registry_tree``, ``load_legal_parameters_only``,
#: ``load_catalogue_file``, ``load_modelo_directory``, ``load_modelo_file``,
#: ``load_modelo_path``, ``clear_fingerprint_cache``,
#: ``collect_registry_tree_fingerprints``) each answer a real external need
#: documented at their call sites -- import-time cycle avoidance for the
#: IRPF/IVA/transactions parameter readers, a deliberate unvalidated-tree read
#: for conformance auditing, or the runtime schema loader's own TTL cache
#: layered atop the canonical fingerprint collector -- and are out of scope
#: for this family; only demoted names are gated.
DEMOTED_REGISTRY_LOADER_SYMBOLS: Final[frozenset[str]] = frozenset(
    {
        "ModeloRevisionSource",
        "ModeloSource",
        "build_snapshot",
        "discover_modelo_sources",
        "load_modelo_source",
    }
)


@dataclass
class RegistryLoaderImportViolation:
    """A production import of a demoted registry raw-loader symbol."""

    importer_mod: str
    importer_path: str
    lineno: int
    imported_names: list[str]


def find_registry_loader_import_violations(
    all_sites: list[ImportSite], *, src_root: Path = SRC_ROOT
) -> list[RegistryLoaderImportViolation]:
    """Return every PRODUCTION import site naming a demoted raw-loader symbol.

    Scoped to non-test sites outside the registry package itself, which still
    reaches its own loader internals directly. The registry package is the
    loader's implementation boundary; other production consumers name the
    public ``authority`` module instead.

    Args:
        all_sites: Import sites to scan, from :func:`walk_module_imports`.
        src_root: Source root ``importer_path`` is resolved relative to;
            injectable so a caller can scan a synthetic tree (matches the
            convention of the other planted-import families in this module).
    """
    violations: list[RegistryLoaderImportViolation] = []
    for site in all_sites:
        if site.is_test:
            continue
        if site.target_mod != REGISTRY_LOADER_PACKAGE:
            continue
        if site.importer_mod == REGISTRY_LOADER_OWNER_PACKAGE or site.importer_mod.startswith(
            REGISTRY_LOADER_OWNER_PACKAGE + "."
        ):
            continue
        hit = [name for name in site.imported_names if name in DEMOTED_REGISTRY_LOADER_SYMBOLS]
        if not hit:
            continue
        try:
            importer_path = str(site.importer_path.relative_to(src_root)).replace("\\", "/")
        except ValueError:
            importer_path = str(site.importer_path).replace("\\", "/")
        violations.append(
            RegistryLoaderImportViolation(
                importer_mod=site.importer_mod,
                importer_path=importer_path,
                lineno=site.lineno,
                imported_names=hit,
            )
        )
    return sorted(violations, key=lambda v: (v.importer_path, v.lineno))


# ---------------------------------------------------------------------------
# Violation family 8: dangling first-party import targets
# ---------------------------------------------------------------------------


FIRST_PARTY_ROOT: Final[str] = "cadrumo"


class DanglingImportKind(StrEnum):
    """Which half of an import edge no longer resolves."""

    MISSING_MODULE = "missing_module"
    MISSING_EXPORT = "missing_export"


@dataclass(frozen=True)
class DanglingImportTarget:
    """One first-party import edge whose target no longer exists.

    The two halves of a deletion that landed without its consumer sweep.
    ``MISSING_MODULE`` is the module itself gone with an importer left behind;
    ``MISSING_EXPORT`` is the module still present but the named symbol dropped
    from it -- the subtler half, and the one that reproduced live on this tree.

    This family exists because the mechanism that already computes the same
    fact tree-wide -- the type checker, over ``src`` with
    ``allowed-unresolved-imports = []`` -- carries hundreds of unrelated
    diagnostics at rest, so one new dangling edge is indistinguishable from the
    standing noise. A family scoped to exactly this rule can hold a clean floor
    and therefore actually bite. It is deliberately NOT a second import
    resolver: it answers one question the whole-tree checker answers too, but
    at a granularity that can be gated at zero.
    """

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    symbol: str | None
    kind: DanglingImportKind
    is_test: bool


def first_party_module_path(mod: str, *, src_root: Path = SRC_ROOT) -> Path | None:
    """Resolve a dotted first-party module name to its file, or ``None``.

    Returns the package ``__init__.py`` for a package and the plain module
    file otherwise, mirroring the import system's own preference order.
    """
    rel = Path(*mod.split("."))
    package_init = src_root / rel / "__init__.py"
    if package_init.is_file():
        return package_init
    plain = src_root / rel.with_suffix(".py")
    if plain.is_file():
        return plain
    return None


def module_export_surface(path: Path) -> tuple[frozenset[str], bool]:
    """Return every module-level name a module binds, and whether that is complete.

    Completeness is the load-bearing half. A module answering attribute access
    through a PEP 562 ``__getattr__``, or re-exporting through ``from x import
    *``, binds names no AST walk can enumerate, so its surface is reported
    NOT enumerable and :func:`find_dangling_first_party_imports` declines to
    judge any symbol against it. Declining is the only sound answer there: a
    detector that guessed would report every lazily-resolved export as
    dangling.

    The walk is deliberately generous about binding forms -- tuple unpacking
    (``a, b = factory()``), PEP 695 ``type`` aliases, ``for``/``with`` targets,
    walrus bindings, and import aliases all bind a module-level name, and each
    was observed as a false positive before it was handled.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return frozenset[str](), False

    names: set[str] = set()
    enumerable = True
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node.name == "__getattr__":
                enumerable = False
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.NamedExpr)):
            names.update(
                sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)
            )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    enumerable = False
                else:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return frozenset(names), enumerable


def _is_first_party(mod: str) -> bool:
    return mod == FIRST_PARTY_ROOT or mod.startswith(FIRST_PARTY_ROOT + ".")


def find_dangling_first_party_imports(
    all_sites: Iterable[ImportSite], *, src_root: Path = SRC_ROOT
) -> list[DanglingImportTarget]:
    """Return every first-party import edge whose target no longer resolves.

    Args:
        all_sites: Import sites to scan, from :func:`walk_module_imports`.
        src_root: Source root the first-party names resolve against;
            injectable so a caller can scan a synthetic tree.
    """
    dangling: list[DanglingImportTarget] = []
    surfaces: dict[str, tuple[frozenset[str], bool]] = {}

    for site in all_sites:
        target = site.target_mod
        if not _is_first_party(target):
            continue
        importer_path = str(site.importer_path).replace("\\", "/")
        target_path = first_party_module_path(target, src_root=src_root)
        if target_path is None:
            dangling.append(
                DanglingImportTarget(
                    importer_mod=site.importer_mod,
                    importer_path=importer_path,
                    lineno=site.lineno,
                    target_mod=target,
                    symbol=None,
                    kind=DanglingImportKind.MISSING_MODULE,
                    is_test=site.is_test,
                )
            )
            continue

        if target not in surfaces:
            surfaces[target] = module_export_surface(target_path)
        surface, enumerable = surfaces[target]
        if not enumerable:
            continue

        is_package = target_path.name == "__init__.py"
        for name in site.imported_names:
            if name == "*" or (name.startswith("__") and name.endswith("__")):
                continue
            if name in surface:
                continue
            # `from package import submodule` binds a module, not a name in
            # the package body; it resolves whenever the submodule file exists.
            if is_package and first_party_module_path(f"{target}.{name}", src_root=src_root) is not None:
                continue
            dangling.append(
                DanglingImportTarget(
                    importer_mod=site.importer_mod,
                    importer_path=importer_path,
                    lineno=site.lineno,
                    target_mod=target,
                    symbol=name,
                    kind=DanglingImportKind.MISSING_EXPORT,
                    is_test=site.is_test,
                )
            )
    return sorted(dangling, key=lambda d: (d.importer_path, d.lineno, d.symbol or ""))


# ---------------------------------------------------------------------------
# Violation family 9: orphaned modules (the other end of the same edge)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrphanedModule:
    """A shipped module nothing in the first-party tree reaches.

    The opposite direction of :class:`DanglingImportTarget`: family 8 finds the
    consumer left behind by a deleted module, family 9 finds the module left
    behind by a deleted consumer. Both are one deletion landing without its
    sweep, and neither is visible to the other's check.

    ``is_reexport_surface`` marks the subset the "no standing non-``__init__``
    re-export bridge modules" rule names directly: a bridge whose last importer
    is gone forwards nothing to nobody, and unlike a module with real
    definitions there is no reading under which it is dormant-but-intended.
    """

    mod: str
    path: str
    is_reexport_surface: bool
    is_test: bool


#: Filenames a running system reaches without any module importing them: a
#: package body, a ``python -m`` entry point, and pytest's own two path-loaded
#: shapes. A zero-importer verdict on these says nothing, so they are excluded
#: by SHAPE rather than by name -- there is no per-module allowlist here.
_NON_IMPORTED_REACH_FILENAMES: Final[frozenset[str]] = frozenset({"__init__.py", "__main__.py", "conftest.py"})


def _string_constants(path: Path) -> set[str]:
    """Return every string constant in a module, for dynamic-reach detection."""
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def first_party_census_files(*, repo_root: Path = REPO_ROOT) -> list[tuple[Path, Path]]:
    """Return every first-party ``.py`` file that can reach a shipped module.

    Each entry pairs the file with the source root its own dotted name is
    taken relative to, because the three first-party trees do not share one:
    the package sits under ``src/``, the harness distribution vendors its own
    ``src/`` root, and the development tooling is rooted at the repository.
    Resolving a tree against the wrong root silently mis-resolves its relative
    imports, which drops real reach and manufactures orphans.
    """
    roots = (
        (repo_root / "src" / "cadrumo", repo_root / "src"),
        (repo_root / "src" / "cadrumo_harness", repo_root / "src" / "cadrumo_harness"),
        (repo_root / "dev", repo_root),
    )
    census: list[tuple[Path, Path]] = []
    for tree, src_root in roots:
        if not tree.is_dir():
            continue
        census.extend(
            (path, src_root)
            for path in scan_directory(tree, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        )
    return census


def _named_by_any_string(path: Path, mod: str, rel: str, string_pool: Iterable[str]) -> bool:
    """True if some string constant in the tree names this module.

    Four shapes were observed reaching a real module through a string the
    import graph cannot follow, and all four must count or a live module reads
    as orphaned: the full dotted name (a subprocess ``-m`` target), the
    repo-relative path, the relative registration suffix ``.<stem>`` (the lazy
    CLI command table), and the bare filename (a path-assembling probe that
    joins directory parts and ends in ``"<stem>.py"``).

    The bias is deliberate and one-directional. Counting a coincidental string
    as reach costs a missed orphan; MISSING a real reach reports a live module
    as dead, and that is the verdict somebody acts on by deleting it.
    """
    suffix = f".{path.stem}"
    filename = path.name
    return any(
        text in (mod, rel, filename) or text.endswith(suffix) or text.endswith(f"/{filename}") for text in string_pool
    )


def find_orphaned_modules(
    package_files: Iterable[Path],
    census_files: Iterable[tuple[Path, Path]],
    reexport_paths: Iterable[str],
    *,
    repo_root: Path = REPO_ROOT,
    src_root: Path = SRC_ROOT,
) -> list[OrphanedModule]:
    """Return every module under the package that nothing reaches.

    Args:
        package_files: The candidate modules -- the shipped package tree.
        census_files: ``(file, source root)`` pairs for every file that may
            REACH a candidate, from :func:`first_party_census_files`. This
            must span the whole first-party tree, not just the package: a
            module read as orphaned purely because its only importers lived in
            a sibling distribution and the development tooling, and a
            false-orphan verdict is the one failure that would get a live
            module deleted.
        reexport_paths: Repo-relative paths of known pure-re-export modules,
            used to mark the bridge subset.
        repo_root: Root the reported paths are relative to.
        src_root: Source root the candidates' dotted names are taken relative
            to; injectable so a caller can scan a synthetic tree.

    A module counts as reached by a static import, by a dynamic
    ``importlib.import_module`` target, or by ANY string constant naming it --
    a lazy CLI command table, a subprocess ``-m`` target and a path-based test
    probe all reach a module through a string the import graph cannot see, and
    each was observed on this tree.
    """
    census = list(census_files)
    reached: set[str] = set()
    string_pool: set[str] = set()

    for path, census_src_root in census:
        for site in walk_module_imports(path, src_root=census_src_root):
            reached.add(site.target_mod)
            for name in site.imported_names:
                reached.add(f"{site.target_mod}.{name}")
        for _lineno, target in iter_dynamic_import_targets(path):
            reached.add(target)
        string_pool |= _string_constants(path)

    bridges = frozenset(reexport_paths)
    orphans: list[OrphanedModule] = []
    for path in package_files:
        if path.name in _NON_IMPORTED_REACH_FILENAMES or path.name.startswith("test_"):
            continue
        mod = module_name_for(path, src_root=src_root)
        if mod in reached:
            continue
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        if _named_by_any_string(path, mod, rel, string_pool):
            continue
        orphans.append(
            OrphanedModule(
                mod=mod,
                path=rel,
                is_reexport_surface=rel in bridges,
                is_test=is_test_module(mod, path),
            )
        )
    return sorted(orphans, key=lambda o: o.path)


# ---------------------------------------------------------------------------
# Fix-strategy analysis: precondition promotions vs. simple consumer rewrites
# ---------------------------------------------------------------------------


@dataclass
class FixClassification:
    """Whether a cross-package symbol needs facade promotion or a consumer rewrite."""

    owning_package: str
    symbol: str
    already_in_facade: bool
    consumer_count: int
    consumer_modules: list[str]

    def __post_init__(self) -> None:
        """Refuse a consumer count that disagrees with the modules listed.

        Both fields are built from one set at the single construction site --
        ``consumer_count=len(consumers)`` beside ``consumer_modules=sorted(
        consumers)`` -- so equality is universal by construction rather than a
        property of today's data. Nothing enforced it: this is a plain
        dataclass and every field is a free parameter. The count is what the
        operator-facing batch summary prints as "N consumer site(s)", the
        figure a refactor is sized against, while ``consumer_modules`` is the
        list of files actually edited. A disagreement misstates the workload
        while the list beside it says otherwise.
        """
        if self.consumer_count != len(self.consumer_modules):
            message = (
                f"consumer_count is {self.consumer_count} but {len(self.consumer_modules)} consumer "
                "module(s) are listed; both are derived from one set and cannot disagree"
            )
            raise ValueError(message)


def classify_fix_strategy(
    priv_violations: list[PrivateImportViolation], facades: dict[str, FacadeInfo]
) -> list[FixClassification]:
    """Classify each cross-package (owning_package, symbol) pair by fix strategy.

    A symbol already present in the owning package's ``__all__`` is a simple
    consumer-side rewrite; an absent one is a precondition facade promotion that
    must land before consumers can switch.
    """
    pair_consumers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for v in priv_violations:
        if v.is_test:
            continue  # precondition sizing is driven by production consumers
        for name in v.imported_names:
            if name == "*":
                continue
            pair_consumers[(v.owning_package, name)].add(v.importer_mod)

    results: list[FixClassification] = []
    for (owner, symbol), consumers in pair_consumers.items():
        facade_info = facades.get(owner)
        already = bool(facade_info and facade_info.has_real_all and symbol in facade_info.all_names)
        results.append(
            FixClassification(
                owning_package=owner,
                symbol=symbol,
                already_in_facade=already,
                consumer_count=len(consumers),
                consumer_modules=sorted(consumers),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Scan ``src/cadrumo`` and print the import-hygiene inventory report."""
    # Prose violations carry arbitrary source text (Spanish prose, en-dashes);
    # a cp1252 console would crash printing them.
    # `sys.stdout` is typed `TextIO`, which declares no `reconfigure`; the
    # runtime object is a `TextIOWrapper`, which does. `errors="replace"` is
    # stronger than the package-wide default and is why this stays here.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Write full inventory as JSON to this path")
    parser.add_argument("--top", type=int, default=20, help="Top-N offender modules to print")
    args = parser.parse_args()

    py_files = list(scan_directory(PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))

    # The dev-boundary families sweep every module under src/, the harness
    # distribution included, while the import-hygiene census proper stays
    # scoped to the cadrumo package whose module names it resolves.
    harness_root = SRC_ROOT / "cadrumo_harness"
    dev_boundary_files = list(py_files)
    if harness_root.is_dir():
        dev_boundary_files += scan_directory(
            harness_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)
        )

    facades = discover_facades()
    real_facades = {pkg: info for pkg, info in facades.items() if info.has_real_all}

    all_sites: list[ImportSite] = []
    for path in py_files:
        all_sites.extend(walk_module_imports(path))

    priv_violations = find_private_import_violations(all_sites)
    fix_classes = classify_fix_strategy(priv_violations, facades)
    underscore_in_all = find_underscore_in_all_violations(facades)
    dev_tooling_imports = find_dev_tooling_import_violations(dev_boundary_files)
    dev_path_reaches = find_dev_path_reach_violations(dev_boundary_files)
    dev_prose_violations = find_dev_prose_violations(dev_boundary_files)
    registry_loader_imports = find_registry_loader_import_violations(all_sites)
    dangling_imports = find_dangling_first_party_imports(all_sites)
    orphaned_modules = find_orphaned_modules(
        py_files,
        first_party_census_files(),
        (),
    )
    # ---- Reporting ----
    print(f"Scanned {len(py_files)} .py files under {PKG_ROOT}")
    print(f"Dev-boundary sweep covers {len(dev_boundary_files)} files (cadrumo + harness distribution)")
    print(f"Discovered {len(facades)} __init__.py files; {len(real_facades)} carry a real, non-empty __all__.")
    print()
    print("=== FACADE BOUNDARY SET (packages with real __all__) ===")
    for pkg in sorted(real_facades):
        print(f"  {pkg}  ({len(real_facades[pkg].all_names)} exported names)")
    print()

    print(f"=== FAMILY 1: cross-package private imports: {len(priv_violations)} total ===")
    non_test = [v for v in priv_violations if not v.is_test]
    test_only = [v for v in priv_violations if v.is_test]
    print(f"  non-test: {len(non_test)}   test-only: {len(test_only)}")
    by_owner = Counter(v.owning_package for v in priv_violations)
    print("  by owning package (target):")
    for owner, cnt in by_owner.most_common(30):
        print(f"    {cnt:4d}  {owner}")
    print()
    by_target_mod = Counter(v.target_mod for v in priv_violations)
    print(f"  top {args.top} offender private target modules:")
    for mod, cnt in by_target_mod.most_common(args.top):
        print(f"    {cnt:4d}  {mod}")
    print()
    by_importer_area = Counter(".".join(v.importer_mod.split(".")[:3]) for v in priv_violations)
    print("  by importer area (top-3 dotted segments):")
    for area, cnt in by_importer_area.most_common(30):
        print(f"    {cnt:4d}  {area}")
    print()

    print(f"=== FAMILY 4: underscore-named entries in __all__: {len(underscore_in_all)} total ===")
    print("  (a public facade exporting a private-named symbol; every hit needs a per-symbol disposition:")
    print("   rename to a public name and sweep consumers, or drop it from __all__)")
    by_underscore_owner = Counter(v.package for v in underscore_in_all)
    for owner, cnt in by_underscore_owner.most_common():
        print(f"    {cnt:4d}  {owner}")
    print()
    for v in sorted(underscore_in_all, key=lambda x: (x.package, x.name)):
        print(f"  [{v.package}] {v.name}  ({v.path})")
    print()

    print(f"=== FAMILY 5: src modules importing the dev tooling: {len(dev_tooling_imports)} total ===")
    print("  (absolute boundary: no module under src/ -- shipped or test -- may import dev/")
    print("   a test needing dev tooling lives under dev/ itself)")
    for v in dev_tooling_imports:
        kind = "dynamic" if v.is_dynamic else "static"
        print(f"  [{kind}] {v.importer_path}:{v.lineno} -> {v.target_mod}")
    print()

    print(f"=== FAMILY 6: src modules building a path into the dev tree: {len(dev_path_reaches)} total ===")
    print("  (the metadata half of the same boundary: no import statement, but the module still")
    print("   names a path into dev/; move the artifact under src/cadrumo/_data/ or the test to dev/)")
    for reach in dev_path_reaches:
        print(f"  [{reach.form}] {reach.module_path}:{reach.lineno} -> {reach.detail!r}")
    print()

    print(f"=== FAMILY 10: prose naming the dev tree under src/: {len(dev_prose_violations)} total ===")
    print("  (comments, docstrings and multi-line strings: awareness is forbidden even where")
    print("   no code path reads the tree; reword to neutral prose)")
    for v in dev_prose_violations:
        print(f"  [{v.source_kind}] {v.module_path}:{v.lineno} -> {v.detail!r}")
    print()

    print(f"=== FAMILY 7: production imports of a demoted raw-loader symbol: {len(registry_loader_imports)} total ===")
    print(f"  (demoted set: {sorted(DEMOTED_REGISTRY_LOADER_SYMBOLS)})")
    for v in registry_loader_imports:
        print(f"  {v.importer_path}:{v.lineno} imports {v.imported_names} from {REGISTRY_LOADER_PACKAGE}")
    print()

    print(f"=== FAMILY 8: dangling first-party import targets: {len(dangling_imports)} total ===")
    print("  (a deletion that landed without its consumer sweep, seen from the consumer end;")
    print("   the whole-tree type checker computes the same fact but carries too much unrelated")
    print("   noise at rest for one new edge to be visible in it)")
    for d in dangling_imports:
        symbol = f" :: {d.symbol}" if d.symbol else ""
        print(f"  [{d.kind}][{'test' if d.is_test else 'prod'}] {d.importer_path}:{d.lineno} -> {d.target_mod}{symbol}")
    print()

    print(f"=== FAMILY 9: orphaned modules (nothing in the first-party tree reaches them): {len(orphaned_modules)} ===")
    print("  (the same deletion seen from the other end: the module left behind when its last")
    print("   consumer went. Reach counts static imports, dynamic importlib targets and any")
    print("   string constant naming the module, across src/, the harness distribution and dev/)")
    orphan_bridges = [o for o in orphaned_modules if o.is_reexport_surface]
    print(f"  of which pure re-export bridges: {len(orphan_bridges)}")
    for o in orphaned_modules:
        kind = "reexport-bridge" if o.is_reexport_surface else "defines-its-own"
        print(f"  [{kind}][{'test' if o.is_test else 'prod'}] {o.path}")
    print()

    print(f"=== FIX STRATEGY: precondition promotions vs. simple consumer rewrites ({len(fix_classes)} pairs) ===")
    needs_promotion = [f for f in fix_classes if not f.already_in_facade]
    simple_rewrite = [f for f in fix_classes if f.already_in_facade]
    print(f"  distinct (owning_package, symbol) pairs consumed cross-package (production only): {len(fix_classes)}")
    print(f"  NEEDS FACADE PROMOTION FIRST (symbol absent from owning __all__): {len(needs_promotion)} pairs")
    print(f"  SIMPLE CONSUMER REWRITE (symbol already in owning __all__):       {len(simple_rewrite)} pairs")
    total_consumer_sites_promo = sum(f.consumer_count for f in needs_promotion)
    total_consumer_sites_rewrite = sum(f.consumer_count for f in simple_rewrite)
    print(f"  production import sites behind promotion-needed pairs: {total_consumer_sites_promo}")
    print(f"  production import sites behind already-facaded pairs:  {total_consumer_sites_rewrite}")
    print()
    print("  --- batches: symbols needing PROMOTION, grouped by owning package ---")
    promo_by_owner: dict[str, list[FixClassification]] = defaultdict(list)
    for f in needs_promotion:
        promo_by_owner[f.owning_package].append(f)
    for owner in sorted(promo_by_owner, key=lambda o: -len(promo_by_owner[o])):
        items = promo_by_owner[owner]
        symbols = sorted({f.symbol for f in items})
        n_sites = sum(f.consumer_count for f in items)
        print(f"    {owner}  :: {len(symbols)} symbol(s) to promote, {n_sites} consumer site(s)")
        print(f"      symbols: {symbols}")
    print()
    print("  --- batches: symbols ALREADY facaded, grouped by owning package (pure consumer rewrite) ---")
    rewrite_by_owner: dict[str, list[FixClassification]] = defaultdict(list)
    for f in simple_rewrite:
        rewrite_by_owner[f.owning_package].append(f)
    for owner in sorted(rewrite_by_owner, key=lambda o: -len(rewrite_by_owner[o])):
        items = rewrite_by_owner[owner]
        symbols = sorted({f.symbol for f in items})
        n_sites = sum(f.consumer_count for f in items)
        print(f"    {owner}  :: {len(symbols)} symbol(s), {n_sites} consumer site(s)")
    print()

    distinct_files_to_edit = {v.importer_path for v in priv_violations if not v.is_test}
    distinct_symbols_all = {f.symbol for f in fix_classes}
    print("=== MAGNITUDE ===")
    print(f"  distinct production files with >=1 cross-package private import: {len(distinct_files_to_edit)}")
    print(f"  distinct (owner, symbol) pairs touched: {len(fix_classes)}")
    print(f"  distinct symbol names touched: {len(distinct_symbols_all)}")
    print(f"  distinct symbols needing facade promotion: {len({f.symbol for f in needs_promotion})}")
    print(f"  distinct owning packages needing >=1 promotion: {len(promo_by_owner)}")
    print(f"  underscore-named __all__ entries (Family 4): {len(underscore_in_all)}")
    print(f"  src modules importing dev/ tooling (Family 5): {len(dev_tooling_imports)}")
    print(f"  src modules reaching a dev/ path (Family 6): {len(dev_path_reaches)}")
    print(f"  src prose naming the dev tree (Family 10): {len(dev_prose_violations)}")
    print(f"  production imports of a demoted registry raw-loader symbol (Family 7): {len(registry_loader_imports)}")
    print(f"  dangling first-party import targets (Family 8): {len(dangling_imports)}")
    print(f"  orphaned modules (Family 9): {len(orphaned_modules)}")
    print()

    if args.json:
        payload = {
            "facades": {
                pkg: {"path": str(info.path.relative_to(REPO_ROOT)).replace("\\", "/"), "all_names": info.all_names}
                for pkg, info in real_facades.items()
            },
            "private_import_violations": [
                {
                    "importer_mod": v.importer_mod,
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "target_mod": v.target_mod,
                    "owning_package": v.owning_package,
                    "imported_names": v.imported_names,
                    "is_test": v.is_test,
                    "in_type_checking": v.in_type_checking,
                }
                for v in priv_violations
            ],
            "fix_classification": [
                {
                    "owning_package": f.owning_package,
                    "symbol": f.symbol,
                    "already_in_facade": f.already_in_facade,
                    "consumer_count": f.consumer_count,
                    "consumer_modules": f.consumer_modules,
                }
                for f in fix_classes
            ],
            "dev_tooling_import_violations": [
                {
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "target_mod": v.target_mod,
                    "is_dynamic": v.is_dynamic,
                }
                for v in dev_tooling_imports
            ],
            "dev_path_reach_violations": [
                {
                    "module_path": reach.module_path,
                    "lineno": reach.lineno,
                    "form": str(reach.form),
                    "detail": reach.detail,
                }
                for reach in dev_path_reaches
            ],
            "dev_prose_violations": [
                {
                    "module_path": v.module_path,
                    "lineno": v.lineno,
                    "source_kind": v.source_kind,
                    "detail": v.detail,
                }
                for v in dev_prose_violations
            ],
            "underscore_in_all_violations": [
                {"package": v.package, "path": v.path, "name": v.name} for v in underscore_in_all
            ],
            "registry_loader_import_violations": [
                {
                    "importer_mod": v.importer_mod,
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "imported_names": v.imported_names,
                }
                for v in registry_loader_imports
            ],
            "dangling_first_party_imports": [
                {
                    "importer_mod": d.importer_mod,
                    "importer_path": d.importer_path,
                    "lineno": d.lineno,
                    "target_mod": d.target_mod,
                    "symbol": d.symbol,
                    "kind": str(d.kind),
                    "is_test": d.is_test,
                }
                for d in dangling_imports
            ],
            "orphaned_modules": [
                {
                    "mod": o.mod,
                    "path": o.path,
                    "is_reexport_surface": o.is_reexport_surface,
                    "is_test": o.is_test,
                }
                for o in orphaned_modules
            ],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding=_UTF_8, newline="\n")
        print(f"Wrote full JSON inventory to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
