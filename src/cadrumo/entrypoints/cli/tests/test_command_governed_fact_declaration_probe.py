"""A command that declares no governed-fact capability never reads a governed fact.

Dispatch opens the pinned governed-fact scope only for a runnable command whose
policy declares ``registry`` or ``encrypted-facts``. A command that reads a
governed fact without declaring either runs with no scope in production, while
any test that lends it one passes. This probe drives every runnable,
non-declaring command through the real CLI with no enclosing scope and fails
naming each command that reaches a missing-scope refusal.

Detection signal
----------------
The refusal family is recognised at its raise sites, not by its text or type.
The text is unreliable because the CLI error boundary may rewrite the message,
and the types are not distinctive: the same family raises ``ValueError``,
``TypeError``, ``RegistryValidationError``, ``InternalInvariantError`` and
several domain errors, each also raised for unrelated reasons. What every
member shares is its location, so the sites are derived from the current source
tree by parsing it:

* a ``raise`` whose message carries the missing-scope wording, including the
  generation-pinned projection cache and the unconditional refusal helpers; and
* a ``raise`` in the body of an ``if`` that tests a value taken from
  ``governed_facts_in_scope()`` for absence (``is None``, ``not x`` or
  ``not isinstance(x, ...)``).

During each invocation a ``sys.monitoring`` ``RAISE`` observer records every
exception raised at one of those source lines. The event fires at the raise
itself, before any handler can catch, translate, re-chain or swallow the
exception, so a rewritten message or a caught-and-downgraded refusal is still
seen. A second observer on the command's own behavior target proves the
invocation reached the handler with no scope lent to it, so a command that
stopped at argument parsing or preflight cannot pass by never running, and a
preflight lease cannot mask a read the way a test-level scope would.

Offline drive
-------------
Every probed command runs with the process sealed: outbound connections, name
resolution, event-loop connections, child processes and shell launches are
refused with ``OSError`` at the standard library, so a ``network`` or
``browser`` command meets its boundary as it would with no network, and no
runtime server, installer, browser or TUI child starts. A command then passes
by refusing at that boundary before any governed-fact read, or by reading
governed facts only inside a scope it opened; either way the raise observer
sees no missing-scope refusal. The boundary each run met is recorded as the
test's ``offline_outcome`` property.
"""

from __future__ import annotations

import ast
import inspect
import os
import socket
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from itertools import islice
from pathlib import Path
from types import CodeType
from typing import Final

import pytest

import cadrumo
from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_runtime_profile
from ....domain.calculations.registry.governed_fact_scope import (
    governed_facts_in_scope,
    outside_governed_fact_validation,
)
from ....domain.calculations.registry.m347_threshold import resolve_m347_counterparty_annual_threshold
from ....tests.offline_seal import OfflineGuard, offline_guard_fixture
from .._command_runtime import build_command_app, runs_in_governed_fact_scope
from ..command_spec import (
    BindingState,
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from ..command_specs import COMMAND_GRAPH
from ._command_drive_support import (
    PROBE_PROFILE_ID,
    PROBE_PROFILE_LABEL,
    free_monitoring_tool,
    handler_code,
    is_runnable,
    seed_probe_profile,
    synthetic_argv,
)
from .cli_runner import invoke_cached_cli, invoke_uncached_typer_app

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MISSING_SCOPE_WORDING: Final = (
    "explicit authority operation or scope",
    "generation-pinned governed-fact scope",
)
_SCOPE_READER: Final = "governed_facts_in_scope"

#: Runnable non-declaring commands the probe cannot drive, with the reason.
_EXEMPTIONS: Final[dict[str, str]] = {}

#: Optional parameters a command's own handler requires one of, which the
#: required-parameter derivation alone would leave the handler to refuse.
_HANDLER_REQUIRED_OPTIONS: Final[dict[str, tuple[str, ...]]] = {
    "config_provision_remove": ("role",),
}


# --- raise-site discovery -------------------------------------------------


@dataclass(frozen=True, slots=True, order=True)
class RaiseSite:
    """One source statement that raises the missing-scope refusal."""

    path: str
    first_line: int
    last_line: int

    def locator(self) -> str:
        """Return the site as a repository-relative ``path:line``."""
        root = Path(cadrumo.__file__).resolve().parent.parent.parent
        return f"{Path(self.path).relative_to(root).as_posix()}:{self.first_line}"


def _calls_scope_reader(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            function = child.func
            name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
            if name == _SCOPE_READER:
                return True
    return False


def _names_scope_value(node: ast.expr, scoped_names: frozenset[str]) -> bool:
    return (isinstance(node, ast.Name) and node.id in scoped_names) or _calls_scope_reader(node)


def _tests_scope_absence(test: ast.expr, scoped_names: frozenset[str]) -> bool:
    """Report whether an ``if`` test checks a scope-derived value for absence."""
    if isinstance(test, ast.BoolOp):
        return any(_tests_scope_absence(value, scoped_names) for value in test.values)
    if isinstance(test, ast.Compare):
        return (
            len(test.ops) == 1
            and isinstance(test.ops[0], ast.Is)
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value is None
            and _names_scope_value(test.left, scoped_names)
        )
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        operand = test.operand
        if (
            isinstance(operand, ast.Call)
            and isinstance(operand.func, ast.Name)
            and operand.func.id == "isinstance"
            and operand.args
        ):
            return _names_scope_value(operand.args[0], scoped_names)
        return _names_scope_value(operand, scoped_names)
    return False


def _message_names_missing_scope(node: ast.Raise) -> bool:
    return any(
        isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and any(wording in child.value for wording in _MISSING_SCOPE_WORDING)
        for child in ast.walk(node)
    )


def _raises_within(statements: Sequence[ast.stmt]) -> Iterator[ast.Raise]:
    for statement in statements:
        for child in ast.walk(statement):
            if isinstance(child, ast.Raise):
                yield child


def _scope_derived_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    names: set[str] = set()
    for child in ast.walk(function):
        if isinstance(child, ast.Assign) and _calls_scope_reader(child.value):
            names.update(target.id for target in child.targets if isinstance(target, ast.Name))
        elif (
            isinstance(child, ast.AnnAssign)
            and child.value is not None
            and _calls_scope_reader(child.value)
            and isinstance(child.target, ast.Name)
        ):
            names.add(child.target.id)
    return frozenset(names)


def _sites_in_module(path: Path) -> Iterator[RaiseSite]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    raises: set[ast.Raise] = {
        node for node in ast.walk(tree) if isinstance(node, ast.Raise) and _message_names_missing_scope(node)
    }
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        scoped_names = _scope_derived_names(function)
        for branch in ast.walk(function):
            if isinstance(branch, ast.If) and _tests_scope_absence(branch.test, scoped_names):
                raises.update(_raises_within(branch.body))
    resolved = os.path.normcase(str(path.resolve()))
    for node in raises:
        yield RaiseSite(resolved, node.lineno, node.end_lineno or node.lineno)


@cache
def missing_scope_raise_sites() -> frozenset[RaiseSite]:
    """Derive every missing-scope raise site from the current product source."""
    package_root = Path(cadrumo.__file__).resolve().parent
    return frozenset(
        site
        for path in package_root.rglob("*.py")
        if "tests" not in path.relative_to(package_root).parts
        for site in _sites_in_module(path)
    )


# --- in-process observation -----------------------------------------------


@dataclass(frozen=True, slots=True)
class ScopeRefusal:
    """One missing-scope refusal observed at its raise site."""

    site: RaiseSite
    error_type: str
    message: str


@dataclass(slots=True)
class ProbeObservation:
    """What one probed invocation did."""

    refusals: list[ScopeRefusal] = field(default_factory=list)
    handler_started: bool = False
    scope_lent_to_handler: bool = False


@contextmanager
def observe_invocation(handler: CodeType) -> Iterator[ProbeObservation]:
    """Record missing-scope raises and the handler's start while the block runs."""
    by_file: dict[str, list[RaiseSite]] = {}
    for site in missing_scope_raise_sites():
        by_file.setdefault(site.path, []).append(site)
    observation = ProbeObservation()
    monitoring = sys.monitoring
    tool_id = free_monitoring_tool()

    def on_raise(code: CodeType, instruction_offset: int, exception: BaseException) -> object:
        sites = by_file.get(os.path.normcase(code.co_filename))
        if sites is None:
            return None
        position = next(islice(code.co_positions(), instruction_offset // 2, None), None)
        line = None if position is None else position[0]
        for site in sites:
            if line is not None and site.first_line <= line <= site.last_line:
                observation.refusals.append(ScopeRefusal(site, type(exception).__qualname__, str(exception)[:160]))
        return None

    def on_start(code: CodeType, instruction_offset: int) -> object:
        del code, instruction_offset
        observation.handler_started = True
        observation.scope_lent_to_handler |= governed_facts_in_scope() is not None
        return None

    monitoring.use_tool_id(tool_id, "governed-fact-declaration-probe")
    try:
        monitoring.register_callback(tool_id, monitoring.events.RAISE, on_raise)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, on_start)
        monitoring.set_events(tool_id, monitoring.events.RAISE)
        monitoring.set_local_events(tool_id, handler, monitoring.events.PY_START)
        yield observation
    finally:
        monitoring.set_local_events(tool_id, handler, monitoring.events.NO_EVENTS)
        monitoring.set_events(tool_id, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool_id, monitoring.events.RAISE, None)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool_id)


# --- population and argv --------------------------------------------------


def non_declaring_population(graph: CommandSpecGraph) -> tuple[CommandSpec, ...]:
    """Every runnable command dispatch does not scope."""
    return tuple(spec for spec in graph.specs if is_runnable(spec) and not runs_in_governed_fact_scope(spec))


def _refusal_report(key: str, spec: CommandSpec, refusals: Sequence[ScopeRefusal]) -> str:
    sites = sorted({refusal.site.locator() for refusal in refusals})
    first = refusals[0]
    return (
        f"{key} reads governed facts without declaring registry or encrypted-facts; "
        f"capabilities={sorted(spec.policy.expanded_capabilities)}; read sites={sites}; "
        f"first refusal {first.error_type}: {first.message}"
    )


_POPULATION: Final = non_declaring_population(COMMAND_GRAPH)
_DRIVEN: Final = tuple(spec.key for spec in _POPULATION if spec.key not in _EXEMPTIONS)


# --- the probe ------------------------------------------------------------


def test_the_raise_site_inventory_covers_the_refusal_family() -> None:
    """Both derivations find their sites, including the projection cache's."""
    sites = missing_scope_raise_sites()
    scope_module = os.path.normcase(
        str(Path(cadrumo.__file__).resolve().parent / "domain/calculations/registry/governed_fact_scope.py")
    )
    m296 = os.path.normcase(str(Path(cadrumo.__file__).resolve().parent / "application/filing/_m296_projection.py"))

    assert any(site.path == scope_module for site in sites)
    assert any(site.path == m296 for site in sites), "the absence-test derivation found no site"


def test_every_exemption_names_a_live_non_declaring_command() -> None:
    """A stale exemption fails: its key must exist and still be unscoped."""
    known = {spec.key for spec in COMMAND_GRAPH.specs}
    population = {spec.key for spec in _POPULATION}

    assert sorted(key for key in _EXEMPTIONS if key not in known) == []
    assert sorted(key for key in _EXEMPTIONS if key not in population) == []
    assert all(reason.strip() for reason in _EXEMPTIONS.values())
    assert len(_DRIVEN) + len(_EXEMPTIONS) == len(_POPULATION)
    for key, names in _HANDLER_REQUIRED_OPTIONS.items():
        assert key in population
        declared = {parameter.name for parameter in COMMAND_GRAPH.spec(key).parameters}
        assert set(names) <= declared, (key, names)


def test_the_offline_seal_refuses_every_boundary(offline_guard: OfflineGuard) -> None:
    """The seal refuses a connection, a resolution and a child process, and records each."""
    with pytest.raises(OSError, match="refuses"):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    with pytest.raises(OSError, match="refuses"), socket.socket() as probe:
        probe.connect(("127.0.0.1", 9))
    with pytest.raises(OSError, match="refuses"):
        socket.getaddrinfo("localhost", 80)
    with pytest.raises(OSError, match="refuses"):
        subprocess.run([sys.executable, "-c", "pass"], check=False)
    first, second = socket.socketpair()
    first.close()
    second.close()

    assert offline_guard.refused == [
        "socket.create_connection",
        "socket.connect",
        "socket.getaddrinfo",
        "child process",
    ]


@pytest.mark.parametrize("key", _DRIVEN)
def test_a_non_declaring_command_never_reaches_a_missing_scope_refusal(
    key: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
    request: pytest.FixtureRequest,
) -> None:
    spec = COMMAND_GRAPH.spec(key)
    handler = spec.handler
    assert handler is not None and handler.state is BindingState.TARGET and handler.target is not None
    workdir = tmp_path / "probe-inputs"
    workdir.mkdir()
    argv = synthetic_argv(COMMAND_GRAPH, spec, workdir, also=_HANDLER_REQUIRED_OPTIONS.get(key, ()))

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path, bucket_id=PROBE_PROFILE_ID, label=PROBE_PROFILE_LABEL
    ) as profile:
        seed_probe_profile(profile)
        with outside_governed_fact_validation(), observe_invocation(handler_code(handler.target)) as observed:
            result = invoke_cached_cli(argv)
    request.node.user_properties.append(("offline_outcome", f"{offline_guard.outcome()}; exit {result.exit_code}"))

    assert observed.refusals == [], _refusal_report(key, spec, observed.refusals)
    assert observed.handler_started, (
        f"{key} never reached its behavior target (exit {result.exit_code}); argv={argv}; output={result.output[-400:]}"
    )
    assert not observed.scope_lent_to_handler, f"{key} ran under a lent governed-fact scope, which masks a missing read"


# --- detector teeth -------------------------------------------------------

_HELP: Final = TranslationKey("cli.root.version_help")
_NO_SCHEMA: Final = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)
_TEETH_TARGET: Final = DeferredTarget(
    ".test_command_governed_fact_declaration_probe", "read_a_governed_fact", __package__
)


def read_a_governed_fact(ctx: object) -> None:
    """Read a governed fact the way an under-declared handler would."""
    del ctx
    resolve_m347_counterparty_annual_threshold(effective_date=date(2025, 1, 1))


def _state_free_policy() -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities=frozenset({"state-free"}),
        side_effects=frozenset({"none"}),
        performance="metadata",
        write_route=CommandWriteRoute.NONE,
    )


def _teeth_graph() -> CommandSpecGraph:
    root = CommandSpec(
        "root",
        None,
        "aeat",
        kind=CommandNodeKind.ROOT,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_state_free_policy(),
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    leaf = CommandSpec(
        "under_declared_read",
        "root",
        "under-declared-read",
        kind=CommandNodeKind.LEAF,
        help_key=_HELP,
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=_state_free_policy(),
        handler=LazyBinding.available(_TEETH_TARGET),
        result_schema=_NO_SCHEMA,
    )
    return CommandSpecGraph((root, leaf))


def test_the_probe_flags_a_state_free_command_that_reads_a_governed_fact() -> None:
    graph = _teeth_graph()
    population = non_declaring_population(graph)
    assert [spec.key for spec in population] == ["under_declared_read"]
    argv = synthetic_argv(graph, population[0], Path())

    with outside_governed_fact_validation(), observe_invocation(handler_code(_TEETH_TARGET)) as observed:
        result = invoke_uncached_typer_app(build_command_app(graph), argv)

    assert observed.handler_started
    assert not observed.scope_lent_to_handler
    assert result.exit_code != 0
    reader = inspect.getsourcefile(resolve_m347_counterparty_annual_threshold)
    assert reader is not None
    assert [refusal.site.path for refusal in observed.refusals] == [os.path.normcase(str(Path(reader).resolve()))]
    assert observed.refusals[0].error_type == "RegistryValidationError"
