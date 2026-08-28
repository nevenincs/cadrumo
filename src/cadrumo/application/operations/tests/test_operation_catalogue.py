"""The derived live-tree operation-exposure census.

This is a census, not a sample. Its denominator is the set of files git
actually tracks under ``src/cadrumo`` — resolved by asking git, never by
walking the filesystem, because a filesystem walk silently absorbs
untracked scratch files, a peer's in-flight rename, and build output, and
a census whose denominator is contaminated proves nothing about the tree
anyone else will see.

Every join below is derived from two independent readings that must agree:
the live production registry, built through the one production composition
seam, and a static scan of those tracked sources. A claim that appears in
one reading and not the other is the finding.

No aggregate count is ever a pass condition. Counts appear only inside
failure messages, where they help a reader locate the divergence; the
assertions are all about membership and shape, so a tree that grows a
twenty-second operation does not have to come back here and edit a
constant.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from ....entrypoints._operation_composition import build_production_operation_registry
from ..registry import OperationDefinition, OperationFrontendProjection, OperationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PACKAGE_PREFIX = "src/cadrumo/"
_DEFINITION_ID_SUFFIX = "_OPERATION_DEFINITION_ID"

_ENTRYPOINT_TIER = "src/cadrumo/entrypoints/"

_FRONTEND_PACKAGES: Mapping[OperationFrontendProjection, str] = {
    OperationFrontendProjection.CLI: "src/cadrumo/entrypoints/cli/",
    OperationFrontendProjection.MCP: "src/cadrumo/entrypoints/mcp/",
    OperationFrontendProjection.TUI: "src/cadrumo/entrypoints/tui/",
}
"""Where a claimed projection's own surface lives.

The census asserts both directions across this map: a definition claiming
a projection must be reachable from that package, and a reference found in
that package must belong to a definition that claims it. Files directly
under the entrypoint tier, in no projection's package, are shared
composition seams and can serve any projection that claims them."""


@dataclass(frozen=True, slots=True)
class _DeclaredExclusion:
    """One deliberately excluded site, with the reason it is excluded.

    An exclusion is not trusted. Every entry is re-verified against the
    live tree: the file must still exist and must still exhibit the
    construct the exclusion was written for. An exclusion that has gone
    stale therefore fails rather than quietly widening the census.
    """

    path: str
    construct: str
    reason: str


_ASYNCIO_RUN_EXCLUSIONS: tuple[_DeclaredExclusion, ...] = (
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/launcher.py",
        construct="asyncio.run",
        reason=(
            "the launcher is the composition root, not a projection; owning the "
            "event loop for one session is the job it exists to do"
        ),
    ),
    _DeclaredExclusion(
        path="src/cadrumo/entrypoints/tui/devtools/replay.py",
        construct="asyncio.run",
        reason=(
            "a diagnostic replay entry point runs standalone against recorded "
            "input and drives no operator-facing screen"
        ),
    ),
)


@cache
def _tracked_sources() -> tuple[str, ...]:
    """Every Python file git tracks under the package, as repo-relative paths."""
    completed = subprocess.run(
        ["git", "ls-files", "--", "src/cadrumo/*.py", "src/cadrumo/**/*.py"],  # noqa: S607
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = tuple(sorted(line.strip() for line in completed.stdout.splitlines() if line.strip()))
    if not paths:
        message = "git tracks no package sources; the census denominator is empty"
        raise AssertionError(message)
    return paths


def _production_sources() -> tuple[str, ...]:
    """The tracked sources excluding test packages, which declare nothing live."""
    return tuple(path for path in _tracked_sources() if "/tests/" not in path)


@cache
def _parsed(path: str) -> ast.Module:
    return ast.parse((_REPO_ROOT / path).read_text(encoding="utf-8"), filename=path)


@cache
def _declared_definition_ids() -> Mapping[str, str]:
    """Every module-level ``*_OPERATION_DEFINITION_ID`` literal, id to path."""
    declared: dict[str, str] = {}
    for path in _production_sources():
        for node in _parsed(path).body:
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith(_DEFINITION_ID_SUFFIX):
                    declared[node.value.value] = path
    return declared


@cache
def _registry() -> OperationRegistry:
    """The one production registry, composed through the one production seam."""
    return build_production_operation_registry()


def _definitions() -> tuple[OperationDefinition, ...]:
    return _registry().definitions


@cache
def _references_by_package() -> Mapping[str, frozenset[str]]:
    """Which declared operation ids each tracked production file names.

    A file names an operation either by its string id or by the constant
    that carries it, and both readings are collected: a surface that
    imports the constant is exposing the operation exactly as much as one
    that spells the literal.
    """
    ids = set(_declared_definition_ids())
    constant_to_id = _definition_id_constants()
    builders = _request_builders()

    collected: dict[str, frozenset[str]] = {}
    for path in _production_sources():
        found: set[str] = set()
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ids:
                found.add(node.value)
            elif isinstance(node, ast.Name):
                if node.id in constant_to_id:
                    found.add(constant_to_id[node.id])
                elif node.id in builders:
                    found |= builders[node.id]
            elif isinstance(node, ast.alias):
                if node.name in constant_to_id:
                    found.add(constant_to_id[node.name])
                elif node.name in builders:
                    found |= builders[node.name]
        if found:
            collected[path] = frozenset(found)
    return collected


@cache
def _request_builders() -> Mapping[str, frozenset[str]]:
    """Application helpers that name an operation, and which one they name.

    A frontend rarely spells an operation id. It calls the application's
    own request builder, and that call is the exposure: resolving one hop
    through the builder is the difference between reading what the tree
    does and reading what it happens to spell.
    """
    literal_ids = set(_declared_definition_ids())
    constants = _definition_id_constants()
    builders: dict[str, frozenset[str]] = {}
    for path in _production_sources():
        for node in ast.walk(_parsed(path)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            named: set[str] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str) and inner.value in literal_ids:
                    named.add(inner.value)
                elif isinstance(inner, ast.Name) and inner.id in constants:
                    named.add(constants[inner.id])
            if named:
                builders[node.name] = frozenset(named) | builders.get(node.name, frozenset())
    return builders


@cache
def _definition_id_constants() -> Mapping[str, str]:
    """Constant name to the operation id it carries."""
    constants: dict[str, str] = {}
    for path in _production_sources():
        for node in _parsed(path).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith(_DEFINITION_ID_SUFFIX):
                    constants[target.id] = node.value.value
    return constants


def _paths_under(prefix: str) -> Iterable[str]:
    return (path for path in _production_sources() if path.startswith(prefix))


def test_the_census_denominator_is_the_tracked_tree() -> None:
    """The census reads git's file list, and that list covers the package."""
    tracked = _tracked_sources()
    assert all(path.startswith(_PACKAGE_PREFIX) for path in tracked)
    # The denominator must reach the operation platform and every frontend
    # package the projection map names, or a join below could pass by
    # scanning nothing at all.
    assert any(path.startswith("src/cadrumo/application/operations/") for path in tracked)
    assert any(path.startswith("src/cadrumo/entrypoints/tui/") for path in tracked)
    assert any(path.startswith("src/cadrumo/entrypoints/cli/") for path in tracked)


def test_every_declared_operation_id_joins_exactly_one_registered_definition() -> None:
    """Declared ids and the live registry are the same set, both directions."""
    declared = _declared_definition_ids()
    registered = {definition.definition_id for definition in _definitions()}
    unregistered = sorted(set(declared) - registered)
    undeclared = sorted(registered - set(declared))
    assert not unregistered, (
        f"declared but absent from the production registry: {[(item, declared[item]) for item in unregistered]}"
    )
    assert not undeclared, f"registered but declared nowhere in the tracked tree: {undeclared}"


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
    """Every operation a projection can actually reach in the tracked tree."""
    references = _references_by_package()
    prefix = _FRONTEND_PACKAGES[projection]
    own: set[str] = set()
    for path in _paths_under(prefix):
        own |= references.get(path, frozenset())
    return frozenset(own | _shared_seam_exposures())


def test_every_claimed_projection_joins_a_real_surface() -> None:
    """A definition claiming a frontend is actually reachable from it."""
    unreached = sorted(
        (definition.definition_id, projection.value)
        for definition in _definitions()
        for projection in definition.permitted_frontends
        if definition.definition_id not in _exposures_for(projection)
    )
    assert not unreached, (
        f"{len(unreached)} projection claims join no surface in the tracked tree "
        f"(denominator: {len(_production_sources())} tracked production sources, "
        f"{len(_definitions())} registered operations): {unreached}"
    )


def test_every_surface_reference_joins_a_definition_that_claims_it() -> None:
    """A frontend never exposes an operation whose contract excludes it."""
    references = _references_by_package()
    claims = {definition.definition_id: definition.permitted_frontends for definition in _definitions()}
    unclaimed: list[tuple[str, str, str]] = []
    for projection, prefix in _FRONTEND_PACKAGES.items():
        for path in _paths_under(prefix):
            for definition_id in sorted(references.get(path, frozenset())):
                if projection not in claims.get(definition_id, frozenset()):
                    unclaimed.append((path, definition_id, projection.value))
    assert not unclaimed, f"a surface exposes an operation its definition does not permit there: {unclaimed}"


def _asyncio_run_sites(prefix: str) -> tuple[str, ...]:
    """Tracked production files under ``prefix`` that own an event loop."""
    found: list[str] = []
    for path in _paths_under(prefix):
        for node in ast.walk(_parsed(path)):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "run"
                and isinstance(node.value, ast.Name)
                and node.value.id == "asyncio"
            ):
                found.append(path)
                break
    return tuple(sorted(found))


def test_no_undeclared_full_screen_surface_owns_the_event_loop() -> None:
    """Only the declared composition and diagnostic seams call ``asyncio.run``."""
    declared = {exclusion.path for exclusion in _ASYNCIO_RUN_EXCLUSIONS}
    live = set(_asyncio_run_sites(_FRONTEND_PACKAGES[OperationFrontendProjection.TUI]))
    undeclared = sorted(live - declared)
    assert not undeclared, f"a full-screen surface owns its own event loop: {undeclared}"


def test_every_declared_exclusion_still_answers_a_live_site() -> None:
    """A stale exclusion fails rather than silently widening the census."""
    live = set(_asyncio_run_sites(_FRONTEND_PACKAGES[OperationFrontendProjection.TUI]))
    stale = [
        exclusion.path
        for exclusion in _ASYNCIO_RUN_EXCLUSIONS
        if exclusion.construct == "asyncio.run" and exclusion.path not in live
    ]
    assert not stale, f"a declared exclusion no longer answers a live site and must be removed: {stale}"
    missing_reason = [exclusion.path for exclusion in _ASYNCIO_RUN_EXCLUSIONS if not exclusion.reason.strip()]
    assert not missing_reason, f"a declared exclusion states no reason: {missing_reason}"


def test_no_full_screen_surface_reaches_an_outbound_adapter_directly() -> None:
    """The full-screen tier never calls a transport; it goes through the platform."""
    prefix = _FRONTEND_PACKAGES[OperationFrontendProjection.TUI]
    offenders: list[tuple[str, str]] = []
    for path in _paths_under(prefix):
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom) and node.module and "adapters.outbound" in node.module:
                offenders.append((path, node.module))
            elif isinstance(node, ast.Import):
                offenders.extend((path, alias.name) for alias in node.names if "adapters.outbound" in alias.name)
    assert not offenders, f"a full-screen surface imports an outbound adapter directly: {offenders}"
