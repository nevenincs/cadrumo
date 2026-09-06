"""Scan for names imported TYPE_CHECKING-only but evaluated at runtime.

A name bound only inside ``if TYPE_CHECKING:`` exists for the type checker and
never at runtime. Using it anywhere the interpreter actually evaluates raises
``NameError`` the first time that line runs -- and no static tool reports it,
because under the guard the name IS bound as far as a type checker is
concerned. Ruff, mypy and the import-hygiene families all read such a module as
correct.

That makes the defect invisible until execution, so it survives exactly as long
as the code path goes unexercised. It shipped in the modelo export executor,
which constructed a type-only ``ModeloExportCommand`` in its preconditions
phase while importing the sibling function from the same module at runtime; the
operation raised ``NameError`` on every invocation until a conformance scenario
first executed it.

Built on :func:`type_checking_guarded_nodes` rather than a second guard walker,
so the definition of "under the guard" has one home.

See Also:
    :mod:`dev.quality.import_hygiene_scan`
        The canonical guard-detection helper this reuses.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import override

from .import_hygiene_scan import type_checking_guarded_nodes

__all__ = ["TypeOnlyRuntimeUse", "scan_paths_for_type_only_runtime_uses", "scan_type_only_runtime_uses"]


@dataclass(frozen=True, slots=True)
class TypeOnlyRuntimeUse:
    """One runtime evaluation of a name bound only under the guard."""

    path: Path
    name: str
    bound_lineno: int
    used_lineno: int

    @override
    def __str__(self) -> str:
        """Render the finding as a locator a reader can open."""
        return (
            f"{self.path}:{self.used_lineno} evaluates {self.name!r} at runtime, "
            f"but it is imported TYPE_CHECKING-only at line {self.bound_lineno}"
        )


def _annotation_subtrees(tree: ast.Module) -> set[int]:
    """Node ids sitting inside an annotation, which is never evaluated here.

    Every module in this tree carries ``from __future__ import annotations``,
    so annotations are strings at runtime and a type-only name is legitimate
    there. That is the entire point of the guard, and flagging it would make
    the gate fire on correct code.
    """
    exempt: set[int] = set()

    def mark(node: ast.AST | None) -> None:
        if node is None:
            return
        exempt.update(id(sub) for sub in ast.walk(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            mark(node.annotation)
        elif isinstance(node, ast.TypeAlias):
            # PEP 695 `type X = ...` defers its value the same way an annotation
            # is deferred, so a guard-only name on the right-hand side is
            # correct rather than a latent NameError.
            mark(node.value)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.TypeAlias):
            # PEP 695 type-parameter bounds and defaults defer the same way.
            for parameter in getattr(node, "type_params", ()):
                mark(getattr(parameter, "bound", None))
                mark(getattr(parameter, "default_value", None))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            mark(node.returns)
            arguments = node.args
            for slot in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ):
                if slot is not None:
                    mark(slot.annotation)
    return exempt


def _runtime_bound_names(tree: ast.Module, guarded: set[int]) -> set[str]:
    """Names the module binds for real, which override any guarded binding.

    A module may import a symbol at runtime AND re-declare it under the guard
    for a type checker's benefit. The runtime binding wins, so the name is not
    a candidate -- the same precedence the import-ownership scanner applies.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.alias):  # pragma: no cover - covered via parents above
            continue
    return bound


def scan_type_only_runtime_uses(path: Path, *, source: str | None = None) -> list[TypeOnlyRuntimeUse]:
    """Report every runtime evaluation of a guard-only name in one module.

    A module that cannot be parsed is skipped and the skip is ANNOUNCED. An
    empty result reads exactly like a clean module, and what goes unreported
    here is a name imported only under ``if TYPE_CHECKING:`` and evaluated at
    runtime - a NameError waiting in shipped code.

    The skip stays because the tree is edited while the sweep runs and one
    half-written file must not cost the thousands that parsed. Measured over
    the shipped tree: 5844 modules, none unparsable and none undecodable.
    """
    if source is not None:
        text = source
    else:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            # The same policy the decode and parse skips follow, for the same
            # stated reason: the tree is edited while the sweep runs, and a file
            # deleted between the walk and this read must not cost the thousands
            # that were read. Announced rather than skipped silently, because
            # saying nothing either way is the one outcome this scan refuses.
            sys.stderr.write(
                f"type-only runtime-use scan: {path} could not be read and was not scanned, so a "
                f"guard-only name evaluated at runtime in it goes unreported: {error}" + chr(10)
            )
            return []
        except UnicodeDecodeError as error:
            # Read strictly. With errors='ignore' an undecodable byte was dropped
            # and the scan then analysed text that is not what the file contains -
            # a finding could be invented or lost with nothing said either way.
            sys.stderr.write(
                f"type-only runtime-use scan: {path} is not valid UTF-8 and was not scanned: {error}" + chr(10)
            )
            return []
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        sys.stderr.write(
            f"type-only runtime-use scan: {path} does not parse and was not scanned, so a "
            f"guard-only name evaluated at runtime in it goes unreported: {error}" + chr(10)
        )
        return []

    guarded = type_checking_guarded_nodes(tree)
    if not guarded:
        return []

    type_only: dict[str, int] = {}
    for node in ast.walk(tree):
        if id(node) not in guarded:
            continue
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                type_only.setdefault(alias.asname or alias.name, node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                type_only.setdefault(alias.asname or alias.name.split(".", 1)[0], node.lineno)

    candidates = {name: lineno for name, lineno in type_only.items() if name not in _runtime_bound_names(tree, guarded)}
    if not candidates:
        return []

    exempt = _annotation_subtrees(tree)
    found: list[TypeOnlyRuntimeUse] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)):
            continue
        if id(node) in exempt or id(node) in guarded:
            continue
        bound_lineno = candidates.get(node.id)
        if bound_lineno is not None:
            found.append(
                TypeOnlyRuntimeUse(
                    path=path,
                    name=node.id,
                    bound_lineno=bound_lineno,
                    used_lineno=node.lineno,
                )
            )
    return found


def scan_paths_for_type_only_runtime_uses(paths: tuple[Path, ...]) -> list[TypeOnlyRuntimeUse]:
    """Scan many modules, reported in a stable order."""
    found: list[TypeOnlyRuntimeUse] = []
    for path in sorted(paths):
        found.extend(scan_type_only_runtime_uses(path))
    return found
