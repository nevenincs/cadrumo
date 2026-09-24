"""A command that reaches AEAT declares the ``aeat`` capability.

The MCP identity gate refuses an unidentified call to a command whose policy
declares ``aeat``: reading AEAT for the wrong taxpayer is a confidentiality
breach even when nothing local changes. A command that reaches AEAT without the
declaration would slip past that gate, so this probe drives every runnable
command that may leave the host (``network``) but does not declare ``aeat``
through the real CLI under the offline seal, and fails naming each one that
reaches for AEAT.

Detection signal
----------------
Three in-process observations, any one of which is an AEAT contact:

* a host the sealed run tried to resolve or connect to that is AEAT's own or
  the Cl@ve identity provider AEAT delegates to, classified by
  ``core.remote_authority``;
* an import of a Sede client module executed by the command's own handler,
  which catches a handler that lazily imports the client before refusing for
  want of a session (a composition root that merely binds the client into a
  port registry is wiring, not a read, and is not counted); and
* the start of any function defined in a Sede client module.

The Sede client modules are derived from the source tree: every module under
``adapters/outbound/aeat`` that defines or names
``default_browser_session_factory``, the one factory every AEAT browser session
is built from.

The limit is the synthetic state: a session-gated flow whose handler holds the
client only through a module-level import and refuses before calling it shows
none of the three. The positive controls prove the instrument fires on real
AEAT commands, and the teeth test proves it flags an undeclared one.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import inspect
import socket
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from typing import Final

import pytest

import cadrumo
from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_runtime_profile
from ....core.external_constants import load_external_constants
from ....core.remote_authority import canonical_remote_hostname, is_aeat_host, is_sanctioned_gov_idp_host
from .._command_runtime import build_command_app
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
from ._offline_seal_fixture import OfflineGuard, offline_guard_fixture
from .cli_runner import invoke_cached_cli, invoke_uncached_typer_app

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SEDE_CLIENT_FACTORY: Final = "default_browser_session_factory"
_AEAT_ADAPTERS: Final = ("adapters", "outbound", "aeat")

#: Optional parameters a command's own handler requires one of.
_HANDLER_REQUIRED_OPTIONS: Final[dict[str, tuple[str, ...]]] = {
    "config_provision_remove": ("role",),
}

#: AEAT-declaring commands whose synthetic run reaches the Sede client, proving
#: the instrument fires on real code paths.
_POSITIVE_CONTROLS: Final = ("config_repair_connectivity", "config_auth_login")


# --- the Sede client ------------------------------------------------------


def _names_sede_factory(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.FunctionDef | ast.AsyncFunctionDef) and _SEDE_CLIENT_FACTORY in (
            getattr(node, "id", None),
            getattr(node, "name", None),
        ):
            return True
        if isinstance(node, ast.Attribute) and node.attr == _SEDE_CLIENT_FACTORY:
            return True
        if isinstance(node, ast.ImportFrom) and any(alias.name == _SEDE_CLIENT_FACTORY for alias in node.names):
            return True
    return False


@cache
def sede_client_modules() -> frozenset[str]:
    """Every AEAT adapter module that defines or names the Sede session factory."""
    source_root = Path(cadrumo.__file__).resolve().parent
    package_root = source_root.joinpath(*_AEAT_ADAPTERS)
    modules: set[str] = set()
    for path in package_root.rglob("*.py"):
        relative = path.relative_to(source_root)
        if "tests" in relative.parts:
            continue
        if _names_sede_factory(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            parts = relative.with_suffix("").parts
            modules.add(".".join(("cadrumo", *(parts[:-1] if parts[-1] == "__init__" else parts))))
    return frozenset(modules)


def _nested_codes(code: CodeType) -> Iterator[CodeType]:
    yield code
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from _nested_codes(constant)


def _module_codes(module: ModuleType) -> Iterator[CodeType]:
    for value in vars(module).values():
        members: list[object] = [value]
        if isinstance(value, type) and value.__module__ == module.__name__:
            members = list(vars(value).values())
        for member in members:
            for candidate in (member, getattr(member, "__func__", None), getattr(member, "fget", None)):
                if isinstance(candidate, FunctionType) and candidate.__module__ == module.__name__:
                    yield from _nested_codes(candidate.__code__)


@cache
def sede_client_codes() -> frozenset[CodeType]:
    """Every code object defined in a Sede client module."""
    return frozenset(code for name in sede_client_modules() for code in _module_codes(importlib.import_module(name)))


# --- observation ----------------------------------------------------------


@dataclass(slots=True)
class AeatContactObservation:
    """What one driven command did toward AEAT, and whether it ran at all."""

    imports: list[str] = field(default_factory=list)
    starts: list[str] = field(default_factory=list)
    handler_started: bool = False

    def contacts(self, guard: OfflineGuard) -> list[str]:
        """Name every AEAT contact the run made, in the order observed."""
        hosts = [f"host {host}" for host in guard.hosts if is_aeat_host(host) or is_sanctioned_gov_idp_host(host)]
        return [*hosts, *(f"import {name}" for name in self.imports), *(f"call {name}" for name in self.starts)]


def _imported_names(
    name: str,
    globals_: Mapping[str, object] | None,
    fromlist: Sequence[str] | None,
    level: int,
) -> set[str]:
    package = None if globals_ is None else globals_.get("__package__")
    if level:
        if not isinstance(package, str):
            return set()
        base = importlib.util.resolve_name("." * level + name, package)
    else:
        base = name
    return {base, *(f"{base}.{item}" for item in fromlist or ())}


@contextmanager
def observe_aeat_contact(handler: CodeType, monkeypatch: pytest.MonkeyPatch) -> Iterator[AeatContactObservation]:
    """Record the handler's Sede-client imports, Sede-client calls and the handler's start."""
    modules = sede_client_modules()
    codes = sede_client_codes()
    observation = AeatContactObservation()
    original_import = builtins.__import__

    def recording_import(
        name: str,
        module_globals: Mapping[str, object] | None = None,
        module_locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if caller is not None and caller.f_code is handler:
            observation.imports.extend(sorted(_imported_names(name, module_globals, fromlist, level) & modules))
        return original_import(name, module_globals, module_locals, fromlist, level)

    monitoring = sys.monitoring
    tool_id = free_monitoring_tool()

    def on_start(code: CodeType, instruction_offset: int) -> object:
        del instruction_offset
        if code is handler:
            observation.handler_started = True
        else:
            observation.starts.append(code.co_qualname)
        return None

    watched = {handler, *codes}
    monitoring.use_tool_id(tool_id, "aeat-capability-probe")
    try:
        monitoring.register_callback(tool_id, monitoring.events.PY_START, on_start)
        for code in watched:
            monitoring.set_local_events(tool_id, code, monitoring.events.PY_START)
        with monkeypatch.context() as scoped:
            scoped.setattr(builtins, "__import__", recording_import)
            yield observation
    finally:
        for code in watched:
            monitoring.set_local_events(tool_id, code, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.free_tool_id(tool_id)


# --- population -----------------------------------------------------------


def network_without_aeat(graph: CommandSpecGraph) -> tuple[CommandSpec, ...]:
    """Every runnable command that may leave the host but does not declare AEAT."""
    return tuple(
        spec
        for spec in graph.specs
        if is_runnable(spec)
        and "network" in spec.policy.expanded_capabilities
        and "aeat" not in spec.policy.expanded_capabilities
    )


_POPULATION: Final = network_without_aeat(COMMAND_GRAPH)


def _drive(key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[AeatContactObservation, int, str]:
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
        with observe_aeat_contact(handler_code(handler.target), monkeypatch) as observed:
            result = invoke_cached_cli(argv)
    return observed, result.exit_code, result.output[-400:]


def test_the_sede_client_is_found_in_the_source_tree() -> None:
    modules = sede_client_modules()

    assert "cadrumo.adapters.outbound.aeat.browser.factory" in modules
    assert len(modules) > 1, "only the factory itself names the Sede client"
    assert sede_client_codes()


def test_the_population_is_every_network_command_without_aeat() -> None:
    keys = {spec.key for spec in _POPULATION}

    assert "config_provision_status" in keys
    assert not keys & set(_POSITIVE_CONTROLS)
    for key in _HANDLER_REQUIRED_OPTIONS:
        assert key in keys


@pytest.mark.parametrize("key", [spec.key for spec in _POPULATION])
def test_a_command_without_aeat_never_reaches_aeat(
    key: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed, exit_code, output = _drive(key, tmp_path, monkeypatch)
    spec = COMMAND_GRAPH.spec(key)

    assert observed.contacts(offline_guard) == [], (
        f"{key} reaches AEAT without declaring the aeat capability; "
        f"capabilities={sorted(spec.policy.expanded_capabilities)}"
    )
    assert observed.handler_started, f"{key} never reached its behavior target (exit {exit_code}); output={output}"


@pytest.mark.parametrize("key", _POSITIVE_CONTROLS)
def test_the_instrument_fires_on_a_command_that_declares_aeat(
    key: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "aeat" in COMMAND_GRAPH.spec(key).policy.expanded_capabilities
    observed, exit_code, output = _drive(key, tmp_path, monkeypatch)

    assert observed.handler_started, f"{key} never reached its behavior target (exit {exit_code}); output={output}"
    assert observed.contacts(offline_guard), f"{key} declares aeat but its run showed no AEAT contact"


# --- detector teeth -------------------------------------------------------

_NO_SCHEMA: Final = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)
_TEETH_TARGET: Final = DeferredTarget(".test_command_aeat_capability_probe", "reach_the_sede", __package__)


def reach_the_sede(ctx: object) -> None:
    """Reach AEAT the way an under-declared handler would."""
    del ctx
    from ....adapters.outbound.aeat.browser import factory

    del factory
    host = canonical_remote_hostname(load_external_constants().aeat.domains.sede)
    assert host is not None
    socket.create_connection((host, 443), timeout=1)


def _network_policy() -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities=frozenset({"network"}),
        side_effects=frozenset({"none"}),
        performance="external-io",
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
        policy=ExecutionPolicySpec(
            capabilities=frozenset({"state-free"}),
            side_effects=frozenset({"none"}),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
        ),
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    leaf = CommandSpec(
        "undeclared_sede_read",
        "root",
        "undeclared-sede-read",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.root.version_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=_network_policy(),
        handler=LazyBinding.available(_TEETH_TARGET),
        result_schema=_NO_SCHEMA,
    )
    return CommandSpecGraph((root, leaf))


def test_the_probe_flags_a_network_command_that_reaches_aeat_undeclared(
    offline_guard: OfflineGuard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _teeth_graph()
    population = network_without_aeat(graph)
    assert [spec.key for spec in population] == ["undeclared_sede_read"]
    argv = synthetic_argv(graph, population[0], Path())

    with observe_aeat_contact(handler_code(_TEETH_TARGET), monkeypatch) as observed:
        invoke_uncached_typer_app(build_command_app(graph), argv)

    assert observed.handler_started
    assert observed.contacts(offline_guard) == [
        "host sede.agenciatributaria.gob.es",
        "import cadrumo.adapters.outbound.aeat.browser.factory",
    ]
