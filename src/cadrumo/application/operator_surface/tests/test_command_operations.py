"""Contract tests for the join between executable commands and the operations they submit."""

from __future__ import annotations

import pytest

from ..command_operations import (
    CommandOperations,
    ConnectionRequestCommands,
    OperationCommands,
    join_command_operations,
)
from ..errors import OperatorSurfaceContractError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_join_carries_both_directions_and_keeps_their_empty_cases() -> None:
    join = join_command_operations(
        (
            (("app", "ledger", "split"), "ledger.split.review"),
            (("app", "ledger", "split"), "ledger.split.manual"),
            (("app", "ledger", "review"), "ledger.split.review"),
            (("config", "storage", "view"), None),
            ((), None),
        ),
        operations_without_command=("modelo.work.form",),
    )

    assert join.commands == (
        CommandOperations(cli_path=()),
        CommandOperations(cli_path=("app", "ledger", "review"), operation_ids=("ledger.split.review",)),
        CommandOperations(
            cli_path=("app", "ledger", "split"), operation_ids=("ledger.split.manual", "ledger.split.review")
        ),
        CommandOperations(cli_path=("config", "storage", "view")),
    )
    assert join.operations == (
        OperationCommands(operation_id="ledger.split.manual", cli_paths=(("app", "ledger", "split"),)),
        OperationCommands(
            operation_id="ledger.split.review", cli_paths=(("app", "ledger", "review"), ("app", "ledger", "split"))
        ),
        OperationCommands(operation_id="modelo.work.form"),
    )


def test_the_join_serializes_to_plain_json_values() -> None:
    join = join_command_operations(((("app", "ledger", "add"), "ledger.add"),), operations_without_command=())

    assert join.model_dump(mode="json") == {
        "commands": [
            {"cli_path": ["app", "ledger", "add"], "operation_ids": ["ledger.add"], "connection_requests": []}
        ],
        "operations": [{"operation_id": "ledger.add", "cli_paths": [["app", "ledger", "add"]]}],
        "connection_requests": [],
    }


def test_the_join_names_the_connection_requests_a_command_sends_in_both_directions() -> None:
    join = join_command_operations(
        (
            (("config", "storage", "view"), None),
            (("config", "storage", "list"), None),
            (("config", "profile", "delete"), None),
            (("app", "ledger", "add"), "ledger.add"),
        ),
        operations_without_command=(),
        connection_request_rows=(
            (("config", "storage", "view"), "storage_inventory"),
            (("config", "storage", "list"), "storage_inventory"),
            (("config", "profile", "delete"), "profile_delete_prepare"),
            (("config", "profile", "delete"), "profile_delete"),
        ),
    )

    assert join.commands == (
        CommandOperations(cli_path=("app", "ledger", "add"), operation_ids=("ledger.add",)),
        CommandOperations(
            cli_path=("config", "profile", "delete"), connection_requests=("profile_delete", "profile_delete_prepare")
        ),
        CommandOperations(cli_path=("config", "storage", "list"), connection_requests=("storage_inventory",)),
        CommandOperations(cli_path=("config", "storage", "view"), connection_requests=("storage_inventory",)),
    )
    assert join.connection_requests == (
        ConnectionRequestCommands(action="profile_delete", cli_paths=(("config", "profile", "delete"),)),
        ConnectionRequestCommands(action="profile_delete_prepare", cli_paths=(("config", "profile", "delete"),)),
        ConnectionRequestCommands(
            action="storage_inventory", cli_paths=(("config", "storage", "list"), ("config", "storage", "view"))
        ),
    )
    forward = {(row.cli_path, action) for row in join.commands for action in row.connection_requests}
    inverse = {(cli_path, row.action) for row in join.connection_requests for cli_path in row.cli_paths}
    assert forward == inverse


@pytest.mark.parametrize(
    ("request_rows", "reason"),
    [
        pytest.param(
            (
                (("config", "storage", "view"), "storage_inventory"),
                (("config", "storage", "view"), "storage_inventory"),
            ),
            "connection request row repeats: 'config storage view' -> 'storage_inventory'",
            id="repeated-row",
        ),
        pytest.param(
            ((("config", "storage", "view"), " "),),
            "command names a blank connection request: 'config storage view'",
            id="blank-action",
        ),
        pytest.param(
            ((("config", "storage", "check"), "storage_check"),),
            "connection request names a command with no operation row: 'config storage check' -> 'storage_check'",
            id="command-the-rows-do-not-name",
        ),
    ],
)
def test_the_join_refuses_connection_request_rows_it_cannot_place(
    request_rows: tuple[tuple[tuple[str, ...], str], ...], reason: str
) -> None:
    with pytest.raises(OperatorSurfaceContractError) as refused:
        join_command_operations(
            ((("config", "storage", "view"), None),),
            operations_without_command=(),
            connection_request_rows=request_rows,
        )

    assert refused.value.surface == "command_operations"
    assert reason in refused.value.reason


@pytest.mark.parametrize(
    ("rows", "without_command", "reason"),
    [
        pytest.param(
            ((("app", "ledger", "add"), "ledger.add"), (("app", "ledger", "add"), "ledger.add")),
            (),
            "row repeats: 'app ledger add' -> 'ledger.add'",
            id="repeated-row",
        ),
        pytest.param(
            ((("app", "ledger", "add"), "ledger.add"), (("app", "ledger", "add"), None)),
            (),
            "command is recorded both as submitting nothing and as submitting an operation: 'app ledger add'",
            id="silent-and-submitting",
        ),
        pytest.param(
            ((("app", " ", "add"), "ledger.add"),),
            (),
            "command path has a blank token",
            id="blank-path-token",
        ),
        pytest.param(
            ((("app", "ledger", "add"), " "),),
            (),
            "command names a blank operation: 'app ledger add'",
            id="blank-operation",
        ),
        pytest.param(
            ((("app", "ledger", "add"), "ledger.add"),),
            ("ledger.add",),
            "operation is recorded both with and without a command: 'ledger.add'",
            id="operation-recorded-both-ways",
        ),
        pytest.param(
            (),
            ("modelo.work.form", "modelo.work.form"),
            "operation without a command repeats: 'modelo.work.form'",
            id="repeated-operation-without-command",
        ),
    ],
)
def test_the_join_refuses_rows_that_contradict_each_other(
    rows: tuple[tuple[tuple[str, ...], str | None], ...], without_command: tuple[str, ...], reason: str
) -> None:
    with pytest.raises(OperatorSurfaceContractError) as refused:
        join_command_operations(rows, operations_without_command=without_command)

    assert refused.value.surface == "command_operations"
    assert reason in refused.value.reason
