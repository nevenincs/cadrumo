#!/usr/bin/env python
"""Audit shipped code that no shipped entrypoint can ever reach.

The question this module answers is narrower and stricter than the vulture
scan in :mod:`dev.audit.dead_code`: "starting from the console scripts the
wheel installs, which shipped modules are never imported, and which symbols
inside the reachable modules are never referenced by shipped code?"

The usage universe is deliberately the shipped tree alone. A reference from a
test module, from ``dev/`` tooling, or from the repository-root ``conftest.py``
is not use: those trees are not installed, and a module that only they touch
is dead weight in the distribution. Such references are still harvested, but
only to LABEL a finding (``used by: tests``) so the reader can tell "kept alive
by its own tests" from "orphaned outright". Neither label clears the finding.

Two reachability layers are computed:

* **Module reachability** walks the import graph from every ``[project.scripts]``
  entry point and from every shipped ``__main__.py``, since ``python -m pkg.thing``
  is an execution surface an installed user has whether or not the packaging
  names it. The walk spans the whole uv workspace: a sibling distribution that
  depends on this package (the harness that ships the MCP server) reaches into
  it from its own console script, and a module only that sibling imports is
  live product code, not dead weight. Static ``import``/``from`` statements are edges; so is any
  string literal that names a shipped module, because the CLI binds its
  command handlers through ``DeferredTarget("cadrumo....", "handler")`` and the
  registry installs cross-domain checks by dotted name. Imports guarded by
  ``if TYPE_CHECKING:`` do not execute at runtime, so a module reachable only
  through them is reported separately as ``type-only``.
* **Orphaned tests** are the giveaway layer: a test module under the package
  whose every shipped subject (the modules and symbols it imports from the
  shipped tree) is itself a finding exists only to exercise dead code, and is
  reported so the code and its tests can be retired together.
* **Symbol reachability** then looks inside the runtime-reachable modules,
  and it resolves two different questions with two different strengths.

  A TOP-LEVEL function, class, or constant is answered exactly. Its only ways
  in are an import of the defining module (``from M import N``, or ``M.N``
  through an import alias), a use inside its own module, or a string naming
  it; the tree has no star imports, so that list is closed. A bare identifier
  load somewhere unrelated does NOT clear it, which is the difference between
  this layer and a name-frequency heuristic.

  A MEMBER -- a method, class attribute, or enum member -- has no defining-site
  import to resolve, so it stays a bare-identifier question: never accessed as
  an attribute, never passed as a keyword argument, never spelled as a string.
  Data-shaped members are checked against the shipped non-Python data as well,
  because registry TOML and locale catalogues address fields and enum values
  by name. Every finding carries the tier it was derived at, so a reader knows
  which ones are safe to act on unread.

The scan is static and read-only. It never imports the production package.

See Also:
    :mod:`dev.audit.dead_code`
        The heuristic vulture runner; it does not model entrypoint reach.
    :func:`run_unreachable_code_scan`
        The one entry point ``just audit-unreachable-code`` calls.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from collections import deque
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from ..quality.import_hygiene_scan import (
    is_shipped_module,
    module_name_for,
    resolve_relative_import,
    type_checking_guarded_nodes,
    wheel_exclude_globs,
)
from ..quality.unread_inputs import report_unread

_UTF_8: Final[str] = UTF_8
_FINDING_CAP: Final[int] = 40
_EXIT_FINDINGS: Final[int] = 3
_EXIT_ERROR: Final[int] = 1

_DOTTED_SPEC: Final = re.compile(r"^\.*[A-Za-z_][\w.]*(:[A-Za-z_]\w*)?$")
_SKIPPED_DIRS: Final[frozenset[str]] = frozenset({"__pycache__"})

# Decorators that merely shape a definition. Any OTHER decorator is read as a
# framework registration (typer command, pydantic validator, textual handler)
# that reaches the symbol without ever spelling its name.
_PLAIN_DECORATORS: Final[frozenset[str]] = frozenset(
    {
        "abstractmethod",
        "cached_property",
        "classmethod",
        "final",
        "overload",
        "override",
        "property",
        "staticmethod",
    }
)
# Method names a framework calls by convention rather than by reference.
_HOOK_METHOD_NAMES: Final[frozenset[str]] = frozenset(
    {"compose", "render", "model_post_init", "check_action", "on_mount", "on_unmount"},
)
_HOOK_METHOD_PREFIXES: Final[tuple[str, ...]] = (
    "on_",
    "_on_",
    "action_",
    "watch_",
    "compute_",
    "validate_",
    "key_",
    "visit_",
)
_ENUM_BASE_SUFFIXES: Final[tuple[str, ...]] = ("Enum", "Flag")


class UnreachableCodeOutcome(StrEnum):
    """The three honest states the scan can land in."""

    CLEAN = "clean"
    FINDINGS = "findings"
    ERROR = "error"


class ModuleReach(StrEnum):
    """How far the entrypoint walk got to a reported module.

    ``UNREACHABLE`` means no root reaches it at all. ``MODULE_EXEC_ONLY`` means
    only a ``python -m`` surface does, never a console script -- an installed
    user can run it, but no product command leads there, so it is a weaker
    kind of alive worth seeing separately. ``TYPE_ONLY`` means only an
    ``if TYPE_CHECKING:`` import names it, which does not execute.
    """

    UNREACHABLE = "unreachable"
    MODULE_EXEC_ONLY = "module-exec-only"
    TYPE_ONLY = "type-only"


class SymbolKind(StrEnum):
    """The definition families the symbol layer inspects."""

    FUNCTION = "function"
    CLASS = "class"
    CONSTANT = "constant"
    METHOD = "method"
    ATTRIBUTE = "attribute"
    ENUM_MEMBER = "enum-member"


class Confidence(StrEnum):
    """How much a finding can be trusted before a human or agent looks.

    ``EXACT`` findings are resolved through the import graph: an unreachable
    module, or a top-level symbol whose every way in was checked and found
    absent. Act on these first. ``NAME_MATCH`` findings are methods, reached
    by attribute access the scan cannot bind to a type, so a same-named live
    method elsewhere hides a real use. ``NAME_MATCH_DATA`` findings are class
    attributes and enum members, which additionally may be reached through
    serialisation, ORM mapping, or registry data; the shipped data corpus is
    consulted for them, but a computed name still escapes it.
    """

    EXACT = "exact"
    NAME_MATCH = "name-match"
    NAME_MATCH_DATA = "name-match-data"


_KIND_CONFIDENCE: Final[dict[SymbolKind, Confidence]] = {
    SymbolKind.FUNCTION: Confidence.EXACT,
    SymbolKind.CLASS: Confidence.EXACT,
    SymbolKind.CONSTANT: Confidence.EXACT,
    SymbolKind.METHOD: Confidence.NAME_MATCH,
    SymbolKind.ATTRIBUTE: Confidence.NAME_MATCH_DATA,
    SymbolKind.ENUM_MEMBER: Confidence.NAME_MATCH_DATA,
}

# Weakest-wins ordering, so a composite finding inherits its softest evidence.
_CONFIDENCE_ORDER: Final[dict[Confidence, int]] = {
    Confidence.EXACT: 0,
    Confidence.NAME_MATCH: 1,
    Confidence.NAME_MATCH_DATA: 2,
}
_CONFIDENCE_BY_ORDER: Final[dict[int, Confidence]] = {rank: tier for tier, rank in _CONFIDENCE_ORDER.items()}

_TOP_LEVEL_KINDS: Final[frozenset[SymbolKind]] = frozenset(
    {SymbolKind.FUNCTION, SymbolKind.CLASS, SymbolKind.CONSTANT},
)
_DATA_SHAPED_KINDS: Final[frozenset[SymbolKind]] = frozenset(
    {SymbolKind.ATTRIBUTE, SymbolKind.ENUM_MEMBER},
)
# Shipped non-Python payloads that address code by name: registry declarations
# and the locale catalogues. Extracted corpus text is prose about tax law, not
# a reference to a symbol, and is not read.
_DATA_GLOBS: Final[tuple[str, ...]] = ("_data/registry/**/*.toml", "_data/registry/**/*.json", "locales/**/*.json")
_DATA_TOKEN: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class EntryPoint:
    """One ``module:attribute`` console-script target."""

    module: str
    attribute: str

    @property
    def spec(self) -> str:
        """The ``module:attribute`` spelling from the packaging table."""
        return f"{self.module}:{self.attribute}"

    @classmethod
    def parse(cls, spec: str) -> EntryPoint:
        """Parse a ``module:attribute`` console-script value."""
        module, separator, attribute = spec.partition(":")
        if not separator or not module or not attribute:
            msg = f"console script {spec!r} is not of the form module:attribute"
            raise ValueError(msg)
        return cls(module=module.strip(), attribute=attribute.strip())


@dataclass(frozen=True)
class OutsideCorpus:
    """A non-shipped tree whose references only label findings.

    Args:
        label: The word rendered after ``used by:``.
        root: Directory walked for ``*.py`` files.
        test_modules_only: When true, only test modules (``tests/`` trees,
            ``test_*.py``, ``conftest.py``) under ``root`` are read; the rest
            of the tree is the shipped universe and is scanned elsewhere.
    """

    label: str
    root: Path
    test_modules_only: bool = False


@dataclass(frozen=True)
class CompanionPackage:
    """A sibling workspace distribution that depends on the audited package.

    Its modules are not the audit's subject, but they are real consumers: an
    installed user running its console script executes them, and whatever they
    import from the audited package is reached. Walking them is the difference
    between "nothing in the product calls this" and "nothing in this one
    distribution calls this".

    Args:
        package: Top-level import name, for example ``cadrumo_harness``.
        src_root: Source root its modules are named relative to.
        entry_points: Its own ``[project.scripts]``.
    """

    package: str
    src_root: Path
    entry_points: tuple[EntryPoint, ...]


@dataclass(frozen=True)
class ShippedTreeSpec:
    """Everything the scan needs to know about one distribution.

    Args:
        repo_root: Paths in findings are rendered relative to this.
        src_root: The ``src/`` directory the package lives under.
        package: The top-level import name of the shipped package.
        entry_points: The console scripts the walk starts from.
        module_roots: Modules executable as ``python -m <module>``, discovered
            from the shipped ``__main__.py`` files. They are walk roots too: an
            installed user can run them without any packaging declaration.
        exclude_globs: Wheel exclude globs; a module they match is unshipped.
        outside: Non-shipped trees whose references label findings.
        data_globs: Shipped non-Python payloads, relative to the package root,
            whose identifier tokens clear a data-shaped member.
        companions: Sibling workspace distributions that consume this package.
    """

    repo_root: Path
    src_root: Path
    package: str
    entry_points: tuple[EntryPoint, ...]
    module_roots: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    outside: tuple[OutsideCorpus, ...] = ()
    data_globs: tuple[str, ...] = ()
    companions: tuple[CompanionPackage, ...] = ()

    @classmethod
    def from_repository(cls, repo_root: Path = REPO_ROOT, *, extra_roots: tuple[str, ...] = ()) -> ShippedTreeSpec:
        """Read the shipped-tree facts from the repository's own packaging config.

        Console scripts and wheel excludes are read from ``pyproject.toml``
        rather than restated, so the audit keeps following the distribution
        as the packaging changes. ``extra_roots`` adds ``module:attribute``
        roots the packaging does not declare, such as a ``python -m`` surface,
        so a campaign can ask "what is dead even if that surface counts?".
        """
        pyproject = repo_root / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding=_UTF_8))
        scripts: dict[str, str] = data["project"].get("scripts", {})
        if not scripts:
            msg = f"{pyproject} declares no [project.scripts]; the walk would have no roots"
            raise ValueError(msg)
        src_root = repo_root / "src"
        package = "cadrumo"
        excludes = wheel_exclude_globs(pyproject)
        companions = _sibling_console_packages(src_root, scripts, audited_package=package)
        entry_points = tuple(
            EntryPoint.parse(spec) for spec in scripts.values() if spec.partition(":")[0].split(".")[0] == package
        ) + tuple(EntryPoint.parse(spec) for spec in extra_roots)
        module_roots = tuple(
            sorted(
                module_name_for(path, src_root=src_root)
                for path in (src_root / package).rglob("__main__.py")
                if _SKIPPED_DIRS.isdisjoint(path.parts)
                and not is_test_path(path, src_root)
                and is_shipped_module(path, src_root=src_root, exclude_globs=tuple(excludes))
            ),
        )
        return cls(
            repo_root=repo_root,
            src_root=src_root,
            package=package,
            entry_points=entry_points,
            module_roots=module_roots,
            exclude_globs=tuple(excludes),
            outside=(
                OutsideCorpus(label="tests", root=src_root / package, test_modules_only=True),
                OutsideCorpus(label="tests", root=repo_root / "conftest.py"),
                OutsideCorpus(label="dev", root=repo_root / "dev"),
            ),
            data_globs=_DATA_GLOBS,
            companions=companions,
        )


def _sibling_console_packages(
    src_root: Path, scripts: dict[str, str], *, audited_package: str
) -> tuple[CompanionPackage, ...]:
    """Group the console scripts that start in a package other than the audited one.

    Read from the declared scripts rather than from workspace membership, so a
    sibling distribution folded into this one keeps contributing its roots. A
    script whose package is not present under ``src/`` is skipped: it cannot be
    walked, and guessing would silently shrink the reachable set.
    """
    grouped: dict[str, list[EntryPoint]] = {}
    for spec in scripts.values():
        entry = EntryPoint.parse(spec)
        package = entry.module.split(".")[0]
        if package == audited_package or not (src_root / package).is_dir():
            continue
        grouped.setdefault(package, []).append(entry)
    return tuple(
        CompanionPackage(package=package, src_root=src_root, entry_points=tuple(entries))
        for package, entries in sorted(grouped.items())
    )


@dataclass(frozen=True)
class ModuleFinding:
    """A shipped module, or a whole package folder, the entrypoints never reach.

    ``spanned_modules`` is 1 for a single module and the member count for a
    package folder whose every module is unreachable and is reported once.

    ``importers`` names the shipped modules outside this finding's own span
    that still import it. It separates two shapes that are identical in the
    reach categories: a module nothing imports at all, and a module whose
    importers exist but are themselves unreached. The scan states the fact;
    what a consumer makes of it is the consumer's disposition.
    """

    path: str
    module: str
    reach: ModuleReach
    spanned_modules: int
    used_by: tuple[str, ...]
    importers: tuple[str, ...] = ()

    @property
    def is_package(self) -> bool:
        """Whether this finding stands for a whole folder."""
        return self.spanned_modules > 1 or self.path.endswith("/")

    @property
    def confidence(self) -> Confidence:
        """Module findings come from resolved imports and are exact."""
        return Confidence.EXACT

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"module:{self.module}"


@dataclass(frozen=True)
class SymbolFinding:
    """A definition inside a reachable module that shipped code never references."""

    path: str
    line: int
    kind: SymbolKind
    name: str
    qualname: str
    used_by: tuple[str, ...]
    module: str = ""

    @property
    def confidence(self) -> Confidence:
        """Name-matched, and weaker still for data-shaped kinds."""
        return _KIND_CONFIDENCE[self.kind]

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"symbol:{self.module}:{self.qualname}"


@dataclass(frozen=True)
class TestFinding:
    """A test module whose every shipped subject is itself a finding.

    ``subjects`` lists what it imports from the shipped tree, as module names
    or ``module:name`` pairs; every one of them is unreachable or unused, so
    the test exists only to keep dead code exercised. The finding is only as
    strong as its weakest subject: a test standing on an unreachable module is
    exact, one standing on a name-matched member inherits that weaker tier.
    """

    path: str
    module: str
    subjects: tuple[str, ...]
    confidence: Confidence = Confidence.EXACT

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"test:{self.module}"


@dataclass(frozen=True)
class UnreachableCodeResult:
    """The scan's typed outcome.

    Construct through :meth:`clean`, :meth:`from_findings`, or :meth:`error`
    so each outcome is bound to its evidence by construction.
    """

    outcome: UnreachableCodeOutcome
    roots: tuple[str, ...] = ()
    shipped_modules: int = 0
    reachable_modules: int = 0
    modules: tuple[ModuleFinding, ...] = ()
    symbols: tuple[SymbolFinding, ...] = ()
    tests: tuple[TestFinding, ...] = ()
    data_cleared: int = 0
    reason: str = ""

    @classmethod
    def clean(cls, *, roots: tuple[str, ...], shipped_modules: int, reachable_modules: int) -> UnreachableCodeResult:
        """A scan in which every shipped module and symbol is reachable."""
        return cls(
            outcome=UnreachableCodeOutcome.CLEAN,
            roots=roots,
            shipped_modules=shipped_modules,
            reachable_modules=reachable_modules,
        )

    @classmethod
    def from_findings(
        cls,
        *,
        roots: tuple[str, ...],
        shipped_modules: int,
        reachable_modules: int,
        modules: tuple[ModuleFinding, ...],
        symbols: tuple[SymbolFinding, ...],
        tests: tuple[TestFinding, ...] = (),
        data_cleared: int = 0,
    ) -> UnreachableCodeResult:
        """A scan that found unreachable modules, unused symbols, or orphaned tests."""
        if not modules and not symbols:
            msg = "from_findings requires at least one module or symbol finding"
            raise ValueError(msg)
        return cls(
            outcome=UnreachableCodeOutcome.FINDINGS,
            roots=roots,
            shipped_modules=shipped_modules,
            reachable_modules=reachable_modules,
            modules=modules,
            symbols=symbols,
            tests=tests,
            data_cleared=data_cleared,
        )

    @classmethod
    def error(cls, reason: str) -> UnreachableCodeResult:
        """A scan that could not produce a trustworthy result; ``reason`` says why."""
        return cls(outcome=UnreachableCodeOutcome.ERROR, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict."""
        return self.outcome is UnreachableCodeOutcome.CLEAN

    @property
    def exact_findings(self) -> tuple[_Finding, ...]:
        """Every finding resolved through the import graph, safe to act on first."""
        ordered: tuple[_Finding, ...] = self.modules + self.tests + self.symbols
        return tuple(finding for finding in ordered if finding.confidence is Confidence.EXACT)

    @property
    def unreachable_module_total(self) -> int:
        """Modules (not findings) the runtime walk never reaches, folders expanded."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.UNREACHABLE)

    @property
    def module_exec_only_total(self) -> int:
        """Modules only a ``python -m`` surface reaches, never a console script."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.MODULE_EXEC_ONLY)

    @property
    def type_only_module_total(self) -> int:
        """Modules reached only through ``TYPE_CHECKING`` imports."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.TYPE_ONLY)

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is UnreachableCodeOutcome.ERROR:
            return f"unreachable-code signal unavailable this cycle: {self.reason}"
        coverage = f"{self.reachable_modules}/{self.shipped_modules} shipped modules reachable at runtime"
        if self.outcome is UnreachableCodeOutcome.CLEAN:
            return f"every shipped module and symbol is reachable from the entrypoints ({coverage})"
        return (
            f"{self.unreachable_module_total} unreachable module(s), "
            f"{self.module_exec_only_total} module-exec-only, "
            f"{self.type_only_module_total} type-only module(s), "
            f"{len(self.symbols)} unused symbol(s) in reachable modules, "
            f"{len(self.tests)} orphaned test module(s) ({coverage})"
        )


# ---------------------------------------------------------------------------
# Shipped-tree census
# ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class ShippedModule:
    """One parsed module of the shipped tree, with the facts the walks need."""

    name: str
    path: Path
    is_package: bool
    tree: ast.Module


def is_test_path(path: Path, root: Path) -> bool:
    """Whether ``path`` is a test module rather than shipped code."""
    relative = path.relative_to(root)
    return "tests" in relative.parts[:-1] or path.name.startswith("test_") or path.name == "conftest.py"


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every ``*.py`` file under ``root``, or ``root`` itself when it is one.

    A root that exists and holds no Python files yields nothing, which is a
    true answer. A root that does not exist yielded the same nothing, and
    every caller then analysed an empty corpus: the reference walk sees no
    references and reports live code dead, the test walk sees no tests and
    reports none. Absence and emptiness were the same event here, so the
    absent case now says so.
    """
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    if not root.is_dir():
        report_unread(
            "unreachable-code enumeration",
            "it does not exist, so every walk over it analysed an empty corpus",
            [str(root)],
        )
        return
    for path in sorted(root.rglob("*.py")):
        if _SKIPPED_DIRS.isdisjoint(path.parts):
            yield path


def parse_module(path: Path) -> ast.Module:
    """Parse one source file into a module tree."""
    return ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))


def _is_resource_anchor(path: Path, tree: ast.Module, src_root: Path) -> bool:
    """True for an empty ``__init__.py`` whose package holds no Python at all.

    ``importlib.resources.files()`` needs a package marker to address a data
    directory. Such a marker is not code and can never be "called"; reporting
    it as unreachable is noise that buries real findings.
    """
    if path.name != "__init__.py" or tree.body:
        return False
    return not any(
        sibling.name != "__init__.py" and not is_test_path(sibling, src_root) for sibling in path.parent.rglob("*.py")
    )


def _load_package(root: Path, src_root: Path, *, exclude_globs: tuple[str, ...]) -> dict[str, ShippedModule]:
    modules: dict[str, ShippedModule] = {}
    for path in iter_python_files(root):
        if is_test_path(path, src_root):
            continue
        if exclude_globs and not is_shipped_module(path, src_root=src_root, exclude_globs=exclude_globs):
            continue
        tree = parse_module(path)
        if _is_resource_anchor(path, tree, src_root):
            continue
        name = module_name_for(path, src_root=src_root)
        modules[name] = ShippedModule(name=name, path=path, is_package=path.name == "__init__.py", tree=tree)
    return modules


def shipped_modules(spec: ShippedTreeSpec) -> dict[str, ShippedModule]:
    """Every module in the audited package, plus the companion distributions that consume it."""
    modules = _load_package(spec.src_root / spec.package, spec.src_root, exclude_globs=spec.exclude_globs)
    for companion in spec.companions:
        modules.update(
            _load_package(companion.src_root / companion.package, companion.src_root, exclude_globs=()),
        )
    return modules


# ---------------------------------------------------------------------------
# Module layer: import-graph reachability from the entry points
# ---------------------------------------------------------------------------


def _ancestors(name: str) -> Iterator[str]:
    parts = name.split(".")
    for end in range(1, len(parts) + 1):
        yield ".".join(parts[:end])


def _known_prefixes(name: str, known: frozenset[str]) -> Iterator[str]:
    yield from (candidate for candidate in _ancestors(name) if candidate in known)


def _string_module_target(value: str, module: ShippedModule, known: frozenset[str]) -> str | None:
    """Resolve a string literal to the shipped module it names, if any.

    Accepts ``pkg.mod``, ``pkg.mod:attr``, and package-relative ``.mod``
    spellings; everything else is prose and is ignored.
    """
    if not _DOTTED_SPEC.match(value):
        return None
    target = value.partition(":")[0]
    if target.startswith("."):
        level = len(target) - len(target.lstrip("."))
        remainder = target[level:] or None
        resolved = resolve_relative_import(module.name, module.is_package, level, remainder)
        return resolved if resolved in known else None
    return target if target in known else None


_MODULE_EXEC_FLAG: Final[str] = "-m"


def _spawn_edges(module: ShippedModule, known: frozenset[str]) -> frozenset[str]:
    """Return the modules ``module`` starts as a ``python -m`` child interpreter.

    A console script that spawns another shipped package as a child process
    reaches it as surely as an import does; the operator types one product
    command and the target runs. Modelling only import edges would report that
    package as ``python -m``-only, which is exactly backwards: the ``python -m``
    surface is the mechanism, and a product command is the caller.

    The edge is only drawn on positive evidence of both halves in the same
    module: the ``-m`` interpreter flag as a literal, and a literal naming a
    shipped package that owns a ``__main__``. A module mentioning a package name
    for any other reason draws nothing, because the flag will be absent.
    """
    literals = {
        node.value for node in ast.walk(module.tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    if _MODULE_EXEC_FLAG not in literals:
        return frozenset()
    targets: set[str] = set()
    for name in literals:
        main = f"{name}.__main__"
        if name in known and main in known:
            targets.update((name, main))
    return frozenset(targets)


def module_edges(module: ShippedModule, known: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(runtime_edges, type_only_edges)`` from ``module`` to shipped modules."""
    guarded = type_checking_guarded_nodes(module.tree)
    runtime: set[str] = set()
    type_only: set[str] = set()
    for node in ast.walk(module.tree):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.extend(_known_prefixes(alias.name, known))
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
            if base is None:
                continue
            targets.extend(_known_prefixes(base, known))
            targets.extend(f"{base}.{alias.name}" for alias in node.names if f"{base}.{alias.name}" in known)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            resolved = _string_module_target(node.value, module, known)
            if resolved is not None:
                targets.append(resolved)
        else:
            continue
        (type_only if id(node) in guarded else runtime).update(targets)
    return frozenset(runtime), frozenset(type_only - runtime)


def reachable_closure(
    roots: Iterable[str],
    modules: dict[str, ShippedModule],
    edges: dict[str, frozenset[str]],
) -> frozenset[str]:
    """Breadth-first closure over ``edges``; importing a module imports its ancestors."""
    seen: set[str] = set()
    queue: deque[str] = deque(root for root in roots if root in modules)
    while queue:
        current = queue.popleft()
        for name in _ancestors(current):
            if name in modules and name not in seen:
                seen.add(name)
                queue.extend(target for target in edges[name] if target not in seen)
    return frozenset(seen)


def _collapse_packages(unreachable: frozenset[str], modules: dict[str, ShippedModule]) -> list[tuple[str, int]]:
    """Report a folder once when every module under it is unreachable.

    Returns ``(module_name, spanned_count)`` pairs: packages first, then the
    loose modules no reported package covers.
    """
    members: dict[str, list[str]] = {}
    for name in sorted(unreachable):
        if not modules[name].is_package:
            continue
        below = [other for other in modules if other == name or other.startswith(name + ".")]
        if all(other in unreachable for other in below):
            members[name] = below
    maximal = [pkg for pkg in members if not any(pkg != other and pkg.startswith(other + ".") for other in members)]
    covered = {name for pkg in maximal for name in members[pkg]}
    findings = [(pkg, len(members[pkg])) for pkg in sorted(maximal)]
    findings.extend((name, 1) for name in sorted(unreachable) if name not in covered)
    return findings


# ---------------------------------------------------------------------------
# Symbol layer: references and definitions inside reachable modules
# ---------------------------------------------------------------------------


def non_reference_nodes(tree: ast.Module) -> set[int]:
    """Nodes whose strings name nothing: ``__all__`` entries and prose.

    A docstring that happens to contain a symbol's name is describing it, not
    reaching it, and an ``__all__`` entry re-exports rather than uses. Counting
    either as a reference silently clears genuinely dead code, so both are cut
    out before any string is read as an identifier.
    """
    skipped: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                skipped.update(id(child) for child in ast.walk(node))
    for node in ast.walk(tree):
        # A bare string expression statement is a docstring or commented-out
        # prose; it is never an expression whose value anything consumes.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            skipped.update(id(child) for child in ast.walk(node))
    return skipped


def string_reference_names(value: str) -> Iterator[str]:
    """Identifiers a string literal may address dynamically (``"mod:attr"``, ``"a.b"``)."""
    if _DOTTED_SPEC.match(value):
        yield from (part for part in re.split(r"[.:]", value) if part)


def forward_reference_names(value: str) -> Iterator[str]:
    """Identifiers a string used in a TYPE position addresses.

    A forward reference is a type expression carried in a string, so
    ``"_AttachmentFileReader | None"`` names a class exactly as an unquoted
    annotation would. The dotted-spec form cannot reach it: a union is not a
    dotted path, so every quoted annotation carrying one read as no reference
    at all and its target was reported unused.

    Only strings the caller has already established sit in a type position are
    passed here, and the value must parse as an expression built solely from
    type syntax. Both guards matter in the same direction: a looser reader that
    treated any prose word as a reference would SUPPRESS real findings, which
    is the failure this audit must never have.
    """
    try:
        parsed = ast.parse(value, mode="eval")
    except SyntaxError:
        return
    allowed = (
        ast.Expression,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Tuple,
        ast.List,
        ast.Load,
        ast.Constant,
        ast.BinOp,
        ast.BitOr,
        ast.Index,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(parsed)):
        return
    for node in ast.walk(parsed):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr


def _type_position_strings(tree: ast.Module) -> Iterator[str]:
    """Yield every string literal the module places in a type position.

    Two positions are unambiguous: the first argument of a ``cast`` call, and
    an annotation written as a string literal.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if name == "cast" and isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield first.value
        annotations = []
        if isinstance(node, (ast.AnnAssign, ast.arg)):
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.append(node.returns)
        for annotation in annotations:
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                yield annotation.value


def _references(tree: ast.Module) -> set[str]:
    """Every bare identifier the module loads, accesses, keywords, imports, or spells."""
    skipped = non_reference_nodes(tree)
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            names.add(node.arg)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(string_reference_names(node.value))
    for value in _type_position_strings(tree):
        names.update(forward_reference_names(value))
    return names


@dataclass(frozen=True)
class _Definition:
    name: str
    qualname: str
    line: int
    kind: SymbolKind
    owner: str = ""
    #: The string literal the member assigns, when it assigns one. A registry
    #: declaration addresses a StrEnum member by this VALUE, never by the
    #: member name, so the data consult cannot see the binding without it.
    value: str = ""


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_framework_bound(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A method a framework reaches by convention or by decorator registration."""
    name = function.name
    if _is_dunder(name) or name in _HOOK_METHOD_NAMES or name.startswith(_HOOK_METHOD_PREFIXES):
        return True
    return any(_decorator_name(decorator) not in _PLAIN_DECORATORS for decorator in function.decorator_list)


def _is_enum_class(node: ast.ClassDef) -> bool:
    return any(_decorator_name(base).endswith(_ENUM_BASE_SUFFIXES) for base in node.bases)


def _assigned_names(node: ast.stmt) -> Iterator[str]:
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return
    for target in targets:
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, ast.Tuple | ast.List):
            yield from (element.id for element in target.elts if isinstance(element, ast.Name))


def _assigned_str_value(statement: ast.stmt) -> str:
    """Return the string literal a single assignment declares, else ``""``.

    Only a bare ``NAME = "literal"`` counts. A computed value, an f-string or
    a call is deliberately not followed: the point is to read the exact token
    a declaration would spell, and anything inferred would widen the data
    consult into guessing.
    """
    if isinstance(statement, ast.Assign | ast.AnnAssign):
        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return ""


def _class_definitions(node: ast.ClassDef) -> Iterator[_Definition]:
    member_kind = SymbolKind.ENUM_MEMBER if _is_enum_class(node) else SymbolKind.ATTRIBUTE
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            if not _is_framework_bound(statement):
                yield _Definition(statement.name, f"{node.name}.{statement.name}", statement.lineno, SymbolKind.METHOD)
        elif isinstance(statement, ast.ClassDef):
            yield _Definition(statement.name, f"{node.name}.{statement.name}", statement.lineno, SymbolKind.CLASS)
            yield from (
                _Definition(inner.name, f"{node.name}.{inner.qualname}", inner.line, inner.kind, owner=inner.owner)
                for inner in _class_definitions(statement)
            )
        else:
            declared = _assigned_str_value(statement)
            for name in _assigned_names(statement):
                if not _is_dunder(name) and name != "_ignore_":
                    yield _Definition(
                        name,
                        f"{node.name}.{name}",
                        statement.lineno,
                        member_kind,
                        owner=node.name,
                        value=declared,
                    )


def _definitions(tree: ast.Module) -> Iterator[_Definition]:
    """Top-level functions, classes, constants, and the members inside each class."""
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            if not any(_decorator_name(d) not in _PLAIN_DECORATORS for d in statement.decorator_list):
                yield _Definition(statement.name, statement.name, statement.lineno, SymbolKind.FUNCTION)
        elif isinstance(statement, ast.ClassDef):
            yield _Definition(statement.name, statement.name, statement.lineno, SymbolKind.CLASS)
            yield from _class_definitions(statement)
        else:
            for name in _assigned_names(statement):
                if not _is_dunder(name):
                    yield _Definition(name, name, statement.lineno, SymbolKind.CONSTANT)


_ENUM_COLLECTION_ATTRS: Final[frozenset[str]] = frozenset(
    {"__members__", "_member_map_", "_member_names_", "_value2member_map_"},
)


def _collection_uses(tree: ast.Module) -> set[str]:
    """Names used as a whole rather than through one attribute.

    An enum whose class is called (value lookup), iterated, passed as an
    argument, placed in a literal collection, or tested with ``in`` reaches
    every member without spelling any of them, so its members are not
    individually auditable by name.
    """
    names: set[str] = set()

    def note(node: ast.expr) -> None:
        if isinstance(node, ast.Name):
            names.add(node.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            note(node.func)
            for arg in node.args:
                note(arg)
            for keyword in node.keywords:
                note(keyword.value)
        elif isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
            note(node.iter)
        elif isinstance(node, ast.Tuple | ast.List | ast.Set):
            for element in node.elts:
                note(element)
        elif isinstance(node, ast.Dict):
            for value in node.values:
                note(value)
        elif isinstance(node, ast.Compare):
            for operator, comparator in zip(node.ops, node.comparators, strict=True):
                if isinstance(operator, ast.In | ast.NotIn):
                    note(comparator)
        elif isinstance(node, ast.Attribute) and node.attr in _ENUM_COLLECTION_ATTRS:
            note(node.value)
    return names


# ---------------------------------------------------------------------------
# Outside corpus: labels only
# ---------------------------------------------------------------------------


@dataclass
class _OutsideUse:
    names: dict[str, set[str]] = field(default_factory=dict)
    modules: dict[str, set[str]] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)
    """Files skipped during the reference walk, and therefore never consulted.

    A skipped file's references are not seen, so every symbol only IT used
    looks unreferenced and is reported as dead. The skip is deliberate - this
    tree is edited while the audit runs and a file can vanish mid-scan - but a
    silent skip means the findings were computed over an incomplete corpus with
    nothing saying so.
    """

    def labels_for_name(self, name: str) -> tuple[str, ...]:
        return tuple(sorted(self.names.get(name, ())))

    def labels_for_module(self, name: str) -> tuple[str, ...]:
        return tuple(sorted(self.modules.get(name, ())))


def _import_aliases(module: ShippedModule, known: frozenset[str]) -> dict[str, str]:
    """Map every local binding that names a shipped module to that module.

    Both spellings bind a module to a name: ``import a.b as c`` and
    ``from . import orm as _orm``. The relative form is resolved through the
    importing module's own position, so a package-relative alias is not lost.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known:
                    aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
            if base is None:
                continue
            for alias in node.names:
                target = f"{base}.{alias.name}"
                if target in known:
                    aliases[alias.asname or alias.name] = target
    return aliases


def resolved_symbol_uses(module: ShippedModule, known: frozenset[str]) -> set[tuple[str, str]]:
    """Return every ``(defining module, symbol)`` pair this module actually reaches.

    Only two syntaxes can reach a top-level symbol across a module boundary:
    a ``from M import N``, and an attribute read on a binding that names ``M``.
    Both are resolved here; a bare identifier load is deliberately not, because
    it says nothing about which module defined the name.
    """
    uses: set[tuple[str, str]] = set()
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
            if base in known:
                uses.update((base, alias.name) for alias in node.names)
    aliases = _import_aliases(module, known)
    if aliases:
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                owner = aliases.get(node.value.id)
                if owner is not None:
                    uses.add((owner, node.attr))
    return uses


def _string_tokens(tree: ast.Module) -> set[str]:
    """Identifiers spelled inside string literals, the only dynamic reach left.

    Docstrings and ``__all__`` are excluded for the reason
    :func:`non_reference_nodes` gives: prose about a symbol is not a use of it.
    """
    skipped = non_reference_nodes(tree)
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            tokens.update(string_reference_names(node.value))
    return tokens


def _data_tokens(spec: ShippedTreeSpec) -> frozenset[str]:
    """Identifier tokens in the shipped non-Python payloads.

    Registry declarations and locale catalogues address fields and enum values
    by name, so a member appearing there is reached by data even though no
    Python statement spells it.
    """
    package_root = spec.src_root / spec.package
    tokens: set[str] = set()
    unread: list[str] = []
    for glob in spec.data_globs:
        for path in package_root.glob(glob):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding=_UTF_8)
            except (OSError, UnicodeDecodeError) as error:
                # A REFERENCE set: a token here is the evidence that a field or
                # enum value is addressed by data rather than by a Python
                # statement. Losing one makes a live member look dead, and dead
                # members here are deletion candidates. The lenient decode was
                # worse than the skip - a replaced byte can split a token so it
                # never matches, with nothing said either way.
                unread.append(f"{path}: {type(error).__name__}: {error}")
                continue
            tokens.update(_DATA_TOKEN.findall(text))
    report_unread(
        "unreachable-code data tokens",
        "a field or enum value addressed only by one of them will look dead and is a deletion candidate",
        unread,
    )
    return frozenset(tokens)


def _declared_data_values(spec: ShippedTreeSpec) -> frozenset[str]:
    """Mapping keys and COMPLETE string values in the shipped declarations.

    Deliberately stricter than :func:`_data_tokens`, and separate from it so
    the name match keeps its existing reach. A StrEnum member's declared value
    is matched against this set, where a loose match clears a live finding on
    a coincidence: tokenising the raw text cleared ``flows.BACK`` because a
    registry sentence reads "created and read back", and ``capabilities.
    PROCESS`` because another reads "Another process is acquiring AEAT". A key
    or a whole string value is a reference; a word inside a sentence, or in a
    comment, is prose about the domain.

    Unparseable files are skipped rather than salvaged by regex: a partial
    read would reintroduce exactly the prose matching this exists to exclude.
    """
    package_root = spec.src_root / spec.package
    values: set[str] = set()
    unread: list[str] = []

    def collect(node: object) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if isinstance(key, str):
                    values.add(key)
                collect(item)
        elif isinstance(node, list):
            for item in node:
                collect(item)
        elif isinstance(node, str):
            values.add(node)

    for glob in spec.data_globs:
        for path in package_root.glob(glob):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding=_UTF_8)
                parsed = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, json.JSONDecodeError) as error:
                unread.append(f"{path}: {type(error).__name__}: {error}")
                continue
            collect(parsed)
    report_unread(
        "unreachable-code declared data values",
        "an enum value addressed only by one of them will look dead and is a deletion candidate",
        unread,
    )
    return frozenset(values)


def _outside_module_name(path: Path, spec: ShippedTreeSpec) -> str:
    """The dotted name an outside file really has, so its relative imports resolve.

    A file under ``src/`` is named from the source root, so an in-source test
    keeps its true package position and a multi-level ``from ...`` import
    resolves. Anything else is named from the repository root, which gives the
    harness trees their own package position without colliding with the
    shipped package.
    """
    root = spec.src_root if path.is_relative_to(spec.src_root) else spec.repo_root
    return module_name_for(path, src_root=root)


def _outside_use(spec: ShippedTreeSpec, known: frozenset[str]) -> _OutsideUse:
    use = _OutsideUse()
    for corpus in spec.outside:
        for path in iter_python_files(corpus.root):
            if corpus.test_modules_only and not is_test_path(path, spec.src_root):
                continue
            try:
                tree = parse_module(path)
            except (OSError, SyntaxError, UnicodeDecodeError):
                # The tree can move under a long scan; a file that is gone or
                # unreadable is skipped rather than crashing the audit, but it
                # is recorded so the report can say the corpus was incomplete.
                use.unreadable.append(str(path))
                continue
            for name in _references(tree):
                use.names.setdefault(name, set()).add(corpus.label)
            probe = ShippedModule(
                name=_outside_module_name(path, spec),
                path=path,
                is_package=path.name == "__init__.py",
                tree=tree,
            )
            runtime, type_only = module_edges(probe, known)
            for target in runtime | type_only:
                use.modules.setdefault(target, set()).add(corpus.label)
    if use.unreadable:
        # Reported at the point of loss rather than folded into the findings.
        # These files' references were never read, so any symbol only THEY use
        # is about to be reported as dead. A reviewer needs to know the corpus
        # was incomplete before acting on a deletion list.
        sys.stderr.write(
            f"unreachable-code: {len(use.unreadable)} file(s) were unreadable during the "
            "reference walk and did not contribute references; findings over symbols they "
            f"use may be false: {sorted(use.unreadable)}" + chr(10)
        )
    return use


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def relative_to_repo(path: Path, spec: ShippedTreeSpec) -> str:
    """Render ``path`` the way a finding reports it, relative to the repository root."""
    return path.relative_to(spec.repo_root).as_posix()


def _shipped_importers(edges: Mapping[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Reverse ``edges`` into "who imports this", over shipped modules only.

    Both runtime and type-checking edges count. The question the reverse graph
    answers is "does anything shipped still name this module", and a
    type-checking-only importer names it just as definitely as a runtime one
    even though the statement never executes.
    """
    reverse: dict[str, set[str]] = {}
    for source, targets in edges.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    return {target: frozenset(sources) for target, sources in reverse.items()}


def _importers_of_span(
    name: str,
    modules: Mapping[str, ShippedModule],
    importers: Mapping[str, frozenset[str]],
) -> tuple[str, ...]:
    """Shipped importers of ``name``'s whole span, excluding the span itself.

    A package finding stands for every module beneath it, so an importer of
    any member is an importer of the finding. Members importing each other are
    internal traffic and say nothing about whether anything outside still
    needs the span.
    """
    span = frozenset(member for member in modules if member == name or member.startswith(name + "."))
    outside_importers = {
        source for member in span for source in importers.get(member, frozenset()) if source not in span
    }
    return tuple(sorted(outside_importers))


def _module_findings(
    spec: ShippedTreeSpec,
    modules: dict[str, ShippedModule],
    script_reach: frozenset[str],
    runtime_reach: frozenset[str],
    full_reach: frozenset[str],
    outside: _OutsideUse,
    importers: Mapping[str, frozenset[str]],
) -> tuple[ModuleFinding, ...]:
    findings: list[ModuleFinding] = []
    audited = frozenset(name for name in modules if name == spec.package or name.startswith(spec.package + "."))
    unreachable = audited - full_reach
    for name, spanned in _collapse_packages(unreachable, modules):
        module = modules[name]
        rendered = relative_to_repo(module.path.parent if module.is_package else module.path, spec)
        if module.is_package:
            rendered += "/"
        used_by: set[str] = set()
        for member in modules:
            if member == name or member.startswith(name + "."):
                used_by.update(outside.labels_for_module(member))
        findings.append(
            ModuleFinding(
                rendered,
                name,
                ModuleReach.UNREACHABLE,
                spanned,
                tuple(sorted(used_by)),
                _importers_of_span(name, modules, importers),
            ),
        )
    for name in sorted((runtime_reach & audited) - script_reach):
        module = modules[name]
        findings.append(
            ModuleFinding(
                relative_to_repo(module.path, spec),
                name,
                ModuleReach.MODULE_EXEC_ONLY,
                1,
                outside.labels_for_module(name),
                _importers_of_span(name, modules, importers),
            ),
        )
    for name in sorted((full_reach & audited) - runtime_reach):
        module = modules[name]
        findings.append(
            ModuleFinding(
                relative_to_repo(module.path, spec),
                name,
                ModuleReach.TYPE_ONLY,
                1,
                outside.labels_for_module(name),
                _importers_of_span(name, modules, importers),
            ),
        )
    return tuple(findings)


def _symbol_findings(
    spec: ShippedTreeSpec,
    modules: dict[str, ShippedModule],
    runtime_reach: frozenset[str],
    full_reach: frozenset[str],
    outside: _OutsideUse,
    data_tokens: frozenset[str],
    declared_values: frozenset[str],
) -> tuple[tuple[SymbolFinding, ...], int]:
    """Return the symbol findings and how many data-shaped members the data corpus cleared."""
    entry_attributes = {entry.attribute for entry in spec.entry_points}
    member_names: set[str] = set(entry_attributes)
    literal_tokens: set[str] = set(entry_attributes)
    resolved_uses: set[tuple[str, str]] = set()
    self_uses: dict[str, set[str]] = {}
    whole_use: set[str] = set()
    for name in full_reach:
        tree = modules[name].tree
        member_names |= _references(tree)
        literal_tokens |= _string_tokens(tree)
        resolved_uses |= resolved_symbol_uses(modules[name], frozenset(modules))
        self_uses[name] = _references(tree)
        whole_use |= _collection_uses(tree)

    findings: list[SymbolFinding] = []
    data_cleared = 0
    audited_reach = sorted(
        name for name in runtime_reach if name == spec.package or name.startswith(spec.package + ".")
    )
    for name in audited_reach:
        module = modules[name]
        for definition in _definitions(module.tree):
            if definition.kind in _TOP_LEVEL_KINDS:
                # Exactly resolvable: an import of this module, a use inside it,
                # or a string naming it. Nothing else can reach a top-level name.
                if (name, definition.name) in resolved_uses or definition.name in self_uses[name]:
                    continue
                if definition.name in literal_tokens:
                    continue
            elif definition.name in member_names:
                continue
            if definition.kind is SymbolKind.ENUM_MEMBER and definition.owner in whole_use:
                continue
            if definition.kind in _DATA_SHAPED_KINDS and (
                definition.name in data_tokens or (definition.value and definition.value in declared_values)
            ):
                data_cleared += 1
                continue
            findings.append(
                SymbolFinding(
                    path=relative_to_repo(module.path, spec),
                    line=definition.line,
                    kind=definition.kind,
                    name=definition.name,
                    qualname=definition.qualname,
                    used_by=outside.labels_for_name(definition.name),
                    module=name,
                ),
            )
    # An overloaded definition yields one row per signature; keep the first.
    return tuple({finding.id: finding for finding in findings}.values()), data_cleared


def _test_subjects(test: ShippedModule, known: frozenset[str]) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Return ``(module subjects, (module, name) symbol subjects)`` a test imports from the shipped tree."""
    modules: set[str] = set()
    symbols: set[tuple[str, str]] = set()
    for node in ast.walk(test.tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name in known)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(test.name, test.is_package, node.level, node.module)
            if base is None or base not in known:
                continue
            for alias in node.names:
                if f"{base}.{alias.name}" in known:
                    modules.add(f"{base}.{alias.name}")
                else:
                    symbols.add((base, alias.name))
    return frozenset(modules), frozenset(symbols)


def _test_findings(
    spec: ShippedTreeSpec,
    known: frozenset[str],
    module_findings: tuple[ModuleFinding, ...],
    symbol_findings: tuple[SymbolFinding, ...],
) -> tuple[TestFinding, ...]:
    """Test modules under the package whose every shipped subject is already a finding."""
    dead_roots = tuple(f.module for f in module_findings if f.reach is ModuleReach.UNREACHABLE)
    dead_symbols = {(f.module, f.name): f.confidence for f in symbol_findings}

    def module_is_dead(name: str) -> bool:
        return any(name == root or name.startswith(root + ".") for root in dead_roots)

    findings: list[TestFinding] = []
    for path in iter_python_files(spec.src_root / spec.package):
        if not is_test_path(path, spec.src_root) or not path.name.startswith("test_"):
            continue
        try:
            tree = parse_module(path)
        except (SyntaxError, UnicodeDecodeError) as error:
            # A finding set, not a reference set: this walk REPORTS test modules
            # whose every subject is already dead, so a skipped module can never
            # be reported as a test of dead code. A broken tracked file is not a
            # race, so it refuses rather than shrinking the findings silently.
            raise SystemExit(
                f"{path} does not parse, so it could not be checked for testing only dead code: {error}"
            ) from error
        except OSError:
            # This one IS a race - the tree is edited while the audit runs - so a
            # file that vanished mid-walk is reported rather than fatal.
            sys.stderr.write(f"unreachable-code: {path} vanished during the test walk and was not checked" + chr(10))
            continue
        test = ShippedModule(module_name_for(path, src_root=spec.src_root), path, False, tree)
        modules, symbols = _test_subjects(test, known)
        if not modules and not symbols:
            continue
        dead_modules = set(modules) | {m for m, _ in symbols if module_is_dead(m)}
        dead_pairs = {(m, n) for m, n in symbols if not module_is_dead(m) and (m, n) in dead_symbols}
        live_pairs = {(m, n) for m, n in symbols if not module_is_dead(m)} - dead_pairs
        if all(module_is_dead(m) for m in modules) and not live_pairs:
            subjects = tuple(sorted(dead_modules)) + tuple(sorted(f"{m}:{n}" for m, n in dead_pairs))
            weakest = max(
                (_CONFIDENCE_ORDER[dead_symbols[pair]] for pair in dead_pairs),
                default=_CONFIDENCE_ORDER[Confidence.EXACT],
            )
            confidence = _CONFIDENCE_BY_ORDER[weakest]
            findings.append(TestFinding(relative_to_repo(path, spec), test.name, subjects, confidence))
    return tuple(findings)


def scan_unreachable_code(spec: ShippedTreeSpec) -> UnreachableCodeResult:
    """Run the two-layer reachability scan over the tree ``spec`` describes."""
    try:
        modules = shipped_modules(spec)
    except SyntaxError as exc:
        return UnreachableCodeResult.error(f"shipped module does not parse: {exc.filename}:{exc.lineno}: {exc.msg}")
    except OSError as exc:
        return UnreachableCodeResult.error(f"shipped tree could not be read ({exc})")
    if not modules:
        return UnreachableCodeResult.error(f"no shipped modules found under {spec.src_root / spec.package}")

    companion_entries = tuple(entry for companion in spec.companions for entry in companion.entry_points)
    roots = (
        tuple(entry.spec for entry in spec.entry_points)
        + tuple(f"{module} (python -m)" for module in spec.module_roots)
        + tuple(f"{entry.spec} (workspace sibling)" for entry in companion_entries)
    )
    root_modules = (
        [entry.module for entry in spec.entry_points]
        + list(spec.module_roots)
        + [entry.module for entry in companion_entries]
    )
    missing = [module for module in root_modules if module not in modules]
    if missing:
        return UnreachableCodeResult.error(f"root module(s) absent from the shipped tree: {', '.join(missing)}")

    known = frozenset(modules)
    edges = {name: module_edges(module, known) for name, module in modules.items()}
    spawned = {name: _spawn_edges(module, known) for name, module in modules.items()}
    runtime_edges = {name: runtime | spawned[name] for name, (runtime, _) in edges.items()}
    full_edges = {name: runtime | type_only | spawned[name] for name, (runtime, type_only) in edges.items()}
    script_reach = reachable_closure(
        [entry.module for entry in spec.entry_points] + [entry.module for entry in companion_entries],
        modules,
        runtime_edges,
    )
    runtime_reach = reachable_closure(root_modules, modules, runtime_edges)
    full_reach = reachable_closure(root_modules, modules, full_edges)

    audited_names = frozenset(name for name in modules if name == spec.package or name.startswith(spec.package + "."))
    audited_total = len(audited_names)
    outside = _outside_use(spec, known)
    data_tokens = _data_tokens(spec)
    declared_values = _declared_data_values(spec)
    shipped_importers = _shipped_importers(full_edges)
    module_findings = _module_findings(
        spec, modules, script_reach, runtime_reach, full_reach, outside, shipped_importers
    )
    symbol_findings, data_cleared = _symbol_findings(
        spec, modules, runtime_reach, full_reach, outside, data_tokens, declared_values
    )

    if not module_findings and not symbol_findings:
        return UnreachableCodeResult.clean(
            roots=roots, shipped_modules=audited_total, reachable_modules=len(runtime_reach & audited_names)
        )
    return UnreachableCodeResult.from_findings(
        roots=roots,
        shipped_modules=audited_total,
        reachable_modules=len(runtime_reach & audited_names),
        modules=module_findings,
        symbols=symbol_findings,
        tests=_test_findings(spec, known, module_findings, symbol_findings),
        data_cleared=data_cleared,
    )


def run_unreachable_code_scan(
    repo_root: Path = REPO_ROOT, *, extra_roots: tuple[str, ...] = ()
) -> UnreachableCodeResult:
    """Scan this repository's shipped tree from its declared console scripts.

    The one entry point ``just audit-unreachable-code`` calls.
    """
    try:
        spec = ShippedTreeSpec.from_repository(repo_root, extra_roots=extra_roots)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        return UnreachableCodeResult.error(f"packaging config unreadable ({exc})")
    return scan_unreachable_code(spec)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def filter_by_confidence(result: UnreachableCodeResult, tier: Confidence) -> UnreachableCodeResult:
    """Return the same result narrowed to one confidence tier.

    A campaign picks the exact tier up first, so the narrowing is done here
    rather than by every consumer re-deriving it from the JSON.
    """
    return UnreachableCodeResult(
        outcome=result.outcome,
        roots=result.roots,
        shipped_modules=result.shipped_modules,
        reachable_modules=result.reachable_modules,
        modules=tuple(f for f in result.modules if f.confidence is tier),
        symbols=tuple(f for f in result.symbols if f.confidence is tier),
        tests=tuple(f for f in result.tests if f.confidence is tier),
        data_cleared=result.data_cleared,
        reason=result.reason,
    )


def _used_by(labels: tuple[str, ...]) -> str:
    return f"[used by: {', '.join(labels)}]" if labels else "[no use anywhere]"


def _capped[T](items: tuple[T, ...], *, full: bool, cap: int) -> tuple[tuple[T, ...], int]:
    shown = items if full else items[:cap]
    return shown, len(items) - len(shown)


def render_console_report(result: UnreachableCodeResult, *, full: bool = False, cap: int = _FINDING_CAP) -> str:
    """Render the operator-facing console report for `just audit-unreachable-code`."""
    out = [f"unreachable code: {result.headline()}"]
    if result.outcome is UnreachableCodeOutcome.ERROR:
        return out[0]
    out.append(f"  roots: {', '.join(result.roots)}")
    if result.data_cleared:
        out.append(f"  {result.data_cleared} data-shaped member(s) cleared by the shipped registry/locale payloads")
    if result.outcome is UnreachableCodeOutcome.CLEAN:
        return "\n".join(out)

    unreachable = tuple(f for f in result.modules if f.reach is ModuleReach.UNREACHABLE)
    exec_only = tuple(f for f in result.modules if f.reach is ModuleReach.MODULE_EXEC_ONLY)
    type_only = tuple(f for f in result.modules if f.reach is ModuleReach.TYPE_ONLY)
    sections: list[tuple[str, tuple[_Finding, ...]]] = [
        (f"modules unreachable from the entrypoints ({result.unreachable_module_total} modules) [exact]", unreachable),
        (
            f"modules only a `python -m` surface reaches, never a console script ({len(exec_only)}) [exact]",
            exec_only,
        ),
        (f"modules reachable only through TYPE_CHECKING imports ({len(type_only)}) [exact]", type_only),
        (f"test modules whose every shipped subject is a finding ({len(result.tests)})", result.tests),
        (f"symbols never referenced by reachable shipped code ({len(result.symbols)})", result.symbols),
    ]
    for title, findings in sections:
        if not findings:
            continue
        out.append(f"  {title}:")
        shown, hidden = _capped(findings, full=full, cap=cap)
        for finding in shown:
            out.append(f"    {_render_finding(finding)}")
        if hidden:
            out.append(f"    ... {hidden} more (--full for all)")
    return "\n".join(out)


type _Finding = ModuleFinding | SymbolFinding | TestFinding


def _render_finding(finding: _Finding) -> str:
    if isinstance(finding, ModuleFinding):
        label = "package" if finding.is_package else "module"
        span = f"  ({finding.spanned_modules} modules)" if finding.spanned_modules > 1 else ""
        return f"{label:<8} {finding.path}{span}  {_used_by(finding.used_by)}"
    if isinstance(finding, TestFinding):
        return f"{finding.path}  exercises only: {', '.join(finding.subjects)}  [{finding.confidence.value}]"
    tier = f"  [{finding.confidence.value}]"
    return (
        f"{finding.path}:{finding.line}  {finding.kind.value:<11} {finding.qualname}  {_used_by(finding.used_by)}{tier}"
    )


def result_as_json(result: UnreachableCodeResult) -> str:
    """Serialise the result for machine consumers."""
    return json.dumps(
        {
            "outcome": result.outcome.value,
            "headline": result.headline(),
            "roots": list(result.roots),
            "shipped_modules": result.shipped_modules,
            "reachable_modules": result.reachable_modules,
            "data_cleared": result.data_cleared,
            "exact_finding_ids": [finding.id for finding in result.exact_findings],
            "modules": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "module": f.module,
                    "reach": f.reach.value,
                    "spanned_modules": f.spanned_modules,
                    "used_by": list(f.used_by),
                    "importers": list(f.importers),
                }
                for f in result.modules
            ],
            "symbols": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "line": f.line,
                    "kind": f.kind.value,
                    "module": f.module,
                    "name": f.name,
                    "qualname": f.qualname,
                    "used_by": list(f.used_by),
                }
                for f in result.symbols
            ],
            "tests": [
                {
                    "id": f.id,
                    "confidence": f.confidence.value,
                    "path": f.path,
                    "module": f.module,
                    "subjects": list(f.subjects),
                }
                for f in result.tests
            ],
            "reason": result.reason,
        },
        indent=2,
        ensure_ascii=False,
    )


def main() -> int:
    """Run the scan and print the report; exit 3 on findings, 1 on error, 0 when clean."""
    parser = argparse.ArgumentParser(description="Audit shipped code no console-script entrypoint can reach.")
    parser.add_argument("--full", action="store_true", help="List every finding, uncapped.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="MODULE:ATTR",
        help="Add a root the packaging does not declare (a python -m surface, for example). Repeatable.",
    )
    parser.add_argument(
        "--confidence",
        choices=[tier.value for tier in Confidence],
        help="Report only findings derived at this tier; 'exact' is the campaign-ready set.",
    )
    args = parser.parse_args()

    result = run_unreachable_code_scan(REPO_ROOT, extra_roots=tuple(args.root))
    if args.confidence is not None:
        result = filter_by_confidence(result, Confidence(args.confidence))
    print(result_as_json(result) if args.json else render_console_report(result, full=args.full))

    if result.outcome is UnreachableCodeOutcome.ERROR:
        return _EXIT_ERROR
    if result.outcome is UnreachableCodeOutcome.FINDINGS:
        return _EXIT_FINDINGS
    return 0


if __name__ == "__main__":
    sys.exit(main())
