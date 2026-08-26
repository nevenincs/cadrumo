"""Audit gate: every production module is exercised by the test suite.

The judged property is per-module and behavioural: *can an executing test
reach code defined in this module?* It is answered over a **symbol-use
graph**, not an import graph. An edge ``A -> B`` exists when module ``A``
references a name that module ``B`` **defines**, resolved through ``A``'s
import bindings and through any chain of re-exporting facades. The closure
is rooted at the test surface (``test_*.py``, ``conftest.py``, and modules
under a ``tests/`` package, whose fixtures and helpers really do run).

Re-export is deliberately **not** a use. A package ``__init__.py`` that
does ``from ._x import Y`` and lists ``Y`` in ``__all__`` contributes no
edge to ``_x``, because importing a facade executes only ``_x``'s
module-level definitions — it never calls ``_x``'s functions. That single
distinction is what the gate exists to enforce. Judging static import
reachability instead lets one import of a package facade from any
surviving test report every module in that package as covered, so an
entire package's tests can be deleted while the gate stays green.

Transitive use is preserved, because it is genuine exercise: a test that
calls a function which calls a helper really does run the helper, so the
helper is exercised even though no test names it. The closure therefore
follows use edges through production code to any depth.

Scope. Package ``__init__.py`` files carry no requirement: they execute
whenever any module beneath them is imported, and their content is
re-export plumbing rather than behaviour. Every other module under
``src/cadrumo/`` must land in the closure or carry an exemption.

Limits worth stating. The walker reads static references only, so a
symbol reached exclusively through a runtime-built string — a subprocess
entry point, a dynamically registered CLI verb — is invisible to it. Those
are the entire content of the exemption table below, and each entry names
the dispatch mechanism that hides it.
"""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

import pytest

from ._inventory import REPO_ROOT, SRC_CADRUMO, ast_for_path, module_name, package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT: Final[Path] = SRC_CADRUMO
_CADRUMO_PACKAGE: Final[str] = "cadrumo"

_MAX_REEXPORT_HOPS: Final[int] = 12
"""Bound on facade-chasing when resolving one symbol to its defining module.

A re-export chain crosses one package boundary per hop. Twelve exceeds the
deepest chain in the tree while keeping resolution terminating on a
pathological cycle.
"""


_DYNAMIC_DISPATCH_EXEMPTIONS: Final[Mapping[str, str]] = {
    # Every entry states the runtime dispatch that hides the module from a
    # static reference walk, and what does exercise it instead. An entry is
    # retired the moment the module lands in the closure on its own -- the
    # redundancy gate below fails until it is deleted.
    "src/cadrumo/adapters/outbound/aeat/_playwright.py": (
        "Driven only through a live Playwright browser process; the browser "
        "integration suite that exercises it runs outside the default lanes. "
        "Retire when a lane-resident test references its symbols."
    ),
    "src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py": (
        "Child-process entry point spawned as `python -m "
        "cadrumo.adapters.persistence.storage.custody._kdf_worker` by "
        "adapters/persistence/storage/custody/_kdf_process.py, so the only "
        "reference to it is a module-path string. The custody KDF suite drives "
        "it end-to-end through that spawn. Retire when the worker body is "
        "reachable without the subprocess boundary."
    ),
    "src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports.py": (
        "Typer subcommand registered through the same `_lazy(...)` dispatch; "
        "exercised end-to-end by the prepared-exports repair CLI suite. "
        "Retire when the command module is registered statically."
    ),
    "src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports_payloads.py": (
        "Response payload models reachable only through the dynamically "
        "dispatched repair command module above, which the CLI suite "
        "drives. Retire when the owning command is registered statically."
    ),
    "src/cadrumo/entrypoints/cli/_app_quickfile.py": (
        "Typer subcommand registered through the same `_lazy(...)` dispatch; "
        "exercised end-to-end by the app-quickfile CLI suite. Retire when the "
        "command module is registered statically."
    ),
    "src/cadrumo/entrypoints/cli/_registry_corpus.py": (
        "Typer subcommand registered through the same `_lazy(...)` dispatch; "
        "exercised through the registry-corpus CLI surface. Retire when the "
        "command module is registered statically."
    ),
    "src/cadrumo/entrypoints/cli/registry.py": (
        "Typer subcommand registered through the same `_lazy(...)` dispatch; "
        "exercised through the registry CLI surface. Retire when the command "
        "module is registered statically."
    ),
}
"""Modules whose only entry into execution is a runtime-built string.

Keyed by repository-relative POSIX path so an exemption names one reviewed
module and can never widen to a directory. Two gates keep the table honest:
an entry naming a vanished path fails, and an entry naming a module the
closure already reaches fails as redundant.
"""


def _is_structural_non_requirement(path: Path) -> bool:
    """Return True for files that carry no exercise requirement at all."""
    name = path.name
    return name in {"__init__.py", "conftest.py", "fixtures.py", "_fixtures.py"}


def _is_test_surface(path: Path) -> bool:
    """Return True when *path* is code the test run itself executes.

    Fixtures and helpers under a ``tests/`` package run as surely as the
    ``test_*.py`` bodies do, so their symbol references are real roots.
    """
    if path.name.startswith("test_") or path.name == "conftest.py":
        return True
    return "tests" in path.relative_to(_SRC_ROOT).parts


@cache
def _tracked_modules() -> tuple[Path, ...]:
    """Return every package ``.py`` file the graph is built over."""
    return package_python_files(include_data=True)


@cache
def _test_surface_modules() -> tuple[Path, ...]:
    """Return the roots of the exercise closure."""
    return tuple(path for path in _tracked_modules() if _is_test_surface(path))


@cache
def _production_modules() -> tuple[Path, ...]:
    """Return every non-test module that must be exercised."""
    return tuple(
        path for path in _tracked_modules() if not _is_test_surface(path) and not _is_structural_non_requirement(path)
    )


@cache
def _known_dotted_names() -> frozenset[str]:
    """Return the dotted name of every module in the tree."""
    return frozenset(module_name(path) for path in _tracked_modules())


@cache
def _module_file_for(dotted: str) -> Path | None:
    """Return the on-disk file for a ``cadrumo.*`` dotted module name."""
    if dotted not in _known_dotted_names():
        return None
    parts = dotted.split(".")
    base = _SRC_ROOT.parent
    candidate = base.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    candidate = base.joinpath(*parts, "__init__.py")
    return candidate if candidate.is_file() else None


def _resolve_relative(current_dotted: str, level: int, module: str | None, *, is_package: bool) -> str | None:
    """Resolve a relative-import target to an absolute dotted name."""
    if level == 0:
        return module
    parts = current_dotted.split(".")
    anchor = parts[: len(parts) - (level - 1)] if is_package else parts[: len(parts) - level]
    if not anchor:
        return None
    return ".".join([*anchor, module]) if module else ".".join(anchor)


_NESTING_STATEMENTS: Final[tuple[type[ast.stmt], ...]] = (ast.If, ast.Try, ast.With, ast.For, ast.While)


def _collect_module_level_names(body: list[ast.stmt], into: set[str]) -> None:
    """Record every name *body* binds at module level.

    Descends into conditional and guarded blocks -- a ``TYPE_CHECKING``
    branch or an optional-dependency ``try``/``except ImportError`` fallback
    binds real module-level names -- but never into a function or class
    body, whose names belong to that scope rather than the module.
    """
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            into.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                into.update(sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            into.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            into.add(node.name.id)
        elif isinstance(node, _NESTING_STATEMENTS):
            for block in ("body", "orelse", "finalbody"):
                _collect_module_level_names(getattr(node, block, []) or [], into)
            for handler in getattr(node, "handlers", []) or []:
                _collect_module_level_names(handler.body, into)


@dataclass(frozen=True)
class _SourceIndex:
    """Per-module definition, re-export and import-binding tables."""

    defines: Mapping[str, frozenset[str]]
    reexports: Mapping[str, Mapping[str, str]]
    bindings: Mapping[Path, Mapping[str, str]]


@cache
def _source_index() -> _SourceIndex:
    """Build the definition / re-export / binding tables once per process."""
    defines: dict[str, frozenset[str]] = {}
    reexports: dict[str, Mapping[str, str]] = {}
    bindings: dict[Path, Mapping[str, str]] = {}

    for path in _tracked_modules():
        tree = ast_for_path(path)
        if not isinstance(tree, ast.Module):
            continue
        dotted = module_name(path)
        is_package = path.name == "__init__.py"

        defined: set[str] = set()
        _collect_module_level_names(tree.body, defined)

        imported: set[str] = set()
        module_reexports: dict[str, str] = {}
        module_bindings: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    origin = alias.name if alias.asname else alias.name.split(".")[0]
                    imported.add(bound)
                    module_bindings[bound] = origin
                    if origin.startswith(_CADRUMO_PACKAGE):
                        module_reexports[bound] = origin
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_relative(dotted, node.level, node.module, is_package=is_package)
                if base is None:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname or alias.name
                    origin = f"{base}.{alias.name}"
                    imported.add(bound)
                    module_bindings[bound] = origin
                    if base.startswith(_CADRUMO_PACKAGE):
                        module_reexports[bound] = origin

        # A name this module imported is defined elsewhere; keeping it out of
        # `defines` is what makes a re-export transparent rather than a home.
        defines[dotted] = frozenset(defined - imported)
        reexports[dotted] = module_reexports
        bindings[path] = module_bindings

    return _SourceIndex(defines=defines, reexports=reexports, bindings=bindings)


@cache
def _defining_module(reference: str, hops: int = 0) -> Path | None:
    """Return the module that *defines* the symbol named by *reference*.

    ``reference`` is an absolute dotted name such as
    ``cadrumo.core.Modelo``. Resolution splits it into the longest prefix
    that names a real module plus the symbol taken from it, then either
    finds the symbol defined there or follows that module's re-export of it
    one hop further. A bare module reference resolves to ``None``: importing
    a module is not using a symbol from it.
    """
    if hops > _MAX_REEXPORT_HOPS or not reference.startswith(_CADRUMO_PACKAGE):
        return None
    if reference in _known_dotted_names():
        return None

    index = _source_index()
    parts = reference.split(".")
    for boundary in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:boundary])
        owner = _module_file_for(prefix)
        if owner is None:
            continue
        symbol = parts[boundary]
        if symbol in index.defines.get(prefix, frozenset()):
            return owner
        origin = index.reexports.get(prefix, {}).get(symbol)
        if origin is None or origin == reference:
            return None
        if origin in _known_dotted_names():
            # The re-exported name is itself a submodule; any remaining
            # attribute chain is the symbol actually taken from it.
            remainder = parts[boundary + 1 :]
            return _defining_module(f"{origin}.{'.'.join(remainder)}", hops + 1) if remainder else None
        return _defining_module(origin, hops + 1)
    return None


def _referenced_origins(tree: ast.Module, module_bindings: Mapping[str, str]) -> set[str]:
    """Return the absolute dotted names *tree* references outside its imports.

    Only the outermost node of an attribute chain is read, so ``a.b.c`` is
    one reference rather than three. Import statements are skipped: binding
    a name is not using it.
    """
    origins: set[str] = set()
    pending: list[ast.AST] = [tree]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Name | ast.Attribute):
            attributes: list[str] = []
            cursor: ast.AST = node
            while isinstance(cursor, ast.Attribute):
                attributes.append(cursor.attr)
                cursor = cursor.value
            if not isinstance(cursor, ast.Name):
                pending.append(cursor)
                continue
            origin = module_bindings.get(cursor.id)
            if origin is not None and origin.startswith(_CADRUMO_PACKAGE):
                tail = ".".join(reversed(attributes))
                origins.add(f"{origin}.{tail}" if tail else origin)
            continue
        pending.extend(ast.iter_child_nodes(node))
    return origins


@cache
def _symbol_use_edges() -> Mapping[Path, frozenset[Path]]:
    """Return, per module, the modules whose defined symbols it references."""
    index = _source_index()
    edges: dict[Path, frozenset[Path]] = {}
    for path in _tracked_modules():
        tree = ast_for_path(path)
        if not isinstance(tree, ast.Module):
            edges[path] = frozenset()
            continue
        targets = {
            defining
            for reference in _referenced_origins(tree, index.bindings.get(path, {}))
            if (defining := _defining_module(reference)) is not None and defining != path
        }
        edges[path] = frozenset(targets)
    return edges


@cache
def _exercised_modules() -> frozenset[Path]:
    """Return every module the test surface can reach through symbol use."""
    edges = _symbol_use_edges()
    reached: set[Path] = set()
    queue: deque[Path] = deque()
    for root in _test_surface_modules():
        for target in edges.get(root, frozenset()):
            if target not in reached:
                reached.add(target)
                queue.append(target)
    while queue:
        for target in edges.get(queue.popleft(), frozenset()):
            if target not in reached:
                reached.add(target)
                queue.append(target)
    return frozenset(reached)


def test_reexport_facade_does_not_launder_exercise() -> None:
    """The load-bearing distinction: importing a facade is not using its members.

    This is the anti-tautology proof for the whole gate. A package
    ``__init__.py`` whose body is ``from ._x import Y`` plus an ``__all__``
    list must contribute **no** use edge to ``_x``. If it did, one import of
    any package facade from any surviving test would re-cover every module
    in that package, which is precisely the blindness this gate replaced.
    """
    edges = _symbol_use_edges()
    pure_reexport_facades = [
        path
        for path in _tracked_modules()
        if path.name == "__init__.py" and not _is_test_surface(path) and not _source_index().defines[module_name(path)]
    ]
    assert pure_reexport_facades, "expected the tree to contain pure re-export package facades"

    laundering = sorted(repo_relative(path) for path in pure_reexport_facades if edges[path])
    assert not laundering, (
        f"{len(laundering)} package facade(s) that define nothing still emit symbol-use edges, "
        "so a bare import of the facade would report its submodules as exercised:\n"
        + "\n".join(f"  {entry}" for entry in laundering)
    )


def test_symbol_use_closure_follows_production_call_chains() -> None:
    """Positive control: exercise travels through production code, not just tests.

    A helper no test names by hand is still genuinely run when an exercised
    production module calls it, so the closure must reach it. Without this
    the gate would demand a test file per module and stop measuring
    behaviour.
    """
    edges = _symbol_use_edges()
    exercised = _exercised_modules()
    directly_referenced = {target for root in _test_surface_modules() for target in edges.get(root, frozenset())}

    indirect = exercised - directly_referenced
    assert indirect, (
        "no module was reached only through a production-to-production use edge; "
        "the closure has collapsed to modules tests name directly"
    )


def test_symbol_resolution_rejects_names_with_no_defining_module() -> None:
    """Negative control: unresolvable and non-first-party names never resolve."""
    assert _defining_module("cadrumo.does.not.exist.Symbol") is None
    assert _defining_module("os.path.join") is None
    # A bare module reference is an import, not a use of a defined symbol.
    assert _defining_module("cadrumo.core") is None


def test_every_production_module_is_exercised_by_a_test() -> None:
    """Canonical gate: every production module lands in the exercise closure.

    A module fails here when nothing an executing test reaches references a
    symbol it defines -- neither a test directly, nor any chain of
    production code a test drives. That is the honest statement that the
    module's behaviour is unproven.

    The fix is to author a real-behavior test that exercises it, or to
    delete the module if nothing calls it. Adding a tautological test to
    silence this gate defeats its purpose, and an exemption is only correct
    when a runtime-built string genuinely hides real execution.
    """
    production = _production_modules()
    assert production, "no production modules were collected; a coverage gate over an empty tree proves nothing"
    exercised = _exercised_modules()
    assert exercised, "the symbol-use closure reached nothing; every module would read as a gap"

    unexercised = sorted(
        repo_relative(path)
        for path in production
        if path not in exercised and repo_relative(path) not in _DYNAMIC_DISPATCH_EXEMPTIONS
    )

    assert not unexercised, (
        f"{len(unexercised)} production module(s) are never exercised by the test suite.\n"
        "Nothing an executing test reaches references any symbol these modules\n"
        "define, directly or through the production code the tests drive.\n"
        "Author a real-behavior test, or delete the module if nothing calls it:\n\n"
        + "\n".join(f"  {entry}" for entry in unexercised)
    )


def test_every_exemption_still_names_a_live_module() -> None:
    """An exemption whose module vanished must fail, not sit quietly.

    A stale entry costs nothing while the path is absent, and the moment
    anyone creates a module there it silently exempts it -- a waiver granted
    by someone who never saw the file.
    """
    dead = sorted(entry for entry in _DYNAMIC_DISPATCH_EXEMPTIONS if not (REPO_ROOT / entry).is_file())

    assert not dead, (
        f"{len(dead)} exemption(s) name a module that no longer exists, so each is a "
        "standing waiver for a path nobody has reviewed:\n"
        + "\n".join(f"  {entry}" for entry in dead)
        + "\n\nDelete the entry. If the module moved, exempt its new path only after "
        "confirming the original rationale still holds there."
    )


def test_no_exemption_covers_an_already_exercised_module() -> None:
    """An exemption the closure has overtaken must fail as redundant.

    This is the half that keeps the table shrinking. Once a module is
    genuinely exercised, its exemption stops describing reality and starts
    pre-authorising the loss of that coverage: delete the module's only test
    later and the waiver absorbs the regression in silence. Every entry
    states the condition that retires it, and this gate enforces retirement.
    """
    exercised = _exercised_modules()
    redundant = sorted(entry for entry in _DYNAMIC_DISPATCH_EXEMPTIONS if (REPO_ROOT / entry).resolve() in exercised)

    assert not redundant, (
        f"{len(redundant)} exemption(s) name a module the test suite already exercises, "
        "so each is a standing waiver that would silently absorb the loss of that coverage:\n"
        + "\n".join(f"  {entry}" for entry in redundant)
        + "\n\nDelete the entry."
    )
