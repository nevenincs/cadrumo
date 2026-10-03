"""Derive module, symbol and orphan-test findings from the resolved reachability facts."""

from __future__ import annotations

import ast
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dev.first_party_source import is_test_source
from dev.quality.source_import_analysis import (
    module_name_for,
    resolve_relative_import,
)

from .unreachable_definitions import _collection_uses, _definitions
from .unreachable_graph import _collapse_packages, _importers_of_span, resolved_symbol_uses
from .unreachable_memo import _walked, parse_module
from .unreachable_models import (
    _CONFIDENCE_BY_ORDER,
    _CONFIDENCE_ORDER,
    _DATA_SHAPED_KINDS,
    _TOP_LEVEL_KINDS,
    Confidence,
    ModuleFinding,
    ModuleReach,
    ShippedModule,
    SymbolFinding,
    SymbolKind,
    TestFinding,
    _Definition,
    _OutsideUse,
)
from .unreachable_policy import _DEV_LABEL
from .unreachable_references import _references, _string_tokens, assembled_reference_names
from .unreachable_tree import ShippedTreeSpec, iter_python_files, relative_to_repo


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
        findings.append(_unreachable_module_finding(name, spanned, spec, modules, outside, importers))
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
) -> tuple[tuple[SymbolFinding, ...], int, int]:
    """Return the symbol findings, the data-corpus clears, and the ``dev/`` clears.

    The two clear counts stay separate because they answer different
    questions: ``data_cleared`` is a registry declaration naming a member the
    import graph cannot see, while ``dev_cleared`` is a repository gate that
    consumes the symbol. Folding them into one number under the data name
    would misreport both.
    """
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
        literal_tokens |= set(assembled_reference_names(tree))
        resolved_uses |= resolved_symbol_uses(modules[name], frozenset(modules))
        self_uses[name] = _references(tree)
        whole_use |= _collection_uses(tree)

    usage = _SymbolUsage(member_names, literal_tokens, resolved_uses, self_uses, whole_use)
    findings: list[SymbolFinding] = []
    data_cleared = 0
    dev_cleared = 0
    audited_reach = sorted(
        name for name in runtime_reach if name == spec.package or name.startswith(spec.package + ".")
    )
    for name in audited_reach:
        module = modules[name]
        for definition in _definitions(module.tree):
            finding, data_clear, dev_clear = _definition_finding(
                name,
                module,
                definition,
                spec,
                usage,
                outside,
                data_tokens,
                declared_values,
            )
            data_cleared += data_clear
            dev_cleared += dev_clear
            if finding is not None:
                findings.append(finding)
    # An overloaded definition yields one row per signature; keep the first.
    return tuple({finding.id: finding for finding in findings}.values()), data_cleared, dev_cleared


def _test_subjects(test: ShippedModule, known: frozenset[str]) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Return ``(module subjects, (module, name) symbol subjects)`` a test imports from the shipped tree."""
    modules: set[str] = set()
    symbols: set[tuple[str, str]] = set()
    for node in _walked(test.tree):
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


def _support_hop_subjects(
    test: ShippedModule,
    known: frozenset[str],
    spec: ShippedTreeSpec,
    cache: dict[Path, tuple[frozenset[str], frozenset[tuple[str, str]]]],
) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Subjects a test reaches through a support module inside its own test package.

    Test modules are excluded from the shipped population, so a relative import
    of a sibling helper resolves to nothing and the test looks subjectless. On
    this tree 239 of 3334 test modules were skipped that way: they are not
    subjectless, they import a support module in their own tests package and
    THAT module imports the real code.

    The hop is applied ONLY to a test that resolved no shipped subject of its
    own, and it is one hop deep. That direction matters: it can only give a
    subjectless test some subjects, so the walk can newly REPORT a test whose
    support reaches nothing but dead code. It can never add a live subject to a
    test that is already reported and thereby silence an existing finding.
    """
    reached_modules: set[str] = set()
    reached_symbols: set[tuple[str, str]] = set()
    for node in _walked(test.tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = resolve_relative_import(test.name, test.is_package, node.level, node.module)
        if base is None or base in known:
            continue
        for alias in node.names:
            for candidate in (f"{base}.{alias.name}", base):
                _support_candidate_subjects(candidate, spec, known, cache, reached_modules, reached_symbols)
    return frozenset(reached_modules), frozenset(reached_symbols)


def _test_findings(
    spec: ShippedTreeSpec,
    known: frozenset[str],
    module_findings: tuple[ModuleFinding, ...],
    symbol_findings: tuple[SymbolFinding, ...],
) -> tuple[TestFinding, ...]:
    """Test modules under the package whose every shipped subject is already a finding."""
    dead_roots = tuple(f.module for f in module_findings if f.reach is ModuleReach.UNREACHABLE)
    dead_symbols = {(f.module, f.name): f.confidence for f in symbol_findings}
    findings: list[TestFinding] = []
    support_cache: dict[Path, tuple[frozenset[str], frozenset[tuple[str, str]]]] = {}
    for path in iter_python_files(spec.src_root / spec.package):
        finding = _test_finding_for_path(path, spec, known, support_cache, dead_roots, dead_symbols)
        if finding is not None:
            findings.append(finding)
    return tuple(findings)


def _test_finding_for_path(
    path: Path,
    spec: ShippedTreeSpec,
    known: frozenset[str],
    support_cache: dict[Path, tuple[frozenset[str], frozenset[tuple[str, str]]]],
    dead_roots: tuple[str, ...],
    dead_symbols: dict[tuple[str, str], Confidence],
) -> TestFinding | None:
    """Resolve one eligible test's subjects before classifying the orphan finding."""
    if not is_test_source(path, root=spec.src_root) or not path.name.startswith("test_"):
        return None
    test = _read_test_module(path, spec)
    if test is None:
        return None
    modules, symbols = _test_subjects(test, known)
    if not modules and not symbols:
        modules, symbols = _support_hop_subjects(test, known, spec, support_cache)
    if not modules and not symbols:
        return None
    return _orphan_test_finding(test, spec, modules, symbols, dead_roots, dead_symbols)


def _unreachable_module_finding(
    name: str,
    spanned: int,
    spec: ShippedTreeSpec,
    modules: dict[str, ShippedModule],
    outside: _OutsideUse,
    importers: Mapping[str, frozenset[str]],
) -> ModuleFinding:
    """Combine the unreachable package span with all outside-use labels."""
    module = modules[name]
    rendered = relative_to_repo(module.path.parent if module.is_package else module.path, spec)
    if module.is_package:
        rendered += "/"
    used_by: set[str] = set()
    for member in modules:
        if member == name or member.startswith(name + "."):
            used_by.update(outside.labels_for_module(member))
    return ModuleFinding(
        rendered,
        name,
        ModuleReach.UNREACHABLE,
        spanned,
        tuple(sorted(used_by)),
        _importers_of_span(name, modules, importers),
    )


@dataclass(frozen=True)
class _SymbolUsage:
    """Resolved Python uses consulted before data and development consumers."""

    member_names: set[str]
    literal_tokens: set[str]
    resolved_uses: set[tuple[str, str]]
    self_uses: dict[str, set[str]]
    whole_use: set[str]


def _python_reaches_definition(name: str, definition: _Definition, usage: _SymbolUsage) -> bool:
    """Apply exact top-level references before member and enum-collection uses."""
    if definition.kind in _TOP_LEVEL_KINDS:
        if (name, definition.name) in usage.resolved_uses or definition.name in usage.self_uses[name]:
            return True
        if definition.name in usage.literal_tokens:
            return True
    elif definition.name in usage.member_names:
        return True
    return definition.kind is SymbolKind.ENUM_MEMBER and definition.owner in usage.whole_use


def _data_reaches_definition(
    definition: _Definition,
    data_tokens: frozenset[str],
    declared_values: frozenset[str],
) -> bool:
    """Clear data-shaped members by tokens or values, and classes by whole parsed values."""
    if definition.kind in _DATA_SHAPED_KINDS and (
        definition.name in data_tokens or (definition.value and definition.value in declared_values)
    ):
        return True
    # A class binding must equal a complete parsed value; prose cannot clear it.
    return definition.kind is SymbolKind.CLASS and definition.name in declared_values


def _definition_finding(
    name: str,
    module: ShippedModule,
    definition: _Definition,
    spec: ShippedTreeSpec,
    usage: _SymbolUsage,
    outside: _OutsideUse,
    data_tokens: frozenset[str],
    declared_values: frozenset[str],
) -> tuple[SymbolFinding | None, int, int]:
    """Keep Python, data and resolved dev clears separate and in their original order."""
    if _python_reaches_definition(name, definition, usage):
        return None, 0, 0
    if _data_reaches_definition(definition, data_tokens, declared_values):
        return None, 1, 0
    labels = outside.labels_for_name(definition.name)
    # Tests annotate findings; only an exact development-tool reference clears.
    if definition.kind in _TOP_LEVEL_KINDS and _DEV_LABEL in outside.resolved_labels(name, definition.name):
        return None, 0, 1
    return (
        SymbolFinding(
            path=relative_to_repo(module.path, spec),
            line=definition.line,
            kind=definition.kind,
            name=definition.name,
            qualname=definition.qualname,
            used_by=labels,
            module=name,
        ),
        0,
        0,
    )


def _support_candidate_subjects(
    candidate: str,
    spec: ShippedTreeSpec,
    known: frozenset[str],
    cache: dict[Path, tuple[frozenset[str], frozenset[tuple[str, str]]]],
    reached_modules: set[str],
    reached_symbols: set[tuple[str, str]],
) -> None:
    """Read only the candidate test module and package, without another support hop."""
    path = spec.src_root / Path(*candidate.split("."))
    for target in (path.with_suffix(".py"), path / "__init__.py"):
        _support_target_subjects(target, candidate, spec, known, cache, reached_modules, reached_symbols)


def _support_target_subjects(
    target: Path,
    candidate: str,
    spec: ShippedTreeSpec,
    known: frozenset[str],
    cache: dict[Path, tuple[frozenset[str], frozenset[tuple[str, str]]]],
    reached_modules: set[str],
    reached_symbols: set[tuple[str, str]],
) -> None:
    """Cache a readable test support module's directly imported shipped subjects."""
    if not target.is_file() or not is_test_source(target, root=spec.src_root):
        return
    found = cache.get(target)
    if found is None:
        try:
            support = ShippedModule(candidate, target, target.name == "__init__.py", parse_module(target))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return
        # One support module serves many tests here, so parsing
        # it once per importer dominated the walk.
        found = _test_subjects(support, known)
        cache[target] = found
    reached_modules.update(found[0])
    reached_symbols.update(found[1])


def _read_test_module(path: Path, spec: ShippedTreeSpec) -> ShippedModule | None:
    """Refuse malformed test sources and report a file that vanished during enumeration."""
    try:
        tree = parse_module(path)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise SystemExit(
            f"{path} does not parse, so it could not be checked for testing only dead code: {error}"
        ) from error
    except OSError:
        sys.stderr.write(f"unreachable-code: {path} vanished during the test walk and was not checked" + chr(10))
        return None
    return ShippedModule(module_name_for(path, src_root=spec.src_root), path, False, tree)


def _module_is_dead(name: str, dead_roots: tuple[str, ...]) -> bool:
    return any(name == root or name.startswith(root + ".") for root in dead_roots)


def _dead_symbol_pairs(
    symbols: frozenset[tuple[str, str]],
    dead_roots: tuple[str, ...],
    dead_symbols: dict[tuple[str, str], Confidence],
) -> set[tuple[str, str]]:
    return {(m, n) for m, n in symbols if not _module_is_dead(m, dead_roots) and (m, n) in dead_symbols}


def _orphan_test_finding(
    test: ShippedModule,
    spec: ShippedTreeSpec,
    modules: frozenset[str],
    symbols: frozenset[tuple[str, str]],
    dead_roots: tuple[str, ...],
    dead_symbols: dict[tuple[str, str], Confidence],
) -> TestFinding | None:
    """Report a test only when every direct or one-hop shipped subject is already dead."""
    dead_modules = set(modules) | {m for m, _ in symbols if _module_is_dead(m, dead_roots)}
    dead_pairs = _dead_symbol_pairs(symbols, dead_roots, dead_symbols)
    live_pairs = {(m, n) for m, n in symbols if not _module_is_dead(m, dead_roots)} - dead_pairs
    if all(_module_is_dead(m, dead_roots) for m in modules) and not live_pairs:
        subjects = tuple(sorted(dead_modules)) + tuple(sorted(f"{m}:{n}" for m, n in dead_pairs))
        weakest = max(
            (_CONFIDENCE_ORDER[dead_symbols[pair]] for pair in dead_pairs),
            default=_CONFIDENCE_ORDER[Confidence.EXACT],
        )
        return TestFinding(relative_to_repo(test.path, spec), test.name, subjects, _CONFIDENCE_BY_ORDER[weakest])
    return None
