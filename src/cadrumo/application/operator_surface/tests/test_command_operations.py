"""Contract tests for the join between executable commands and the operations they submit."""

from __future__ import annotations

import pytest

from ..command_operations import (
    CommandOperations,
    OperationCommands,
    RuntimeRequestCommands,
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
        "commands": [{"cli_path": ["app", "ledger", "add"], "operation_ids": ["ledger.add"], "runtime_requests": []}],
        "operations": [{"operation_id": "ledger.add", "cli_paths": [["app", "ledger", "add"]]}],
        "runtime_requests": [],
    }


def test_the_join_names_the_runtime_requests_a_command_sends_in_both_directions() -> None:
    join = join_command_operations(
        (
            (("config", "storage", "view"), None),
            (("config", "storage", "list"), None),
            (("config", "profile", "delete"), None),
            (("app", "ledger", "add"), "ledger.add"),
        ),
        operations_without_command=(),
        runtime_request_rows=(
            (("config", "storage", "view"), "storage_inventory"),
            (("config", "storage", "list"), "storage_inventory"),
            (("config", "profile", "delete"), "profile_delete_prepare"),
            (("config", "profile", "delete"), "profile_delete"),
        ),
    )

    assert join.commands == (
        CommandOperations(cli_path=("app", "ledger", "add"), operation_ids=("ledger.add",)),
        CommandOperations(
            cli_path=("config", "profile", "delete"), runtime_requests=("profile_delete", "profile_delete_prepare")
        ),
        CommandOperations(cli_path=("config", "storage", "list"), runtime_requests=("storage_inventory",)),
        CommandOperations(cli_path=("config", "storage", "view"), runtime_requests=("storage_inventory",)),
    )
    assert join.runtime_requests == (
        RuntimeRequestCommands(action="profile_delete", cli_paths=(("config", "profile", "delete"),)),
        RuntimeRequestCommands(action="profile_delete_prepare", cli_paths=(("config", "profile", "delete"),)),
        RuntimeRequestCommands(
            action="storage_inventory", cli_paths=(("config", "storage", "list"), ("config", "storage", "view"))
        ),
    )
    forward = {(row.cli_path, action) for row in join.commands for action in row.runtime_requests}
    inverse = {(cli_path, row.action) for row in join.runtime_requests for cli_path in row.cli_paths}
    assert forward == inverse


@pytest.mark.parametrize(
    ("request_rows", "reason"),
    [
        pytest.param(
            (
                (("config", "storage", "view"), "storage_inventory"),
                (("config", "storage", "view"), "storage_inventory"),
            ),
            "runtime request row repeats: 'config storage view' -> 'storage_inventory'",
            id="repeated-row",
        ),
        pytest.param(
            ((("config", "storage", "view"), " "),),
            "command names a blank runtime request: 'config storage view'",
            id="blank-action",
        ),
        pytest.param(
            ((("config", "storage", "check"), "storage_check"),),
            "runtime request names a command with no operation row: 'config storage check' -> 'storage_check'",
            id="command-the-rows-do-not-name",
        ),
    ],
)
def test_the_join_refuses_runtime_request_rows_it_cannot_place(
    request_rows: tuple[tuple[tuple[str, ...], str], ...], reason: str
) -> None:
    with pytest.raises(OperatorSurfaceContractError) as refused:
        join_command_operations(
            ((("config", "storage", "view"), None),), operations_without_command=(), runtime_request_rows=request_rows
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
