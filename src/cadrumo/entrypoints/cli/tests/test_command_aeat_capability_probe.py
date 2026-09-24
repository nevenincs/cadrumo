"""A command that reaches AEAT declares the ``aeat`` capability.

The MCP identity gate refuses an unidentified call to a command whose policy
declares ``aeat``: reading AEAT for the wrong taxpayer is a confidentiality
breach even when nothing local changes. A command that reaches AEAT without the
declaration would slip past that gate, so this probe drives every runnable
command that does not declare ``aeat`` but may leave the host (``network``) or
belongs to the ``config auth`` family, which reads the configured AEAT
credentials, through the real CLI under the offline seal, and fails naming each
one that reaches for AEAT.

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

The Sede client modules are declared, and a test holds the declaration to the
source tree: every module under ``adapters/outbound/aeat`` that defines or
names ``default_browser_session_factory``, the one factory every AEAT browser
session is built from, must be declared, and nothing else may be.

Every run carries a synthetic, self-signed certificate naming the seeded
taxpayer, configured through settings. Without it a session-gated flow refuses
at credential loading, before it builds a Sede session, and shows none of the
three signals; with it the flow reaches the Sede client and stops at the sealed
browser launch. What remains out of reach is a command whose arguments or prior
local state the synthetic run cannot satisfy. The positive controls prove the
instrument fires on real AEAT commands, and the teeth test proves it flags an
undeclared one.
"""

from __future__ import annotations

import ast
import dis
import importlib
import importlib.util
import inspect
import os
import socket
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from typing import Final

import pytest

import cadrumo
from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_runtime_profile
from ....application.live.notification_ports import NotificationsSnapshot, NotificationType, RemoteNotification
from ....application.live.notifications import NotificationsService
from ....core.config import load_settings
from ....core.external_constants import load_external_constants
from ....core.period import Period, PeriodKind, accepted_filing_period_codes
from ....core.remote_authority import canonical_remote_hostname, is_aeat_host, is_sanctioned_gov_idp_host
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.user_profile.values import UserProfileFact
from ....tests.offline_seal import OfflineGuard, offline_guard_fixture
from ...live_state_composition import compose_notifications_ports
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
    PROBE_PROFILE_TAX_ID,
    command_path,
    free_monitoring_tool,
    handler_code,
    is_runnable,
    seed_probe_profile,
    synthetic_aeat_credentials,
    synthetic_argv,
)
from .cli_runner import invoke_cached_cli, invoke_uncached_typer_app

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SEDE_CLIENT_FACTORY: Final = "default_browser_session_factory"

#: Every AEAT adapter module that defines or names the Sede session factory.
_SEDE_CLIENT_MODULES: Final = (
    "cadrumo.adapters.outbound.aeat.browser.connectivity",
    "cadrumo.adapters.outbound.aeat.browser.factory",
    "cadrumo.adapters.outbound.aeat.sede.censal_datos",
    "cadrumo.adapters.outbound.aeat.sede.groi_check",
    "cadrumo.adapters.outbound.aeat.sede.iva_compensation_wallet",
    "cadrumo.adapters.outbound.aeat.sede.nif_iva_check",
    "cadrumo.adapters.outbound.aeat.sede.notifications",
    "cadrumo.adapters.outbound.aeat.sede.walker",
    "cadrumo.adapters.outbound.aeat.verify.contract",
)
_AEAT_ADAPTERS: Final = ("adapters", "outbound", "aeat")

#: Optional parameters a command's own handler requires one of.
_HANDLER_REQUIRED_OPTIONS: Final[dict[str, tuple[str, ...]]] = {
    "config_provision_remove": ("role",),
}

#: The quarterly self-assessment modelo the period-scoped live reads are asked
#: for; any modelo the Sede register holds would do.
_LIVE_MODELO: Final = "303"


@cache
def _filing_year() -> int:
    """The last filing year the published authority authors, a year every live read accepts."""
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon


@cache
def _quarterly_period_code() -> str:
    """The first filing-period code the period vocabulary accepts as a quarter."""
    year = _filing_year()
    return next(code for code in accepted_filing_period_codes() if Period.from_year_and_code(year, code).is_quarterly)


#: The annual income-tax modelo a reconcile pull is asked for: a natural-person
#: profile opens its work unit with no further profile facts.
_ANNUAL_MODELO: Final = "100"


@cache
def _annual_period_code() -> str:
    """The filing-period code the period vocabulary classifies as annual."""
    year = _filing_year()
    return next(
        code
        for code in accepted_filing_period_codes()
        if Period.from_year_and_code(year, code).kind is PeriodKind.ANNUAL
    )


def _supplied_values(key: str) -> dict[str, str]:
    """Domain-valid values for the parameters a live read validates against the period vocabulary."""
    year = str(_filing_year())
    period = _quarterly_period_code()
    return {
        "app_live_filed_pull": {"modelos": _LIVE_MODELO, "year": year},
        "app_live_filed_pull_sources": {"modelo": _LIVE_MODELO, "year": year, "period": period},
        "app_live_iva_wallet_pull": {"year": year, "period": period},
        "app_live_iva_wallet_pull_evidence": {
            "year_from": year,
            "year_to": year,
            "target_year": year,
            "target_period": period,
        },
        "app_live_justificante_pull": {"modelo": _LIVE_MODELO, "year": year, "period": period},
        "app_live_notifications_document_pull": {"certificado_id": _READ_NOTIFICATION_ID},
        "app_modelo_reconcile_pull": {"modelo": _ANNUAL_MODELO, "year": year, "period": _annual_period_code()},
    }.get(key, {})


#: A synthetic AEAT certificado identifier (ten to sixteen digits).
_READ_NOTIFICATION_ID: Final = "1000000000000001"


def _seed_read_notification() -> None:
    """Record, through the real notifications service, a snapshot holding one row AEAT reports read."""
    sede = str(load_external_constants().aeat.domains.sede)
    year = _filing_year()
    row = RemoteNotification(
        certificado_id=_READ_NOTIFICATION_ID,
        tipo=NotificationType.NOTIFICACION,
        concepto="Probe notification",
        titular_nif=PROBE_PROFILE_TAX_ID,
        titular_nombre="Ana Perez",
        destinatario_nif=PROBE_PROFILE_TAX_ID,
        destinatario_nombre="Ana Perez",
        fecha_emision=date(year, 1, 15),
        fecha_notificacion=date(year, 1, 20),
        modo_notificacion="Electronica",
        leida=True,
        source_url=sede,
    )
    snapshot = NotificationsSnapshot(rows=(row,), captured_at=datetime.now(UTC), source_url=sede)
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        NotificationsService(ports=compose_notifications_ports(settings=load_settings())).capture(
            bucket_id=PROBE_PROFILE_ID,
            snapshot=snapshot,
            authenticated_identity=PROBE_PROFILE_TAX_ID,
        )


def _seed_live_work_unit() -> None:
    """Open the modelo work unit a reconcile pull resolves, through the real ``work create`` verb."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            _ANNUAL_MODELO,
            "--year",
            str(_filing_year()),
            "--period",
            _annual_period_code(),
            "--allow-not-applicable",
        ],
    )
    assert result.exit_code == 0, result.output


#: Profile facts a modelo work unit requires before it can be opened.
_PROFILE_FACTS: Final[dict[str, tuple[UserProfileFact, ...]]] = {
    "app_modelo_reconcile_pull": (
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="activities.description", value="economic activity"),
    ),
}

#: Local state a command reads before it reaches the Sede, seeded through real repositories.
_SEEDERS: Final[dict[str, Callable[[], None]]] = {
    "app_live_notifications_document_pull": _seed_read_notification,
    "app_modelo_reconcile_pull": _seed_live_work_unit,
}


#: AEAT-declaring commands whose synthetic run reaches the Sede client, proving
#: the instrument fires on real code paths.
_POSITIVE_CONTROLS: Final = (
    "app_live_expedientes_pull",
    "app_live_filed_discover",
    "app_live_filed_pull",
    "app_live_filed_pull_all",
    "app_live_filed_pull_sources",
    "app_live_iva_wallet_pull",
    "app_live_iva_wallet_pull_evidence",
    "app_live_iva_wallet_pull_history",
    "app_live_justificante_pull",
    "app_live_notifications_document_pull",
    "app_live_notifications_pull",
    "app_live_verify_nif_iva",
    "app_live_verify_tgvi",
    "config_auth_login",
    "config_profile_censo_pull",
    "config_repair_connectivity",
    "app_modelo_reconcile_pull",
)

#: AEAT-declaring commands the probe cannot drive offline, each with the
#: precondition it lacks and why its declaration is still correct.
_AEAT_EXEMPTIONS: Final[dict[str, str]] = {}

#: The command group whose members read the configured AEAT credentials and
#: session, and so are driven whatever network capability they declare.
_AUTHENTICATION_FAMILY: Final = ("config", "auth")


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


def scanned_sede_client_modules() -> frozenset[str]:
    """Every AEAT adapter module the source tree shows defining or naming the Sede session factory."""
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
    """Yield the code the module's own source defines, never a decorator's shared wrapper."""
    source = os.path.normcase(str(Path(module.__file__ or "").resolve()))
    for value in vars(module).values():
        members: list[object] = [value]
        if isinstance(value, type) and value.__module__ == module.__name__:
            members = list(vars(value).values())
        for member in members:
            for candidate in (member, getattr(member, "__func__", None), getattr(member, "fget", None)):
                if not isinstance(candidate, FunctionType):
                    continue
                code = inspect.unwrap(candidate).__code__
                if os.path.normcase(str(Path(code.co_filename).resolve())) == source:
                    yield from _nested_codes(code)


@cache
def sede_client_codes() -> frozenset[CodeType]:
    """Every code object defined in a declared Sede client module."""
    codes: set[CodeType] = set()
    for name in _SEDE_CLIENT_MODULES:
        codes.update(_module_codes(importlib.import_module(name)))
    return frozenset(codes)


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


def _import_sites(code: CodeType) -> dict[int, tuple[str, int, tuple[str, ...]]]:
    """Map each import instruction in ``code`` to its module name, level and from-list."""
    instructions = [instruction for instruction in dis.get_instructions(code) if instruction.opname != "EXTENDED_ARG"]
    sites: dict[int, tuple[str, int, tuple[str, ...]]] = {}
    for index, instruction in enumerate(instructions):
        if instruction.opname != "IMPORT_NAME":
            continue
        level, fromlist = instructions[index - 2].argval, instructions[index - 1].argval
        site = (str(instruction.argval), int(level), tuple(fromlist or ()))
        sites[instruction.offset] = site
        sites[instruction.start_offset] = site
    return sites


@contextmanager
def observe_aeat_contact(handler: CodeType) -> Iterator[AeatContactObservation]:
    """Record the handler's Sede-client imports, Sede-client calls and the handler's start."""
    modules = frozenset(_SEDE_CLIENT_MODULES)
    codes = sede_client_codes()
    import_sites = _import_sites(handler)
    observation = AeatContactObservation()

    def on_instruction(code: CodeType, instruction_offset: int) -> object:
        site = import_sites.get(instruction_offset) if code is handler else None
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if site is not None and caller is not None and caller.f_code is handler:
            name, level, fromlist = site
            observation.imports.extend(sorted(_imported_names(name, caller.f_globals, fromlist, level) & modules))
        return None

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
        monitoring.register_callback(tool_id, monitoring.events.INSTRUCTION, on_instruction)
        for code in watched:
            events = monitoring.events.PY_START
            if code is handler:
                events |= monitoring.events.INSTRUCTION
            monitoring.set_local_events(tool_id, code, events)
        yield observation
    finally:
        for code in watched:
            monitoring.set_local_events(tool_id, code, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
        monitoring.register_callback(tool_id, monitoring.events.INSTRUCTION, None)
        monitoring.free_tool_id(tool_id)


# --- population -----------------------------------------------------------


def aeat_suspects_without_aeat(graph: CommandSpecGraph) -> tuple[CommandSpec, ...]:
    """Every runnable command without ``aeat`` that may leave the host or reads AEAT credentials."""
    return tuple(
        spec
        for spec in graph.specs
        if is_runnable(spec)
        and "aeat" not in spec.policy.expanded_capabilities
        and (
            "network" in spec.policy.expanded_capabilities
            or command_path(graph, spec)[: len(_AUTHENTICATION_FAMILY)] == _AUTHENTICATION_FAMILY
        )
    )


_POPULATION: Final = aeat_suspects_without_aeat(COMMAND_GRAPH)


def _drive(key: str, tmp_path: Path) -> tuple[AeatContactObservation, int, str]:
    spec = COMMAND_GRAPH.spec(key)
    handler = spec.handler
    assert handler is not None and handler.state is BindingState.TARGET and handler.target is not None
    workdir = tmp_path / "probe-inputs"
    workdir.mkdir()
    argv = synthetic_argv(
        COMMAND_GRAPH,
        spec,
        workdir,
        also=_HANDLER_REQUIRED_OPTIONS.get(key, ()),
        values=_supplied_values(key),
    )
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path, bucket_id=PROBE_PROFILE_ID, label=PROBE_PROFILE_LABEL
    ) as profile:
        seed_probe_profile(profile, extra_facts=_PROFILE_FACTS.get(key, ()))
        seeder = _SEEDERS.get(key)
        if seeder is not None:
            seeder()
        with (
            synthetic_aeat_credentials(workdir),
            observe_aeat_contact(handler_code(handler.target)) as observed,
        ):
            result = invoke_cached_cli(argv)
    return observed, result.exit_code, result.output[-400:]


def test_the_declared_sede_client_is_the_one_in_the_source_tree() -> None:
    scanned = scanned_sede_client_modules()

    assert "cadrumo.adapters.outbound.aeat.browser.factory" in scanned
    assert len(scanned) > 1, "only the factory itself names the Sede client"
    assert sorted(_SEDE_CLIENT_MODULES) == sorted(scanned)
    assert sede_client_codes()


def test_every_aeat_command_is_a_positive_control_or_a_reasoned_exemption() -> None:
    """A stale exemption or an undriven AEAT command fails."""
    declaring = {spec.key for spec in COMMAND_GRAPH.specs if is_runnable(spec) and "aeat" in spec.policy.capabilities}

    assert set(_POSITIVE_CONTROLS) | set(_AEAT_EXEMPTIONS) == declaring
    assert not set(_POSITIVE_CONTROLS) & set(_AEAT_EXEMPTIONS)
    assert all(reason.strip() for reason in _AEAT_EXEMPTIONS.values())
    assert set(_SEEDERS) | set(_PROFILE_FACTS) <= set(_POSITIVE_CONTROLS)


def test_the_population_covers_network_commands_and_the_authentication_family() -> None:
    keys = {spec.key for spec in _POPULATION}

    assert {"config_provision_status", "config_auth_test", "config_auth_status"} <= keys
    assert not keys & set(_POSITIVE_CONTROLS)
    for key in _HANDLER_REQUIRED_OPTIONS:
        assert key in keys


@pytest.mark.parametrize("key", [spec.key for spec in _POPULATION])
def test_a_command_without_aeat_never_reaches_aeat(
    key: str,
    tmp_path: Path,
    offline_guard: OfflineGuard,
) -> None:
    observed, exit_code, output = _drive(key, tmp_path)
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
) -> None:
    assert "aeat" in COMMAND_GRAPH.spec(key).policy.expanded_capabilities
    observed, exit_code, output = _drive(key, tmp_path)

    assert observed.handler_started, f"{key} never reached its behavior target (exit {exit_code}); output={output}"
    assert observed.contacts(offline_guard), (
        f"{key} declares aeat but its run showed no AEAT contact; exit {exit_code}; output={output}"
    )


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
) -> None:
    graph = _teeth_graph()
    population = aeat_suspects_without_aeat(graph)
    assert [spec.key for spec in population] == ["undeclared_sede_read"]
    argv = synthetic_argv(graph, population[0], Path())

    with observe_aeat_contact(handler_code(_TEETH_TARGET)) as observed:
        invoke_uncached_typer_app(build_command_app(graph), argv)

    sede_host = canonical_remote_hostname(load_external_constants().aeat.domains.sede)
    assert observed.handler_started
    assert observed.contacts(offline_guard) == [
        f"host {sede_host}",
        "import cadrumo.adapters.outbound.aeat.browser.factory",
    ]
