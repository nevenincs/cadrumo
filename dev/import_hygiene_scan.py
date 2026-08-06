"""Import-hygiene scanner for top-level-export centralisation.

Discovery-phase tool: builds an inventory of cross-package private imports,
shim/re-export modules, and redundantly re-exported symbols across
``src/cadrumo``. READ-ONLY: it does not modify production code.

It is also the SINGLE AUTHORITY for the one-way ``src/cadrumo`` -> ``dev/``
boundary, in both the shapes that boundary breaks in: Family 5 detects a
shipped module IMPORTING ``dev.*``, and Family 6 detects a shipped module
building a PATH into the ``dev/`` tree at runtime. The two are one rule with
two syntaxes -- ``dev/`` ships in neither the wheel nor the sdist, so a shipped
module reaching it by either route is broken for every installed user -- and
they live together here so a fix to one cannot silently leave the other behind.
Consumers assert against these functions rather than re-implementing them; the
boundary gate under ``src/cadrumo/tests`` is one such consumer, and its
importing ``dev.*`` is not itself a violation, because a test module is
wheel-excluded and a scanner's own imports have no bearing on the shipped
surface it measures.

Re-run with:

    python dev/import_hygiene_scan.py [--json OUT.json] [--top N]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PKG_ROOT = SRC_ROOT / "cadrumo"
_UTF_8: Final[str] = "utf-8"


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
    is_pure_reexport_shape: bool = False


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
    for init_path in PKG_ROOT.rglob("__init__.py"):
        mod = module_name_for(init_path)
        try:
            src = init_path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(init_path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        all_names: list[str] = []
        has_real_all = False
        for node in ast.walk(tree):
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

    # Track TYPE_CHECKING guard membership via a simple ancestor stack walk.
    type_checking_nodes: set[int] = set()

    def mark_type_checking(node: ast.If) -> None:
        test_expr = node.test
        is_tc = (isinstance(test_expr, ast.Name) and test_expr.id == "TYPE_CHECKING") or (
            isinstance(test_expr, ast.Attribute) and test_expr.attr == "TYPE_CHECKING"
        )
        if is_tc:
            for child in ast.walk(node):
                type_checking_nodes.add(id(child))

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            mark_type_checking(node)

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


def find_private_import_violations(all_sites: list[ImportSite]) -> list[PrivateImportViolation]:
    """Return every import site that reaches into a foreign package's privates."""
    violations: list[PrivateImportViolation] = []
    for site in all_sites:
        if not site.target_mod.startswith("cadrumo"):
            continue
        if not has_private_component(site.target_mod):
            continue
        owner = owning_package(site.target_mod)
        importer = site.importer_mod
        # Legitimate: importer is under the owning package (sibling/descendant),
        # OR importer *is* the owning package's own __init__ building its facade.
        if importer == owner or importer.startswith(owner + "."):
            continue
        violations.append(
            PrivateImportViolation(
                importer_mod=importer,
                importer_path=str(site.importer_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                lineno=site.lineno,
                target_mod=site.target_mod,
                owning_package=owner,
                imported_names=site.imported_names,
                is_test=site.is_test,
                in_type_checking=site.in_type_checking,
            )
        )
    return violations


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
    """A non-test module under ``src/`` that imports the unshipped ``dev/`` tooling."""

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
    exclude_globs: tuple[str, ...] | None = None,
) -> list[DevToolingImportViolation]:
    """Return every SHIPPED module under ``src_root`` that imports ``dev.``.

    The ``dev/`` tree is development tooling and ships in neither the wheel nor
    the sdist. A shipped module importing it therefore raises
    ``ModuleNotFoundError`` for every installed user, while resolving fine in a
    source checkout -- a defect no test run in the repository can surface.

    Scoped deliberately to SHIPPED modules, the boundary being read from the
    packaging config rather than restated. An excluded test tree's ``dev.``
    import cannot reach an installed user: it encodes "this suite requires the
    repo checkout and the dev dependency group", which is already true and
    intended. Widening this family to unshipped tests would be an ownership
    preference, not a correctness gate, and would convert a hard zero into a
    migration backlog. That is a decision, not an oversight; revisit it by
    ruling, never by drift.

    Args:
        py_files: Module files to scan.
        src_root: Source root importer names are resolved against.
        exclude_globs: Wheel exclude globs; read from the packaging config when
            omitted.
    """
    globs = wheel_exclude_globs() if exclude_globs is None else exclude_globs
    violations: list[DevToolingImportViolation] = []
    for path in py_files:
        mod = module_name_for(path, src_root=src_root)
        if not is_shipped_module(path, src_root=src_root, exclude_globs=globs):
            continue
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
    exclude_globs: tuple[str, ...] | None = None,
) -> list[DevPathReachViolation]:
    r"""Return every SHIPPED module under ``src_root`` that builds a ``dev/`` path.

    This is the metadata loophole an import scan alone cannot see: a module
    reading a dev artifact at runtime does not import ``dev.*`` but is just as
    broken for every installed user, because ``dev/`` ships in neither the
    wheel nor the sdist. Family 5 catches the code dependency; this family
    catches the data dependency.

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
    while depending on a dev artifact at runtime. A shipped module has no
    legitimate reason to name the dev tree at all.

    Scoped to SHIPPED modules on the same reasoning as Family 5, and the
    boundary is read from the packaging config rather than restated.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve shipped status and relative paths.
        exclude_globs: Wheel exclude globs; read from the packaging config when
            omitted.
    """
    globs = wheel_exclude_globs() if exclude_globs is None else exclude_globs
    violations: list[DevPathReachViolation] = []
    for path in py_files:
        if not is_shipped_module(path, src_root=src_root, exclude_globs=globs):
            continue
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        violations.extend(
            DevPathReachViolation(rel, lineno, form, detail) for lineno, form, detail in dev_path_hits(tree)
        )
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.form, v.detail))


# ---------------------------------------------------------------------------
# Violation family 2: shim / pure re-export / alias modules
# ---------------------------------------------------------------------------


@dataclass
class ShimModule:
    """A module flagged as a shim / pure re-export / English-alias surface."""

    mod: str
    path: str
    reason: str
    detail: str


SPANISH_ALIAS_HINTS = {
    "vat": "iva",
    "census": "censo",
    "form": "modelo",
    "receipt": "justificante",
    "box": "casilla",
    "invoice_draft": "borrador",
    "authorization": "apoderamiento",
    "withholding": "retencion",
    "filing": "declaracion",
}


def module_body_defs(tree: ast.Module) -> tuple[int, int, int]:
    """Return (n_imports_stmts, n_real_defs, n_all_assigns).

    ``__future__`` imports are excluded from the import count (every module
    may carry one; it is not "re-export" signal). Annotated assignments
    (``NAME: Type = value``, e.g. a module-level typed constant/data record)
    count as real defs, same as a plain ``Assign``, a function, or a class --
    UNLESS the value is a bare ``Name`` reference (``Foo = _internal.Foo`` /
    ``Foo = Foo``), which is itself a re-export alias, not a real definition.
    """
    n_imports = 0
    n_defs = 0
    n_all = 0
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            n_imports += 1
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            n_all += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            n_defs += 1
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue  # docstring
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, (ast.Name, ast.Attribute)):
                # Bare re-export alias (Foo = Bar / Foo = mod.Bar); not a
                # real definition.
                continue
            n_defs += 1
    return n_imports, n_defs, n_all


def find_shim_modules(py_files: list[Path], facades: dict[str, FacadeInfo]) -> list[ShimModule]:
    """Return modules whose shape or naming marks them as shim / alias surfaces."""
    shims: list[ShimModule] = []
    for path in py_files:
        if path.name == "__init__.py":
            continue  # __init__ facades are expected to be import+__all__
        if path.name == "__main__.py":
            # Entry-point module: `from .cli import app` + `if __name__ ==
            # "__main__": app()` is the standard `python -m pkg` pattern, not
            # a Family-2 shim/pure-reexport surface.
            continue
        try:
            src = path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        mod = module_name_for(path)
        if is_test_module(mod, path):
            continue

        n_imports, n_defs, n_all = module_body_defs(tree)

        # Pure re-export shape: only imports (+ optional __all__), zero
        # real function/class definitions, and at least one import.
        if n_imports > 0 and n_defs == 0:
            shims.append(
                ShimModule(
                    mod=mod,
                    path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    reason="pure_reexport_shape",
                    detail=f"{n_imports} import stmt(s), 0 real defs, __all__={'yes' if n_all else 'no'}",
                )
            )

        # English-alias-over-Spanish-stem heuristic: module basename contains
        # an English hint token and the sibling directory also contains a
        # same-shaped Spanish-stem module.
        base = path.stem.lstrip("_")
        for en_hint, es_stem in SPANISH_ALIAS_HINTS.items():
            if en_hint in base.lower() and es_stem not in base.lower():
                sibling_es = path.with_name(path.name.replace(en_hint, es_stem))
                if sibling_es.exists() and sibling_es != path:
                    shims.append(
                        ShimModule(
                            mod=mod,
                            path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                            reason="english_alias_over_spanish_stem",
                            detail=f"hint='{en_hint}' sibling='{sibling_es.relative_to(REPO_ROOT)}'",
                        )
                    )

        # Compat/deprecation naming heuristic.
        lowered = mod.lower()
        for marker in ("_compat", "_legacy", "_deprecated", "_shim", "_bridge"):
            if marker in lowered:
                shims.append(
                    ShimModule(
                        mod=mod,
                        path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        reason="compat_naming_marker",
                        detail=f"marker='{marker}'",
                    )
                )
    return shims


# ---------------------------------------------------------------------------
# Violation family 3: redundant re-exports (symbol in >1 __all__, or
# imported from both a private submodule and a facade across the codebase)
# ---------------------------------------------------------------------------


@dataclass
class MultiSourcedSymbol:
    """A symbol exported / consumed from more than one module surface."""

    symbol: str
    facades: list[str]
    private_sources: list[str]
    consumed_from_facade_by: list[str]
    consumed_from_private_by: list[str]
    confidence: str = "high"  # "high" (same resolved origin) | "name_collision" (different origins; likely unrelated)


def _facade_export_origins(facades: dict[str, FacadeInfo]) -> dict[str, dict[str, set[str]]]:
    """Resolve each facade's ``__all__`` name to its absolute origin module(s).

    Best-effort: only direct ``from X import Name [as Alias]`` statements in the
    ``__init__`` body are resolved; a name built by other means is simply absent
    from this map.
    """
    origins: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        try:
            src = info.path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(info.path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = resolve_relative_import(pkg, True, node.level, node.module)
                if not target:
                    continue
                for alias in node.names:
                    exported_as = alias.asname or alias.name
                    if exported_as in info.all_names:
                        origins[pkg][exported_as].add(target)
    return origins


def find_multi_sourced_symbols(facades: dict[str, FacadeInfo], all_sites: list[ImportSite]) -> list[MultiSourcedSymbol]:
    """Return symbols reachable from more than one facade / private surface."""
    # Map symbol -> set of facades whose __all__ contains it.
    symbol_to_facades: dict[str, set[str]] = defaultdict(set)
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        for name in info.all_names:
            symbol_to_facades[name].add(pkg)

    facade_export_origins = _facade_export_origins(facades)

    # Map symbol -> set of private modules it's imported FROM (target private
    # module -> imported name), restricted to cadrumo.* targets.
    symbol_private_sources: dict[str, set[str]] = defaultdict(set)
    symbol_facade_consumers: dict[str, set[str]] = defaultdict(set)
    symbol_private_consumers: dict[str, set[str]] = defaultdict(set)

    facade_targets = {pkg for pkg, info in facades.items() if info.has_real_all}

    for site in all_sites:
        if not site.target_mod.startswith("cadrumo"):
            continue
        for name in site.imported_names:
            if name == "*":
                continue
            if has_private_component(site.target_mod):
                symbol_private_sources[name].add(site.target_mod)
                symbol_private_consumers[name].add(site.importer_mod)
            elif site.target_mod in facade_targets:
                symbol_facade_consumers[name].add(site.importer_mod)

    results: list[MultiSourcedSymbol] = []

    def _is_ancestor_or_descendant(a: str, b: str) -> bool:
        return a == b or a.startswith(b + ".") or b.startswith(a + ".")

    # Case A: symbol declared __all__ in more than one facade package. Split
    # by confidence: "hierarchical_rollup" when every pair of declaring
    # facades is in a parent/child (umbrella aggregator) relationship -- this
    # codebase's umbrella packages (e.g. `cadrumo.adapters.persistence.storage`
    # over its `.envelope` / `.bucket` / `.crypto` sub-facades,
    # `cadrumo.core.errors` over `.registry`) deliberately roll up child-facade
    # symbols into a parent convenience facade, which is NOT the violation
    # this family targets; "high" when at least two declaring facades are
    # NOT in an ancestor/descendant relationship AND resolve the name to the
    # SAME underlying origin module (genuine structural duplication across
    # orthogonal packages); "name_collision" when every non-hierarchical pair
    # resolves to different origins (near-certainly two unrelated symbols
    # sharing a name, e.g. two domains each defining their own `Settings`).
    for symbol, pkgs in symbol_to_facades.items():
        if len(pkgs) <= 1:
            continue
        pkg_list = sorted(pkgs)
        all_hierarchical = all(
            _is_ancestor_or_descendant(pkg_list[i], pkg_list[j])
            for i in range(len(pkg_list))
            for j in range(i + 1, len(pkg_list))
        )
        origin_sets = [facade_export_origins.get(pkg, {}).get(symbol, set()) for pkg in pkgs]
        origin_counts: Counter[str] = Counter()
        for s in origin_sets:
            for o in s:
                origin_counts[o] += 1
        shared_origin = any(c > 1 for c in origin_counts.values())
        if all_hierarchical:
            confidence = "hierarchical_rollup"
        elif shared_origin:
            confidence = "high"
        else:
            confidence = "name_collision"
        results.append(
            MultiSourcedSymbol(
                symbol=symbol,
                facades=pkg_list,
                private_sources=sorted(symbol_private_sources.get(symbol, [])),
                consumed_from_facade_by=sorted(symbol_facade_consumers.get(symbol, [])),
                consumed_from_private_by=sorted(symbol_private_consumers.get(symbol, [])),
                confidence=confidence,
            )
        )

    # Case B: symbol importable from a facade AND actually imported from a
    # private submodule by real consumers elsewhere (not the owning facade
    # building itself) AND also imported from the facade by some consumer.
    for symbol, priv_mods in symbol_private_sources.items():
        facade_consumers = symbol_facade_consumers.get(symbol, set())
        priv_consumers = symbol_private_consumers.get(symbol, set())
        # Only interesting if the symbol also appears in >=1 facade __all__
        # and is genuinely consumed (not just declared) from both shapes.
        if symbol in symbol_to_facades and facade_consumers and priv_consumers:
            # Exclude consumers that are simply the owning package building
            # its own facade (those are legitimate, not redundant); a
            # private-module consumer that lives INSIDE the owner is fine,
            # only flag if some consumer is outside the owning package.
            owners = {owning_package(p) for p in priv_mods}
            outside_priv_consumers = set()
            for c in priv_consumers:
                if not any(c == own or c.startswith(own + ".") for own in owners):
                    outside_priv_consumers.add(c)
            if outside_priv_consumers and facade_consumers:
                existing = next((r for r in results if r.symbol == symbol), None)
                if existing is None:
                    results.append(
                        MultiSourcedSymbol(
                            symbol=symbol,
                            facades=sorted(symbol_to_facades[symbol]),
                            private_sources=sorted(priv_mods),
                            consumed_from_facade_by=sorted(facade_consumers),
                            consumed_from_private_by=sorted(outside_priv_consumers),
                            confidence="high",
                        )
                    )
    return results


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Write full inventory as JSON to this path")
    parser.add_argument("--top", type=int, default=20, help="Top-N offender modules to print")
    args = parser.parse_args()

    py_files = sorted(PKG_ROOT.rglob("*.py"))
    py_files = [p for p in py_files if "__pycache__" not in p.parts]

    facades = discover_facades()
    real_facades = {pkg: info for pkg, info in facades.items() if info.has_real_all}

    all_sites: list[ImportSite] = []
    for path in py_files:
        all_sites.extend(walk_module_imports(path))

    priv_violations = find_private_import_violations(all_sites)
    shims = find_shim_modules(py_files, facades)
    multi_sourced = find_multi_sourced_symbols(facades, all_sites)
    fix_classes = classify_fix_strategy(priv_violations, facades)
    underscore_in_all = find_underscore_in_all_violations(facades)
    dev_tooling_imports = find_dev_tooling_import_violations(py_files)
    dev_path_reaches = find_dev_path_reach_violations(py_files)

    # ---- Reporting ----
    print(f"Scanned {len(py_files)} .py files under {PKG_ROOT}")
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

    print(f"=== FAMILY 2: shim/alias/pure-reexport modules: {len(shims)} total ===")
    by_reason = Counter(s.reason for s in shims)
    for reason, cnt in by_reason.most_common():
        print(f"  {cnt:4d}  {reason}")
    print()
    for s in shims:
        print(f"  [{s.reason}] {s.path} :: {s.detail}")
    print()

    by_confidence = Counter(m.confidence for m in multi_sourced)
    print(f"=== FAMILY 3: redundant / multi-sourced symbols: {len(multi_sourced)} total ===")
    print(f"  by confidence: {dict(by_confidence)}")
    print("  (name_collision = same name, different resolved origin -- likely unrelated symbols, LOW priority)")
    print("  (hierarchical_rollup = umbrella parent facade re-exporting a child facade's symbol -- NOT a violation)")
    print()
    _order = {"high": 0, "name_collision": 1, "hierarchical_rollup": 2}
    for m in sorted(multi_sourced, key=lambda x: (_order.get(x.confidence, 9), x.symbol)):
        print(f"  [{m.confidence}] {m.symbol}")
        print(f"    facades: {m.facades}")
        print(f"    private_sources: {m.private_sources}")
        print(f"    consumed_from_facade_by: {len(m.consumed_from_facade_by)} sites")
        print(
            f"    consumed_from_private_by: {len(m.consumed_from_private_by)} sites -> {m.consumed_from_private_by[:5]}"
        )
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

    print(f"=== FAMILY 5: shipped modules importing the unshipped dev tooling: {len(dev_tooling_imports)} total ===")
    print("  (dev/ ships in neither the wheel nor the sdist, so each hit is a ModuleNotFoundError")
    print("   for every installed user; move what the shipped side needs under src/cadrumo)")
    for v in dev_tooling_imports:
        kind = "dynamic" if v.is_dynamic else "static"
        print(f"  [{kind}] {v.importer_path}:{v.lineno} -> {v.target_mod}")
    print()

    print(f"=== FAMILY 6: shipped modules building a path into the dev tree: {len(dev_path_reaches)} total ===")
    print("  (the metadata half of the same boundary: no import statement, but the module still")
    print("   depends on an artifact absent from the wheel; move it under src/cadrumo/_data/)")
    for reach in dev_path_reaches:
        print(f"  [{reach.form}] {reach.module_path}:{reach.lineno} -> {reach.detail!r}")
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
    print(f"  shipped modules importing dev/ tooling (Family 5): {len(dev_tooling_imports)}")
    print(f"  shipped modules reaching a dev/ path (Family 6): {len(dev_path_reaches)}")
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
            "shim_modules": [{"mod": s.mod, "path": s.path, "reason": s.reason, "detail": s.detail} for s in shims],
            "multi_sourced_symbols": [
                {
                    "symbol": m.symbol,
                    "facades": m.facades,
                    "private_sources": m.private_sources,
                    "consumed_from_facade_by": m.consumed_from_facade_by,
                    "consumed_from_private_by": m.consumed_from_private_by,
                    "confidence": m.confidence,
                }
                for m in multi_sourced
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
            "underscore_in_all_violations": [
                {"package": v.package, "path": v.path, "name": v.name} for v in underscore_in_all
            ],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding=_UTF_8, newline="\n")
        print(f"Wrote full JSON inventory to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
