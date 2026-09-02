#!/usr/bin/env python
"""Audit persistence surfaces whose readers ship but whose writers do not.

:mod:`dev.audit.unreachable_code` answers a question about the IMPORT graph:
which shipped modules can no entrypoint reach? That question is blind to a
whole defect class, because a store with no writer is perfectly reachable.
Every module involved is imported by something, every test passes, and the
product ships commands that read a namespace nothing on earth can fill.

This module answers the complementary question about the DATA path: for a
persistence surface whose READ side a product command reaches, does a
production WRITE path still exist?

The shape it detects is exact, and it is the shape that has already caused two
regressions here. A snapshot/repository service exposes ``capture``-style verbs
that persist and ``list``/``show``/``latest``-style verbs that read. A refactor
deletes the last producer -- the parser, the importer, the acquisition adapter
-- and nothing goes red, because the service class, its payload models, its
storage namespace, and the CLI commands that read them all remain imported and
tested. The store is simply never filled again.

How a surface is identified
---------------------------

Not by name. The tree already carries a structural anchor: the lifecycle bases
in ``cadrumo.application.live.snapshot_base``. Every bucket-scoped snapshot
service subclasses one of them, and the base's own template methods are what
reach the repository. So the audit resolves the subclass closure of those
declared bases through the shipped import graph, keeps the LEAF classes (an
intermediate base is not itself a surface), and derives each leaf's read and
write verbs from what its method bodies actually touch:

* a method that reaches the repository's ``save`` -- directly, or through
  another method of the same class hierarchy -- is a WRITE verb;
* a method that reaches any other repository verb, and is not a write, is a
  READ verb.

Nothing is spelled by hand except the base module and class names, which are
verified to exist before the scan runs. A rename that loses the anchor fails
the audit rather than silently reporting a clean tree.

How a caller is bound
---------------------

``capture`` is a common method name, so a bare search for ``.capture(``
anywhere in the tree would clear every surface as soon as any ONE of them had
a writer. The binding is therefore two-sided: a module counts as a writer for
surface ``C`` only when it both resolves an import of ``C`` (or of a top-level
function in ``C``'s own module that persists through it) AND spells one of
``C``'s write verbs outside a docstring. The same rule, with the read verbs,
identifies readers.

Only shipped, non-test modules count. A reference from ``tests`` or from
``dev/`` is harvested to LABEL a finding, never to clear it, exactly as the
reachability audit treats those trees.

What is reported
----------------

A finding is the asymmetry, not the absence: the surface has at least one
reader in a module a console script reaches, and no writer anywhere in
production. A surface with neither readers nor writers is not reported here --
that is dead code, and :mod:`dev.audit.unreachable_code` owns it.

Known limits, stated rather than tuned away
-------------------------------------------

The audit deliberately prefers precision to recall, because a gate that cries
wolf gets switched off:

* A writer stranded in a shipped module that no entrypoint reaches still
  clears the surface. The module itself is then the unreachable-module
  ratchet's finding, and reporting it twice in two vocabularies would make
  both harder to act on.
* A writer reached only through an indirection the static pass cannot follow
  (``getattr`` with a computed name, a callable stored in a table under a
  different key) is invisible. A write verb spelled as a plain string literal
  IS seen, which covers the deferred-target style this CLI uses.
* A surface written only by a TUI screen, a migration, or any other shipped
  production module is correctly cleared; those are real writers.
* A class that reaches the repository through a helper that is neither a
  method of the hierarchy nor a top-level function of the defining module is
  not classified, so its verbs may be missed. Such a surface reports no write
  verbs at all and is skipped rather than guessed at.

The scan is static and read-only. It never imports the production package.

See Also:
    :mod:`dev.audit.unreachable_code`
        The import-graph reachability audit whose machinery this reuses.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT
from ..quality.import_hygiene_scan import resolve_relative_import
from .unreachable_code import (
    ShippedTreeSpec,
    _is_test_path,
    _iter_python_files,
    _module_edges,
    _non_reference_nodes,
    _parse,
    _reachable,
    _relative,
    _resolved_symbol_uses,
    _shipped_modules,
    _ShippedModule,
    _string_reference_names,
)

_EXIT_FINDINGS: Final[int] = 3
_EXIT_ERROR: Final[int] = 1

#: The repository verb that makes a method a producer. Everything else on the
#: snapshot repository protocol is a consumer.
_PERSIST_VERB: Final[str] = "save"
#: The consuming half of the same protocol.
_READ_VERBS: Final[frozenset[str]] = frozenset({"exists", "load", "list_snapshots", "resolve"})


class WritePathOutcome(StrEnum):
    """The three honest states this scan can land in."""

    CLEAN = "clean"
    FINDINGS = "findings"
    ERROR = "error"


@dataclass(frozen=True)
class PersistenceSurfaceSpec:
    """Where the persistence-surface hierarchy is rooted.

    Args:
        base_module: Dotted module defining the lifecycle bases.
        base_classes: Class names in ``base_module`` every surface derives
            from. A name absent from the tree is an error, not an empty scan.
    """

    base_module: str
    base_classes: tuple[str, ...]

    @classmethod
    def for_repository(cls) -> PersistenceSurfaceSpec:
        """The anchor this repository's live snapshot services actually use."""
        return cls(
            base_module="cadrumo.application.live.snapshot_base",
            base_classes=("SnapshotService", "StatelessSnapshotService"),
        )


@dataclass(frozen=True)
class WritePathFinding:
    """A persistence surface read by a product command and written by nothing.

    Args:
        path: Repository-relative file defining the surface class.
        line: Line the class is defined on.
        module: Dotted module defining it.
        service: Class name of the surface.
        read_verbs: Public methods that consume the store.
        write_verbs: Public methods that fill it.
        read_callers: Shipped modules a console script reaches that read it.
        write_labels: Non-shipped trees (``tests``, ``dev``) that still write
            it. A label explains why the surface looks alive; it never clears
            the finding, because neither tree is installed.
    """

    path: str
    line: int
    module: str
    service: str
    read_verbs: tuple[str, ...]
    write_verbs: tuple[str, ...]
    read_callers: tuple[str, ...]
    write_labels: tuple[str, ...]

    @property
    def id(self) -> str:
        """Stable identifier a gate or agent can track this finding by."""
        return f"write-path:{self.module}:{self.service}"


@dataclass(frozen=True)
class WritePathResult:
    """The scan's typed outcome.

    Construct through :meth:`clean`, :meth:`from_findings`, or :meth:`error`,
    so every outcome is bound to its evidence.
    """

    outcome: WritePathOutcome
    surfaces_examined: tuple[str, ...] = ()
    findings: tuple[WritePathFinding, ...] = ()
    reason: str = ""

    @classmethod
    def clean(cls, *, surfaces_examined: tuple[str, ...]) -> WritePathResult:
        """Every examined surface still has a production writer."""
        return cls(outcome=WritePathOutcome.CLEAN, surfaces_examined=surfaces_examined)

    @classmethod
    def from_findings(
        cls, *, surfaces_examined: tuple[str, ...], findings: tuple[WritePathFinding, ...]
    ) -> WritePathResult:
        """At least one surface is read by a product command and written by nothing."""
        if not findings:
            msg = "from_findings requires at least one finding"
            raise ValueError(msg)
        return cls(outcome=WritePathOutcome.FINDINGS, surfaces_examined=surfaces_examined, findings=findings)

    @classmethod
    def error(cls, reason: str) -> WritePathResult:
        """The scan could not produce a trustworthy result; ``reason`` says why."""
        return cls(outcome=WritePathOutcome.ERROR, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict."""
        return self.outcome is WritePathOutcome.CLEAN

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is WritePathOutcome.ERROR:
            return f"write-path signal unavailable this cycle: {self.reason}"
        examined = f"{len(self.surfaces_examined)} persistence surface(s) examined"
        if self.outcome is WritePathOutcome.CLEAN:
            return f"every readable persistence surface still has a production writer ({examined})"
        return f"{len(self.findings)} readable persistence surface(s) with no production write path ({examined})"


# ---------------------------------------------------------------------------
# Surface discovery: the subclass closure of the declared lifecycle bases
# ---------------------------------------------------------------------------


type _Symbol = tuple[str, str]


def _symbol_imports(module: _ShippedModule, known: frozenset[str]) -> dict[str, _Symbol]:
    """Map each local binding that names a shipped module's symbol to that symbol.

    Only ``from M import N`` binds a class name into another module's
    namespace in this tree; a module alias reaches the class through an
    attribute, which :func:`_base_symbols` resolves separately.
    """
    bindings: dict[str, _Symbol] = {}
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
        if base is None or base not in known:
            continue
        for alias in node.names:
            if f"{base}.{alias.name}" not in known:
                bindings[alias.asname or alias.name] = (base, alias.name)
    return bindings


def _module_aliases(module: _ShippedModule, known: frozenset[str]) -> dict[str, str]:
    """Map each local binding that names a shipped MODULE to that module."""
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


def _base_symbols(node: ast.ClassDef, module: _ShippedModule, known: frozenset[str]) -> frozenset[_Symbol]:
    """Resolve every base of ``node`` to the ``(module, name)`` it denotes.

    Generic bases (``Base[TPayload, TCapture]``) are unwrapped; a base the
    module neither imports nor defines resolves to nothing, which simply keeps
    it out of the closure.
    """
    symbols: dict[str, _Symbol] = _symbol_imports(module, known)
    aliases = _module_aliases(module, known)
    local = {child.name for child in module.tree.body if isinstance(child, ast.ClassDef)}
    resolved: set[_Symbol] = set()
    for base in node.bases:
        target = base.value if isinstance(base, ast.Subscript) else base
        if isinstance(target, ast.Name):
            if target.id in symbols:
                resolved.add(symbols[target.id])
            elif target.id in local:
                resolved.add((module.name, target.id))
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            owner = aliases.get(target.value.id)
            if owner is not None:
                resolved.add((owner, target.attr))
    return frozenset(resolved)


@dataclass(frozen=True, eq=False)
class _SurfaceClass:
    symbol: _Symbol
    node: ast.ClassDef
    bases: frozenset[_Symbol]
    module: _ShippedModule


def _class_index(modules: dict[str, _ShippedModule], known: frozenset[str]) -> dict[_Symbol, _SurfaceClass]:
    """Every top-level class in the shipped tree, keyed by ``(module, name)``."""
    index: dict[_Symbol, _SurfaceClass] = {}
    for module in modules.values():
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                symbol = (module.name, node.name)
                index[symbol] = _SurfaceClass(symbol, node, _base_symbols(node, module, known), module)
    return index


def _subclass_closure(index: dict[_Symbol, _SurfaceClass], roots: frozenset[_Symbol]) -> frozenset[_Symbol]:
    """Every class that derives, transitively, from one of ``roots``."""
    closure = set(roots)
    changed = True
    while changed:
        changed = False
        for symbol, entry in index.items():
            if symbol not in closure and entry.bases & closure:
                closure.add(symbol)
                changed = True
    return frozenset(closure)


def _leaf_surfaces(index: dict[_Symbol, _SurfaceClass], closure: frozenset[_Symbol]) -> tuple[_SurfaceClass, ...]:
    """The concrete end of each hierarchy: a class nothing in the closure extends."""
    extended = {base for symbol in closure for base in index[symbol].bases}
    return tuple(index[symbol] for symbol in sorted(closure - extended))


def _ancestry(
    index: dict[_Symbol, _SurfaceClass], leaf: _SurfaceClass, closure: frozenset[_Symbol]
) -> tuple[_SurfaceClass, ...]:
    """``leaf`` and every closure ancestor above it, nearest first."""
    seen: list[_SurfaceClass] = []
    queue: list[_Symbol] = [leaf.symbol]
    visited: set[_Symbol] = set()
    while queue:
        symbol = queue.pop(0)
        if symbol in visited or symbol not in closure:
            continue
        visited.add(symbol)
        entry = index[symbol]
        seen.append(entry)
        queue.extend(sorted(entry.bases))
    return tuple(seen)


# ---------------------------------------------------------------------------
# Verb classification: what each method of a surface actually touches
# ---------------------------------------------------------------------------


def _is_self_dispatch(receiver: ast.expr) -> bool:
    """Whether ``receiver`` is ``self`` or ``super()``, the two self-dispatch spellings."""
    if isinstance(receiver, ast.Name):
        return receiver.id == "self"
    return isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name) and receiver.func.id == "super"


def _called_attributes(body: Iterable[ast.stmt]) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(self-dispatched method names, every attribute called)``.

    ``self.x()`` and ``super().x()`` are the two self-dispatch spellings in
    this tree; both mean the method reaches whatever ``x`` reaches.
    """
    own: set[str] = set()
    called: set[str] = set()
    for statement in body:
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            called.add(node.func.attr)
            if _is_self_dispatch(node.func.value):
                own.add(node.func.attr)
    return frozenset(own), frozenset(called)


@dataclass(frozen=True)
class _MethodFacts:
    self_calls: frozenset[str]
    persists_directly: bool
    reads_directly: bool


def _method_facts(ancestry: tuple[_SurfaceClass, ...]) -> dict[str, _MethodFacts]:
    """Collect, for every method in the hierarchy, what it dispatches and touches.

    A name defined more than once (an override) is merged rather than shadowed:
    an override that stops persisting does not make the inherited producer
    invisible, and treating the union as the truth keeps the classification
    conservative in the direction that avoids false findings.
    """
    facts: dict[str, _MethodFacts] = {}
    for entry in ancestry:
        for node in entry.node.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            own, called = _called_attributes(node.body)
            previous = facts.get(node.name)
            facts[node.name] = _MethodFacts(
                self_calls=own | (previous.self_calls if previous else frozenset()),
                persists_directly=(_PERSIST_VERB in called - own) or bool(previous and previous.persists_directly),
                reads_directly=bool(_READ_VERBS & (called - own)) or bool(previous and previous.reads_directly),
            )
    return facts


def _closed_over(facts: dict[str, _MethodFacts], seeds: Iterable[str]) -> frozenset[str]:
    """Every method that reaches a seed through self-dispatch."""
    resolved = set(seeds)
    changed = True
    while changed:
        changed = False
        for name, method in facts.items():
            if name not in resolved and method.self_calls & resolved:
                resolved.add(name)
                changed = True
    return frozenset(resolved)


def _public(names: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(name for name in names if not name.startswith("_")))


@dataclass(frozen=True)
class _SurfaceVerbs:
    read: tuple[str, ...]
    write: tuple[str, ...]


def _surface_verbs(ancestry: tuple[_SurfaceClass, ...]) -> _SurfaceVerbs:
    """Split the hierarchy's public methods into consumers and producers."""
    facts = _method_facts(ancestry)
    writes = _closed_over(facts, (name for name, method in facts.items() if method.persists_directly))
    reads = _closed_over(facts, (name for name, method in facts.items() if method.reads_directly)) - writes
    return _SurfaceVerbs(read=_public(reads), write=_public(writes))


def _module_level_delegates(module: _ShippedModule, verbs: _SurfaceVerbs) -> tuple[frozenset[str], frozenset[str]]:
    """Top-level functions of the defining module that drive the surface for a caller.

    ``capture_expedientes`` constructs the service and calls its producer, so
    importing that function IS the write path even though the caller never
    spells the method name.
    """
    writers: set[str] = set()
    readers: set[str] = set()
    for node in module.tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        _, called = _called_attributes(node.body)
        if called & frozenset(verbs.write):
            writers.add(node.name)
        elif called & frozenset(verbs.read):
            readers.add(node.name)
    return frozenset(writers), frozenset(readers)


# ---------------------------------------------------------------------------
# Caller binding
# ---------------------------------------------------------------------------


def _spelled_attributes(tree: ast.Module) -> frozenset[str]:
    """Attribute names and string-literal identifiers a module really spells.

    Docstrings and ``__all__`` are cut out for the reason the reachability
    audit gives: prose naming a method is describing it, not calling it. A
    bare ``Name`` load is not counted either, because it says nothing about
    which object the name was reached on.
    """
    skipped = _non_reference_nodes(tree)
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(_string_reference_names(node.value))
    return frozenset(names)


def _loaded_names(tree: ast.Module) -> frozenset[str]:
    """Bare identifier loads, used only where no import can bind the name."""
    skipped = _non_reference_nodes(tree)
    return frozenset(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and id(node) not in skipped
    )


def _binds_surface(resolved: set[_Symbol], module: str, service: str) -> bool:
    return (module, service) in resolved


def _callers(
    surface: _SurfaceClass,
    verbs: _SurfaceVerbs,
    delegates: tuple[frozenset[str], frozenset[str]],
    modules: dict[str, _ShippedModule],
    known: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(reader modules, writer modules)`` among shipped production code.

    A module qualifies only when it binds the surface -- by importing the class
    itself, or by importing a top-level delegate of the defining module -- and
    then spells a verb of the matching half. The two-sided binding is what
    keeps a common method name like ``capture`` from clearing every surface in
    the tree at once.
    """
    write_delegates, read_delegates = delegates
    readers: set[str] = set()
    writers: set[str] = set()
    for name, module in modules.items():
        if name == surface.module.name:
            continue
        resolved = _resolved_symbol_uses(module, known)
        spelled = _spelled_attributes(module.tree)
        if any((surface.module.name, delegate) in resolved for delegate in write_delegates):
            writers.add(name)
        if any((surface.module.name, delegate) in resolved for delegate in read_delegates):
            readers.add(name)
        if not _binds_surface(resolved, surface.module.name, surface.node.name):
            continue
        if spelled & frozenset(verbs.write):
            writers.add(name)
        if spelled & frozenset(verbs.read):
            readers.add(name)
    return frozenset(readers), frozenset(writers)


def _outside_write_labels(spec: ShippedTreeSpec, surface: _SurfaceClass, verbs: _SurfaceVerbs) -> tuple[str, ...]:
    """Non-shipped trees that write the surface, for labelling only.

    A label answers the reader's first question -- "then why does this look
    alive?" -- and never clears the finding: neither ``tests`` nor ``dev/`` is
    installed, so neither can fill a store for a user. The class name is
    matched as a bare load here as well as an attribute, because the natural
    spelling in a test is ``DeudasService().capture(...)``.
    """
    labels: set[str] = set()
    write_verbs = frozenset(verbs.write)
    for corpus in spec.outside:
        for path in _iter_python_files(corpus.root):
            if corpus.test_modules_only and not _is_test_path(path, spec.src_root):
                continue
            try:
                tree = _parse(path)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            spelled = _spelled_attributes(tree)
            if surface.node.name in spelled | _loaded_names(tree) and spelled & write_verbs:
                labels.add(corpus.label)
    return tuple(sorted(labels))


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _script_reachable(spec: ShippedTreeSpec, modules: dict[str, _ShippedModule]) -> frozenset[str]:
    """Modules a declared console script reaches, the audit's strongest liveness."""
    known = frozenset(modules)
    edges = {name: _module_edges(module, known)[0] for name, module in modules.items()}
    companion_entries = tuple(entry for companion in spec.companions for entry in companion.entry_points)
    roots = [entry.module for entry in spec.entry_points] + [entry.module for entry in companion_entries]
    return _reachable(roots, modules, edges)


def _surface_findings(
    spec: ShippedTreeSpec,
    modules: dict[str, _ShippedModule],
    index: dict[_Symbol, _SurfaceClass],
    closure: frozenset[_Symbol],
    script_reach: frozenset[str],
) -> tuple[tuple[str, ...], tuple[WritePathFinding, ...]]:
    known = frozenset(modules)
    examined: list[str] = []
    findings: list[WritePathFinding] = []
    for leaf in _leaf_surfaces(index, closure):
        verbs = _surface_verbs(_ancestry(index, leaf, closure))
        if not verbs.read or not verbs.write:
            # Neither half classified: the hierarchy reaches its store through
            # something this pass does not model. Guessing would be noise.
            continue
        examined.append(f"{leaf.module.name}:{leaf.node.name}")
        delegates = _module_level_delegates(leaf.module, verbs)
        readers, writers = _callers(leaf, verbs, delegates, modules, known)
        live_readers = tuple(sorted(readers & script_reach))
        if writers or not live_readers:
            continue
        findings.append(
            WritePathFinding(
                path=_relative(leaf.module.path, spec),
                line=leaf.node.lineno,
                module=leaf.module.name,
                service=leaf.node.name,
                read_verbs=verbs.read,
                write_verbs=verbs.write,
                read_callers=live_readers,
                write_labels=_outside_write_labels(spec, leaf, verbs),
            ),
        )
    return tuple(examined), tuple(findings)


def scan_write_path_coverage(spec: ShippedTreeSpec, surface: PersistenceSurfaceSpec) -> WritePathResult:
    """Scan the tree ``spec`` describes for readable surfaces with no writer."""
    try:
        modules = _shipped_modules(spec)
    except SyntaxError as exc:
        return WritePathResult.error(f"shipped module does not parse: {exc.filename}:{exc.lineno}: {exc.msg}")
    except OSError as exc:
        return WritePathResult.error(f"shipped tree could not be read ({exc})")
    if surface.base_module not in modules:
        return WritePathResult.error(f"persistence-surface base module absent from the tree: {surface.base_module}")

    known = frozenset(modules)
    index = _class_index(modules, known)
    roots = frozenset((surface.base_module, name) for name in surface.base_classes)
    missing = sorted(name for _, name in roots - frozenset(index))
    if missing:
        return WritePathResult.error(
            f"persistence-surface base class(es) absent from {surface.base_module}: {', '.join(missing)}",
        )

    closure = _subclass_closure(index, roots)
    script_reach = _script_reachable(spec, modules)
    examined, findings = _surface_findings(spec, modules, index, closure, script_reach)
    if not examined:
        return WritePathResult.error(
            f"no persistence surface derived from {', '.join(sorted(name for _, name in roots))} could be classified",
        )
    if not findings:
        return WritePathResult.clean(surfaces_examined=examined)
    return WritePathResult.from_findings(surfaces_examined=examined, findings=findings)


def run_write_path_scan(repo_root: Path = REPO_ROOT) -> WritePathResult:
    """Scan this repository. The one entry point ``just audit-write-paths`` calls."""
    try:
        spec = ShippedTreeSpec.from_repository(repo_root)
    except (OSError, KeyError, ValueError) as exc:
        return WritePathResult.error(f"packaging config unreadable ({exc})")
    return scan_write_path_coverage(spec, PersistenceSurfaceSpec.for_repository())


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _write_labels(labels: tuple[str, ...]) -> str:
    return f"[written only by: {', '.join(labels)}]" if labels else "[no writer anywhere]"


def render_console_report(result: WritePathResult) -> str:
    """Render the operator-facing console report."""
    out = [f"write-path coverage: {result.headline()}"]
    if result.outcome is WritePathOutcome.ERROR:
        return out[0]
    if result.outcome is WritePathOutcome.CLEAN:
        out.extend(f"  ok  {name}" for name in result.surfaces_examined)
        return "\n".join(out)
    out.append("  surfaces a product command reads and no production code fills:")
    for finding in result.findings:
        out.append(f"    {finding.path}:{finding.line}  {finding.service}  {_write_labels(finding.write_labels)}")
        out.append(f"      write verbs never called: {', '.join(finding.write_verbs)}")
        out.append(f"      read verbs reached from:  {', '.join(finding.read_callers)}")
    return "\n".join(out)


def result_as_json(result: WritePathResult) -> str:
    """Serialise the result for machine consumers."""
    return json.dumps(
        {
            "outcome": result.outcome.value,
            "headline": result.headline(),
            "surfaces_examined": list(result.surfaces_examined),
            "findings": [
                {
                    "id": finding.id,
                    "path": finding.path,
                    "line": finding.line,
                    "module": finding.module,
                    "service": finding.service,
                    "read_verbs": list(finding.read_verbs),
                    "write_verbs": list(finding.write_verbs),
                    "read_callers": list(finding.read_callers),
                    "write_labels": list(finding.write_labels),
                }
                for finding in result.findings
            ],
            "reason": result.reason,
        },
        indent=2,
        ensure_ascii=False,
    )


def main() -> int:
    """Run the scan and print the report; exit 3 on findings, 1 on error, 0 when clean."""
    parser = argparse.ArgumentParser(
        description="Audit persistence surfaces a product command reads but no production code writes.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args()

    result = run_write_path_scan()
    print(result_as_json(result) if args.json else render_console_report(result))

    if result.outcome is WritePathOutcome.ERROR:
        return _EXIT_ERROR
    if result.outcome is WritePathOutcome.FINDINGS:
        return _EXIT_FINDINGS
    return 0


if __name__ == "__main__":
    sys.exit(main())
