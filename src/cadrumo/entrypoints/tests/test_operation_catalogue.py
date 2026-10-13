"""The derived live-tree operation-exposure census.

This is a census, not a sample. Its denominator is the live source tree under
``src/cadrumo`` and the installed MCP adapter under ``src/cadrumo_harness/mcp``, walked from disk without consulting version-control state, so
a peer's new source file enters the census immediately.

Every join below is derived from two independent readings that must agree:
the live production registry, built through the one production composition
seam, and a static scan of those source files. A claim that appears in
one reading and not the other is the finding.

No aggregate count is ever a pass condition. Counts appear only inside
failure messages, where they help a reader locate the divergence; the
assertions are all about membership and shape, so a tree that grows a
twenty-second operation does not have to come back here and edit a
constant.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...tests.inventory import package_python_files, releases_parsed_sources
from ..operation_composition import build_production_operation_registry
from .source_tree_support import SourceTree, module_level_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PACKAGE_PREFIX = "src/cadrumo/"
_MCP_PACKAGE_PREFIX = "src/cadrumo_harness/mcp/"
_DEFINITION_ID_SUFFIX = "_DEFINITION_ID"
_NO_IDS = frozenset[str]()

_ENTRYPOINT_TIER = "src/cadrumo/entrypoints/"

_FRONTEND_PACKAGES: Mapping[OperationFrontendProjection, str] = {
    OperationFrontendProjection.CLI: "src/cadrumo/entrypoints/cli/",
    OperationFrontendProjection.MCP: _MCP_PACKAGE_PREFIX,
    OperationFrontendProjection.TUI: "src/cadrumo/entrypoints/tui/",
}
"""Where each frontend's own surface lives.

The census asserts both directions across this map: every registered
operation must be named by some frontend's package or by a shared seam, and a
reference found in a frontend's package must belong to a registered
definition. Files directly under the entrypoint tier, in no frontend's
package, are shared composition seams and serve every frontend. The MCP
adapter dispatches any registered operation by its id, which a scan for named
ids does not see."""


@dataclass(frozen=True, slots=True)
class _DeclaredExclusion:
    """One deliberately excluded site, with the reason it is excluded.

    An exclusion is not trusted. Every entry is re-verified against the
    live tree: the file must still exist and must still exhibit the
    construct the exclusion was written for. An exclusion that has gone
    stale therefore fails rather than quietly widening the census.
    """

    path: str
    owner: str
    construct: str
    reason: str


_ASYNCIO_RUN_EXCLUSIONS: tuple[_DeclaredExclusion, ...] = (
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/installed_session.py",
        owner="_run_runtime_session.requester_for_api.fresh_credential_client",
        construct="asyncio.run",
        reason="the requester calls this credential-client opener on its owned worker thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/installed_session.py",
        owner="_attempt_runtime_session",
        construct="asyncio.run",
        reason=(
            "the installed session is the launcher's production composition root; "
            "it owns one event loop per admitted profile session"
        ),
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/runtime_account.py",
        owner="compose_runtime_account_factories.password.rotate",
        construct="asyncio.run",
        reason="PassphraseScreen.start_attempt invokes rotation on an owned worker thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/modelo/runtime_lifecycle.py",
        owner="_RuntimeModeloLifecycleBindings.admit",
        construct="asyncio.run",
        reason="the lifecycle door invokes attestation admission through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/runtime_actividad_asset.py",
        owner="RuntimeActivityAssetTuiActionsV1._call",
        construct="asyncio.run",
        reason="the activity-asset screen dispatches these synchronous actions through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/runtime_evidence.py",
        owner="RuntimeEvidenceTuiDoorV1._call_sync",
        construct="asyncio.run",
        reason="the evidence screen reads records and reader readiness through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/secret/automation_requester_delivery.py",
        owner="RequesterDeliveryMixin._reconcile_fresh",
        construct="asyncio.run",
        reason=(
            "the enrollment journey invokes this reconciliation callback on the worker thread the "
            "requester submits from; the fresh credential client it opens there closes asynchronously"
        ),
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/modelo/runtime_lifecycle.py",
        owner="_RuntimeModeloLifecycleBindings.read",
        construct="asyncio.run",
        reason="ModeloWorkspaceLifecycleDoor runs prerequisite, renewal and preflight reads through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/modelo/runtime_workbench_reads.py",
        owner="RuntimeModeloWorkbenchSource.read_form",
        construct="asyncio.run",
        reason="ModeloWorkbenchScreen loads its InstalledModeloWorkbench reader through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/modelo/runtime_workbench_reads.py",
        owner="RuntimeModeloWorkbenchSource.help_card",
        construct="asyncio.run",
        reason="WorkbenchHelpMixin reads InstalledModeloWorkbench.help_card through asyncio.to_thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/profile/runtime_auth_configuration.py",
        owner="configure_runtime_auth",
        construct="asyncio.run",
        reason="the profile field editor invokes RuntimeProfileManagerComposition._field on its owned worker thread",
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/modelo/runtime_work_create.py",
        owner="compose_runtime_work_create_handoff.create",
        construct="asyncio.run",
        reason="declarations overview and calendar invoke the create handoff through asyncio.to_thread",
    ),
)


@cache
def _source_files() -> tuple[str, ...]:
    """Every Python file under the product and installed MCP packages."""
    mcp_root = _REPO_ROOT / "src" / "cadrumo_harness" / "mcp"
    paths = tuple(
        path.relative_to(_REPO_ROOT).as_posix()
        for path in (*package_python_files(include_data=True), *mcp_root.rglob("*.py"))
    )
    if not paths:
        message = "the repository contains no visible package sources; the census denominator is empty"
        raise AssertionError(message)
    return paths


def _production_sources() -> tuple[str, ...]:
    """The source files excluding test packages, which declare nothing live."""
    return tuple(path for path in _source_files() if "/tests/" not in path)


@cache
def _tree() -> SourceTree:
    """The census files as one source tree, each parsed once and each import resolved once.

    An import resolves only to a file of the census: a module outside its
    denominator names no surface here, however real the file is on disk.
    """
    census_files = frozenset(_source_files())
    return releases_parsed_sources(
        SourceTree(
            _REPO_ROOT,
            packages=frozenset({"cadrumo", "cadrumo_harness"}),
            prefix="src",
            contains=census_files.__contains__,
        )
    )


@cache
def _declared_definition_ids() -> Mapping[str, str]:
    """Every module-level ``*_DEFINITION_ID`` literal or enum-derived ID, id to path."""
    declared: dict[str, str] = dict(_dynamic_definition_ids())
    for path in _production_sources():
        for name, value in module_level_bindings(_tree().parsed(path)):
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if name.endswith(_DEFINITION_ID_SUFFIX):
                declared[value.value] = path
    return declared


@cache
def _dynamic_definition_ids() -> Mapping[str, str]:
    """Read the one enum-derived declaration family from its source module."""
    from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS

    path = "src/cadrumo/application/overview/read_request.py"
    return {definition_id: path for definition_id in OVERVIEW_READ_DEFINITION_IDS.values()}


@cache
def _definition_id_collections() -> Mapping[tuple[str, str], frozenset[str]]:
    """Preserve the IDs carried by the overview's enum-derived declaration."""
    return {
        ("src/cadrumo/application/overview/read_request.py", "OVERVIEW_READ_DEFINITION_IDS"): frozenset(
            _dynamic_definition_ids()
        )
    }


@cache
def _registry() -> OperationRegistry:
    """The one production registry, composed through the one production seam."""
    return build_production_operation_registry()


def _definitions() -> tuple[OperationDefinition, ...]:
    return _registry().definitions


@cache
def _references_by_package() -> Mapping[str, frozenset[str]]:
    """Which declared operation ids each production source file names.

    A file names an operation through the constant that declares it, the
    builder that returns its request, or a literal spelled at a dispatch
    site. A bare string that merely equals an id is not one of those: the
    same spelling is also a CLI command key, an operator action's target
    command key, and a full-screen navigation destination, so reading
    every matching string would report a surface for a word rather than
    for a call.
    """
    dispatch_ids = _dispatched_literal_ids()
    constant_to_id = _definition_id_constants()
    collections = _definition_id_collections()
    builders = _request_builders()

    def named_by_name(name: str, origins: Mapping[str, tuple[str, str]]) -> frozenset[str]:
        origin = origins.get(name)
        if origin is None:
            return _NO_IDS
        if origin in constant_to_id:
            return frozenset({constant_to_id[origin]})
        if origin in collections:
            return collections[origin]
        return builders.get(origin, _NO_IDS)

    collected: dict[str, frozenset[str]] = {}
    for path in _production_sources():
        origins = _tree().name_origins(path)
        found: set[str] = set(dispatch_ids.get(path, _NO_IDS))
        for node in ast.walk(_tree().parsed(path)):
            if isinstance(node, ast.Name):
                found |= named_by_name(node.id, origins)
            elif isinstance(node, ast.Attribute):
                origin = _attribute_origin(node, origins)
                if origin is None:
                    continue
                if origin in constant_to_id:
                    found.add(constant_to_id[origin])
                found |= collections.get(origin, _NO_IDS)
            elif isinstance(node, ast.alias):
                found |= named_by_name(node.asname or node.name.split(".")[-1], origins)
        if found:
            collected[path] = frozenset(found)
    return collected


def _attribute_origin(node: ast.Attribute, origins: Mapping[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Resolve ``module_alias.CONSTANT`` to the module the alias imports."""
    if not isinstance(node.value, ast.Name):
        return None
    module = origins.get(node.value.id)
    return (module[0], node.attr) if module is not None else None


_DISPATCH_ARGUMENT = "definition_id"


@cache
def _dispatched_literal_ids() -> Mapping[str, frozenset[str]]:
    """Operation ids a file hard-codes at a dispatch site, by file.

    Naming the platform's ``definition_id`` argument is how a caller
    reaches an operation, so a literal written there is an exposure even
    though the declaring constant was bypassed. This is the one place a
    bare string is read as a reference, which is what keeps a hard-coded
    dispatch from escaping the census.
    """
    ids = frozenset(_declared_definition_ids())
    dispatched = {path: _dispatched_literals_in_tree(_tree().parsed(path), ids) for path in _production_sources()}
    return {path: found for path, found in dispatched.items() if found}


def _dispatched_literals_in_tree(tree: ast.AST, ids: frozenset[str]) -> frozenset[str]:
    """Every declared id this tree writes into the platform's dispatch argument."""
    found: set[str] = set()
    for node in ast.walk(tree):
        values: list[ast.expr] = []
        if isinstance(node, ast.Call):
            values = [item.value for item in node.keywords if item.arg == _DISPATCH_ARGUMENT]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            values = [node.value] if _binds_dispatch_argument(node.target) else []
        elif isinstance(node, ast.Assign):
            values = [node.value] if any(_binds_dispatch_argument(item) for item in node.targets) else []
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value in ids:
                found.add(value.value)
    return frozenset(found)


def _binds_dispatch_argument(target: ast.expr) -> bool:
    """Whether this assignment target is the platform's dispatch argument."""
    if isinstance(target, ast.Name):
        return target.id == _DISPATCH_ARGUMENT
    return isinstance(target, ast.Attribute) and target.attr == _DISPATCH_ARGUMENT


@cache
def _request_builders() -> Mapping[tuple[str, str], frozenset[str]]:
    """Application helpers that name an operation, and which one they name.

    A frontend rarely spells an operation id. It calls the application's
    own request builder, and that call is the exposure: resolving one hop
    through the builder is the difference between reading what the tree
    does and reading what it happens to spell.

    Each helper is keyed by the module that defines it, so a caller joins
    the helper it imported rather than every helper that happens to share
    its name. Delegation inside the defining module is followed to a
    fixed point, because a module's private id selector is part of the
    helper rather than a second hop away from it; the composition seam
    reaches several operations only through such a selector, and
    stopping short would read those operations as composed by nothing.
    Delegation across modules is not followed: a call graph walked past
    its own module reaches everything from anywhere and stops
    distinguishing a surface from a transitive import.
    """
    literal_ids = set(_declared_definition_ids())
    constants = _definition_id_constants()
    collections = _definition_id_collections()

    def read(path: str, node: ast.AST, *, read_literals: bool) -> tuple[set[str], set[tuple[str, str]]]:
        """The ids this subtree names outright, and the helpers it defers to."""
        origins = _tree().name_origins(path)
        named: set[str] = set()
        deferred: set[tuple[str, str]] = set()
        for inner in ast.walk(node):
            if (
                read_literals
                and isinstance(inner, ast.Constant)
                and isinstance(inner.value, str)
                and inner.value in literal_ids
            ):
                named.add(inner.value)
            elif isinstance(inner, ast.Name | ast.Attribute):
                origin = origins.get(inner.id) if isinstance(inner, ast.Name) else _attribute_origin(inner, origins)
                if origin is None:
                    continue
                if origin in constants:
                    named.add(constants[origin])
                elif origin in collections:
                    named |= collections[origin]
                elif isinstance(inner, ast.Name) and origin[0] == path:
                    deferred.add(origin)
        return named, deferred

    # A module-level population (``DEFINITIONS = (_definition(id=..._ID), ...)``)
    # carries its ids to the builder that returns it, one hop like a request
    # builder. A population reaches its operations through the constants that
    # declare them; a bare string in a population is some other token that
    # shares the spelling, such as the operator catalogue's target command key.
    direct: dict[tuple[str, str], set[str]] = {}
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}

    def record(key: tuple[str, str], named: set[str], deferred: set[tuple[str, str]]) -> None:
        direct.setdefault(key, set()).update(named)
        edges.setdefault(key, set()).update(deferred - {key})

    for path in _production_sources():
        tree = _tree().parsed(path)
        for node in tree.body:
            if not isinstance(node, ast.Assign) or isinstance(node.value, ast.Constant):
                continue
            named, deferred = read(path, node.value, read_literals=False)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    record((path, target.id), named, deferred)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                record((path, node.name), *read(path, node, read_literals=True))

    resolved = {key: set(found) for key, found in direct.items()}
    changed = True
    while changed:
        changed = False
        for key, targets in edges.items():
            grown = resolved[key].union(*(resolved.get(target, set()) for target in targets)) if targets else None
            if grown is not None and grown != resolved[key]:
                resolved[key] = grown
                changed = True
    return {key: frozenset(found) for key, found in resolved.items() if found}


@cache
def _definition_id_constants() -> Mapping[tuple[str, str], str]:
    """Canonical declaring module and constant name to the operation id it carries."""
    constants: dict[tuple[str, str], str] = {}
    for path in _production_sources():
        for name, value in module_level_bindings(_tree().parsed(path)):
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if name.endswith(_DEFINITION_ID_SUFFIX):
                constants[path, name] = value.value
    return constants


def _paths_under(prefix: str) -> Iterable[str]:
    return (path for path in _production_sources() if path.startswith(prefix))


def test_the_census_denominator_is_the_repository_visible_tree() -> None:
    """The census reads the repository-visible tree and covers the package."""
    sources = _source_files()
    assert all(path.startswith((_PACKAGE_PREFIX, _MCP_PACKAGE_PREFIX)) for path in sources)
    # The denominator must reach the operation platform and every frontend
    # package the projection map names, or a join below could pass by
    # scanning nothing at all.
    assert any(path.startswith("src/cadrumo/application/operations/") for path in sources)
    assert any(path.startswith("src/cadrumo/entrypoints/tui/") for path in sources)
    assert any(path.startswith("src/cadrumo/entrypoints/cli/") for path in sources)
    assert any(path.startswith(_MCP_PACKAGE_PREFIX) for path in sources)
    assert any(path == "src/cadrumo_harness/mcp/server.py" for path in sources)


def test_every_declared_operation_id_joins_exactly_one_registered_definition() -> None:
    """Declared ids and the live registry are the same set, both directions."""
    declared = _declared_definition_ids()
    registered = {definition.definition_id for definition in _definitions()}
    unregistered = sorted(set(declared) - registered)
    undeclared = sorted(registered - set(declared))
    assert not unregistered, (
        f"declared but absent from the production registry: {[(item, declared[item]) for item in unregistered]}"
    )
    assert not undeclared, f"registered but declared nowhere in the source tree: {undeclared}"


def test_every_registered_definition_carries_a_matching_executor_factory() -> None:
    """Each definition's factory binds the exact request type it declares."""
    mismatched = [
        definition.definition_id
        for definition in _definitions()
        if definition.executor_factory.request_type is not definition.request_type
    ]
    assert not mismatched, f"executor factory request type diverges from the definition: {mismatched}"


def test_every_recovery_action_reference_maps_to_exactly_one_definition() -> None:
    """An operator action identity never fans out across two operations."""
    seen: dict[str, list[str]] = {}
    for definition in _definitions():
        reference = definition.action_reference
        if reference is None:
            continue
        seen.setdefault(reference.action_id, []).append(definition.definition_id)
    fanned = {action: owners for action, owners in seen.items() if len(owners) > 1}
    assert not fanned, f"one recovery action dispatches more than one operation: {fanned}"


@cache
def _shared_seam_exposures() -> frozenset[str]:
    """Operations named by an entrypoint-tier seam outside any one projection."""
    references = _references_by_package()
    projection_prefixes = tuple(_FRONTEND_PACKAGES.values())
    shared: set[str] = set()
    for path, named in references.items():
        if not path.startswith(_ENTRYPOINT_TIER):
            continue
        if any(path.startswith(prefix) for prefix in projection_prefixes):
            continue
        shared |= named
    return frozenset(shared)


def _exposures_for(projection: OperationFrontendProjection) -> frozenset[str]:
    """Every operation a projection can actually reach in the source tree."""
    references = _references_by_package()
    prefix = _FRONTEND_PACKAGES[projection]
    own: set[str] = set()
    for path in _paths_under(prefix):
        own |= references.get(path, _NO_IDS)
    return frozenset(own | _shared_seam_exposures())


def test_every_registered_operation_joins_a_real_surface() -> None:
    """No operation is registered that no frontend's own surface or shared seam names."""
    exposed = frozenset[str]().union(*(_exposures_for(projection) for projection in OperationFrontendProjection))
    unreached = sorted(
        definition.definition_id for definition in _definitions() if definition.definition_id not in exposed
    )
    assert not unreached, (
        f"{len(unreached)} operations join no surface in the source tree "
        f"(denominator: {len(_production_sources())} production sources, "
        f"{len(_definitions())} registered operations): {unreached}"
    )


def test_every_surface_reference_joins_a_registered_definition() -> None:
    """A frontend never names an operation the registry does not hold."""
    references = _references_by_package()
    registered = {definition.definition_id for definition in _definitions()}
    unregistered: list[tuple[str, str, str]] = []
    for projection, prefix in _FRONTEND_PACKAGES.items():
        for path in _paths_under(prefix):
            for definition_id in sorted(references.get(path, _NO_IDS)):
                if definition_id not in registered:
                    unregistered.append((path, definition_id, projection.value))
    assert not unregistered, f"a surface names an operation that is not registered: {unregistered}"


def _asyncio_run_sites_in_tree(path: str, tree: ast.AST) -> tuple[tuple[str, str], ...]:
    """Name every exact call site, retaining duplicates within one owner."""
    found: list[tuple[str, str]] = []

    def visit(node: ast.AST, owners: tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            owners = (*owners, node.name)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        ):
            found.append((path, ".".join(owners)))
        for child in ast.iter_child_nodes(node):
            visit(child, owners)

    visit(tree, ())
    return tuple(found)


def _asyncio_run_sites(prefix: str) -> tuple[tuple[str, str], ...]:
    """Enumerate exact event-loop owners under one production frontend."""
    return tuple(
        sorted(site for path in _paths_under(prefix) for site in _asyncio_run_sites_in_tree(path, _tree().parsed(path)))
    )


def test_no_undeclared_full_screen_surface_owns_the_event_loop() -> None:
    """Each off-loop bridge has exactly one declared call site."""
    declared = Counter((item.path, item.owner) for item in _ASYNCIO_RUN_EXCLUSIONS)
    live = Counter(_asyncio_run_sites(_FRONTEND_PACKAGES[OperationFrontendProjection.TUI]))
    undeclared = sorted((live - declared).elements())
    assert not undeclared, f"a full-screen surface owns its own event loop: {undeclared}"


def test_every_declared_exclusion_still_answers_a_live_site() -> None:
    """A stale exclusion fails rather than silently widening the census."""
    live = Counter(_asyncio_run_sites(_FRONTEND_PACKAGES[OperationFrontendProjection.TUI]))
    declared = Counter((item.path, item.owner) for item in _ASYNCIO_RUN_EXCLUSIONS if item.construct == "asyncio.run")
    stale = sorted((declared - live).elements())
    assert not stale, f"a declared exclusion no longer answers a live site and must be removed: {stale}"
    missing_reason = [(item.path, item.owner) for item in _ASYNCIO_RUN_EXCLUSIONS if not item.reason.strip()]
    assert not missing_reason, f"a declared exclusion states no reason: {missing_reason}"


def test_event_loop_census_detects_an_extra_call_in_the_same_owner() -> None:
    """A path or function-name allowlist must not hide a second call."""
    tree = ast.parse("def bridge():\n    asyncio.run(first())\n    asyncio.run(second())\n")
    sites = _asyncio_run_sites_in_tree("bridge.py", tree)
    assert sites == (("bridge.py", "bridge"), ("bridge.py", "bridge"))
    assert Counter(sites) - Counter({("bridge.py", "bridge"): 1}) == Counter({("bridge.py", "bridge"): 1})


def test_the_declaration_census_reads_an_annotated_declaration() -> None:
    """A typed declaration is a declaration; the bare form is not the contract."""
    module = ast.parse('X_DEFINITION_ID: OperationId = "domain.thing.do"\nY_DEFINITION_ID = "domain.thing.undo"\n')
    assert dict(module_level_bindings(module)).keys() == {"X_DEFINITION_ID", "Y_DEFINITION_ID"}


def test_the_reference_census_detects_a_hard_coded_dispatch() -> None:
    """A surface bypassing the declaring constant is still read as exposure."""
    ids = frozenset({"domain.thing.do", "domain.thing.undo"})
    dispatching = ast.parse('submit(definition_id="domain.thing.do", payload=request)\n')
    assert _dispatched_literals_in_tree(dispatching, ids) == frozenset({"domain.thing.do"})
    # The same spelling used as another namespace's token is not a dispatch:
    # command keys, operator action targets and navigation destinations all
    # share the operation id's spelling.
    naming = ast.parse('DESTINATION = "domain.thing.undo"\nhelp(command="domain.thing.undo")\n')
    assert _dispatched_literals_in_tree(naming, ids) == frozenset()


def test_qualified_constant_resolution_keeps_its_declaring_module() -> None:
    """A module alias resolves only its own symbol, even when another module uses the same name."""
    reference = ast.parse("requests.DO_DEFINITION_ID", mode="eval").body
    assert isinstance(reference, ast.Attribute)
    assert _attribute_origin(reference, {"requests": ("own/requests.py", "requests")}) == (
        "own/requests.py",
        "DO_DEFINITION_ID",
    )
    assert _attribute_origin(reference, {"unrelated": ("elsewhere/requests.py", "requests")}) is None


def test_aliased_and_qualified_real_ids_reach_the_shared_composition_seam() -> None:
    """The live alias shapes must carry their declared families through one builder hop."""
    builders = _request_builders()
    assert builders[
        "src/cadrumo/application/prorrata_register/registered_operations.py", "build_prorrata_list_definition"
    ] == frozenset({"ledger.prorrata.list"})
    assert builders[
        "src/cadrumo/application/overview/read_operation.py", "build_overview_read_definition"
    ] == frozenset(_dynamic_definition_ids())


def test_no_full_screen_surface_reaches_an_outbound_adapter_directly() -> None:
    """The full-screen tier never calls a transport; it goes through the platform."""
    prefix = _FRONTEND_PACKAGES[OperationFrontendProjection.TUI]
    offenders: list[tuple[str, str]] = []
    for path in _paths_under(prefix):
        for node in ast.walk(_tree().parsed(path)):
            if (
                isinstance(node, ast.ImportFrom)
                and (node.module is not None and node.module)
                and "adapters.outbound" in node.module
            ):
                offenders.append((path, node.module))
            elif isinstance(node, ast.Import):
                offenders.extend((path, alias.name) for alias in node.names if "adapters.outbound" in alias.name)
    assert not offenders, f"a full-screen surface imports an outbound adapter directly: {offenders}"
