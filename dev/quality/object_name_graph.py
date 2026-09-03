"""Deterministic dependency components for reviewed object-name rename operations.

This module owns scheduling evidence, not rename intent.  Callers project the
reviewed manifest onto primitive operation, finding, definition-path, and allowlist
mappings.  The graph then combines those mappings with hard reference evidence and
returns indivisible operation-to-file components.  Semantic and clone evidence is
carried alongside a component but can never connect two operations.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, Protocol

import grimp

from .._paths import REPO_ROOT

_GRAPH_SCHEMA_VERSION: Final[int] = 1
_FIRST_PARTY_ROOTS: Final[tuple[str, ...]] = ("cadrumo", "cadrumo_harness", "dev")


class ObjectNameGraphError(RuntimeError):
    """Raised when graph evidence cannot prove a bounded rename component."""


class ReferenceKind(StrEnum):
    """Hard reference classes that make a file part of a rename component."""

    COLLISION_MEMBER = "collision-member"
    DEFINITION = "definition"
    DYNAMIC_IMPORT = "dynamic-import"
    EXPORT = "export"
    GENERATED_ARTIFACT = "generated-artifact"
    RUNTIME_IMPORT = "runtime-import"
    SYMBOL_IMPORT = "symbol-import"
    TYPE_ONLY_IMPORT = "type-only-import"


@dataclass(frozen=True, slots=True)
class HardEdge:
    """One operation-to-file dependency established by non-advisory evidence."""

    operation_id: str
    path: str
    kind: ReferenceKind
    detail: str = ""
    direct_importer_count: int = 0
    generator_owner: str | None = None


@dataclass(frozen=True, slots=True)
class AdvisoryEvidence:
    """Semantic, clone, or path evidence that may rank but never join components."""

    source: str
    detail: str
    paths: tuple[str, ...] = ()
    weight: int = 0


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    """Explainable component risk signals in their scheduling order."""

    generated_artifact_count: int
    dynamic_reference_count: int
    boundary_crossing_count: int
    affected_file_count: int
    operation_count: int
    maximum_direct_fan_in: int
    advisory: tuple[AdvisoryEvidence, ...]

    def ordering_key(self, component_id: str) -> tuple[int, int, int, int, int, int, str]:
        """Return the transparent low-risk-first scheduling key."""
        return (
            self.generated_artifact_count,
            self.dynamic_reference_count,
            self.boundary_crossing_count,
            self.affected_file_count,
            self.operation_count,
            self.maximum_direct_fan_in,
            component_id,
        )


@dataclass(frozen=True, slots=True)
class OperationComponent:
    """An indivisible connected component of operations and affected files."""

    component_id: str
    operation_ids: tuple[str, ...]
    affected_paths: tuple[str, ...]
    hard_edges: tuple[HardEdge, ...]
    risk: RiskEvidence

    @property
    def scheduling_key(self) -> tuple[int, int, int, int, int, int, str]:
        """Return the deterministic, low-risk-first component ordering key."""
        return self.risk.ordering_key(self.component_id)


@dataclass(frozen=True, slots=True)
class OperationLocator:
    """Minimal graph projection of a reviewed operation's old definition."""

    operation_id: str
    module: str
    definition_path: str
    symbol: str | None = None


class RenameOperationLike(Protocol):
    """Structural projection implemented by the reviewed manifest operation."""

    operation_id: str
    finding_id: str
    old_locator: str
    old_path: str
    changed_paths: tuple[str, ...]
    expected_reference_classes: tuple[str, ...]


class RenameManifestLike(Protocol):
    """Structural manifest seam used without redefining manifest authority."""

    operations: tuple[RenameOperationLike, ...]


class InventoryFindingLike(Protocol):
    """Finding fields needed to recover every collision definition path."""

    id: str
    qualified_sites: tuple[str, ...]


class InventoryDeclarationLike(Protocol):
    """Declaration fields needed to map qualified finding sites to files."""

    qualified_locator: str
    path: str


class InventoryLike(Protocol):
    """Structural seam implemented by the canonical object-name inventory."""

    findings: tuple[InventoryFindingLike, ...]
    declarations: tuple[InventoryDeclarationLike, ...]


def operation_locators(manifest: RenameManifestLike) -> tuple[OperationLocator, ...]:
    """Project reviewed manifest operations onto import-graph locators."""
    locators: list[OperationLocator] = []
    for operation in manifest.operations:
        try:
            kind, qualified_binding = operation.old_locator.split(":", 1)
            qualified, _binding = qualified_binding.rsplit("#binding=", 1)
        except ValueError as exc:
            raise ObjectNameGraphError(
                f"operation {operation.operation_id!r} has malformed old locator {operation.old_locator!r}"
            ) from exc
        if kind == "module":
            module, symbol = qualified, None
        else:
            module, separator, symbol = qualified.rpartition(".")
            if not separator:
                raise ObjectNameGraphError(f"operation {operation.operation_id!r} symbol locator has no owning module")
        locators.append(OperationLocator(operation.operation_id, module, operation.old_path, symbol))
    return tuple(sorted(locators, key=lambda item: item.operation_id))


def build_manifest_components(
    manifest: RenameManifestLike,
    *,
    inventory: InventoryLike,
    hard_edges: Iterable[HardEdge] = (),
    advisory_evidence: Iterable[AdvisoryEvidence] = (),
) -> tuple[OperationComponent, ...]:
    """Build components from the landed manifest seam without duplicating its model."""
    operations = tuple(manifest.operations)
    declarations_by_locator: dict[str, set[str]] = defaultdict(set)
    for declaration in inventory.declarations:
        declarations_by_locator[declaration.qualified_locator].add(declaration.path)
    findings_by_id = {finding.id: finding for finding in inventory.findings}
    collision_paths: dict[str, tuple[str, ...]] = {}
    for operation in operations:
        finding = findings_by_id.get(operation.finding_id)
        if finding is None:
            raise ObjectNameGraphError(f"operation {operation.operation_id!r} names an unknown finding")
        paths = {path for locator in finding.qualified_sites for path in declarations_by_locator.get(locator, ())}
        if not paths:
            raise ObjectNameGraphError(
                f"finding {operation.finding_id!r} has no declaration paths in the canonical inventory"
            )
        collision_paths[operation.operation_id] = tuple(sorted(paths))
    components = build_operation_components(
        (operation.operation_id for operation in operations),
        finding_ids={operation.operation_id: operation.finding_id for operation in operations},
        definition_paths={operation.operation_id: operation.old_path for operation in operations},
        collision_paths=collision_paths,
        changed_path_allowlists={operation.operation_id: operation.changed_paths for operation in operations},
        hard_edges=hard_edges,
        advisory_evidence=advisory_evidence,
    )
    edges_by_operation: dict[str, list[HardEdge]] = defaultdict(list)
    for component in components:
        for edge in component.hard_edges:
            edges_by_operation[edge.operation_id].append(edge)
    for operation in operations:
        observed = {_manifest_reference_class(edge.kind) for edge in edges_by_operation[operation.operation_id]}
        component = next(item for item in components if operation.operation_id in item.operation_ids)
        operation_kinds_by_path: dict[str, set[ReferenceKind]] = defaultdict(set)
        operations_by_path: dict[str, set[str]] = defaultdict(set)
        for edge in component.hard_edges:
            operation_kinds_by_path[edge.path].add(edge.kind)
            operations_by_path[edge.path].add(edge.operation_id)
        if any(
            operation.operation_id in operations_by_path[path]
            and len(operations_by_path[path]) > 1
            and bool(operation_kinds_by_path[path] - {ReferenceKind.COLLISION_MEMBER, ReferenceKind.DEFINITION})
            for path in component.affected_paths
        ):
            observed.add("shared-consumer")
        expected = set(operation.expected_reference_classes)
        if observed != expected:
            raise ObjectNameGraphError(
                f"operation {operation.operation_id!r} reference classes differ from reviewed intent; "
                f"expected={sorted(expected)!r}, observed={sorted(observed)!r}"
            )
    return components


def _manifest_reference_class(kind: ReferenceKind) -> str:
    return {
        ReferenceKind.COLLISION_MEMBER: "definition",
        ReferenceKind.DEFINITION: "definition",
        ReferenceKind.DYNAMIC_IMPORT: "dynamic-target",
        ReferenceKind.EXPORT: "export",
        ReferenceKind.GENERATED_ARTIFACT: "generated-artifact",
        ReferenceKind.RUNTIME_IMPORT: "static-import",
        ReferenceKind.SYMBOL_IMPORT: "static-import",
        ReferenceKind.TYPE_ONLY_IMPORT: "type-only-import",
    }[kind]


def _normalise_path(path: str) -> str:
    if "\\" in path or ":" in path:
        raise ObjectNameGraphError(f"graph path must be normalized POSIX: {path!r}")
    candidate = PurePosixPath(path)
    if (
        not path
        or candidate.is_absolute()
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or candidate.as_posix() != path
    ):
        raise ObjectNameGraphError(f"graph path must be repository-relative: {path!r}")
    return path


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _component_id(operation_ids: Sequence[str], edges: Sequence[HardEdge]) -> str:
    payload = {
        "schema_version": _GRAPH_SCHEMA_VERSION,
        "operation_ids": list(operation_ids),
        "hard_edges": [
            {
                "operation_id": edge.operation_id,
                "path": edge.path,
                "kind": edge.kind,
                "detail": edge.detail,
                "direct_importer_count": edge.direct_importer_count,
                "generator_owner": edge.generator_owner,
            }
            for edge in edges
        ],
    }
    return f"sha256:{hashlib.sha256(_canonical_json(payload)).hexdigest()}"


def _boundary(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts:
        return ""
    if parts[0] == "dev":
        return "dev"
    if len(parts) >= 3 and parts[0] == "src":
        if parts[1] == "cadrumo" and len(parts) >= 3:
            if len(parts) == 3 and PurePosixPath(path).suffix == ".py":
                return "src/cadrumo"
            return f"src/cadrumo/{parts[2]}"
        return f"src/{parts[1]}"
    return parts[0]


def _edge_key(edge: HardEdge) -> tuple[str, str, str, str, int, str]:
    return (
        edge.operation_id,
        edge.path,
        edge.kind,
        edge.detail,
        edge.direct_importer_count,
        edge.generator_owner or "",
    )


def _validated_edge(edge: HardEdge, operation_ids: frozenset[str]) -> HardEdge:
    if edge.operation_id not in operation_ids:
        raise ObjectNameGraphError(f"hard edge names unknown operation {edge.operation_id!r}")
    if edge.direct_importer_count < 0:
        raise ObjectNameGraphError("direct importer count cannot be negative")
    path = _normalise_path(edge.path)
    if edge.kind is ReferenceKind.GENERATED_ARTIFACT and not edge.generator_owner:
        raise ObjectNameGraphError(f"generated artifact {path!r} for {edge.operation_id!r} has no owning generator")
    return HardEdge(
        operation_id=edge.operation_id,
        path=path,
        kind=edge.kind,
        detail=edge.detail,
        direct_importer_count=edge.direct_importer_count,
        generator_owner=edge.generator_owner,
    )


def build_operation_components(
    operation_ids: Iterable[str],
    *,
    finding_ids: Mapping[str, str],
    definition_paths: Mapping[str, str],
    collision_paths: Mapping[str, Collection[str]],
    changed_path_allowlists: Mapping[str, Collection[str]],
    hard_edges: Iterable[HardEdge] = (),
    advisory_evidence: Iterable[AdvisoryEvidence] = (),
) -> tuple[OperationComponent, ...]:
    """Build deterministic operation-to-file connected components.

    Every definition and every definition participating in the same finding is a
    hard edge.  Additional reference evidence may add import, export, dynamic, or
    generated surfaces.  Every discovered hard path must already be named by the
    reviewed operation's changed-path allowlist.  Extra allowlist entries do not
    create edges; actual-write equality is enforced later by rehearsal.
    """
    operations = tuple(sorted(operation_ids))
    operation_set = frozenset(operations)
    if not operations or len(operation_set) != len(operations):
        raise ObjectNameGraphError("operation identifiers must be non-empty and unique")
    required_keys = (set(finding_ids), set(definition_paths), set(collision_paths), set(changed_path_allowlists))
    if any(keys != set(operation_set) for keys in required_keys):
        raise ObjectNameGraphError("finding, definition, and allowlist mappings must exactly cover operations")

    allowlists = {
        operation_id: frozenset(_normalise_path(path) for path in changed_path_allowlists[operation_id])
        for operation_id in operations
    }
    definitions = {operation_id: _normalise_path(definition_paths[operation_id]) for operation_id in operations}
    for operation_id in operations:
        finding_id = finding_ids[operation_id]
        if not finding_id:
            raise ObjectNameGraphError(f"operation {operation_id!r} has no finding identifier")

    collected: set[HardEdge] = set()
    for operation_id in operations:
        collected.add(HardEdge(operation_id, definitions[operation_id], ReferenceKind.DEFINITION))
        for collision_path in sorted({_normalise_path(path) for path in collision_paths[operation_id]}):
            if collision_path != definitions[operation_id]:
                collected.add(
                    HardEdge(
                        operation_id,
                        collision_path,
                        ReferenceKind.COLLISION_MEMBER,
                        detail=f"finding:{finding_ids[operation_id]}",
                    )
                )
    collected.update(_validated_edge(edge, operation_set) for edge in hard_edges)
    edges = tuple(sorted(collected, key=_edge_key))

    for edge in edges:
        if edge.path not in allowlists[edge.operation_id]:
            raise ObjectNameGraphError(
                f"hard reference {edge.path!r} ({edge.kind}) is outside the changed-path allowlist "
                f"for {edge.operation_id!r}"
            )

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        operation_node = f"operation:{edge.operation_id}"
        file_node = f"file:{edge.path}"
        adjacency[operation_node].add(file_node)
        adjacency[file_node].add(operation_node)

    advisories = tuple(
        sorted(
            (
                AdvisoryEvidence(
                    source=item.source,
                    detail=item.detail,
                    paths=tuple(sorted(_normalise_path(path) for path in item.paths)),
                    weight=item.weight,
                )
                for item in advisory_evidence
            ),
            key=lambda item: (item.source, item.paths, -item.weight, item.detail),
        )
    )
    components: list[OperationComponent] = []
    unseen = {f"operation:{operation_id}" for operation_id in operations}
    while unseen:
        start = min(unseen)
        pending = [start]
        visited: set[str] = set()
        while pending:
            node = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            pending.extend(sorted(adjacency[node] - visited, reverse=True))
        component_operations = tuple(
            sorted(node.removeprefix("operation:") for node in visited if node.startswith("operation:"))
        )
        component_paths = tuple(sorted(node.removeprefix("file:") for node in visited if node.startswith("file:")))
        component_edges = tuple(edge for edge in edges if edge.operation_id in component_operations)
        component_advisory = tuple(
            item for item in advisories if not item.paths or set(item.paths) & set(component_paths)
        )
        boundaries = {_boundary(path) for path in component_paths}
        risk = RiskEvidence(
            generated_artifact_count=sum(edge.kind is ReferenceKind.GENERATED_ARTIFACT for edge in component_edges),
            dynamic_reference_count=sum(edge.kind is ReferenceKind.DYNAMIC_IMPORT for edge in component_edges),
            boundary_crossing_count=max(0, len(boundaries) - 1),
            affected_file_count=len(component_paths),
            operation_count=len(component_operations),
            maximum_direct_fan_in=max((edge.direct_importer_count for edge in component_edges), default=0),
            advisory=component_advisory,
        )
        identifier = _component_id(component_operations, component_edges)
        components.append(OperationComponent(identifier, component_operations, component_paths, component_edges, risk))
        unseen.difference_update(f"operation:{operation_id}" for operation_id in component_operations)
    return tuple(sorted(components, key=lambda component: component.scheduling_key))


def _module_path(module: str, repo_root: Path) -> str:
    parts = module.split(".")
    roots = (repo_root / "dev",) if parts[0] == "dev" else (repo_root / "src",)
    relative_parts = parts[1:] if parts[0] == "dev" else parts
    for root in roots:
        module_path = root.joinpath(*relative_parts).with_suffix(".py")
        package_path = root.joinpath(*relative_parts, "__init__.py")
        for path in (module_path, package_path):
            if path.is_file():
                return path.relative_to(repo_root).as_posix()
    raise ObjectNameGraphError(f"first-party module {module!r} does not map to a source file")


def _module_name(path: Path, repo_root: Path) -> str:
    relative = path.relative_to(repo_root)
    parts = list(relative.with_suffix("").parts)
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


@contextlib.contextmanager
def _bound_import_root(repo_root: Path) -> Iterator[None]:
    """Bind package discovery and the process directory to one verified tree."""
    resolved = repo_root.resolve()
    if not (resolved / "src").is_dir() or not (resolved / "dev").is_dir():
        raise ObjectNameGraphError(f"graph repository root lacks src/ or dev/: {resolved}")
    for package in _FIRST_PARTY_ROOTS:
        loaded = sys.modules.get(package)
        loaded_file = getattr(loaded, "__file__", None)
        if loaded_file is not None and not Path(loaded_file).resolve().is_relative_to(resolved):
            raise ObjectNameGraphError(f"loaded package {package!r} belongs to a different tree: {loaded_file}")
    original_path = list(sys.path)
    original_directory = Path.cwd()
    sys.path[:0] = [str(resolved / "src"), str(resolved)]
    os.chdir(resolved)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        os.chdir(original_directory)
        sys.path[:] = original_path
        importlib.invalidate_caches()


def _qualified_expression(node: ast.expr, bindings: Mapping[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return bindings.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _qualified_expression(node.value, bindings)
        return None if owner is None else f"{owner}.{node.attr}"
    return None


def _import_bindings(tree: ast.Module, owner: str, *, package_module: bool) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                bindings[local] = alias.name if alias.asname else local
        elif isinstance(node, ast.ImportFrom):
            target = _import_from_target(node, owner, package_module=package_module)
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = f"{target}.{alias.name}"
    return bindings


def _type_checking_node_ids(tree: ast.Module) -> frozenset[int]:
    """Return nodes lexically guarded by a conventional positive TYPE_CHECKING test."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_guard = isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        is_guard = is_guard or (
            isinstance(test, ast.Attribute)
            and isinstance(test.value, ast.Name)
            and test.value.id == "typing"
            and test.attr == "TYPE_CHECKING"
        )
        if is_guard:
            guarded.update(id(descendant) for statement in node.body for descendant in ast.walk(statement))
    return frozenset(guarded)


def _call_argument(node: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(node.args) > position:
        return node.args[position]
    return next((item.value for item in node.keywords if item.arg == keyword), None)


def _dynamic_target(node: ast.Call, owner: str, *, package_module: bool) -> tuple[bool, str | None]:
    name = _call_argument(node, 0, "name")
    if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
        return False, None
    target = name.value
    if not target.startswith("."):
        return True, target
    package_node = _call_argument(node, 1, "package")
    if isinstance(package_node, ast.Constant) and isinstance(package_node.value, str):
        package = package_node.value
    elif isinstance(package_node, ast.Name) and package_node.id == "__package__":
        package = owner if package_module else owner.rsplit(".", 1)[0]
    else:
        return False, None
    try:
        return True, importlib.util.resolve_name(target, package)
    except (ImportError, ValueError):
        return False, None


def _import_from_target(node: ast.ImportFrom, owner: str, *, package_module: bool) -> str:
    if node.level == 0:
        return node.module or ""
    package = owner if package_module else owner.rsplit(".", 1)[0]
    relative = f"{'.' * node.level}{node.module or ''}"
    try:
        return importlib.util.resolve_name(relative, package)
    except (ImportError, ValueError):
        return ""


def collect_import_edges(
    locators: Sequence[OperationLocator],
    *,
    repo_root: Path = REPO_ROOT,
    all_graph: grimp.ImportGraph | None = None,
    runtime_graph: grimp.ImportGraph | None = None,
) -> tuple[HardEdge, ...]:
    """Collect definition, runtime, type-only, symbol, export, and dynamic edges.

    Grimp supplies module-level reach.  A focused AST pass adds exact imported
    symbols, exports, and literal dynamic module targets.  Computed dynamic targets
    are returned as errors when the call occurs in an already affected importer;
    callers may also provide stricter manifest-specific dynamic evidence as hard
    edges before component construction.
    """
    if not locators:
        return ()
    if (all_graph is None) != (runtime_graph is None):
        raise ObjectNameGraphError("all-static and runtime import graphs must be injected together")
    if all_graph is None or runtime_graph is None:
        with _bound_import_root(repo_root):
            all_graph = grimp.build_graph(
                _FIRST_PARTY_ROOTS[0],
                *_FIRST_PARTY_ROOTS[1:],
                include_external_packages=False,
                exclude_type_checking_imports=False,
                cache_dir=None,
            )
            runtime_graph = grimp.build_graph(
                _FIRST_PARTY_ROOTS[0],
                *_FIRST_PARTY_ROOTS[1:],
                include_external_packages=False,
                exclude_type_checking_imports=True,
                cache_dir=None,
            )
    edges: set[HardEdge] = set()
    locators_by_module: dict[str, list[OperationLocator]] = defaultdict(list)
    for locator in locators:
        locators_by_module[locator.module].append(locator)
    all_importers_by_module = {
        locator.module: all_graph.find_modules_that_directly_import(locator.module) for locator in locators
    }
    runtime_importers_by_module = {
        locator.module: runtime_graph.find_modules_that_directly_import(locator.module) for locator in locators
    }
    for locator in sorted(locators, key=lambda item: item.operation_id):
        definition_path = _normalise_path(locator.definition_path)
        edges.add(HardEdge(locator.operation_id, definition_path, ReferenceKind.DEFINITION))
        if locator.module not in all_graph.modules:
            raise ObjectNameGraphError(f"old module {locator.module!r} is absent from the import graph")
        if locator.symbol is not None:
            continue
        all_importers = all_importers_by_module[locator.module]
        runtime_importers = runtime_importers_by_module[locator.module]
        for importer in sorted(all_importers):
            kind = ReferenceKind.RUNTIME_IMPORT if importer in runtime_importers else ReferenceKind.TYPE_ONLY_IMPORT
            edges.add(
                HardEdge(
                    locator.operation_id,
                    _module_path(importer, repo_root),
                    kind,
                    detail=f"imports:{locator.module}",
                    direct_importer_count=len(all_importers),
                )
            )

    dynamically_unresolved: list[tuple[str, int]] = []
    for path in sorted((*((repo_root / "src").rglob("*.py")), *((repo_root / "dev").rglob("*.py")))):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise ObjectNameGraphError(f"cannot inspect references in {relative}: {exc}") from exc
        owner = _module_name(path, repo_root)
        bindings = _import_bindings(tree, owner, package_module=path.name == "__init__.py")
        type_checking_nodes = _type_checking_node_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for locator in locators_by_module.get(node.value, ()):
                    edges.add(
                        HardEdge(
                            locator.operation_id,
                            relative,
                            ReferenceKind.DYNAMIC_IMPORT,
                            detail=f"literal-line:{node.lineno}",
                        )
                    )
            if isinstance(node, ast.ImportFrom):
                target = _import_from_target(node, owner, package_module=path.name == "__init__.py")
                for locator in locators_by_module.get(target, ()):
                    if not locator.symbol or not any(alias.name == locator.symbol for alias in node.names):
                        continue
                    if path.name == "__init__.py":
                        kind = ReferenceKind.EXPORT
                    elif id(node) in type_checking_nodes:
                        kind = ReferenceKind.TYPE_ONLY_IMPORT
                    else:
                        kind = ReferenceKind.SYMBOL_IMPORT
                    edges.add(HardEdge(locator.operation_id, relative, kind, detail=f"line:{node.lineno}"))
            if isinstance(node, ast.Attribute):
                expression = _qualified_expression(node, bindings)
                for locator in locators:
                    if locator.symbol is not None and expression == f"{locator.module}.{locator.symbol}":
                        kind = (
                            ReferenceKind.TYPE_ONLY_IMPORT
                            if id(node) in type_checking_nodes
                            else ReferenceKind.SYMBOL_IMPORT
                        )
                        edges.add(
                            HardEdge(
                                locator.operation_id,
                                relative,
                                kind,
                                detail=f"qualified-use-line:{node.lineno}",
                            )
                        )
            if not isinstance(node, ast.Call):
                continue
            called = _qualified_expression(node.func, bindings)
            if called not in {"importlib.import_module", "import_module", "__import__", "builtins.__import__"}:
                continue
            resolved, target = _dynamic_target(node, owner, package_module=path.name == "__init__.py")
            if resolved:
                for locator in locators_by_module.get(target or "", ()):
                    edges.add(
                        HardEdge(
                            locator.operation_id,
                            relative,
                            ReferenceKind.DYNAMIC_IMPORT,
                            detail=f"line:{node.lineno}",
                        )
                    )
            else:
                dynamically_unresolved.append((relative, node.lineno))
    already_affected = {edge.path for edge in edges}
    unresolved_affected = sorted(site for site in dynamically_unresolved if site[0] in already_affected)
    if unresolved_affected:
        rendered = ", ".join(f"{path}:{line}" for path, line in unresolved_affected)
        raise ObjectNameGraphError(f"unresolved dynamic import in affected surface(s): {rendered}")
    return tuple(sorted(edges, key=_edge_key))


def semantic_advisory(candidates: Iterable[object]) -> tuple[AdvisoryEvidence, ...]:
    """Project semantic-duplication candidates without granting them graph authority."""
    evidence: list[AdvisoryEvidence] = []
    for candidate in candidates:
        sites = tuple(str(site) for site in getattr(candidate, "sites", ()))
        paths = tuple(sorted({site.split(":", 1)[0].replace("\\", "/") for site in sites}))
        evidence.append(
            AdvisoryEvidence(
                source=f"semantic:{getattr(candidate, 'detector', 'unknown')}",
                detail=str(getattr(candidate, "fingerprint", "")),
                paths=paths,
                weight=int(getattr(candidate, "weight", 0)),
            )
        )
    return tuple(sorted(evidence, key=lambda item: (item.source, item.paths, -item.weight, item.detail)))


def clone_advisory(result: object) -> tuple[AdvisoryEvidence, ...]:
    """Project typed jscpd evidence while preserving an unavailable outcome."""
    outcome = str(getattr(result, "outcome", "unavailable"))
    reason = str(getattr(result, "reason", ""))
    groups = tuple(getattr(result, "groups", ()))
    if not groups:
        return (AdvisoryEvidence(source=f"clone:{outcome}", detail=reason),)
    evidence: list[AdvisoryEvidence] = []
    for group in groups:
        rendered = str(group.render())
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        evidence.append(AdvisoryEvidence(source=f"clone:{outcome}", detail=f"sha256:{digest}"))
    return tuple(sorted(evidence, key=lambda item: (item.source, item.detail)))
