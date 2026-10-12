"""Whatever a command does, the terminal interface and MCP can ask for the same work.

Every executable command of the live tree is held to each of four ways of
reaching the other frontends that applies to it: it submits a registered
operation; it sends a runtime request or an installation act; it works in the
command-line process and a declared operation, installation act or ``authority``
query does the same work; or it has no work to share, and says why. A command
that submits in one mode and works in process in another is held to both. A
command in none of the four does work only the command line can do, and fails
here by name.

The first two ways are read from the recorded command table, which the tests
beside this one hold to the live handlers and registry. The third and fourth
are declared, and the declarations are held here to the live registry, the
table of installation acts and the harness's own tools, in both directions: a
counterpart that does not exist fails, and so does an installation act or a
registered operation that no command reaches and nothing accounts for. Each
declared pair also names the test that runs the command and its counterpart
and compares what they return. That test must exist, and a pair no test
compares says so, so that the pairs nothing proves stay a visible list. An
operation a command submits or serves must be one the runtime can admit, or be
declared with the reason it cannot.

No count is a pass condition. The assertions are about membership, so a tree
that gains a command, an operation or an act changes what is checked and
nothing here is edited unless the new thing is unreached.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import NoReturn

import pytest

from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE

from ....application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from ....application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from ....application.export.google_operation import (
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
)
from ....application.operations.registry import OperationRegistry
from ....application.operator_surface.command_operations import CommandOperationJoin, CommandOperations
from ....application.operator_surface.command_ports import CommandNodeKind
from ....application.runtime.installation_requests import INSTALLATION_ACT_CONTRACTS, InstallationAct
from ...operation_composition import build_production_operation_registry
from ...runtime.installation_composition import production_installation_acts
from ..command_specs import COMMAND_GRAPH
from ..operator_surface_reconciliation import recorded_command_operation_join
from .command_frontend_counterparts import (
    AUTHORITY_TOOL,
    COMMANDS_WITH_NO_WORK_TO_SHARE,
    EXECUTE_TOOL,
    IN_PROCESS_COMMAND_COUNTERPARTS,
    INSTALLATION_ACTS_WITHOUT_A_COMMAND,
    INSTALLATION_TOOL,
    OPERATIONS_WITHOUT_A_COMMAND,
    OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER,
    SESSION_DOOR_COMMAND_TOOLS,
    SESSION_TOOL,
    CommandReach,
    Counterpart,
    ToolRoute,
    Unproven,
    command_reaches,
    operations_without_an_access_resolver,
    other_frontend_routes,
    proof_finding,
    reach_of_every_command,
    requests_beyond_admission,
    unproven_pairs,
)
from .command_operation_derivation import PROFILE_ADMISSION_ACTION, CliPath

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SELECTOR_ARGUMENT: Mapping[str, str] = {
    AUTHORITY_TOOL: "query",
    INSTALLATION_TOOL: "action",
    SESSION_TOOL: "action",
}
"""The argument through which each of these tools is told which piece of work to do."""


def _unused_port(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no executor runs in a registry that is only read")


@cache
def _join() -> CommandOperationJoin:
    return recorded_command_operation_join()


@cache
def _registered() -> frozenset[str]:
    return frozenset(definition.definition_id for definition in build_production_operation_registry().definitions)


def _rows() -> dict[CliPath, CommandOperations]:
    return {row.cli_path: row for row in _join().commands}


def _spelled(cli_path: CliPath) -> str:
    return " ".join(("aeat", *cli_path))


def _tool_selectors(tool: str) -> frozenset[str]:
    """Read from the harness's own catalogue what one tool can be told to do."""
    schemas = {name: schema for name, _description, schema in MCP_TOOL_CATALOGUE}
    assert tool in schemas, f"the harness serves no tool named {tool!r}"
    declaration = schemas[tool]["properties"][_SELECTOR_ARGUMENT[tool]]
    return frozenset(declaration["enum"])


def _route_finding(route: ToolRoute) -> str | None:
    """Say why a declared route leads nowhere, when it does."""
    if route.tool == EXECUTE_TOOL:
        return None if route.selector in _registered() else "names an operation that is not registered"
    if route.tool in _SELECTOR_ARGUMENT:
        known = _tool_selectors(route.tool)
        return None if route.selector in known else f"names nothing the {route.tool} tool can be told to do"
    if route.selector is not None:
        return "gives a selector to a tool that takes none"
    tools = {name for name, _description, _schema in MCP_TOOL_CATALOGUE}
    return None if route.tool in tools else "names a tool the harness does not serve"


# -- every command reaches the other frontends ----------------------------------


def test_the_recorded_commands_are_the_executable_nodes_of_the_live_tree() -> None:
    """The commands judged below are the live ones: every leaf and every group that runs a callback."""
    nodes = COMMAND_GRAPH.nodes()
    executable = {node.path[1:] for node in nodes if node.spec.handler is not None}
    leaves = {node.path[1:] for node in nodes if node.spec.kind == CommandNodeKind.LEAF}
    assert leaves, "the live command graph declares no leaf; the denominator is empty"
    assert leaves <= executable
    assert set(_rows()) == executable


def test_every_executable_command_reaches_the_other_frontends_or_has_no_work_to_share() -> None:
    """No command does work that only the command line can do."""
    reach = reach_of_every_command(_join().commands)

    unreached = [_spelled(cli_path) for cli_path in reach[CommandReach.UNREACHED]]
    assert not unreached, (
        "these commands submit nothing, send nothing and declare no counterpart, so the terminal interface "
        f"and MCP cannot do what they do: {unreached}"
    )
    for cli_path in _rows():
        assert sum(cli_path in paths for paths in reach.values()) >= 1, _spelled(cli_path)
    for populated in (
        CommandReach.SUBMITS_OPERATION,
        CommandReach.SENDS_RUNTIME_REQUEST,
        CommandReach.WORKS_IN_PROCESS,
        CommandReach.NO_WORK_TO_SHARE,
    ):
        assert reach[populated], f"no command {populated.value}; the reading has lost a whole way of reaching"


def test_admission_to_a_profile_alone_is_not_read_as_reaching_the_runtime() -> None:
    """A command that only logs in to a profile has sent nothing about its work."""
    admitted_only = CommandOperations(cli_path=("config", "example"), runtime_requests=(PROFILE_ADMISSION_ACTION,))
    sends = CommandOperations(
        cli_path=("config", "example"), runtime_requests=(PROFILE_ADMISSION_ACTION, "session_inventory")
    )

    assert command_reaches(admitted_only, in_process={}, no_work={}) == (CommandReach.UNREACHED,)
    assert command_reaches(sends, in_process={}, no_work={}) == (CommandReach.SENDS_RUNTIME_REQUEST,)


def test_the_reading_names_every_way_a_command_reaches_and_one_no_way_covers() -> None:
    """A planted command of each kind is read as that kind, one with two ways as both, and one with none as unreached."""
    submits = CommandOperations(cli_path=("a",), operation_ids=("ledger.list",))
    sends = CommandOperations(cli_path=("b",), runtime_requests=("storage_check",))
    paired = CommandOperations(cli_path=("c",))
    idle = CommandOperations(cli_path=("d",))
    alone = CommandOperations(cli_path=("e",))
    both = CommandOperations(cli_path=("f",), operation_ids=("ledger.list",))
    served = Counterpart((ToolRoute(EXECUTE_TOOL, "ledger.list"),), Unproven("planted"))
    in_process: dict[CliPath, Counterpart] = {
        ("c",): served,
        ("f",): served,
        ("z",): Counterpart((), Unproven("planted")),
    }
    no_work: dict[CliPath, str] = {("d",): "prints its own help"}

    assert command_reaches(submits, in_process=in_process, no_work=no_work) == (CommandReach.SUBMITS_OPERATION,)
    assert command_reaches(sends, in_process=in_process, no_work=no_work) == (CommandReach.SENDS_RUNTIME_REQUEST,)
    assert command_reaches(paired, in_process=in_process, no_work=no_work) == (CommandReach.WORKS_IN_PROCESS,)
    assert command_reaches(idle, in_process=in_process, no_work=no_work) == (CommandReach.NO_WORK_TO_SHARE,)
    assert command_reaches(alone, in_process=in_process, no_work=no_work) == (CommandReach.UNREACHED,)
    assert command_reaches(both, in_process=in_process, no_work=no_work) == (
        CommandReach.SUBMITS_OPERATION,
        CommandReach.WORKS_IN_PROCESS,
    )
    # A row that names no counterpart pairs the command with nothing.
    assert command_reaches(CommandOperations(cli_path=("z",)), in_process=in_process, no_work=no_work) == (
        CommandReach.UNREACHED,
    )


def test_a_command_that_submits_an_operation_and_works_in_process_is_held_to_both() -> None:
    """The real tree's commands with an operation row and an in-process row are read in both ways."""
    rows = _rows()
    both = sorted(
        cli_path
        for cli_path, row in rows.items()
        if row.operation_ids and IN_PROCESS_COMMAND_COUNTERPARTS.get(cli_path) is not None
    )
    reach = reach_of_every_command(rows.values())

    assert both, "no command both submits an operation and works in process; the reading has lost a whole kind"
    for cli_path in both:
        assert cli_path in reach[CommandReach.SUBMITS_OPERATION], _spelled(cli_path)
        assert cli_path in reach[CommandReach.WORKS_IN_PROCESS], _spelled(cli_path)
        assert other_frontend_routes(rows[cli_path]), _spelled(cli_path)


# -- the declarations name live things -------------------------------------------


def test_every_declared_row_names_an_executable_command_once() -> None:
    """A row for a command that left the tree, or a command declared two ways, fails."""
    rows = _rows()
    for name, declared in (
        ("in-process counterparts", IN_PROCESS_COMMAND_COUNTERPARTS),
        ("session and key tools", SESSION_DOOR_COMMAND_TOOLS),
        ("commands with no work to share", COMMANDS_WITH_NO_WORK_TO_SHARE),
    ):
        unknown = sorted(_spelled(cli_path) for cli_path in set(declared) - set(rows))
        assert not unknown, f"{name} name commands the live tree does not have: {unknown}"
    both = sorted(
        _spelled(cli_path) for cli_path in set(IN_PROCESS_COMMAND_COUNTERPARTS) & set(COMMANDS_WITH_NO_WORK_TO_SHARE)
    )
    assert not both, f"declared both as having a counterpart and as having no work to share: {both}"


def test_every_declared_counterpart_and_tool_route_exists() -> None:
    """Each operation is registered, each act is served, and each query and action is one its tool takes."""
    findings = {
        f"{_spelled(cli_path)} -> {route.tool} {route.selector or ''}".rstrip(): finding
        for declared in (IN_PROCESS_COMMAND_COUNTERPARTS, SESSION_DOOR_COMMAND_TOOLS)
        for cli_path, pair in declared.items()
        for route in pair.routes
        if (finding := _route_finding(route)) is not None
    }
    assert not findings, f"declared routes that lead nowhere: {findings}"
    empty = sorted(
        _spelled(cli_path)
        for declared in (IN_PROCESS_COMMAND_COUNTERPARTS, SESSION_DOOR_COMMAND_TOOLS)
        for cli_path, pair in declared.items()
        if not pair.routes
    )
    assert not empty, f"declared rows that name no route: {empty}"


def test_the_installation_tool_offers_every_act_the_runtime_serves() -> None:
    """An act named as a counterpart is one the installed runtime answers and the harness offers."""
    served = production_installation_acts().served_acts
    assert served == frozenset(INSTALLATION_ACT_CONTRACTS)
    assert _tool_selectors(INSTALLATION_TOOL) == {act.value for act in served}


def test_a_route_that_leads_nowhere_is_found() -> None:
    """An unregistered operation, an unknown act, query, action and tool are each named."""
    assert _route_finding(ToolRoute(EXECUTE_TOOL, "ledger.no-such-operation")) is not None
    assert _route_finding(ToolRoute(INSTALLATION_TOOL, "no_such_act")) is not None
    assert _route_finding(ToolRoute(AUTHORITY_TOOL, "no_such_query")) is not None
    assert _route_finding(ToolRoute(SESSION_TOOL, "no_such_action")) is not None
    assert _route_finding(ToolRoute("no_such_tool")) is not None
    assert _route_finding(ToolRoute("status", "anything")) is not None
    assert _route_finding(ToolRoute(EXECUTE_TOOL, "ledger.list")) is None
    assert _route_finding(ToolRoute(INSTALLATION_TOOL, InstallationAct.STORAGE_CHECK.value)) is None
    assert _route_finding(ToolRoute("status")) is None


def test_a_command_with_no_work_to_share_sends_nothing_and_says_why() -> None:
    """The set stays small and true: a member that starts reaching the runtime has to leave it."""
    rows = _rows()
    unexplained = sorted(
        _spelled(path) for path, reason in COMMANDS_WITH_NO_WORK_TO_SHARE.items() if not reason.strip()
    )
    assert not unexplained, f"declared as having no work to share, with no reason: {unexplained}"
    reaching = sorted(
        _spelled(cli_path)
        for cli_path in COMMANDS_WITH_NO_WORK_TO_SHARE
        if rows[cli_path].operation_ids or rows[cli_path].runtime_requests
    )
    assert not reaching, f"declared as having no work to share, yet they reach the runtime: {reaching}"
    assert ("app", "tui") in COMMANDS_WITH_NO_WORK_TO_SHARE


def test_every_command_that_sends_a_session_or_key_request_names_the_tool_that_sends_it() -> None:
    """A request of the runtime's door that is no installation act is asked for through a declared tool."""
    acts = {act.value for act in InstallationAct}
    sending = {
        cli_path for cli_path, row in _rows().items() if not row.operation_ids and requests_beyond_admission(row) - acts
    }
    undeclared = sorted(_spelled(cli_path) for cli_path in sending - set(SESSION_DOOR_COMMAND_TOOLS))
    stale = sorted(_spelled(cli_path) for cli_path in set(SESSION_DOOR_COMMAND_TOOLS) - sending)
    assert not undeclared, f"commands that send a session or key request with no tool named for it: {undeclared}"
    assert not stale, f"commands named with a session or key tool that send no such request: {stale}"


def test_every_command_that_reaches_the_other_frontends_has_a_tool_route() -> None:
    """An MCP client can find a tool for the work of every command that has work to share."""
    without_a_route = sorted(
        _spelled(row.cli_path)
        for row in _join().commands
        if set(command_reaches(row)) - {CommandReach.NO_WORK_TO_SHARE, CommandReach.UNREACHED}
        and not row.operation_ids
        and not other_frontend_routes(row)
    )
    assert not without_a_route


# -- nothing made for the other frontends is left unaccounted for ---------------------


def _paired(tool: str) -> frozenset[str]:
    return frozenset(
        route.selector
        for pair in IN_PROCESS_COMMAND_COUNTERPARTS.values()
        for route in pair.routes
        if route.tool == tool and route.selector is not None
    )


def test_every_installation_act_is_sent_by_a_command_or_serves_the_work_of_one() -> None:
    """An act no command reaches is declared with its reason, and the declaration cannot go stale."""
    sent = {row.action for row in _join().runtime_requests if row.cli_paths}
    reached = sent | _paired(INSTALLATION_TOOL)
    declared = {act.value for act in INSTALLATION_ACTS_WITHOUT_A_COMMAND}
    every = {act.value for act in InstallationAct}

    unaccounted = sorted(every - reached - declared)
    stale = sorted(declared & reached)
    assert not unaccounted, f"installation acts no command sends and no command's work is served by: {unaccounted}"
    assert not stale, f"declared as having no command, yet a command reaches them: {stale}"
    assert all(reason.strip() for reason in INSTALLATION_ACTS_WITHOUT_A_COMMAND.values())


def test_every_registered_operation_is_submitted_by_a_command_or_serves_the_work_of_one() -> None:
    """An operation only the other frontends submit is declared with its reason, and that cannot go stale."""
    join = _join()
    registered = _registered()
    submitted = {row.operation_id for row in join.operations if row.cli_paths}
    unsubmitted = registered - submitted
    paired = _paired(EXECUTE_TOOL)
    declared = set(OPERATIONS_WITHOUT_A_COMMAND)

    unaccounted = sorted(unsubmitted - paired - declared)
    assert not unaccounted, (
        "registered operations no command submits, that serve no command's in-process work and that nothing "
        f"accounts for: {unaccounted}"
    )
    assert not sorted(declared - registered), f"declared, but not registered: {sorted(declared - registered)}"
    assert not sorted(declared & submitted), (
        f"declared as having no command, yet one submits: {sorted(declared & submitted)}"
    )
    assert not sorted(declared & paired), (
        f"declared as having no command, yet paired with one: {sorted(declared & paired)}"
    )
    assert all(entry.reason.strip() for entry in OPERATIONS_WITHOUT_A_COMMAND.values())
    unreached_siblings = {
        operation_id: entry.command_line_operation
        for operation_id, entry in OPERATIONS_WITHOUT_A_COMMAND.items()
        if entry.command_line_operation is not None and entry.command_line_operation not in submitted
    }
    assert not unreached_siblings, (
        f"named as the command line's way to the same records, but no command submits them: {unreached_siblings}"
    )


# -- every pair says what holds the command to its counterpart ---------------------


def test_every_declared_pair_names_a_test_that_exists_or_says_that_none_compares_it() -> None:
    """A proof is a test function that exists in a file that exists; the absence of one is stated with a reason."""
    findings: dict[str, str] = {}
    for name, declared in (
        ("in-process counterparts", IN_PROCESS_COMMAND_COUNTERPARTS),
        ("session and key tools", SESSION_DOOR_COMMAND_TOOLS),
    ):
        for cli_path, pair in declared.items():
            if isinstance(pair.proof, Unproven):
                if not pair.proof.reason.strip():
                    findings[f"{name}: {_spelled(cli_path)}"] = "says no test compares it, and gives no reason"
            elif (finding := proof_finding(pair.proof)) is not None:
                findings[f"{name}: {_spelled(cli_path)}"] = f"proof {pair.proof} {finding}"
    assert not findings, f"pairs whose proof is not a test that exists: {findings}"
    proven = [pair for pair in IN_PROCESS_COMMAND_COUNTERPARTS.values() if isinstance(pair.proof, str)]
    assert proven, "no in-process pair names a test; the proofs have been lost"


def test_a_proof_that_names_no_test_is_found(tmp_path: Path) -> None:
    """A malformed proof, a missing file, a file that is not Python and a test the file lacks are each named."""
    (tmp_path / "test_present.py").write_text(
        "def test_defined():\n    pass\n\nclass TestGrouped:\n    def test_inside(self):\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "test_broken.py").write_text("def test_defined(:\n", encoding="utf-8")

    assert proof_finding("test_present.py::test_defined", root=tmp_path) is None
    assert proof_finding("test_present.py", root=tmp_path) is not None
    assert proof_finding("test_present.py::", root=tmp_path) is not None
    assert proof_finding("test_present.py::test_defined[param]", root=tmp_path) is not None
    assert proof_finding("test_present.py::test_missing", root=tmp_path) is not None
    assert proof_finding("test_present.py::test_inside", root=tmp_path) is not None
    assert proof_finding("test_absent.py::test_defined", root=tmp_path) is not None
    assert proof_finding("test_broken.py::test_defined", root=tmp_path) is not None


def test_the_pairs_no_test_compares_are_listed_and_each_names_a_live_command() -> None:
    """The unproven pairs are data the report reads, and none belongs to a command that left the tree."""
    unproven = unproven_pairs()
    rows = _rows()

    assert {cli_path for cli_path, _reason in unproven} <= set(rows)
    declared = {*IN_PROCESS_COMMAND_COUNTERPARTS, *SESSION_DOOR_COMMAND_TOOLS}
    proven = {
        cli_path
        for cli_path in declared
        if isinstance(
            (IN_PROCESS_COMMAND_COUNTERPARTS.get(cli_path) or SESSION_DOOR_COMMAND_TOOLS[cli_path]).proof, str
        )
    }
    assert {cli_path for cli_path, _reason in unproven} == declared - proven


# -- every operation a command submits or serves can be admitted ---------------------


def test_every_operation_a_command_reaches_has_an_access_resolver_or_is_declared_to_have_none() -> None:
    """The runtime refuses an operation with no resolver for every frontend, so none may pass unnoticed."""
    registry = build_production_operation_registry()
    reached = (
        {row.operation_id for row in _join().operations if row.cli_paths}
        | _paired(EXECUTE_TOOL)
        | set(OPERATIONS_WITHOUT_A_COMMAND)
    )
    without_a_resolver = operations_without_an_access_resolver(registry, reached)

    undeclared = sorted(without_a_resolver - set(OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER))
    stale = sorted(set(OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER) - without_a_resolver)
    assert not undeclared, f"operations the runtime cannot admit, with no reason declared: {undeclared}"
    assert not stale, f"declared as having no access resolver, yet they have one or nothing reaches them: {stale}"
    assert all(reason.strip() for reason in OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER.values())


def test_an_operation_composed_without_an_access_resolver_is_found() -> None:
    """Of an operation with a resolver and one without, only the one the runtime could not admit is named."""
    with_a_resolver = build_auth_read_definition(_unused_port)
    without_a_resolver = build_google_sheets_export_operation_definition()
    registry = OperationRegistry(
        definitions=(with_a_resolver, without_a_resolver),
        public_registrations=(
            build_auth_read_registration(with_a_resolver),
            build_google_sheets_export_operation_registration(without_a_resolver),
        ),
    )

    found = operations_without_an_access_resolver(registry, [AUTH_READ_OPERATION_DEFINITION_ID, "export.google-sheets"])

    assert found == {"export.google-sheets"}
