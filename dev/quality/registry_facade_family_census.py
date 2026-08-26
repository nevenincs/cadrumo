"""Deterministically census the exact registry family mechanically relocated by c941.

This is deliberately not a general import scanner.  Its only candidate set is
the rename set recorded by c94133f295; the checked-in matrix then receives a
separate, human-reviewed semantic adjudication for every one of those rows.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RELOCATION_COMMIT: Final = "c94133f29516b12e3529f3d154c31592562f6198"
REGISTRY_PATH: Final = "src/cadrumo/domain/calculations/registry"
MATRIX_VERSION: Final = 2
DISPOSITIONS: Final = (
    "keep_public",
    "hard_move_complete",
    "privatize_external_elimination",
    "delete",
)
RAG_RESULT_FIELDS: Final = frozenset({"path", "line_start", "line_end", "node_type", "symbol"})
EVIDENCE_FILE_SUFFIXES: Final = frozenset({".json", ".md", ".py", ".rst", ".toml", ".yaml", ".yml"})
EVIDENCE_ROOTS: Final = ("src", "dev", "docs")
TERMINAL_STATES: Final = {
    "keep_public": frozenset({"public_local_definitions_only"}),
    "hard_move_complete": frozenset(
        {
            "public_local_definitions_only",
            "retired_after_hard_move",
            "schema_local_definitions_only",
        },
    ),
    "privatize_external_elimination": frozenset({"private_same_package_only"}),
    "delete": frozenset({"deleted_no_surface"}),
}
CONSUMER_CATEGORIES: Final = (
    "production",
    "test",
    "fixture",
    "documentation",
    "tooling",
    "annotation",
    "registration",
    "dynamic_target",
    "package_attribute",
    "transitive",
)
ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "dev/quality/registry_facade_family_census.v1.json"
PLAN_PATH = ROOT / ".vault/plan/2026-08-11-tui-architecture-plan.md"


@dataclass(frozen=True, slots=True)
class RelocatedFamily:
    """One exact c941 private-to-public module rename."""

    similarity: int
    old_path: str
    new_path: str

    @property
    def old_module(self) -> str:
        """Return the old Python module name."""
        return _module_name(self.old_path)

    @property
    def new_module(self) -> str:
        """Return the current Python module name."""
        return _module_name(self.new_path)


@dataclass(frozen=True, slots=True)
class EvidenceFile:
    """One authored file read from the current census tree."""

    path: str
    text: str


@dataclass(frozen=True, slots=True)
class EvidenceCensus:
    """Derived current-tree consumer and parser measurements."""

    consumers: dict[str, dict[str, list[str]]]
    dynamic_imports: dict[str, list[dict[str, str]]]
    measurements: dict[str, int]


def _git(*arguments: str) -> str:
    """Run one fixed, repository-local read-only git query."""
    return subprocess.run(  # noqa: S603  # fixed read-only git subcommand assembled only by this module
        ("git", *arguments),  # noqa: S607  # repository tool is fixed; only literal call sites supply arguments
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _module_name(path: str) -> str:
    """Convert a source path under ``src/`` to its importable Python name."""
    if not path.startswith("src/") or not path.endswith(".py"):
        raise ValueError(f"not a Python source path: {path!r}")
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def exact_relocation_candidates() -> tuple[RelocatedFamily, ...]:
    """Return exactly the rename candidates recorded in the c941 diff."""
    output = _git(
        "diff-tree",
        "-r",
        "-M",
        "--name-status",
        "--format=",
        f"{RELOCATION_COMMIT}^",
        RELOCATION_COMMIT,
        "--",
        REGISTRY_PATH,
    )
    candidates: list[RelocatedFamily] = []
    for line in output.splitlines():
        match = re.fullmatch(r"R(\d+)\t([^\t]+)\t([^\t]+)", line)
        if match is None:
            continue
        similarity, old_path, new_path = match.groups()
        candidates.append(RelocatedFamily(int(similarity), old_path, new_path))
    candidates.sort(key=lambda candidate: candidate.old_path)
    if len(candidates) != 78:
        raise RuntimeError(f"c941 registry family must contain exactly 78 renames, found {len(candidates)}")
    if (
        len({candidate.old_path for candidate in candidates}) != 78
        or len({candidate.new_path for candidate in candidates}) != 78
    ):
        raise RuntimeError("c941 registry rename family is not one-to-one")
    return tuple(candidates)


def mechanical_relocation_pairs() -> tuple[tuple[str, str], ...]:
    """Return the exact historical rename pairs as the mechanical-delta proof."""
    return tuple((candidate.old_path, candidate.new_path) for candidate in exact_relocation_candidates())


def _historic_facade_exports() -> dict[str, tuple[str, ...]]:
    """Derive c941-parent ``__all__`` symbols by their private defining module."""
    source = _git("show", f"{RELOCATION_COMMIT}^:{REGISTRY_PATH}/__init__.py")
    tree = ast.parse(source, filename="c941-parent-registry-__init__.py")
    public_names: set[str] | None = None
    lazy_exports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        else:
            continue
        if name == "__all__":
            public_names = set(ast.literal_eval(value))
        elif name == "_LAZY_EXPORTS":
            lazy_exports = ast.literal_eval(value)
    if public_names is None:
        raise RuntimeError("c941-parent registry facade has no literal __all__")
    exports: dict[str, list[str]] = defaultdict(list)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
            continue
        old_path = f"{REGISTRY_PATH}/{node.module}.py"
        for alias in node.names:
            exported_name = alias.asname or alias.name
            if exported_name in public_names:
                exports[old_path].append(exported_name)
    for exported_name, lazy_module in lazy_exports.items():
        if exported_name in public_names:
            exports[f"{REGISTRY_PATH}/{lazy_module.removeprefix('.')}.py"].append(exported_name)
    return {path: tuple(sorted(set(names))) for path, names in exports.items()}


def _base_category(relative_path: str) -> str:
    """Classify a consumer's operational home without guessing its semantics."""
    if relative_path.startswith("docs/"):
        return "documentation"
    if relative_path.endswith("conftest.py") or "/fixtures/" in relative_path:
        return "fixture"
    if relative_path.startswith("dev/"):
        return "test" if "/tests/" in relative_path else "tooling"
    if "/tests/" in relative_path:
        return "test"
    return "production"


_EVIDENCE_FILE_CACHE: tuple[EvidenceFile, ...] | None = None


def _evidence_files() -> tuple[EvidenceFile, ...]:
    """Return one deterministic current-tree snapshot for the census run."""
    global _EVIDENCE_FILE_CACHE
    if _EVIDENCE_FILE_CACHE is not None:
        return _EVIDENCE_FILE_CACHE
    files: list[EvidenceFile] = []
    for root_name in EVIDENCE_ROOTS:
        root = ROOT / root_name
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in EVIDENCE_FILE_SUFFIXES:
                files.append(
                    EvidenceFile(
                        path=path.relative_to(ROOT).as_posix(),
                        text=path.read_text(encoding="utf-8", errors="replace"),
                    ),
                )
    _EVIDENCE_FILE_CACHE = tuple(sorted(files, key=lambda item: item.path))
    return _EVIDENCE_FILE_CACHE


def _evidence_text(path: str) -> str:
    """Read one named source object from the current evidence snapshot."""
    for evidence_file in _evidence_files():
        if evidence_file.path == path:
            return evidence_file.text
    raise RuntimeError(f"evidence commit lacks required source object: {path}")


def _consumer_module_name(relative_path: str) -> tuple[str, bool] | None:
    """Return the import name and package flag for a scoped Python source path."""
    if not relative_path.endswith(".py"):
        return None
    source_path = relative_path.removeprefix("src/").removesuffix(".py")
    module = source_path.replace("/", ".")
    is_package = module.endswith(".__init__")
    if is_package:
        module = module.removesuffix(".__init__")
    return module, is_package


def _resolve_relative_import(
    current_module: str,
    *,
    is_package: bool,
    level: int,
    module: str | None,
) -> str | None:
    """Resolve one ``ImportFrom`` target against its importing module."""
    if level == 0:
        return module
    package = current_module if is_package else current_module.rpartition(".")[0]
    if not package:
        return None
    parts = package.split(".")
    climb = level - 1
    if climb >= len(parts):
        return None
    base = ".".join(parts[: len(parts) - climb])
    return f"{base}.{module}" if module else base


def _python_import_context(
    tree: ast.AST,
    *,
    current_module: str,
    is_package: bool,
) -> tuple[tuple[str, ...], dict[str, str], tuple[tuple[str, str], ...]]:
    """Resolve direct imports, their local spellings, and from-import members."""
    imports: set[str] = set()
    aliases: dict[str, str] = {}
    from_members: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                local_name = alias.asname or alias.name.split(".")[0]
                aliases[local_name] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_relative_import(
                current_module,
                is_package=is_package,
                level=node.level,
                module=node.module,
            )
            if target is None:
                continue
            imports.add(target)
            for alias in node.names:
                if alias.name == "*":
                    from_members.append((target, "*"))
                    continue
                member_target = f"{target}.{alias.name}"
                aliases[alias.asname or alias.name] = member_target
                from_members.append((target, alias.name))
                if node.module is None:
                    imports.add(member_target)
    return tuple(sorted(imports)), aliases, tuple(from_members)


def _dotted_name(node: ast.AST) -> str | None:
    """Return a dotted expression spelling when it has no dynamic limb."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _resolve_import_alias(reference: str, aliases: dict[str, str]) -> str:
    """Expand the first lexical segment of an imported local spelling."""
    first, dot, rest = reference.partition(".")
    target = aliases.get(first)
    if target is None:
        return reference
    return f"{target}{dot}{rest}" if dot else target


def _candidate_for_reference(reference: str, by_new_module: dict[str, RelocatedFamily]) -> RelocatedFamily | None:
    """Find the exact family owner of a module or imported symbol reference."""
    module = reference
    while module:
        candidate = by_new_module.get(module)
        if candidate is not None:
            return candidate
        module = module.rpartition(".")[0]
    return None


def _owner_for_reference(
    reference: str,
    *,
    by_new_module: dict[str, RelocatedFamily],
    member_owners: dict[str, str],
) -> str | None:
    """Resolve a leaf module or package-export symbol to its one c941 family row."""
    if candidate := _candidate_for_reference(reference, by_new_module):
        return candidate.old_path
    package = "cadrumo.domain.calculations.registry."
    if reference.startswith(package):
        return member_owners.get(reference.removeprefix(package).split(".", maxsplit=1)[0])
    return None


def _annotation_expressions(tree: ast.AST) -> tuple[ast.AST, ...]:
    """Collect every function, variable, and type-alias annotation expression."""
    expressions: list[ast.AST] = []
    type_alias_node = getattr(ast, "TypeAlias", None)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            expressions.append(node.annotation)
            annotation_name = _dotted_name(node.annotation)
            if annotation_name is not None and annotation_name.endswith("TypeAlias") and node.value is not None:
                expressions.append(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                expressions.append(node.returns)
            arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if node.args.vararg is not None:
                arguments = (*arguments, node.args.vararg)
            if node.args.kwarg is not None:
                arguments = (*arguments, node.args.kwarg)
            expressions.extend(argument.annotation for argument in arguments if argument.annotation is not None)
        elif type_alias_node is not None and isinstance(node, type_alias_node):
            value = getattr(node, "value", None)
            if isinstance(value, ast.AST):
                expressions.append(value)
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and (_dotted_name(node.value.func) or "").endswith("TypeAliasType")
        ):
            expressions.extend(node.value.args[1:])
    return tuple(expressions)


def _annotation_owners(
    tree: ast.AST,
    *,
    aliases: dict[str, str],
    by_new_module: dict[str, RelocatedFamily],
) -> set[str]:
    """Resolve family references in variable, function, and type-alias annotations."""
    owners: set[str] = set()
    pending = list(_annotation_expressions(tree))
    while pending:
        expression = pending.pop()
        for node in ast.walk(expression):
            reference = _dotted_name(node)
            if reference is not None:
                candidate = _candidate_for_reference(_resolve_import_alias(reference, aliases), by_new_module)
                if candidate is not None:
                    owners.add(candidate.old_path)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                try:
                    pending.append(ast.parse(node.value, mode="eval"))
                except SyntaxError:
                    continue
    return owners


def _facade_member_owners(candidates: tuple[RelocatedFamily, ...]) -> dict[str, str]:
    """Map each historic facade member to one exact family row, failing on ambiguity."""
    owners: dict[str, str] = {}
    for old_path, symbols in _historic_facade_exports().items():
        for symbol in symbols:
            existing = owners.setdefault(symbol, old_path)
            if existing != old_path:
                raise RuntimeError(f"historic registry facade member has multiple owners: {symbol}")
    module_stems = {Path(candidate.new_path).stem: candidate.old_path for candidate in candidates}
    return {**module_stems, **owners}


def _package_attribute_owners(
    tree: ast.AST,
    *,
    aliases: dict[str, str],
    from_members: tuple[tuple[str, str], ...],
    member_owners: dict[str, str],
) -> set[str]:
    """Attribute a registry facade use to the exact member owner, never every row."""
    package = "cadrumo.domain.calculations.registry"
    owners: set[str] = set()
    for imported_from, member in from_members:
        if imported_from != package:
            continue
        if member == "*":
            owners.update(member_owners.values())
        elif owner := member_owners.get(member):
            owners.add(owner)
    package_locals = {local for local, target in aliases.items() if target == package}
    for node in ast.walk(tree):
        reference = _dotted_name(node)
        if reference is None or reference.partition(".")[0] not in package_locals:
            continue
        member = reference.removeprefix(f"{reference.partition('.')[0]}").removeprefix(".").split(".", maxsplit=1)[0]
        if owner := member_owners.get(member):
            owners.add(owner)
    return owners


def _transitive_consumer_paths(
    candidate_module: str,
    *,
    direct_modules: set[str],
    importers: dict[str, set[str]],
    module_paths: dict[str, set[str]],
) -> set[str]:
    """Return the complete reverse-import closure beyond direct consumers."""
    # A package-attribute use has no import edge from the defining leaf module:
    # ``from registry import Member`` imports the package, not
    # ``registry.defining_leaf``.  The exact member pass has already established
    # those direct modules, so seed the same graph walk with both kinds of edge.
    frontier = [candidate_module, *direct_modules]
    visited_modules = {candidate_module, *direct_modules}
    paths: set[str] = set()
    while frontier:
        imported = frontier.pop()
        for importer in importers.get(imported, ()):
            if importer in visited_modules:
                continue
            visited_modules.add(importer)
            frontier.append(importer)
            if importer not in direct_modules:
                paths.update(module_paths[importer])
    return paths


def _dynamic_import_call(node: ast.Call, aliases: dict[str, str]) -> str | None:
    """Return a supported dynamic-import callee after lexical alias resolution."""
    reference = _dotted_name(node.func)
    if reference is None:
        return None
    resolved = _resolve_import_alias(reference, aliases)
    return resolved if resolved in {"__import__", "importlib.import_module"} else None


def _resolve_dynamic_target(target: str, *, module: str, is_package: bool) -> str:
    """Resolve a literal ``import_module`` target when it is relative."""
    if not target.startswith("."):
        return target
    level = len(target) - len(target.lstrip("."))
    return _resolve_relative_import(module, is_package=is_package, level=level, module=target[level:] or None) or target


_EVIDENCE_CENSUS_CACHE: EvidenceCensus | None = None


def _all_evidence_consumers(candidates: tuple[RelocatedFamily, ...]) -> EvidenceCensus:
    """Census every family member from one current-tree snapshot.

    Text, manifests, receipts, fixtures, and Python source are all read from the
    current source corpus. Python edges retain relative-import and dynamic-import
    semantics rather than silently treating those references as absent.
    """
    hits = {candidate.old_path: {category: set() for category in CONSUMER_CATEGORIES} for candidate in candidates}
    direct_modules = {candidate.old_path: set() for candidate in candidates}
    importers: dict[str, set[str]] = defaultdict(set)
    module_paths: dict[str, set[str]] = defaultdict(set)
    by_new_module = {candidate.new_module: candidate for candidate in candidates}
    member_owners = _facade_member_owners(candidates)
    literal_dynamic: list[dict[str, str]] = []
    unresolved_dynamic: list[dict[str, str]] = []
    relative_import_edges = 0
    type_alias_nodes = 0
    for evidence_file in _evidence_files():
        relative = evidence_file.path
        text = evidence_file.text
        base = _base_category(relative)
        for candidate in candidates:
            if candidate.old_module in text or candidate.new_module in text:
                hits[candidate.old_path][base].add(relative)
        if not relative.endswith(".py"):
            continue
        tree = ast.parse(text, filename=relative)
        consumer_module = _consumer_module_name(relative)
        if consumer_module is None:
            continue
        module, is_package = consumer_module
        module_paths[module].add(relative)
        imports, aliases, from_members = _python_import_context(
            tree,
            current_module=module,
            is_package=is_package,
        )
        relative_import_edges += sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level > 0
        )
        type_alias = getattr(ast, "TypeAlias", None)
        type_alias_nodes += sum(1 for node in ast.walk(tree) if type_alias is not None and isinstance(node, type_alias))
        for imported in imports:
            importers[imported].add(module)
            if old_path := _owner_for_reference(imported, by_new_module=by_new_module, member_owners=member_owners):
                direct_modules[old_path].add(module)
                hits[old_path][base].add(relative)
        for old_path in _package_attribute_owners(
            tree,
            aliases=aliases,
            from_members=from_members,
            member_owners=member_owners,
        ):
            hits[old_path]["package_attribute"].add(relative)
            direct_modules[old_path].add(module)
        for old_path in _annotation_owners(tree, aliases=aliases, by_new_module=by_new_module):
            hits[old_path]["annotation"].add(relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _dynamic_import_call(node, aliases)
            argument = (
                node.args[0] if node.args else next((item.value for item in node.keywords if item.arg == "name"), None)
            )
            if callee is None or argument is None:
                continue
            site = f"{relative}:{node.lineno}"
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                target = _resolve_dynamic_target(argument.value, module=module, is_package=is_package)
                if old_path := _owner_for_reference(target, by_new_module=by_new_module, member_owners=member_owners):
                    hits[old_path]["dynamic_target"].add(relative)
                    literal_dynamic.append({"site": site, "target": target, "row_path": old_path})
            else:
                unresolved_dynamic.append({"site": site, "callee": callee, "expression": ast.unparse(argument)})
            registration = _resolve_import_alias(_dotted_name(node.func) or "", aliases)
            if not registration.rpartition(".")[2].startswith("register"):
                continue
            references = [registration.removesuffix(f".{registration.rpartition('.')[2]}")]
            references.extend(
                _resolve_import_alias(reference, aliases)
                for reference in (_dotted_name(arg) for arg in node.args)
                if reference
            )
            for reference in references:
                if old_path := _owner_for_reference(
                    reference, by_new_module=by_new_module, member_owners=member_owners
                ):
                    hits[old_path]["registration"].add(relative)
    for candidate in candidates:
        hits[candidate.old_path]["transitive"].update(
            _transitive_consumer_paths(
                candidate.new_module,
                direct_modules=direct_modules[candidate.old_path],
                importers=importers,
                module_paths=module_paths,
            )
        )
    return EvidenceCensus(
        consumers={
            old_path: {category: sorted(paths) for category, paths in categories.items()}
            for old_path, categories in hits.items()
        },
        dynamic_imports={
            "literal": sorted(literal_dynamic, key=lambda item: (item["site"], item["target"])),
            "unresolved": sorted(unresolved_dynamic, key=lambda item: (item["site"], item["expression"])),
        },
        measurements={"relative_import_edges": relative_import_edges, "type_alias_nodes": type_alias_nodes},
    )


def _evidence_census() -> EvidenceCensus:
    """Return the cached current-tree evidence census."""
    global _EVIDENCE_CENSUS_CACHE
    if _EVIDENCE_CENSUS_CACHE is None:
        _EVIDENCE_CENSUS_CACHE = _all_evidence_consumers(exact_relocation_candidates())
    return _EVIDENCE_CENSUS_CACHE


def _evidence_symbol_locators(candidate: RelocatedFamily, symbols: tuple[str, ...]) -> dict[str, list[str]]:
    """Locate every historic facade symbol in its current evidence module."""
    tree = ast.parse(_evidence_text(candidate.new_path), filename=candidate.new_path)
    locations: dict[str, list[str]] = {symbol: [] for symbol in symbols}
    type_alias = getattr(ast, "TypeAlias", None)
    for node in tree.body:
        names: set[str] = set()
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
        elif type_alias is not None and isinstance(node, type_alias):
            name = getattr(node, "name", None)
            if isinstance(name, ast.Name):
                names.add(name.id)
        for symbol in sorted(names & locations.keys()):
            locations[symbol].append(f"{candidate.new_path}:{node.lineno}")
    return locations


def _structured_semantic_evidence(
    candidate: RelocatedFamily,
    *,
    locators: dict[str, list[str]],
    all_locators: dict[str, dict[str, list[str]]],
) -> dict[str, object]:
    """Record falsifiable owner, competing-site, and substitutability anchors."""
    owner_definition_locators = sorted(locator for values in locators.values() for locator in values)
    competing_sites: dict[str, list[str]] = {}
    for symbol in sorted(locators):
        alternatives = sorted(
            locator
            for other_path, other_locators in all_locators.items()
            if other_path != candidate.old_path
            for locator in other_locators.get(symbol, [])
        )
        if alternatives:
            competing_sites[symbol] = alternatives
    return {
        "owner_definition_locators": owner_definition_locators,
        "competing_site_census": competing_sites,
        "substitutability": {
            "result": "no_substitutable_c941_owner",
            "rationale": (
                "The one-to-one c941 old/new pair is the only reviewed family owner; "
                "AST locator and competing-site census are anchored to the current-tree evidence snapshot."
            ),
        },
        "anchors": {
            "census_root": "current_worktree",
            "relocation_pair": [candidate.old_path, candidate.new_path],
        },
    }


def generated_rows() -> list[dict[str, object]]:
    """Produce the exact c941 family rows without inventing their adjudications."""
    candidates = exact_relocation_candidates()
    facade_exports = _historic_facade_exports()
    locators = {
        candidate.old_path: _evidence_symbol_locators(candidate, facade_exports.get(candidate.old_path, ()))
        for candidate in candidates
    }
    evidence_census = _evidence_census()
    rows: list[dict[str, object]] = []
    for row_number, candidate in enumerate(candidates, start=1):
        exported_symbols = facade_exports.get(candidate.old_path, ())
        rows.append(
            {
                "row_id": f"R{row_number:02d}",
                "old_path": candidate.old_path,
                "new_path": candidate.new_path,
                "rename_similarity": candidate.similarity,
                "facade_exported_symbols": list(exported_symbols),
                "current_symbol_locators": locators[candidate.old_path],
                "consumers": evidence_census.consumers[candidate.old_path],
                "semantic_evidence": _structured_semantic_evidence(
                    candidate,
                    locators=locators[candidate.old_path],
                    all_locators=locators,
                ),
                "semantic_owner": None,
                "rag_query": None,
                "rag_result": None,
                "alternative_owner_evidence": None,
                "disposition": None,
                "follow_on_step_id": None,
            }
        )
    return rows


def matrix_document() -> dict[str, object]:
    """Return the schema-versioned, intentionally unadjudicated S175 matrix template."""
    return {
        "schema_version": MATRIX_VERSION,
        "relocation_commit": RELOCATION_COMMIT,
        "consumer_categories": list(CONSUMER_CATEGORIES),
        "dynamic_imports": _evidence_census().dynamic_imports,
        "evidence_measurements": _evidence_census().measurements,
        "review_status": "pending_independent_architecture_review",
        "rows": generated_rows(),
        "final_package_gate": None,
    }


def _terminal_destinations(row: dict[str, object]) -> list[dict[str, object]]:
    """Return explicit future terminal paths without requiring compatibility paths."""
    new_path = row["new_path"]
    if not isinstance(new_path, str):
        raise RuntimeError("terminal destination requires a source path")
    if new_path.endswith("/aeat_hosts.py"):
        return [
            {"path": "src/cadrumo/core/remote_authority.py", "allowed_absence": False, "role": "defining_owner"},
            {"path": new_path, "allowed_absence": True, "role": "retired_candidate"},
        ]
    if new_path.endswith("/record_spec.py"):
        return [
            {
                "path": "src/cadrumo/domain/calculations/registry/schema_exports.py",
                "allowed_absence": False,
                "role": "defining_owner",
            },
            {"path": new_path, "allowed_absence": True, "role": "retired_candidate"},
        ]
    if row.get("disposition") in {"privatize_external_elimination", "delete"}:
        return [{"path": new_path, "allowed_absence": True, "role": "retired_public_candidate"}]
    return [{"path": new_path, "allowed_absence": False, "role": "defining_owner"}]


def _symbol_terminal_destinations(
    row: dict[str, object],
    generated: dict[str, object],
) -> dict[str, dict[str, str]]:
    """Provide structured future destinations only for evidence symbols now absent."""
    symbols = generated["facade_exported_symbols"]
    locators = generated["current_symbol_locators"]
    if not isinstance(symbols, list) or not isinstance(locators, dict):
        raise RuntimeError("generated symbol evidence is malformed")
    destination = _terminal_destinations(row)[0]["path"]
    if not isinstance(destination, str):
        raise RuntimeError("terminal destination path is malformed")
    return {
        symbol: {"path": destination, "reason": "future_terminal_destination"}
        for symbol in symbols
        if isinstance(symbol, str) and not locators.get(symbol)
    }


def refresh_reviewed_matrix_document(document: dict[str, object]) -> dict[str, object]:
    """Refresh only derived fields in a reviewed matrix, keyed by c941 pair.

    This intentionally cannot create an adjudication from the blank template:
    the reviewed owner, evidence, disposition, terminal state, and plan binding
    are copied verbatim from an existing exact 78-row artifact.
    """
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 78 or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("only an existing exact 78-row reviewed matrix may be refreshed")
    existing_by_pair = {(row.get("old_path"), row.get("new_path")): row for row in rows}
    expected = generated_rows()
    expected_pairs = {(row["old_path"], row["new_path"]) for row in expected}
    if set(existing_by_pair) != expected_pairs or len(existing_by_pair) != 78:
        raise RuntimeError("reviewed matrix pairs must exactly match the c941 family before refresh")
    refreshed_rows: list[dict[str, object]] = []
    derived_fields = {
        "row_id",
        "old_path",
        "new_path",
        "rename_similarity",
        "facade_exported_symbols",
        "current_symbol_locators",
        "consumers",
        "semantic_evidence",
    }
    reviewed_fields = {
        "semantic_owner",
        "rag_query",
        "rag_result",
        "alternative_owner_evidence",
        "disposition",
        "terminal_state",
        "follow_on_step_id",
        "follow_on_action",
        "follow_on_scope",
        "follow_on_predecessors",
    }
    for generated in expected:
        pair = (generated["old_path"], generated["new_path"])
        existing = existing_by_pair[pair]
        refreshed = {field: existing[field] for field in reviewed_fields}
        refreshed.update({field: generated[field] for field in derived_fields})
        evidence = refreshed["semantic_evidence"]
        if not isinstance(evidence, dict) or not isinstance(evidence.get("substitutability"), dict):
            raise RuntimeError(f"reviewed semantic evidence is malformed for {pair[0]}")
        result = refreshed["rag_result"]
        if not isinstance(result, dict):
            raise RuntimeError(f"reviewed RAG evidence is malformed for {pair[0]}")
        competitors = evidence.get("competing_site_census")
        competitor_symbols = ", ".join(sorted(competitors)) if isinstance(competitors, dict) and competitors else "none"
        evidence["substitutability"]["rationale"] = (
            f"RAG `{refreshed['rag_query']}` returned `{result['path']}:{result['line_start']}` "
            f"for `{result['symbol']}`; reviewed owner `{refreshed['semantic_owner']}` was compared against "
            f"exact competing c941 symbols: {competitor_symbols}."
        )
        refreshed["terminal_destinations"] = _terminal_destinations(refreshed)
        refreshed["symbol_terminal_destinations"] = _symbol_terminal_destinations(refreshed, generated)
        refreshed_rows.append(refreshed)
    refreshed_document = dict(document)
    refreshed_document["schema_version"] = MATRIX_VERSION
    refreshed_document["relocation_commit"] = RELOCATION_COMMIT
    refreshed_document["consumer_categories"] = list(CONSUMER_CATEGORIES)
    refreshed_document["dynamic_imports"] = _evidence_census().dynamic_imports
    refreshed_document["evidence_measurements"] = _evidence_census().measurements
    refreshed_document["rows"] = refreshed_rows
    return refreshed_document


def _canonical_plan_step_ids() -> frozenset[str]:
    """Read the canonical Step IDs owned by the reviewed TUI architecture plan."""
    matches = re.findall(r"`(W\d{2}\.P\d{2}\.S\d+)`", PLAN_PATH.read_text(encoding="utf-8"))
    return frozenset(str(match) for match in matches)


def check_matrix_document(document: dict[str, object]) -> None:
    """Fail closed on census drift or an incomplete/many-to-one adjudication."""
    required_document_fields = {
        "schema_version",
        "relocation_commit",
        "consumer_categories",
        "dynamic_imports",
        "evidence_measurements",
        "review_status",
        "rows",
        "final_package_gate",
    }
    if set(document) != required_document_fields:
        raise RuntimeError("registry facade matrix document schema is incomplete or has unrelated fields")
    if document.get("schema_version") != MATRIX_VERSION or document.get("relocation_commit") != RELOCATION_COMMIT:
        raise RuntimeError("registry facade matrix has the wrong schema or relocation commit")
    if document.get("consumer_categories") != list(CONSUMER_CATEGORIES):
        raise RuntimeError("registry facade matrix consumer-category schema drifted")
    if document.get("review_status") != "pending_independent_architecture_review":
        raise RuntimeError("registry facade matrix must retain its pending independent-review status")
    evidence_census = _evidence_census()
    if document.get("dynamic_imports") != evidence_census.dynamic_imports:
        raise RuntimeError("registry facade matrix dynamic-import evidence drifted")
    if document.get("evidence_measurements") != evidence_census.measurements:
        raise RuntimeError("registry facade matrix current-tree measurements drifted")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 78:
        raise RuntimeError("registry facade matrix must contain exactly 78 rows")
    expected = generated_rows()
    expected_pairs = set(mechanical_relocation_pairs())
    actual_pairs = {(row.get("old_path"), row.get("new_path")) for row in rows if isinstance(row, dict)}
    if actual_pairs != expected_pairs:
        raise RuntimeError("registry facade matrix is missing, extra, duplicate, or unrelated c941 rows")
    steps: set[str] = set()
    rationales: set[str] = set()
    disposition_counts = {disposition: 0 for disposition in DISPOSITIONS}
    required_row_fields = {
        "row_id",
        "old_path",
        "new_path",
        "rename_similarity",
        "facade_exported_symbols",
        "current_symbol_locators",
        "consumers",
        "semantic_owner",
        "semantic_evidence",
        "rag_query",
        "rag_result",
        "alternative_owner_evidence",
        "disposition",
        "terminal_state",
        "terminal_destinations",
        "symbol_terminal_destinations",
        "follow_on_step_id",
        "follow_on_action",
        "follow_on_scope",
        "follow_on_predecessors",
    }
    canonical_step_ids = _canonical_plan_step_ids()
    plan = PLAN_PATH.read_text(encoding="utf-8")
    if "- [ ] `W03.P20.S175`" not in plan:
        raise RuntimeError("S175 must remain open pending independent architecture review")
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("registry facade matrix rows must be objects")
        if set(row) != required_row_fields:
            raise RuntimeError(f"registry facade row {row.get('old_path')!r} has an incomplete or grouped schema")
        pair = (row["old_path"], row["new_path"])
        generated = next(item for item in expected if (item["old_path"], item["new_path"]) == pair)
        if row.get("row_id") != generated["row_id"]:
            raise RuntimeError(f"registry facade row {pair[0]} has a non-canonical row id")
        if (
            row.get("facade_exported_symbols") != generated["facade_exported_symbols"]
            or row.get("current_symbol_locators") != generated["current_symbol_locators"]
            or row.get("consumers") != generated["consumers"]
        ):
            raise RuntimeError(f"registry facade consumer census drifted for {pair[0]}")
        for field in (
            "semantic_owner",
            "rag_query",
            "alternative_owner_evidence",
            "disposition",
            "terminal_state",
            "follow_on_step_id",
            "follow_on_action",
            "follow_on_scope",
        ):
            if not isinstance(row.get(field), str) or not row[field]:
                raise RuntimeError(f"registry facade row {pair[0]} lacks reviewed {field}")
        rag_result = row.get("rag_result")
        if not isinstance(rag_result, dict) or set(rag_result) != RAG_RESULT_FIELDS:
            raise RuntimeError(f"registry facade row {pair[0]} lacks one auditable RAG result")
        if (
            not isinstance(rag_result["path"], str)
            or not isinstance(rag_result["line_start"], int)
            or not isinstance(rag_result["line_end"], int)
            or not isinstance(rag_result["node_type"], str)
            or not isinstance(rag_result["symbol"], str)
            or rag_result["path"] != row["new_path"]
        ):
            raise RuntimeError(f"registry facade row {pair[0]} has a malformed RAG defining-owner result")
        rag_location = f"{rag_result['path']}:{rag_result['line_start']}"
        if rag_location not in row["alternative_owner_evidence"]:
            raise RuntimeError(f"registry facade row {pair[0]} alternative-owner evidence omits its RAG result")
        semantic_evidence = row.get("semantic_evidence")
        if not isinstance(semantic_evidence, dict) or set(semantic_evidence) != {
            "owner_definition_locators",
            "competing_site_census",
            "substitutability",
            "anchors",
        }:
            raise RuntimeError(f"registry facade row {pair[0]} has no structured semantic evidence")
        anchors = semantic_evidence["anchors"]
        if not isinstance(anchors, dict) or anchors.get("census_root") != "current_worktree":
            raise RuntimeError(f"registry facade row {pair[0]} has unanchored semantic evidence")
        if anchors.get("relocation_pair") != [row["old_path"], row["new_path"]]:
            raise RuntimeError(f"registry facade row {pair[0]} semantic evidence has another relocation pair")
        rationale = semantic_evidence["substitutability"].get("rationale")
        if not isinstance(rationale, str) or row["rag_query"] not in rationale or rationale in rationales:
            raise RuntimeError(f"registry facade row {pair[0]} has templated substitutability evidence")
        rationales.add(rationale)
        if row["semantic_owner"] not in row["alternative_owner_evidence"]:
            raise RuntimeError(f"registry facade row {pair[0]} lacks alternative-owner comparison evidence")
        locators = row.get("current_symbol_locators")
        terminal_symbols = row.get("symbol_terminal_destinations")
        if not isinstance(locators, dict) or not isinstance(terminal_symbols, dict):
            raise RuntimeError(f"registry facade row {pair[0]} has malformed symbol evidence")
        for symbol in row["facade_exported_symbols"]:
            if not isinstance(symbol, str):
                raise RuntimeError(f"registry facade row {pair[0]} has a non-string facade symbol")
            terminal = terminal_symbols.get(symbol)
            if not locators.get(symbol) and not (
                isinstance(terminal, dict)
                and isinstance(terminal.get("path"), str)
                and isinstance(terminal.get("reason"), str)
            ):
                raise RuntimeError(f"registry facade row {pair[0]} has no source or terminal locator for {symbol}")
        destinations = row.get("terminal_destinations")
        if (
            not isinstance(destinations, list)
            or not destinations
            or any(
                not isinstance(destination, dict)
                or set(destination) != {"path", "allowed_absence", "role"}
                or not isinstance(destination["path"], str)
                or not isinstance(destination["allowed_absence"], bool)
                or not isinstance(destination["role"], str)
                for destination in destinations
            )
        ):
            raise RuntimeError(f"registry facade row {pair[0]} has malformed terminal destinations")
        if "unresolved" in row["semantic_owner"].lower() or "unresolved" in row["terminal_state"].lower():
            raise RuntimeError(f"registry facade row {pair[0]} remains unresolved")
        if row["disposition"] not in DISPOSITIONS:
            raise RuntimeError(f"registry facade row {pair[0]} has an invalid disposition")
        if row["terminal_state"] not in TERMINAL_STATES[row["disposition"]]:
            raise RuntimeError(f"registry facade row {pair[0]} has an invalid terminal state")
        if row["follow_on_predecessors"] != ["W03.P20.S175"]:
            raise RuntimeError(f"registry facade row {pair[0]} does not remain independently gated by S175")
        if row["follow_on_step_id"] in steps:
            raise RuntimeError("registry facade matrix maps more than one row to one follow-on Step")
        if row["follow_on_step_id"] not in canonical_step_ids:
            raise RuntimeError(f"registry facade row {pair[0]} names a non-canonical follow-on Step")
        plan_row = f"- [ ] `{row['follow_on_step_id']}` - {row['follow_on_action']}; `{row['follow_on_scope']}`."
        if plan_row not in plan:
            raise RuntimeError(f"registry facade follow-on Step is absent or diverges: {row['follow_on_step_id']}")
        steps.add(row["follow_on_step_id"])
        disposition_counts[row["disposition"]] += 1
    if disposition_counts != {
        "keep_public": 54,
        "hard_move_complete": 9,
        "privatize_external_elimination": 13,
        "delete": 2,
    }:
        raise RuntimeError("registry facade matrix disposition counts do not match the reviewed 54/9/13/2 adjudication")
    final_gate = document.get("final_package_gate")
    if not isinstance(final_gate, dict) or set(final_gate) != {"step_id", "action", "scope", "predecessor_step_ids"}:
        raise RuntimeError("registry facade matrix lacks the final inert-package gate")
    for field in ("step_id", "action", "scope"):
        if not isinstance(final_gate.get(field), str) or not final_gate[field]:
            raise RuntimeError("registry facade final package gate is incomplete")
    if final_gate["step_id"] in steps or final_gate["step_id"] not in canonical_step_ids:
        raise RuntimeError("registry facade final package gate must be a distinct canonical Step")
    if final_gate.get("predecessor_step_ids") != sorted(steps):
        raise RuntimeError("registry facade final package gate must wait for every disposition Step")
    final_plan_row = f"- [ ] `{final_gate['step_id']}` - {final_gate['action']}; `{final_gate['scope']}`."
    if final_plan_row not in plan:
        raise RuntimeError("registry facade final package gate is absent or diverges")


def current_terminal_state_report(
    document: dict[str, object],
    *,
    exists: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    """Report future terminal progress without making S175 depend on future moves.

    A disposition Step may legitimately remove its historic public path, or move
    it to a direct defining module.  This report therefore records missing paths
    as progress/pending proof rather than dereferencing them through the current
    evidence generator or asking a future Step to retain an alias or re-export.
    """
    rows = document.get("rows")
    if not isinstance(rows, list):
        raise RuntimeError("current terminal report requires matrix rows")
    path_exists = exists or (lambda path: (ROOT / path).is_file())
    row_states: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("current terminal report requires object rows")
        destinations = row.get("terminal_destinations")
        if not isinstance(destinations, list):
            raise RuntimeError("current terminal report requires terminal destinations")
        observed = [
            {
                "path": destination["path"],
                "role": destination["role"],
                "exists": path_exists(destination["path"]),
                "allowed_absence": destination["allowed_absence"],
            }
            for destination in destinations
            if isinstance(destination, dict)
            and isinstance(destination.get("path"), str)
            and isinstance(destination.get("role"), str)
            and isinstance(destination.get("allowed_absence"), bool)
        ]
        if len(observed) != len(destinations):
            raise RuntimeError(f"current terminal report has malformed destinations for {row.get('old_path')}")
        absent_allowed = any(not item["exists"] and item["allowed_absence"] for item in observed)
        missing_owner = any(not item["exists"] and item["role"] == "defining_owner" for item in observed)
        status = (
            "terminal_candidate_absent_pending_step_proof"
            if absent_allowed
            else "terminal_destination_missing_pending_step"
            if missing_owner
            else "disposition_open_pending_step_proof"
        )
        row_states.append(
            {
                "row_id": row.get("row_id"),
                "step_id": row.get("follow_on_step_id"),
                "status": status,
                "destinations": observed,
            }
        )
    return {
        "census_root": "current_worktree",
        "review_status": document.get("review_status"),
        "open_disposition_step_ids": [state["step_id"] for state in row_states],
        "rows": row_states,
    }


def main(argv: list[str] | None = None) -> int:
    """Write the deterministic template or verify a fully reviewed matrix."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-template", action="store_true")
    parser.add_argument("--refresh-reviewed", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-current-terminal", action="store_true")
    args = parser.parse_args(argv)
    if args.write_template:
        MATRIX_PATH.write_text(json.dumps(matrix_document(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.refresh_reviewed:
        reviewed = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        MATRIX_PATH.write_text(
            json.dumps(refresh_reviewed_matrix_document(reviewed), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.check:
        check_matrix_document(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))
    if args.check_current_terminal:
        document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        check_matrix_document(document)
        print(json.dumps(current_terminal_state_report(document), indent=2, sort_keys=True))
    if not args.write_template and not args.refresh_reviewed and not args.check and not args.check_current_terminal:
        print(json.dumps(matrix_document(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
