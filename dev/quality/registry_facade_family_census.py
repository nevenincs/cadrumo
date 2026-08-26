"""Deterministically census the exact registry family mechanically relocated by c941.

This is deliberately not a general import scanner.  Its only candidate set is
the rename set recorded by c94133f295; the checked-in matrix then receives a
separate, human-reviewed semantic adjudication for every one of those rows.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import subprocess
import tarfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RELOCATION_COMMIT: Final = "c94133f29516b12e3529f3d154c31592562f6198"
EVIDENCE_COMMIT: Final = "aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8"
REGISTRY_PATH: Final = "src/cadrumo/domain/calculations/registry"
MATRIX_VERSION: Final = 2
DISPOSITIONS: Final = (
    "keep_public",
    "hard_move_complete",
    "privatize_external_elimination",
    "delete",
)
RAG_QUERY_FIELDS: Final = frozenset({"text", "type", "domain", "prefer", "request_id"})
RAG_RESULT_FIELDS: Final = frozenset(
    {"id", "path", "score", "source", "line_start", "line_end", "node_type", "function_name", "class_name"}
)
# These are the two semantic searches performed for the Sol remediation.  They
# are intentionally *not* derived from the AST locator census below: a RAG
# result is an observed vaultspec-rag result, whereas the locators are
# deterministic immutable-source evidence.  All non-target rows retain null
# RAG fields rather than claiming an unperformed semantic search.
RAG_DISCOVERY_BY_PAIR: Final = {
    (
        "src/cadrumo/domain/calculations/registry/_aeat_hosts.py",
        "src/cadrumo/domain/calculations/registry/aeat_hosts.py",
    ): {
        "query": {
            "text": "AEAT remote read host authority canonical hostname only:prod",
            "type": "code",
            "domain": "prod",
            "prefer": "production",
            "request_id": "eec115fcf1ae4225b7e9209afc205b2b",
        },
        "result": {
            "id": "src/cadrumo/domain/calculations/registry/aeat_hosts.py:1:19-51:a2db203363d2",
            "path": "src/cadrumo/domain/calculations/registry/aeat_hosts.py",
            "score": 0.941738772392273,
            "source": "codebase",
            "line_start": 19,
            "line_end": 51,
            "node_type": None,
            "function_name": None,
            "class_name": None,
        },
    },
    (
        "src/cadrumo/domain/calculations/registry/_record_spec.py",
        "src/cadrumo/domain/calculations/registry/record_spec.py",
    ): {
        "query": {
            "text": "ENCODING_ALIAS_MAP registry schema export value policy only:prod",
            "type": "code",
            "domain": "prod",
            "prefer": "production",
            "request_id": "f8cff429a3cd4d8fa1dc335774db9e47",
        },
        "result": {
            "id": "src/cadrumo/domain/calculations/registry/schema_exports.py:0:1-41:708338918763",
            "path": "src/cadrumo/domain/calculations/registry/schema_exports.py",
            "score": 1.0188962697982789,
            "source": "codebase",
            "line_start": 1,
            "line_end": 41,
            "node_type": None,
            "function_name": None,
            "class_name": None,
        },
    },
}
EVIDENCE_FILE_SUFFIXES: Final = frozenset(
    {".cfg", ".csv", ".ini", ".json", ".md", ".py", ".rst", ".toml", ".tsv", ".txt", ".xml", ".yaml", ".yml"},
)
# The generated registry corpus is deliberately excluded.  The archive pathspec
# keeps authored source, fixtures, manifests, receipts, and documentation while
# avoiding a multi-hundred-megabyte generated-data snapshot.
EVIDENCE_ARCHIVE_PATHS: Final = (".vault", "dev", "docs", "src", ":(exclude)src/cadrumo/_data")
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
    """One authored text object read from the immutable evidence commit."""

    path: str
    text: str


@dataclass(frozen=True, slots=True)
class EvidenceCensus:
    """Consumers and parser measurements derived from one immutable archive."""

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


def _git_bytes(*arguments: str) -> bytes:
    """Run a fixed repository-local git query that returns raw object bytes."""
    return subprocess.run(  # noqa: S603  # fixed read-only git subcommand assembled only by this module
        ("git", *arguments),  # noqa: S607  # repository tool is fixed; only literal call sites supply arguments
        cwd=ROOT,
        check=True,
        capture_output=True,
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
            evaluated_exports = ast.literal_eval(value)
            if not isinstance(evaluated_exports, dict):
                raise RuntimeError("c941-parent registry facade has a non-string lazy export")
            lazy_exports = {}
            for exported_name, module_name in evaluated_exports.items():
                if not isinstance(exported_name, str) or not isinstance(module_name, str):
                    raise RuntimeError("c941-parent registry facade has a non-string lazy export")
                lazy_exports[exported_name] = module_name
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
    """Read the complete authored census corpus from an immutable Git archive.

    This deliberately does not traverse ``ROOT``.  Consequently a dirty tree,
    later disposition move, or generated-data churn cannot alter the S175
    reviewed evidence.  The archive includes text, fixtures, manifests, and
    receipts as well as Python source.
    """
    global _EVIDENCE_FILE_CACHE
    if _EVIDENCE_FILE_CACHE is not None:
        return _EVIDENCE_FILE_CACHE
    archive = _git_bytes("archive", "--format=tar", EVIDENCE_COMMIT, "--", *EVIDENCE_ARCHIVE_PATHS)
    files: list[EvidenceFile] = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            if not member.isfile() or Path(member.name).suffix not in EVIDENCE_FILE_SUFFIXES:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                raise RuntimeError(f"evidence archive cannot read {member.name}")
            files.append(EvidenceFile(member.name, extracted.read().decode("utf-8", errors="replace")))
    _EVIDENCE_FILE_CACHE = tuple(sorted(files, key=lambda evidence_file: evidence_file.path))
    return _EVIDENCE_FILE_CACHE


def _evidence_text(path: str) -> str:
    """Read one source object from the immutable evidence archive."""
    for evidence_file in _evidence_files():
        if evidence_file.path == path:
            return evidence_file.text
    raise RuntimeError(f"evidence commit lacks required source object: {path}")


def _consumer_module_name(relative_path: str) -> tuple[str, bool] | None:
    """Return an import name and package flag for a Python evidence file."""
    if not relative_path.endswith(".py"):
        return None
    source_path = relative_path.removeprefix("src/").removesuffix(".py")
    module = source_path.replace("/", ".")
    is_package = module.endswith(".__init__")
    return (module.removesuffix(".__init__") if is_package else module, is_package)


def _resolve_relative_import(
    current_module: str,
    *,
    is_package: bool,
    level: int,
    module: str | None,
) -> str | None:
    """Resolve an ``ImportFrom`` target to its absolute module spelling."""
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
    """Resolve imports, local aliases, and exact ``from`` members."""
    imports: set[str] = set()
    aliases: dict[str, str] = {}
    from_members: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_relative_import(
                current_module,
                is_package=is_package,
                level=node.level,
                module=node.module,
            )
            if target is None:
                continue
            # ``from . import member`` binds a concrete member, not a useful
            # reverse edge to the whole package. Keeping the package edge here
            # makes the transitive closure jump through ``cadrumo`` and turns a
            # family census into an unrelated whole-repository closure.
            if node.module is not None:
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
    """Return a dotted expression spelling only when every limb is static."""
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
    return reference if target is None else f"{target}{dot}{rest}" if dot else target


def _candidate_for_reference(reference: str, by_new_module: dict[str, RelocatedFamily]) -> RelocatedFamily | None:
    """Find the one candidate which owns a module or member reference."""
    module = reference
    while module:
        candidate = by_new_module.get(module)
        if candidate is not None:
            return candidate
        module = module.rpartition(".")[0]
    return None


def _is_type_alias(node: ast.AST) -> bool:
    """Return whether this interpreter exposes the PEP 695 ``TypeAlias`` node."""
    type_alias = getattr(ast, "TypeAlias", None)
    return isinstance(type_alias, type) and isinstance(node, type_alias)


def _annotation_expressions(tree: ast.AST) -> tuple[ast.AST, ...]:
    """Collect function, variable, and both legacy and PEP 695 alias expressions."""
    expressions: list[ast.AST] = []
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
        elif _is_type_alias(node):
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
                    parsed = ast.parse(node.value, mode="eval")
                except SyntaxError:
                    continue
                pending.append(parsed)
    return owners


def _facade_member_owners(candidates: tuple[RelocatedFamily, ...]) -> dict[str, str]:
    """Map each historic facade member and module stem to one exact row."""
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
    """Attribute each package-member access to its exact family owner."""
    package = "cadrumo.domain.calculations.registry"
    owners: set[str] = set()
    for imported_from, member in from_members:
        if imported_from != package:
            continue
        if member == "*":
            owners.update(member_owners.values())
        elif owner := member_owners.get(member):
            owners.add(owner)
    for node in ast.walk(tree):
        reference = _dotted_name(node)
        if reference is None:
            continue
        resolved = _resolve_import_alias(reference, aliases)
        if not resolved.startswith(f"{package}."):
            continue
        member = resolved.removeprefix(f"{package}.").split(".", maxsplit=1)[0]
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
    """Return the exact one-hop reverse edges beyond direct consumers.

    A recursive walk can jump from a package-level import to the entire project
    (for example through ``cadrumo``), which is not evidence of this leaf
    family's substitutability. The direct pass records every concrete consumer;
    this category preserves only its falsifiable immediate reverse edges.
    """
    paths: set[str] = set()
    for imported in (candidate_module, *direct_modules):
        for importer in importers.get(imported, ()):
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
    """Resolve a literal ``import_module`` target, including relative strings."""
    if not target.startswith("."):
        return target
    level = len(target) - len(target.lstrip("."))
    return _resolve_relative_import(module, is_package=is_package, level=level, module=target[level:] or None) or target


_EVIDENCE_CENSUS_CACHE: EvidenceCensus | None = None


def _all_evidence_consumers(candidates: tuple[RelocatedFamily, ...]) -> EvidenceCensus:
    """Census every candidate from the single immutable evidence corpus."""
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
        mentions_candidate = False
        for candidate in candidates:
            if candidate.old_module in text or candidate.new_module in text:
                hits[candidate.old_path][base].add(relative)
                mentions_candidate = True
        if not relative.endswith(".py"):
            continue
        # The regression measurements intentionally cover the application
        # source tree. Other authored Python is parsed only when it actually
        # references this registry family, so tooling and fixtures still retain
        # direct, package-attribute, annotation, and dynamic evidence without
        # inflating the source-language measurements.
        in_application_source = relative.startswith("src/cadrumo/")
        if not in_application_source and not mentions_candidate and "cadrumo.domain.calculations.registry" not in text:
            continue
        tree = ast.parse(text, filename=relative)
        consumer_module = _consumer_module_name(relative)
        if consumer_module is None:
            continue
        module, is_package = consumer_module
        module_paths[module].add(relative)
        imports, aliases, from_members = _python_import_context(tree, current_module=module, is_package=is_package)
        if in_application_source:
            relative_import_edges += sum(
                1 for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level > 0
            )
            type_alias_nodes += sum(1 for node in ast.walk(tree) if _is_type_alias(node))
        for imported in imports:
            importers[imported].add(module)
            candidate = _candidate_for_reference(imported, by_new_module)
            if candidate is not None:
                # A resolved relative ``ImportFrom`` may name neither the old
                # nor the public module textually (for example,
                # ``from .. import authority``).  It is nevertheless a direct
                # consumer in the evidence file's operational category.
                hits[candidate.old_path][base].add(relative)
                direct_modules[candidate.old_path].add(module)
        for old_path in _package_attribute_owners(
            tree,
            aliases=aliases,
            from_members=from_members,
            member_owners=member_owners,
        ):
            hits[old_path]["package_attribute"].add(relative)
            direct_modules[old_path].add(module)
        registrations = {
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("register")
        }
        for old_path in _annotation_owners(tree, aliases=aliases, by_new_module=by_new_module):
            hits[old_path]["annotation"].add(relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _dynamic_import_call(node, aliases)
            if callee is None or not node.args:
                continue
            site = f"{relative}:{node.lineno}"
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                target = _resolve_dynamic_target(argument.value, module=module, is_package=is_package)
                candidate = _candidate_for_reference(target, by_new_module)
                if candidate is not None:
                    hits[candidate.old_path]["dynamic_target"].add(relative)
                    literal_dynamic.append({"site": site, "target": target, "row_path": candidate.old_path})
            else:
                unresolved_dynamic.append({"site": site, "callee": callee, "expression": ast.unparse(argument)})
        for candidate in candidates:
            if any(candidate.new_module in registration for registration in registrations):
                hits[candidate.old_path]["registration"].add(relative)
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
    """Return the cached census bound to ``EVIDENCE_COMMIT``."""
    global _EVIDENCE_CENSUS_CACHE
    if _EVIDENCE_CENSUS_CACHE is None:
        _EVIDENCE_CENSUS_CACHE = _all_evidence_consumers(exact_relocation_candidates())
    return _EVIDENCE_CENSUS_CACHE


def _top_level_binding_details(path: str, text: str, symbols: set[str]) -> dict[str, list[dict[str, object]]]:
    """Locate top-level definitions and imports for the requested symbols."""
    locations: dict[str, list[dict[str, object]]] = {symbol: [] for symbol in symbols}
    tree = ast.parse(text, filename=path)
    for node in tree.body:
        bindings: list[tuple[str, str]] = []
        if isinstance(node, ast.ClassDef):
            bindings.append((node.name, "class_definition"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bindings.append((node.name, "function_definition"))
        elif isinstance(node, ast.Assign):
            bindings.extend((target.id, "assignment") for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bindings.append((node.target.id, "annotated_assignment"))
        elif isinstance(node, ast.Import):
            bindings.extend((alias.asname or alias.name.split(".")[0], "import") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bindings.extend((alias.asname or alias.name, "import_from") for alias in node.names if alias.name != "*")
        elif _is_type_alias(node):
            alias_name = getattr(node, "name", None)
            if isinstance(alias_name, ast.Name):
                bindings.append((alias_name.id, "type_alias"))
            elif isinstance(alias_name, str):
                bindings.append((alias_name, "type_alias"))
        for name, node_type in bindings:
            if name in locations:
                locations[name].append({"symbol": name, "path": path, "line": node.lineno, "node_type": node_type})
    return locations


def _evidence_symbol_locator_details(
    candidate: RelocatedFamily, symbols: tuple[str, ...]
) -> dict[str, list[dict[str, object]]]:
    """Read current-module binding evidence only from the reviewed commit."""
    return _top_level_binding_details(candidate.new_path, _evidence_text(candidate.new_path), set(symbols))


def _evidence_symbol_locators(candidate: RelocatedFamily, symbols: tuple[str, ...]) -> dict[str, list[str]]:
    """Return the compact locator arrays stored in the checked matrix."""
    details = _evidence_symbol_locator_details(candidate, symbols)
    return {symbol: [f"{detail['path']}:{detail['line']}" for detail in details[symbol]] for symbol in symbols}


def _all_symbol_definition_sites(
    candidates: tuple[RelocatedFamily, ...],
    symbols: set[str],
) -> dict[str, list[dict[str, object]]]:
    """Census competing definitions/imports across all 78 c941 destinations.

    The semantic question is whether another mechanically-relocated registry
    family member can substitute for a reviewed owner. Restricting this census
    to the complete candidate family avoids treating ordinary third-party names
    as architectural alternatives while preserving every in-family locator.
    """
    sites: dict[str, list[dict[str, object]]] = {symbol: [] for symbol in symbols}
    for candidate in candidates:
        details = _top_level_binding_details(candidate.new_path, _evidence_text(candidate.new_path), symbols)
        for symbol, values in details.items():
            sites[symbol].extend(values)
    return {symbol: sorted(values, key=_definition_site_sort_key) for symbol, values in sites.items()}


def _definition_site_sort_key(item: dict[str, object]) -> tuple[str, int]:
    """Return the checked path/line ordering key for one structured locator."""
    path = item.get("path")
    line = item.get("line")
    if not isinstance(path, str) or not isinstance(line, int):
        raise RuntimeError("structured definition site has no path/line anchor")
    return path, line


def _structured_semantic_evidence(
    candidate: RelocatedFamily,
    *,
    locator_details: dict[str, list[dict[str, object]]],
    definition_sites: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    """Record falsifiable owner, competing-site, and substitutability evidence."""
    owner_definition_locators = [detail for symbol in sorted(locator_details) for detail in locator_details[symbol]]
    competing_site_census = {
        symbol: [detail for detail in definition_sites[symbol] if detail["path"] != candidate.new_path]
        for symbol in sorted(locator_details)
        if any(detail["path"] != candidate.new_path for detail in definition_sites[symbol])
    }
    competing_count = sum(len(values) for values in competing_site_census.values())
    return {
        "owner_definition_locators": owner_definition_locators,
        "competing_site_census": competing_site_census,
        "substitutability": {
            "result": "candidate_owner_not_substitutable",
            "rationale": (
                f"{candidate.old_path} maps one-to-one to {candidate.new_path} in c941; "
                f"{len(owner_definition_locators)} reviewed owner bindings and {competing_count} competing bindings "
                "were measured from immutable AST evidence. Same-name bindings are not substitutes "
                "for the reviewed owner."
            ),
        },
        "anchors": {
            "evidence_commit": EVIDENCE_COMMIT,
            "relocation_pair": [candidate.old_path, candidate.new_path],
            "competing_site_scope": "all_78_c941_destination_modules",
        },
    }


def generated_rows() -> list[dict[str, object]]:
    """Produce the exact c941 family rows from immutable evidence only."""
    candidates = exact_relocation_candidates()
    facade_exports = _historic_facade_exports()
    locator_details = {
        candidate.old_path: _evidence_symbol_locator_details(candidate, facade_exports.get(candidate.old_path, ()))
        for candidate in candidates
    }
    locators = {
        old_path: {
            symbol: [f"{detail['path']}:{detail['line']}" for detail in details]
            for symbol, details in per_symbol.items()
        }
        for old_path, per_symbol in locator_details.items()
    }
    definition_sites = _all_symbol_definition_sites(
        candidates,
        {symbol for symbols in facade_exports.values() for symbol in symbols},
    )
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
                    locator_details=locator_details[candidate.old_path],
                    definition_sites=definition_sites,
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
        "evidence_commit": EVIDENCE_COMMIT,
        "consumer_categories": list(CONSUMER_CATEGORIES),
        "dynamic_imports": _evidence_census().dynamic_imports,
        "evidence_measurements": _evidence_census().measurements,
        "review_status": "pending_independent_architecture_review",
        "rows": generated_rows(),
        "final_package_gate": None,
    }


def _terminal_destinations(row: dict[str, object]) -> list[dict[str, object]]:
    """Return explicit final paths without preserving compatibility surfaces."""
    new_path = row.get("new_path")
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
    """Supply a future defining destination whenever immutable source lacks one."""
    symbols = generated.get("facade_exported_symbols")
    locators = generated.get("current_symbol_locators")
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


def _reviewed_rag_discovery(row: dict[str, object]) -> dict[str, dict[str, object]] | None:
    """Return one manually retained, genuine RAG discovery for a reviewed pair."""
    pair = (row.get("old_path"), row.get("new_path"))
    discovery = RAG_DISCOVERY_BY_PAIR.get(pair)
    if discovery is None:
        return None
    return {"query": dict(discovery["query"]), "result": dict(discovery["result"])}


def _validate_rag_discovery(row: dict[str, object]) -> None:
    """Require real search payloads only for the two reviewed semantic queries."""
    discovery = _reviewed_rag_discovery(row)
    rag_query = row.get("rag_query")
    rag_result = row.get("rag_result")
    if discovery is None:
        if rag_query is not None or rag_result is not None:
            raise RuntimeError(f"registry facade row {row.get('old_path')} has an unperformed RAG discovery")
        return
    if not isinstance(rag_query, dict) or set(rag_query) != RAG_QUERY_FIELDS:
        raise RuntimeError(f"registry facade row {row.get('old_path')} has malformed RAG query evidence")
    if not isinstance(rag_result, dict) or set(rag_result) != RAG_RESULT_FIELDS:
        raise RuntimeError(f"registry facade row {row.get('old_path')} has malformed RAG result evidence")
    if (
        not isinstance(rag_query["text"], str)
        or not rag_query["text"]
        or rag_query["type"] != "code"
        or rag_query["domain"] != "prod"
        or rag_query["prefer"] != "production"
        or not isinstance(rag_query["request_id"], str)
        or not rag_query["request_id"]
        or not isinstance(rag_result["id"], str)
        or not rag_result["id"]
        or not isinstance(rag_result["path"], str)
        or not rag_result["path"].startswith("src/")
        or not isinstance(rag_result["score"], float)
        or rag_result["source"] != "codebase"
        or not isinstance(rag_result["line_start"], int)
        or not isinstance(rag_result["line_end"], int)
        or rag_result["line_start"] < 1
        or rag_result["line_end"] < rag_result["line_start"]
        or rag_result["node_type"] is not None
        or rag_result["function_name"] is not None
        or rag_result["class_name"] is not None
    ):
        raise RuntimeError(f"registry facade row {row.get('old_path')} has invalid RAG result field values")
    if rag_query != discovery["query"] or rag_result != discovery["result"]:
        raise RuntimeError(f"registry facade row {row.get('old_path')} RAG discovery drifted from its review record")


def _alternative_owner_evidence(row: dict[str, object], generated: dict[str, object]) -> str:
    """Summarize the row-specific owner comparison at its immutable anchor."""
    owner = row.get("semantic_owner")
    if not isinstance(owner, str):
        raise RuntimeError("alternative-owner evidence requires a reviewed semantic owner")
    semantic = generated.get("semantic_evidence")
    if not isinstance(semantic, dict):
        raise RuntimeError("alternative-owner evidence requires structured semantic evidence")
    competing = semantic.get("competing_site_census")
    competing_count = sum(len(values) for values in competing.values()) if isinstance(competing, dict) else 0
    discovery = _reviewed_rag_discovery(row)
    if discovery is not None:
        query = discovery["query"]
        result = discovery["result"]
        return (
            f"Vaultspec-RAG code query {query['text']!r} (request {query['request_id']}) selected "
            f"{result['path']}:{result['line_start']}-{result['line_end']} for {owner}; immutable evidence "
            f"{EVIDENCE_COMMIT} separately records {competing_count} non-owner bindings, none substitutable "
            "for this c941 pair."
        )
    return (
        f"Immutable evidence {EVIDENCE_COMMIT} anchors {owner}; "
        f"the full competing-site census records {competing_count} non-owner bindings, "
        "none substitutable for this c941 pair."
    )


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
    for generated in expected:
        pair = (generated["old_path"], generated["new_path"])
        existing = existing_by_pair[pair]
        semantic_owner = existing.get("semantic_owner")
        if not isinstance(semantic_owner, str) or not semantic_owner:
            raise RuntimeError(f"reviewed matrix row {pair[0]} lacks its semantic owner")
        refreshed = {
            field: existing[field]
            for field in (
                "semantic_owner",
                "disposition",
                "terminal_state",
                "follow_on_step_id",
                "follow_on_action",
                "follow_on_scope",
                "follow_on_predecessors",
            )
        }
        refreshed.update({field: generated[field] for field in derived_fields})
        discovery = _reviewed_rag_discovery(refreshed)
        refreshed["rag_query"] = None if discovery is None else discovery["query"]
        refreshed["rag_result"] = None if discovery is None else discovery["result"]
        refreshed["alternative_owner_evidence"] = _alternative_owner_evidence(refreshed, generated)
        refreshed["terminal_destinations"] = _terminal_destinations(refreshed)
        refreshed["symbol_terminal_destinations"] = _symbol_terminal_destinations(refreshed, generated)
        refreshed_rows.append(refreshed)
    refreshed_document = dict(document)
    refreshed_document["schema_version"] = MATRIX_VERSION
    refreshed_document["relocation_commit"] = RELOCATION_COMMIT
    refreshed_document["evidence_commit"] = EVIDENCE_COMMIT
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
        "evidence_commit",
        "consumer_categories",
        "dynamic_imports",
        "evidence_measurements",
        "review_status",
        "rows",
        "final_package_gate",
    }
    if set(document) != required_document_fields:
        raise RuntimeError("registry facade matrix document schema is incomplete or has unrelated fields")
    if (
        document.get("schema_version") != MATRIX_VERSION
        or document.get("relocation_commit") != RELOCATION_COMMIT
        or document.get("evidence_commit") != EVIDENCE_COMMIT
    ):
        raise RuntimeError(
            "registry facade matrix has the wrong schema, relocation commit, or immutable evidence commit"
        )
    if document.get("consumer_categories") != list(CONSUMER_CATEGORIES):
        raise RuntimeError("registry facade matrix consumer-category schema drifted")
    if document.get("review_status") != "pending_independent_architecture_review":
        raise RuntimeError("registry facade matrix must retain its pending independent-review status")
    evidence_census = _evidence_census()
    if document.get("dynamic_imports") != evidence_census.dynamic_imports:
        raise RuntimeError("registry facade matrix immutable dynamic-import evidence drifted")
    if document.get("evidence_measurements") != evidence_census.measurements:
        raise RuntimeError("registry facade matrix immutable parser measurements drifted")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 78:
        raise RuntimeError("registry facade matrix must contain exactly 78 rows")
    expected = generated_rows()
    expected_pairs = set(mechanical_relocation_pairs())
    actual_pairs = {(row.get("old_path"), row.get("new_path")) for row in rows if isinstance(row, dict)}
    if actual_pairs != expected_pairs:
        raise RuntimeError("registry facade matrix is missing, extra, duplicate, or unrelated c941 rows")
    steps: set[str] = set()
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
        for derived_field in ("facade_exported_symbols", "current_symbol_locators", "consumers", "semantic_evidence"):
            if row.get(derived_field) != generated[derived_field]:
                raise RuntimeError(f"registry facade immutable evidence drifted for {pair[0]} ({derived_field})")
        for field in (
            "semantic_owner",
            "alternative_owner_evidence",
            "disposition",
            "terminal_state",
            "follow_on_step_id",
            "follow_on_action",
            "follow_on_scope",
        ):
            if not isinstance(row.get(field), str) or not row[field]:
                raise RuntimeError(f"registry facade row {pair[0]} lacks reviewed {field}")
        _validate_rag_discovery(row)
        if row["alternative_owner_evidence"] != _alternative_owner_evidence(row, generated):
            raise RuntimeError(f"registry facade row {pair[0]} alternative-owner evidence drifted")
        semantic_evidence = row.get("semantic_evidence")
        if not isinstance(semantic_evidence, dict) or set(semantic_evidence) != {
            "owner_definition_locators",
            "competing_site_census",
            "substitutability",
            "anchors",
        }:
            raise RuntimeError(f"registry facade row {pair[0]} lacks structured semantic evidence")
        anchors = semantic_evidence["anchors"]
        if not isinstance(anchors, dict) or anchors.get("evidence_commit") != EVIDENCE_COMMIT:
            raise RuntimeError(f"registry facade row {pair[0]} has no immutable evidence anchor")
        if anchors.get("relocation_pair") != [row["old_path"], row["new_path"]]:
            raise RuntimeError(f"registry facade row {pair[0]} semantic evidence has another relocation pair")
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
                raise RuntimeError(
                    f"registry facade row {pair[0]} has no source/import or terminal locator for {symbol}"
                )
        if terminal_symbols != _symbol_terminal_destinations(row, generated):
            raise RuntimeError(f"registry facade row {pair[0]} symbol terminal destinations drifted")
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
        if destinations != _terminal_destinations(row):
            raise RuntimeError(f"registry facade row {pair[0]} terminal destinations drifted")
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
    """Report current disposition progress without dereferencing historic evidence.

    Unlike the immutable evidence check, this operates against the current tree
    so future hard moves, privatizations, and deletions can be observed. Missing
    retired paths are valid terminal candidates, never a reason to recreate a
    facade alias, forwarding module, or re-export.
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
        observed: list[dict[str, object]] = []
        for destination in destinations:
            if (
                not isinstance(destination, dict)
                or not isinstance(destination.get("path"), str)
                or not isinstance(destination.get("role"), str)
                or not isinstance(destination.get("allowed_absence"), bool)
            ):
                raise RuntimeError(f"current terminal report has malformed destinations for {row.get('old_path')}")
            observed.append(
                {
                    "path": destination["path"],
                    "role": destination["role"],
                    "exists": path_exists(destination["path"]),
                    "allowed_absence": destination["allowed_absence"],
                }
            )
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
        "current_state_root": "working_tree",
        "evidence_commit": document.get("evidence_commit"),
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
