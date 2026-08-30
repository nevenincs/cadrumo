"""Census of the registry load closure: what a load imports, what it runs, and who runs the rest.

Answers one question the campaign left open -- *of everything a sanctioned
registry load reaches, what actually executes, and for the remainder, which
entry point owns it?* Two prior design reviews each missed a registry module a
keyword search did not surface, so the denominator here is derived from the
import graph and the package directory rather than from whichever modules a
search returned.

Three measurements, kept separate because they answer different questions:

**The static load closure** is what a sanctioned load *imports*: every module
transitively reachable by runtime import from :data:`LOAD_ENTRY_POINTS`.
``TYPE_CHECKING``-guarded imports are excluded, because they never execute. The
closure is checkable against reality -- its registry members equal the registry
entries in ``sys.modules`` after a real load -- and it is the honest denominator
for "reachable".

**The traced execution sets** are what a load *runs*: the modules in which a
function body starts during one traced entry point, recorded with
:mod:`sys.monitoring`. Imports happen outside the traced window deliberately, so
a module that only contributes definitions records nothing. That is a
measurement boundary, not a verdict, and the distinction is load-bearing here:
``_validate_cache`` publishes three cache objects bound at import by
``_validate`` and defines no function of its own, so it can never appear in any
execution set however live it is.

**The reference map** is who *can* run a module: which production and test
modules name a symbol the package facade owns for it. A registry module is
almost never imported directly from outside the package -- the architecture
rules route every cross-package import through the facade -- so module-level
importer counts systematically read zero for modules with real consumers. The
map is symbol-level for exactly that reason.

What this cannot see, stated rather than assumed away:

- **Dynamic import targets that are not literal strings.** :func:`dynamic_import_sites`
  harvests ``import_module("literal")`` edges the AST-only graph misses -- the
  registry facade's own PEP 562 lazy exports are built this way -- and reports
  every non-literal target as UNRESOLVED. There is no sanctioned inventory of
  first-party function-local edges to check those against, so an unresolved site
  is reported on the graph difference alone and left unclassified; it is never
  implied that a list cleared it.
- **Attribute access through a module object.** ``from ... import registry``
  followed by ``registry.symbol`` reads as a package import, not a symbol
  reference.
- **Reflective lookup.** ``getattr(registry, name)`` over a computed name.

A module the reference map finds nowhere is therefore a dead CANDIDATE, never a
dead verdict; :func:`unreferenced_modules` returns candidates, and the reviewed
call lives in :mod:`dev.registry.load_census_classification`. The first run of
this scanner produced two candidates -- ``_constructs`` and ``_handoff_paths`` --
and both turned out to be consumed by registry gates importing them through the
facade, which module-level importer counting could not see. That is the whole
reason the reference map exists.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import grimp

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

SOURCE_ROOT: Final[Path] = REPO_ROOT / "src"
ROOT_PACKAGE: Final[str] = "cadrumo"
REGISTRY_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry"
REGISTRY_DIR: Final[Path] = SOURCE_ROOT / "cadrumo" / "domain" / "calculations" / "registry"

#: The sanctioned way to load the registry: the validated authority, plus the
#: package facade every cross-package consumer must route through to reach it.
#: ``ValidatedRegistryAuthority.load`` is the only production load entry point
#: the authority-flow rule admits.
LOAD_ENTRY_POINTS: Final[tuple[str, ...]] = (
    REGISTRY_PACKAGE,
    f"{REGISTRY_PACKAGE}.authority",
)

#: Directories scanned for symbol references. ``dev`` is included because the
#: registry conformance and maintenance tooling is a real consumer -- the live
#: parity oracle catalogue is assembled there and nowhere else -- so omitting it
#: would report live oracle modules as unreferenced.
REFERENCE_SCAN_ROOTS: Final[tuple[Path, ...]] = (SOURCE_ROOT / "cadrumo", REPO_ROOT / "dev")

#: Cache directories whose redirection forces a cold load. Both are settings
#: fields; pointing them at empty directories denies the loader its compiled
#: tree and denies the validator its persisted verdict.
COLD_REGIME_ENV: Final[tuple[str, ...]] = (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_VALIDATION_VERDICT_CACHE_DIR",
)

TRACE_REGIMES: Final[tuple[str, ...]] = ("warm", "cold", "inspection_snapshot")


class LoadCensusError(RuntimeError):
    """Raised when the census cannot be computed from the tree as it stands."""


def is_test_module(module: str) -> bool:
    """Return whether ``module`` belongs to the test surface rather than production.

    Returns:
        ``True`` for test packages, ``test_*`` modules and ``conftest`` modules.
    """
    parts = module.split(".")
    return "tests" in parts or parts[-1].startswith("test_") or parts[-1] == "conftest"


def build_runtime_graph() -> grimp.ImportGraph:
    """Build the first-party import graph as it exists at RUNTIME.

    ``TYPE_CHECKING``-guarded imports are excluded so the graph describes what a
    running interpreter imports, matching the project's import-linter contract.

    Returns:
        The :class:`grimp.ImportGraph` for the ``cadrumo`` root package.
    """
    # Caching is off deliberately: grimp keys its cache on file mtimes and does not
    # evict a module whose file was deleted, so after any relocation the cached graph
    # still carries the retired module and the closure gate reds on a ghost. A census
    # of what a running interpreter imports has to be read from the tree, not a cache.
    return grimp.build_graph(
        ROOT_PACKAGE,
        include_external_packages=False,
        exclude_type_checking_imports=True,
        cache_dir=None,
    )


def static_load_closure(graph: grimp.ImportGraph) -> frozenset[str]:
    """Return every module a sanctioned registry load imports, transitively.

    Args:
        graph: The runtime import graph.

    Returns:
        The entry points and everything upstream of them.

    Raises:
        LoadCensusError: If a declared entry point is absent from the graph.
    """
    closure: set[str] = set()
    for entry in LOAD_ENTRY_POINTS:
        if entry not in graph.modules:
            raise LoadCensusError(f"sanctioned load entry point {entry!r} is not in the import graph")
        closure.add(entry)
        closure |= graph.find_upstream_modules(entry)
    return frozenset(closure)


def registry_package_modules() -> frozenset[str]:
    """Return every production module file in the registry package.

    Derived from the directory rather than from the facade, so a module the
    facade never mentions is still counted.

    Returns:
        Dotted module names, ``conftest`` excluded.
    """
    modules: set[str] = set()
    for path in scan_directory(REGISTRY_DIR, pattern="*.py"):
        stem = path.stem
        if stem == "conftest":
            continue
        modules.add(REGISTRY_PACKAGE if stem == "__init__" else f"{REGISTRY_PACKAGE}.{stem}")
    return frozenset(modules)


def dynamic_reach(graph: grimp.ImportGraph, closure: frozenset[str]) -> frozenset[str]:
    """Return modules the closure reaches only through a resolved dynamic import.

    An AST import graph cannot represent ``import_module(name)``, so a module
    imported that way is absent from the static closure however certainly the
    load path reaches it. The cross-domain snapshot checks are the live case:
    ``_snapshot`` imports the renta routing-integrity modules by name for their
    registration side effect, and the import-linter contract sanctions exactly
    that edge while the graph cannot see it.

    Args:
        graph: The runtime import graph.
        closure: The static load closure.

    Returns:
        The dynamically reached modules and everything statically upstream of
        them, minus what the closure already holds.
    """
    reached: set[str] = set()
    for site in dynamic_import_sites():
        if site.target is None or site.module not in closure:
            continue
        if site.target not in graph.modules:
            continue
        reached.add(site.target)
        reached |= graph.find_upstream_modules(site.target)
    return frozenset(reached - closure)


def census_universe(graph: grimp.ImportGraph) -> frozenset[str]:
    """Return every module this census must classify.

    The union of three terms: the static load closure, what the closure reaches
    dynamically, and the registry package. The last matters most -- a registry
    module the load never imports is exactly the case the census exists to
    catch, and it is invisible from the closure alone.

    Args:
        graph: The runtime import graph.

    Returns:
        Production modules only; test modules are out of scope.
    """
    closure = static_load_closure(graph)
    members = closure | dynamic_reach(graph, closure) | registry_package_modules()
    return frozenset(m for m in members if not is_test_module(m))


@dataclass(frozen=True)
class DynamicImportSite:
    """One ``import_module`` call site and what it resolves to, if anything."""

    module: str
    lineno: int
    target: str | None

    @property
    def resolved(self) -> bool:
        """Whether the call site names a literal first-party module.

        Returns:
            ``True`` when a literal target was recovered.
        """
        return self.target is not None


def _module_name_for(path: Path) -> str | None:
    for root in REFERENCE_SCAN_ROOTS:
        try:
            relative = path.resolve().relative_to(root.parent)
        except ValueError:
            continue
        parts = list(relative.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)
    return None


def _iter_source_files() -> Iterable[Path]:
    for root in REFERENCE_SCAN_ROOTS:
        yield from scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None


def _absolute(target: str, package: str | None) -> str | None:
    if not target.startswith("."):
        return target
    return None if package is None else f"{package}{target}"


def _literal_dynamic_target(node: ast.Call, package: str | None) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return _absolute(first.value, package)


def _string_tuple_constants(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Collect module-level names bound to a tuple or list of string literals."""
    constants: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        targets: list[ast.expr]
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, (ast.Tuple, ast.List)):
            continue
        items = [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if len(items) != len(value.elts) or not items:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = tuple(items)
    return constants


def _is_import_module_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    return name == "import_module"


def _loop_resolved_targets(tree: ast.Module, constants: Mapping[str, tuple[str, ...]]) -> dict[int, tuple[str, ...]]:
    """Resolve ``for name in CONSTANT: import_module(name)`` to the constant's members.

    This is the one indirection worth following, because it is how every
    production dynamic-import site in this tree is written: a module-level tuple
    of module paths, iterated, each imported for its registration side effect.
    Reading the tuple recovers targets an argument-only scan reports as
    unknowable, and the cross-domain snapshot checks are exactly this shape.
    """
    resolved: dict[int, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Name):
            continue
        members = constants.get(node.iter.id)
        variable = node.target.id if isinstance(node.target, ast.Name) else None
        if members is None or variable is None:
            continue
        for inner in ast.walk(node):
            if _is_import_module_call(inner) and inner.args:
                argument = inner.args[0]
                if isinstance(argument, ast.Name) and argument.id == variable:
                    resolved[inner.lineno] = members
    return resolved


def dynamic_import_sites(*, production_only: bool = True) -> tuple[DynamicImportSite, ...]:
    """Harvest every ``import_module`` call site the AST import graph cannot represent.

    Two shapes are resolved: a literal argument (relative literals are resolved
    against the calling package, which is how the registry facade's PEP 562
    lazy export table is written), and a loop over a module-level tuple of
    module paths. Anything else -- an f-string, a comprehension over a mapping,
    a computed name -- is recorded with ``target=None`` and stays unclassified.

    Args:
        production_only: Restrict to production modules. Dynamic imports inside
            tests cannot affect any load closure, and reporting them buries the
            handful that can.

    Returns:
        One record per resolved target, or one per unresolved call site.
    """
    sites: list[DynamicImportSite] = []
    for path in _iter_source_files():
        module = _module_name_for(path)
        tree = _parse(path)
        if module is None or tree is None:
            continue
        if production_only and is_test_module(module):
            continue
        package = module.rsplit(".", 1)[0] if path.name != "__init__.py" else module
        loop_targets = _loop_resolved_targets(tree, _string_tuple_constants(tree))
        for node in ast.walk(tree):
            if not _is_import_module_call(node):
                continue
            assert isinstance(node, ast.Call)
            members = loop_targets.get(node.lineno)
            if members is not None:
                sites.extend(DynamicImportSite(module, node.lineno, _absolute(member, package)) for member in members)
                continue
            sites.append(DynamicImportSite(module, node.lineno, _literal_dynamic_target(node, package)))
    return tuple(sites)


def facade_symbol_owners() -> Mapping[str, str]:
    """Map each symbol the registry facade publishes to the module that defines it.

    Both publication mechanisms are read: the eager ``from ._module import ...``
    statements and the ``_LAZY_EXPORTS`` table the PEP 562 ``__getattr__``
    resolves through. Omitting the second would drop the oracle and live-parity
    modules, which are published only lazily.

    Returns:
        Symbol name to owning dotted module name.

    Raises:
        LoadCensusError: If the facade cannot be parsed.
    """
    facade = REGISTRY_DIR / "__init__.py"
    tree = _parse(facade)
    if tree is None:
        raise LoadCensusError(f"cannot parse the registry facade at {facade}")
    owners: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                owners[alias.asname or alias.name] = f"{REGISTRY_PACKAGE}.{node.module}"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_LAZY_EXPORTS" and isinstance(node.value, ast.Dict):
                    for key, value in zip(node.value.keys, node.value.values, strict=True):
                        if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                            owners[str(key.value)] = f"{REGISTRY_PACKAGE}.{str(value.value).lstrip('.')}"
    if not owners:
        raise LoadCensusError("the registry facade published no symbols; the parser is reading it wrongly")
    return owners


@dataclass(frozen=True)
class ReferenceMap:
    """Who names each registry module's facade symbols, split by surface."""

    production: Mapping[str, frozenset[str]] = field(default_factory=dict)
    tests: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def consumers(self, module: str) -> frozenset[str]:
        """Return every module naming a symbol ``module`` owns.

        Args:
            module: The owning dotted module name.

        Returns:
            Production and test consumers combined.
        """
        return self.production.get(module, frozenset()) | self.tests.get(module, frozenset())


def build_reference_map(owners: Mapping[str, str] | None = None) -> ReferenceMap:
    """Find every module that imports a registry facade symbol, by owning module.

    Args:
        owners: Symbol-to-module map; computed from the facade when omitted.

    Returns:
        The reference map, with production and test consumers kept apart so a
        module reachable only from a quality gate is visible as such.
    """
    resolved = dict(owners or facade_symbol_owners())
    production: dict[str, set[str]] = {}
    tests: dict[str, set[str]] = {}
    for path in _iter_source_files():
        module = _module_name_for(path)
        tree = _parse(path)
        if module is None or tree is None:
            continue
        # The package's own production modules reach siblings by direct import,
        # which the graph already records. Its TESTS reach them through the
        # facade (``from .. import symbol``), so they are consumers this map
        # must see -- excluding them once reported two live modules as dead.
        if module.startswith(REGISTRY_PACKAGE + ".") and not is_test_module(module):
            continue
        bucket = tests if is_test_module(module) else production
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported_from = node.module or ""
            reaches_facade = imported_from.endswith("calculations.registry") or (
                node.level > 0 and imported_from == "" and module.startswith(REGISTRY_PACKAGE)
            )
            if not reaches_facade:
                continue
            for alias in node.names:
                owner = resolved.get(alias.name)
                if owner is not None:
                    bucket.setdefault(owner, set()).add(module)
    return ReferenceMap(
        production={k: frozenset(v) for k, v in production.items()},
        tests={k: frozenset(v) for k, v in tests.items()},
    )


def unreferenced_modules(graph: grimp.ImportGraph, reference_map: ReferenceMap) -> frozenset[str]:
    """Return registry modules nothing outside themselves and the facade reaches.

    A module qualifies only when three independent signals agree: no production
    module inside the package imports it, no module anywhere imports a symbol the
    facade owns for it, and no test imports it directly. These are DEAD
    CANDIDATES for review, not a verdict -- see this module's docstring for what
    the instrument cannot see.

    Args:
        graph: The runtime import graph.
        reference_map: The symbol-level reference map.

    Returns:
        Candidate modules, facade excluded.
    """
    candidates: set[str] = set()
    for module in sorted(registry_package_modules()):
        if module == REGISTRY_PACKAGE:
            continue
        importers = graph.find_modules_that_directly_import(module)
        in_package = {i for i in importers if i.startswith(REGISTRY_PACKAGE + ".") and not is_test_module(i)}
        direct_tests = {i for i in importers if is_test_module(i)}
        if not in_package and not direct_tests and not reference_map.consumers(module):
            candidates.add(module)
    return frozenset(candidates)


def _trace_script(regime: str) -> str:
    snapshot_block = ""
    if regime == "inspection_snapshot":
        snapshot_block = """
        from cadrumo.domain.calculations.registry.snapshot import build_snapshot

        for modelo in authority.modelos:
            for period in ("1T", "0A", "ANUAL", "1"):
                try:
                    build_snapshot(
                        modelo,
                        authority.catalogues,
                        source_root=source_root,
                        filing_year=FILING_YEAR,
                        period=period,
                    )
                except Exception:
                    continue
                break
"""
    return f"""
import json
import sys
from pathlib import Path

SOURCE = Path({str(SOURCE_ROOT)!r}).resolve()
TOOL = sys.monitoring
TOOL_ID = TOOL.PROFILER_ID
FILING_YEAR = 2024


def module_for(filename):
    try:
        path = Path(filename).resolve()
        relative = path.relative_to(SOURCE)
    except (OSError, ValueError):
        return None
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def main():
    from cadrumo.core.resources._boundary import bundled_path
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

    root = bundled_path("registry", "aeat")
    source_root = bundled_path()
    executed = set()

    def on_start(code, offset):
        executed.add(code.co_filename)
        return TOOL.DISABLE

    prelude = {regime!r} == "inspection_snapshot"
    if prelude:
        authority = ValidatedRegistryAuthority.load(root, source_root=source_root)

    TOOL.use_tool_id(TOOL_ID, "load-census")
    TOOL.register_callback(TOOL_ID, TOOL.events.PY_START, on_start)
    TOOL.set_events(TOOL_ID, TOOL.events.PY_START)
    try:
        if not prelude:
            authority = ValidatedRegistryAuthority.load(root, source_root=source_root)
{snapshot_block}
    finally:
        TOOL.set_events(TOOL_ID, 0)
        TOOL.free_tool_id(TOOL_ID)

    modules = sorted({{m for f in executed if (m := module_for(f)) and m.startswith("cadrumo")}})
    Path(sys.argv[1]).write_text(json.dumps(modules, indent=2), encoding="utf-8")


main()
"""


def trace_regime(regime: str) -> frozenset[str]:
    """Run one traced entry point in a subprocess and return the modules that executed.

    The trace records modules in which a function body STARTS, so a module whose
    only contribution is import-time definitions records nothing. Imports are
    performed outside the traced window on purpose -- otherwise every closure
    member would register and the measurement would answer nothing.

    Args:
        regime: One of :data:`TRACE_REGIMES`.

    Returns:
        Dotted module names that executed.

    Raises:
        LoadCensusError: For an unknown regime or a failed trace.
    """
    if regime not in TRACE_REGIMES:
        raise LoadCensusError(f"unknown trace regime {regime!r}; expected one of {TRACE_REGIMES}")
    with tempfile.TemporaryDirectory() as workspace:
        area = Path(workspace)
        output = area / "executed.json"
        script = area / "trace.py"
        script.write_text(_trace_script(regime), encoding="utf-8", newline="\n")
        environment = None
        if regime == "cold":
            import os

            environment = dict(os.environ)
            for index, variable in enumerate(COLD_REGIME_ENV):
                isolated = area / f"cold-{index}"
                isolated.mkdir()
                environment[variable] = str(isolated)
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(script), str(output)],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not output.exists():
            raise LoadCensusError(f"{regime} trace failed:\n{completed.stderr}")
        return frozenset(json.loads(output.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class CensusReport:
    """One census run: the derived universe, the reviewed classification, the residue."""

    universe: frozenset[str]
    closure: frozenset[str]
    registry_modules: frozenset[str]
    unclassified: tuple[str, ...]
    stale_rules: tuple[str, ...]
    dead_candidates: frozenset[str]
    undeclared_dead_candidates: tuple[str, ...]
    unresolved_dynamic_sites: tuple[DynamicImportSite, ...]

    @property
    def clean(self) -> bool:
        """Whether every derived member carries exactly one reviewed classification.

        Returns:
            ``True`` when nothing is unclassified, no rule is stale, and every
            dead candidate has been adjudicated.
        """
        return not (self.unclassified or self.stale_rules or self.undeclared_dead_candidates)


def run_census() -> CensusReport:
    """Compute the census against the working tree.

    Returns:
        The report. Trace measurements are deliberately excluded: classification
        completeness is a static property, and binding a gate to a two-regime
        load trace would make it slow without making it stricter.
    """
    from .load_census_classification import classify_universe, stale_rules

    graph = build_runtime_graph()
    closure = static_load_closure(graph)
    registry_modules = registry_package_modules()
    universe = census_universe(graph)
    reference_map = build_reference_map()
    candidates = unreferenced_modules(graph, reference_map)
    classified = classify_universe(universe)
    declared_dead = {module for module, entry in classified.items() if entry.classification == "dead"}
    return CensusReport(
        universe=universe,
        closure=closure,
        registry_modules=registry_modules,
        unclassified=tuple(sorted(m for m in universe if m not in classified)),
        stale_rules=stale_rules(universe),
        dead_candidates=candidates,
        undeclared_dead_candidates=tuple(sorted(candidates - declared_dead)),
        unresolved_dynamic_sites=tuple(site for site in dynamic_import_sites() if not site.resolved),
    )


def _render(report: CensusReport, traces: Mapping[str, frozenset[str]]) -> str:
    lines = [
        f"static load closure          : {len(report.closure)}",
        f"registry package modules     : {len(report.registry_modules)}",
        f"census universe              : {len(report.universe)}",
        f"unclassified                 : {len(report.unclassified)}",
        f"stale classification rules   : {len(report.stale_rules)}",
        f"dead candidates              : {len(report.dead_candidates)}",
        f"unresolved dynamic sites     : {len(report.unresolved_dynamic_sites)}",
    ]
    for regime, executed in traces.items():
        registry_executed = {m for m in executed if m.startswith(REGISTRY_PACKAGE)}
        lines.append(f"trace[{regime}]: {len(executed)} modules, {len(registry_executed)} in the registry package")
    for label, members in (
        ("UNCLASSIFIED", report.unclassified),
        ("STALE RULE", report.stale_rules),
        ("DEAD CANDIDATE NOT ADJUDICATED", report.undeclared_dead_candidates),
    ):
        lines.extend(f"  {label}: {member}" for member in members)
    lines.extend(
        f"  UNRESOLVED DYNAMIC IMPORT: {site.module}:{site.lineno}" for site in report.unresolved_dynamic_sites
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the census and report.

    Args:
        argv: Command-line arguments; ``sys.argv`` when omitted.

    Returns:
        ``0`` when every derived member is classified, ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trace", action="store_true", help="also run the load traces (slow; cold rebuilds caches)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    arguments = parser.parse_args(argv)

    report = run_census()
    traces = {regime: trace_regime(regime) for regime in TRACE_REGIMES} if arguments.trace else {}
    if arguments.json:
        print(
            json.dumps(
                {
                    "closure": sorted(report.closure),
                    "registry_modules": sorted(report.registry_modules),
                    "universe": sorted(report.universe),
                    "unclassified": list(report.unclassified),
                    "stale_rules": list(report.stale_rules),
                    "dead_candidates": sorted(report.dead_candidates),
                    "undeclared_dead_candidates": list(report.undeclared_dead_candidates),
                    "unresolved_dynamic_sites": [
                        {"module": s.module, "lineno": s.lineno} for s in report.unresolved_dynamic_sites
                    ],
                    "traces": {regime: sorted(executed) for regime, executed in traces.items()},
                },
                indent=2,
            )
        )
    else:
        print(_render(report, traces))
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
