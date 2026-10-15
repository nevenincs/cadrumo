"""The connection requests each command sends are read from the handlers' source, beside its operations.

The first half reads the live tree: the request door names the records, the
command graph names the handlers, and the reading joins them. The second half
proves the reading on a small source tree written for the purpose.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from cadrumo.application.operator_surface.command_operations import join_command_operations
from cadrumo.entrypoints.tests.source_tree_support import SourceTree
from cadrumo.tests.inventory import SRC_CADRUMO
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo_client.contracts.installation_requests import InstallationAct
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH
from dev.operation_contract_manifest.command_operation_derivation import (
    CONNECTION_REQUEST_PACKAGE,
    OPERATION_EXCHANGE_MODULE,
    PROFILE_ADMISSION_ACTION,
    SUBMISSION_RECORD,
    CliPath,
    derive_command_connection_requests,
    derive_live_command_connection_requests,
    derive_live_command_operations,
    live_command_handlers,
    live_connection_request_actions,
    main,
    render_command_operation_table,
)
from dev.operation_contract_manifest.submission_flow import SubmissionFlow, Symbol

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _runtime_command_handlers() -> dict[CliPath, Symbol | None]:
    handlers: dict[CliPath, Symbol | None] = {}
    for node in RUNTIME_COMMAND_GRAPH.nodes():
        binding = node.spec.handler
        if binding is None:
            continue
        target = binding.target
        handlers[node.path[1:]] = None if target is None else (target.module.replace(".", "/") + ".py", target.qualname)
    return handlers


def _derive_runtime_command_requests() -> dict[CliPath, frozenset[str]]:
    tree = SourceTree(
        SRC_CADRUMO.parent,
        packages=frozenset({"cadrumo", "cadrumo_client", "cadrumo_runtime"}),
    )
    flow = SubmissionFlow(
        tree,
        scanned=(
            "cadrumo_runtime/commands/",
            "cadrumo_client/commands/",
            "cadrumo_client/transport/",
            CONNECTION_REQUEST_PACKAGE,
        ),
        submission=SUBMISSION_RECORD,
    )
    return derive_command_connection_requests(
        handlers=_runtime_command_handlers(),
        flow=flow,
        request_actions=live_connection_request_actions(),
        request_package=CONNECTION_REQUEST_PACKAGE,
    )


def test_runtime_command_handlers_are_read_from_their_own_graph() -> None:
    sent = _derive_runtime_command_requests()
    handlers = _runtime_command_handlers()
    assert set(sent) == set(handlers)
    known = frozenset[str]().union(*live_connection_request_actions().values())
    assert not {path: actions - known for path, actions in sent.items() if actions - known}


def test_the_request_door_names_every_installation_act_and_no_operation_exchange() -> None:
    actions_by_record = live_connection_request_actions()

    actions = frozenset[str]().union(*actions_by_record.values())
    assert {act.value for act in InstallationAct} <= actions
    assert {PROFILE_ADMISSION_ACTION, "profile_delete", "password_reset", "session_inventory"} <= actions
    assert not any(action.startswith("operation_") for action in actions)
    assert not any(path == OPERATION_EXCHANGE_MODULE.replace(".", "/") + ".py" for path, _name in actions_by_record)
    assert all(record_actions for record_actions in actions_by_record.values())


def test_every_executable_command_is_read_and_names_only_requests_of_the_door() -> None:
    sent = derive_live_command_connection_requests()

    assert set(sent) == set(live_command_handlers())
    known = frozenset[str]().union(*live_connection_request_actions().values())
    unknown = {cli_path: actions - known for cli_path, actions in sent.items() if actions - known}
    assert not unknown


def test_an_aeat_login_sends_its_runtime_admission_request() -> None:
    assert {PROFILE_ADMISSION_ACTION} <= derive_live_command_connection_requests()[("config", "login")]


def test_the_tui_launcher_and_root_send_no_connection_request() -> None:
    sent = derive_live_command_connection_requests()

    assert sent[("app", "tui")] == frozenset()
    assert sent[()] == frozenset()


@pytest.mark.parametrize(
    ("program", "cli_path", "expected"),
    [
        pytest.param(
            CommandProgram.AEAT,
            ("config", "profile", "delete"),
            {"profile_delete_prepare", "profile_delete"},
            id="delete",
        ),
        pytest.param(
            CommandProgram.AUTHENTICATION,
            ("config", "passphrase", "reset"),
            {"password_reset_prepare", "password_reset"},
            id="reset",
        ),
        pytest.param(
            CommandProgram.AUTHENTICATION,
            ("config", "profile", "resume"),
            {"profile_recovery_prepare", "profile_resume"},
            id="resume",
        ),
        pytest.param(
            CommandProgram.AUTHENTICATION,
            ("config", "profile", "sessions"),
            {"session_inventory"},
            id="sessions",
        ),
        pytest.param(
            CommandProgram.AUTHENTICATION,
            ("config", "profile", "automation", "deny"),
            {"automation_deny"},
            id="deny",
        ),
    ],
)
def test_management_command_sends_its_request(program: CommandProgram, cli_path: CliPath, expected: set[str]) -> None:
    sent = (
        derive_live_command_connection_requests()
        if program is CommandProgram.AEAT
        else _derive_runtime_command_requests()
    )
    assert expected <= sent[cli_path]


def test_the_rendered_table_can_carry_the_connection_request_rows_and_the_join_accepts_them() -> None:
    derivation = derive_live_command_operations()
    sent = derive_live_command_connection_requests()

    plain = render_command_operation_table(derivation)
    carrying = render_command_operation_table(derivation, sent)

    assert carrying.startswith(plain)
    assert "COMMAND_CONNECTION_REQUEST_ROWS" not in plain
    recorded = {
        statement.target.id: ast.literal_eval(statement.value)
        for statement in ast.parse(carrying).body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.value is not None
    }
    request_rows = recorded["COMMAND_CONNECTION_REQUEST_ROWS"]
    assert set(request_rows) == {(cli_path, action) for cli_path, actions in sent.items() for action in actions}
    operation_rows = recorded["COMMAND_OPERATION_ROWS"]
    without_command = recorded["OPERATIONS_WITHOUT_COMMAND"]
    join = join_command_operations(
        operation_rows, operations_without_command=without_command, connection_request_rows=request_rows
    )
    forward = {(row.cli_path, action) for row in join.commands for action in row.connection_requests}
    inverse = {(cli_path, row.action) for row in join.connection_requests for cli_path in row.cli_paths}
    assert forward == inverse == set(request_rows)
    assert {row.cli_path for row in join.commands} == set(sent)


def test_an_unknown_argument_is_refused_before_anything_is_read_or_written() -> None:
    assert main(["--connection-request"]) == 2


# -- the reading, proved on a source tree written for the purpose --------------

_FIXTURE_RECORDS: Final[str] = """
class Submit:
    def __init__(self, **fields):
        self.fields = fields


class Login:
    pass


class StorageInventory:
    pass


class ProfileDelete:
    pass


class Session:
    pass


class NeverSent:
    pass


DESCRIBED = (Login, StorageInventory, ProfileDelete, Session, NeverSent)


def described(request):
    return [record for record in DESCRIBED if type(request) is record]
"""

_FIXTURE_CLIENT: Final[str] = """
from ..runtime.records import Login, ProfileDelete


class Client:
    def login(self):
        return Login()

    def delete(self):
        return ProfileDelete()


def open_client() -> Client:
    return Client()


async def open_client_later() -> Client:
    return Client()
"""

_FIXTURE_COMMANDS: Final[str] = """
import asyncio

from ..runtime.records import Session, StorageInventory, described
from .client import open_client, open_client_later


def run_act(request):
    return described(request)


def inventory():
    return run_act(StorageInventory())


def delete():
    client = open_client()
    client.login()
    client.delete()


def chained():
    open_client().login()


def run_to_completion():
    client = asyncio.run(open_client_later())
    client.delete()


def lock(kind):
    return run_act(Session())


def annotated(request: StorageInventory) -> StorageInventory:
    return request


def untyped(client):
    client.delete()


def quiet():
    return 1
"""

_FIXTURE_ACTIONS: Final[Mapping[Symbol, frozenset[str]]] = {
    ("pkg/runtime/records.py", "Login"): frozenset({"profile_login"}),
    ("pkg/runtime/records.py", "StorageInventory"): frozenset({"storage_inventory"}),
    ("pkg/runtime/records.py", "ProfileDelete"): frozenset({"profile_delete"}),
    ("pkg/runtime/records.py", "Session"): frozenset({"session_lock", "session_status"}),
    ("pkg/runtime/records.py", "NeverSent"): frozenset({"never_sent"}),
}

_FIXTURE_HANDLERS: Final[Mapping[CliPath, Symbol | None]] = {
    ("inventory",): ("pkg/cli/commands.py", "inventory"),
    ("delete",): ("pkg/cli/commands.py", "delete"),
    ("chained",): ("pkg/cli/commands.py", "chained"),
    ("run-to-completion",): ("pkg/cli/commands.py", "run_to_completion"),
    ("lock",): ("pkg/cli/commands.py", "lock"),
    ("annotated",): ("pkg/cli/commands.py", "annotated"),
    ("untyped",): ("pkg/cli/commands.py", "untyped"),
    ("quiet",): ("pkg/cli/commands.py", "quiet"),
    ("unavailable",): None,
}


def test_the_reading_names_the_requests_each_handler_reaches(tmp_path: Path) -> None:
    files = {
        "pkg/__init__.py": "",
        "pkg/runtime/__init__.py": "",
        "pkg/runtime/records.py": _FIXTURE_RECORDS,
        "pkg/cli/__init__.py": "",
        "pkg/cli/client.py": _FIXTURE_CLIENT,
        "pkg/cli/commands.py": _FIXTURE_COMMANDS,
    }
    for relative, source in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    flow = SubmissionFlow(
        SourceTree(tmp_path, packages=frozenset({"pkg"})),
        scanned=("pkg/cli/", "pkg/runtime/"),
        submission=("pkg/runtime/records.py", "Submit"),
    )

    sent = derive_command_connection_requests(
        handlers=_FIXTURE_HANDLERS, flow=flow, request_actions=_FIXTURE_ACTIONS, request_package="pkg/runtime/"
    )

    assert sent == {
        # A record handed to a shared submitter is named where the command builds it. The submitter
        # reaches a table of the records' own package that names every record, and that sends none.
        ("inventory",): {"storage_inventory"},
        # A method is followed through the class its receiver is declared to return.
        ("delete",): {"profile_login", "profile_delete"},
        # A receiver that is the result of a coroutine run to completion has the class the coroutine returns.
        ("run-to-completion",): {"profile_delete"},
        # A record with several actions contributes every one of them.
        ("lock",): {"session_lock", "session_status"},
        # Naming a record in an annotation constructs nothing.
        ("annotated",): set(),
        # A receiver the source gives no class for is not followed, whether a parameter or a call.
        ("untyped",): set(),
        ("chained",): set(),
        # Sending nothing is recorded, for an implemented command and an unimplemented one alike.
        ("quiet",): set(),
        ("unavailable",): set(),
    }
