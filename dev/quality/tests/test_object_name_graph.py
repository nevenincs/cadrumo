"""Detector-teeth tests for deterministic object-name rename components."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import grimp
import pytest

from ...audit.duplication import DuplicationResult
from ...audit.semantic_duplication import Candidate
from ..object_name_graph import (
    AdvisoryEvidence,
    HardEdge,
    InventoryLike,
    ObjectNameGraphError,
    OperationLocator,
    ReferenceKind,
    RenameManifestLike,
    build_manifest_components,
    build_operation_components,
    clone_advisory,
    collect_import_edges,
    semantic_advisory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclass(frozen=True)
class _Operation:
    operation_id: str
    finding_id: str
    old_locator: str
    old_path: str
    changed_paths: tuple[str, ...]
    expected_reference_classes: tuple[str, ...]


@dataclass(frozen=True)
class _Manifest:
    operations: tuple[_Operation, ...]


@dataclass(frozen=True)
class _Finding:
    id: str
    qualified_sites: tuple[str, ...]


@dataclass(frozen=True)
class _Declaration:
    qualified_locator: str
    path: str


@dataclass(frozen=True)
class _Inventory:
    findings: tuple[_Finding, ...]
    declarations: tuple[_Declaration, ...]


def _build(
    operation_ids: tuple[str, ...],
    *,
    edges: tuple[HardEdge, ...] = (),
    advisory: tuple[AdvisoryEvidence, ...] = (),
):
    definitions = {operation_id: f"src/cadrumo/{operation_id}.py" for operation_id in operation_ids}
    allowlists = {
        operation_id: {definitions[operation_id], *(edge.path for edge in edges if edge.operation_id == operation_id)}
        for operation_id in operation_ids
    }
    return build_operation_components(
        operation_ids,
        finding_ids={operation_id: f"finding-{operation_id}" for operation_id in operation_ids},
        definition_paths=definitions,
        collision_paths={operation_id: (definitions[operation_id],) for operation_id in operation_ids},
        changed_path_allowlists=allowlists,
        hard_edges=edges,
        advisory_evidence=advisory,
    )


def _write(root: Path, relative: str, source: str = "") -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def _graph(*modules: str, imports: tuple[tuple[str, str], ...] = ()) -> grimp.ImportGraph:
    graph = grimp.ImportGraph()
    for module in modules:
        graph.add_module(module)
    for importer, imported in imports:
        graph.add_import(importer=importer, imported=imported)
    return graph


def test_disjoint_operations_stay_isolated_until_a_consumer_is_shared() -> None:
    disjoint = _build(
        ("alpha", "beta"),
        edges=(
            HardEdge("alpha", "src/cadrumo/alpha_consumer.py", ReferenceKind.RUNTIME_IMPORT),
            HardEdge("beta", "src/cadrumo/beta_consumer.py", ReferenceKind.RUNTIME_IMPORT),
        ),
    )
    assert {component.operation_ids for component in disjoint} == {("alpha",), ("beta",)}

    shared_path = "src/cadrumo/shared_consumer.py"
    shared = _build(
        ("alpha", "beta"),
        edges=(
            HardEdge("alpha", shared_path, ReferenceKind.RUNTIME_IMPORT),
            HardEdge("beta", shared_path, ReferenceKind.SYMBOL_IMPORT),
        ),
    )
    assert len(shared) == 1
    assert shared[0].operation_ids == ("alpha", "beta")
    assert shared[0].affected_paths == (
        "src/cadrumo/alpha.py",
        "src/cadrumo/beta.py",
        shared_path,
    )


def test_every_hard_reference_class_is_preserved_and_explains_risk() -> None:
    edges = (
        HardEdge("alpha", "src/cadrumo/runtime.py", ReferenceKind.RUNTIME_IMPORT, direct_importer_count=7),
        HardEdge("alpha", "src/cadrumo/type_hint.py", ReferenceKind.TYPE_ONLY_IMPORT),
        HardEdge("alpha", "src/cadrumo/dynamic.py", ReferenceKind.DYNAMIC_IMPORT),
        HardEdge("alpha", "src/cadrumo/__init__.py", ReferenceKind.EXPORT),
        HardEdge("alpha", "src/cadrumo/symbol_user.py", ReferenceKind.SYMBOL_IMPORT),
        HardEdge("alpha", "src/cadrumo/collision.py", ReferenceKind.COLLISION_MEMBER),
        HardEdge("alpha", "docs/api/alpha.rst", ReferenceKind.GENERATED_ARTIFACT, generator_owner="apidocs"),
    )
    component = _build(("alpha",), edges=edges)[0]

    assert {edge.kind for edge in component.hard_edges} == {
        ReferenceKind.DEFINITION,
        ReferenceKind.RUNTIME_IMPORT,
        ReferenceKind.TYPE_ONLY_IMPORT,
        ReferenceKind.DYNAMIC_IMPORT,
        ReferenceKind.EXPORT,
        ReferenceKind.SYMBOL_IMPORT,
        ReferenceKind.COLLISION_MEMBER,
        ReferenceKind.GENERATED_ARTIFACT,
    }
    assert component.risk.generated_artifact_count == 1
    assert component.risk.dynamic_reference_count == 1
    assert component.risk.maximum_direct_fan_in == 7
    assert component.risk.boundary_crossing_count == 1


def test_manifest_projection_expands_inventory_collision_paths_and_reconciles_reference_classes() -> None:
    locator = "class:cadrumo.alpha.Alpha#binding=1"
    peer_locator = "class:cadrumo.beta.Alpha#binding=1"
    operation = _Operation(
        operation_id="rename-alpha",
        finding_id="finding-alpha",
        old_locator=locator,
        old_path="src/cadrumo/alpha.py",
        changed_paths=("src/cadrumo/alpha.py",),
        expected_reference_classes=("definition",),
    )
    manifest = cast(RenameManifestLike, _Manifest((operation,)))
    inventory = cast(
        InventoryLike,
        _Inventory(
            findings=(_Finding("finding-alpha", (locator, peer_locator)),),
            declarations=(
                _Declaration(locator, "src/cadrumo/alpha.py"),
                _Declaration(peer_locator, "src/cadrumo/beta.py"),
            ),
        ),
    )

    component = build_manifest_components(manifest, inventory=inventory)[0]

    assert component.affected_paths == ("src/cadrumo/alpha.py", "src/cadrumo/beta.py")
    assert any(edge.kind is ReferenceKind.COLLISION_MEMBER for edge in component.hard_edges)

    stale_expectation = cast(
        RenameManifestLike,
        _Manifest((replace(operation, expected_reference_classes=("definition", "dynamic-target")),)),
    )
    with pytest.raises(ObjectNameGraphError, match="reference classes differ from reviewed intent"):
        build_manifest_components(stale_expectation, inventory=inventory)


def test_import_collector_distinguishes_runtime_type_only_dynamic_and_export(tmp_path: Path) -> None:
    _write(tmp_path, "dev/__init__.py")
    _write(tmp_path, "src/cadrumo/target.py", "class Thing: pass\n")
    _write(tmp_path, "src/cadrumo/runtime.py", "import cadrumo.target\n")
    _write(
        tmp_path,
        "src/cadrumo/type_hint.py",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from cadrumo.target import Thing\n",
    )
    _write(
        tmp_path,
        "src/cadrumo/dynamic.py",
        "import importlib\nimportlib.import_module(name='.target', package='cadrumo')\n",
    )
    _write(tmp_path, "dev/packaging/campaign.py", "Form('target', module='cadrumo.target')\n")
    _write(
        tmp_path,
        "dev/packaging/tests/test_campaign.py",
        "_EXPECTED_EXECUTION: object = {'lane': (('cadrumo.target', ()),)}\n",
    )
    _write(tmp_path, "src/cadrumo/__init__.py", "from .target import Thing\n__all__ = ['Thing']\n")
    all_graph = _graph(
        "cadrumo",
        "cadrumo.target",
        "cadrumo.runtime",
        "cadrumo.type_hint",
        "cadrumo.dynamic",
        imports=(
            ("cadrumo", "cadrumo.target"),
            ("cadrumo.runtime", "cadrumo.target"),
            ("cadrumo.type_hint", "cadrumo.target"),
        ),
    )
    runtime_graph = _graph(
        "cadrumo",
        "cadrumo.target",
        "cadrumo.runtime",
        "cadrumo.type_hint",
        "cadrumo.dynamic",
        imports=(("cadrumo", "cadrumo.target"), ("cadrumo.runtime", "cadrumo.target")),
    )

    edges = collect_import_edges(
        (
            OperationLocator("module-op", "cadrumo.target", "src/cadrumo/target.py"),
            OperationLocator("symbol-op", "cadrumo.target", "src/cadrumo/target.py", "Thing"),
        ),
        repo_root=tmp_path,
        all_graph=all_graph,
        runtime_graph=runtime_graph,
    )

    observed = {(edge.operation_id, edge.path, edge.kind) for edge in edges}
    assert ("module-op", "src/cadrumo/runtime.py", ReferenceKind.RUNTIME_IMPORT) in observed
    assert ("module-op", "src/cadrumo/type_hint.py", ReferenceKind.TYPE_ONLY_IMPORT) in observed
    assert ("module-op", "src/cadrumo/dynamic.py", ReferenceKind.DYNAMIC_IMPORT) in observed
    assert ("module-op", "dev/packaging/campaign.py", ReferenceKind.DYNAMIC_IMPORT) in observed
    assert ("module-op", "dev/packaging/tests/test_campaign.py", ReferenceKind.DYNAMIC_IMPORT) in observed
    assert ("symbol-op", "src/cadrumo/type_hint.py", ReferenceKind.TYPE_ONLY_IMPORT) in observed
    assert ("symbol-op", "src/cadrumo/__init__.py", ReferenceKind.EXPORT) in observed
    assert ("symbol-op", "src/cadrumo/dynamic.py", ReferenceKind.DYNAMIC_IMPORT) in observed
    assert ("symbol-op", "dev/packaging/campaign.py", ReferenceKind.DYNAMIC_IMPORT) not in observed
    assert ("symbol-op", "dev/packaging/tests/test_campaign.py", ReferenceKind.DYNAMIC_IMPORT) not in observed


def test_collector_preserves_multiple_symbols_and_mixed_type_checking_context(tmp_path: Path) -> None:
    _write(tmp_path, "dev/__init__.py")
    _write(tmp_path, "src/cadrumo/target.py", "class RuntimeThing: pass\nclass TypeThing: pass\n")
    _write(
        tmp_path,
        "src/cadrumo/mixed.py",
        "from typing import TYPE_CHECKING\n"
        "from cadrumo.target import RuntimeThing\n"
        "if TYPE_CHECKING:\n"
        "    from cadrumo.target import TypeThing\n",
    )
    all_graph = _graph(
        "cadrumo",
        "cadrumo.target",
        "cadrumo.mixed",
        imports=(("cadrumo.mixed", "cadrumo.target"),),
    )
    runtime_graph = _graph(
        "cadrumo",
        "cadrumo.target",
        "cadrumo.mixed",
        imports=(("cadrumo.mixed", "cadrumo.target"),),
    )
    edges = collect_import_edges(
        (
            OperationLocator("runtime-op", "cadrumo.target", "src/cadrumo/target.py", "RuntimeThing"),
            OperationLocator("type-op", "cadrumo.target", "src/cadrumo/target.py", "TypeThing"),
        ),
        repo_root=tmp_path,
        all_graph=all_graph,
        runtime_graph=runtime_graph,
    )
    observed = {(edge.operation_id, edge.path, edge.kind) for edge in edges}

    assert ("runtime-op", "src/cadrumo/mixed.py", ReferenceKind.SYMBOL_IMPORT) in observed
    assert ("type-op", "src/cadrumo/mixed.py", ReferenceKind.TYPE_ONLY_IMPORT) in observed


def test_missing_allowlist_path_and_unowned_generated_artifact_refuse() -> None:
    with pytest.raises(ObjectNameGraphError, match="outside the changed-path allowlist"):
        build_operation_components(
            ("alpha",),
            finding_ids={"alpha": "finding-alpha"},
            definition_paths={"alpha": "src/cadrumo/alpha.py"},
            collision_paths={"alpha": ("src/cadrumo/alpha.py",)},
            changed_path_allowlists={"alpha": ("src/cadrumo/alpha.py",)},
            hard_edges=(HardEdge("alpha", "src/cadrumo/consumer.py", ReferenceKind.RUNTIME_IMPORT),),
        )
    with pytest.raises(ObjectNameGraphError, match="has no owning generator"):
        _build(
            ("alpha",),
            edges=(HardEdge("alpha", "docs/api/alpha.rst", ReferenceKind.GENERATED_ARTIFACT),),
        )


@pytest.mark.parametrize("path", ["C:/outside.py", "src/../outside.py", r"src\outside.py", "/outside.py"])
def test_unsafe_graph_paths_refuse(path: str) -> None:
    with pytest.raises(ObjectNameGraphError, match="graph path"):
        build_operation_components(
            ("alpha",),
            finding_ids={"alpha": "finding-alpha"},
            definition_paths={"alpha": path},
            collision_paths={"alpha": (path,)},
            changed_path_allowlists={"alpha": (path,)},
        )


def test_component_identity_and_order_are_stable_under_reversed_input() -> None:
    edges = (
        HardEdge("alpha", "src/cadrumo/alpha_consumer.py", ReferenceKind.RUNTIME_IMPORT),
        HardEdge(
            "beta",
            "docs/api/beta.rst",
            ReferenceKind.GENERATED_ARTIFACT,
            generator_owner="apidocs",
        ),
    )
    forward = _build(("alpha", "beta"), edges=edges)
    reverse = _build(("beta", "alpha"), edges=tuple(reversed(edges)))

    assert forward == reverse
    assert [component.operation_ids for component in forward] == [("alpha",), ("beta",)]
    assert forward[0].risk.generated_artifact_count == 0
    assert forward[1].risk.generated_artifact_count == 1


def test_semantic_and_clone_advisory_evidence_never_connect_operations() -> None:
    semantic = semantic_advisory(
        (
            Candidate(
                detector="call_fingerprint",
                fingerprint="same calls",
                sites=("src/cadrumo/alpha.py:2 alpha", "src/cadrumo/beta.py:2 beta"),
                weight=9,
            ),
        )
    )
    clone = clone_advisory(DuplicationResult.unavailable("npx absent"))
    components = _build(("alpha", "beta"), advisory=semantic + clone)

    assert len(components) == 2
    assert all(any(item.source == "clone:unavailable" for item in component.risk.advisory) for component in components)
    assert all(
        any(item.source == "semantic:call_fingerprint" for item in component.risk.advisory) for component in components
    )
    assert all(
        next(item for item in component.risk.advisory if item.source == "clone:unavailable").detail == "npx absent"
        for component in components
    )


def test_unresolved_dynamic_import_in_an_affected_file_refuses(tmp_path: Path) -> None:
    _write(tmp_path, "dev/__init__.py")
    _write(
        tmp_path,
        "src/cadrumo/target.py",
        "from importlib import import_module\nname = 'cadrumo.other'\nimport_module(name=name)\n",
    )
    all_graph = _graph("cadrumo", "cadrumo.target")
    runtime_graph = _graph("cadrumo", "cadrumo.target")

    with pytest.raises(ObjectNameGraphError, match=r"unresolved dynamic import.*target.py:3"):
        collect_import_edges(
            (OperationLocator("module-op", "cadrumo.target", "src/cadrumo/target.py"),),
            repo_root=tmp_path,
            all_graph=all_graph,
            runtime_graph=runtime_graph,
        )


def test_parse_error_and_unmappable_importer_fail_closed(tmp_path: Path) -> None:
    _write(tmp_path, "dev/__init__.py")
    _write(tmp_path, "src/cadrumo/target.py")
    _write(tmp_path, "src/cadrumo/broken.py", "def broken(:\n")
    graph = _graph("cadrumo", "cadrumo.target")
    with pytest.raises(ObjectNameGraphError, match=r"cannot inspect references.*broken.py"):
        collect_import_edges(
            (OperationLocator("module-op", "cadrumo.target", "src/cadrumo/target.py"),),
            repo_root=tmp_path,
            all_graph=graph,
            runtime_graph=graph,
        )

    _write(tmp_path, "src/cadrumo/broken.py")
    graph = _graph(
        "cadrumo",
        "cadrumo.target",
        "cadrumo.missing",
        imports=(("cadrumo.missing", "cadrumo.target"),),
    )
    with pytest.raises(ObjectNameGraphError, match="does not map to a source file"):
        collect_import_edges(
            (OperationLocator("module-op", "cadrumo.target", "src/cadrumo/target.py"),),
            repo_root=tmp_path,
            all_graph=graph,
            runtime_graph=graph,
        )


def test_internal_graph_build_refuses_a_first_party_package_loaded_from_another_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "dev/__init__.py")
    _write(tmp_path, "src/cadrumo/target.py")
    monkeypatch.setitem(sys.modules, "cadrumo", SimpleNamespace(__file__=str(tmp_path.parent / "foreign.py")))

    with pytest.raises(ObjectNameGraphError, match="belongs to a different tree"):
        collect_import_edges(
            (OperationLocator("module-op", "cadrumo.target", "src/cadrumo/target.py"),),
            repo_root=tmp_path,
        )
