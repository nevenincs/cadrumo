"""The runtime requests each command sends are read from the handlers' source, beside its operations.

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

from ....application.operator_surface.command_operations import join_command_operations
from ....application.runtime.installation_requests import InstallationAct
from ...tests.source_tree_support import SourceTree
from ._operation_submission_flow_support import SubmissionFlow, Symbol
from .command_operation_derivation import (
    OPERATION_EXCHANGE_MODULE,
    PROFILE_ADMISSION_ACTION,
    CliPath,
    derive_command_runtime_requests,
    derive_live_command_operations,
    derive_live_command_runtime_requests,
    live_command_handlers,
    live_runtime_request_actions,
    main,
    render_command_operation_table,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_request_door_names_every_installation_act_and_no_operation_exchange() -> None:
    actions_by_record = live_runtime_request_actions()

    actions = frozenset[str]().union(*actions_by_record.values())
    assert {act.value for act in InstallationAct} <= actions
    assert {PROFILE_ADMISSION_ACTION, "profile_delete", "password_reset", "session_inventory"} <= actions
    assert not any(action.startswith("operation_") for action in actions)
    assert not any(path == OPERATION_EXCHANGE_MODULE.replace(".", "/") + ".py" for path, _name in actions_by_record)
    assert all(record_actions for record_actions in actions_by_record.values())


def test_every_executable_command_is_read_and_names_only_requests_of_the_door() -> None:
    sent = derive_live_command_runtime_requests()

    assert set(sent) == set(live_command_handlers())
    known = frozenset[str]().union(*live_runtime_request_actions().values())
    unknown = {cli_path: actions - known for cli_path, actions in sent.items() if actions - known}
    assert not unknown


@pytest.mark.parametrize(
    ("cli_path", "expected"),
    [
        pytest.param(("config", "login"), {PROFILE_ADMISSION_ACTION}, id="login"),
        pytest.param(("config", "profile", "delete"), {"profile_delete_prepare", "profile_delete"}, id="delete"),
        pytest.param(("config", "passphrase", "reset"), {"password_reset_prepare", "password_reset"}, id="reset"),
        pytest.param(("config", "profile", "resume"), {"profile_recovery_prepare", "profile_resume"}, id="resume"),
        pytest.param(("config", "profile", "sessions"), {"session_inventory"}, id="sessions"),
        pytest.param(("config", "profile", "automation", "deny"), {"automation_deny"}, id="deny"),
    ],
)
def test_a_command_that_sends_a_runtime_request_is_no_longer_read_as_sending_nothing(
    cli_path: CliPath, expected: set[str]
) -> None:
    assert expected <= derive_live_command_runtime_requests()[cli_path]


def test_the_launcher_and_a_command_that_only_reads_bundled_data_send_no_runtime_request() -> None:
    sent = derive_live_command_runtime_requests()

    assert sent["app", "tui"] == frozenset()
    assert sent[()] == frozenset()


def test_the_rendered_table_can_carry_the_runtime_request_rows_and_the_join_accepts_them() -> None:
    derivation = derive_live_command_operations()
    sent = derive_live_command_runtime_requests()

    plain = render_command_operation_table(derivation)
    carrying = render_command_operation_table(derivation, sent)

    assert carrying.startswith(plain)
    assert "COMMAND_RUNTIME_REQUEST_ROWS" not in plain
    recorded = {
        statement.target.id: ast.literal_eval(statement.value)
        for statement in ast.parse(carrying).body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.value is not None
    }
    request_rows = recorded["COMMAND_RUNTIME_REQUEST_ROWS"]
    assert set(request_rows) == {(cli_path, action) for cli_path, actions in sent.items() for action in actions}
    operation_rows = recorded["COMMAND_OPERATION_ROWS"]
    without_command = recorded["OPERATIONS_WITHOUT_COMMAND"]
    join = join_command_operations(
        operation_rows, operations_without_command=without_command, runtime_request_rows=request_rows
    )
    forward = {(row.cli_path, action) for row in join.commands for action in row.runtime_requests}
    inverse = {(cli_path, row.action) for row in join.runtime_requests for cli_path in row.cli_paths}
    assert forward == inverse == set(request_rows)
    assert {row.cli_path for row in join.commands} == set(sent)


def test_an_unknown_argument_is_refused_before_anything_is_read_or_written() -> None:
    assert main(["--runtime-request"]) == 2


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
"""

_FIXTURE_COMMANDS: Final[str] = """
from ..runtime.records import Session, StorageInventory
from .client import open_client


def run_act(request):
    return request


def inventory():
    return run_act(StorageInventory())


def delete():
    client = open_client()
    client.login()
    client.delete()


def chained():
    open_client().login()


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

    sent = derive_command_runtime_requests(handlers=_FIXTURE_HANDLERS, flow=flow, request_actions=_FIXTURE_ACTIONS)

    assert sent == {
        # A record handed to a shared submitter is named where the command builds it.
        ("inventory",): {"storage_inventory"},
        # A method is followed through the class its receiver is declared to return.
        ("delete",): {"profile_login", "profile_delete"},
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
