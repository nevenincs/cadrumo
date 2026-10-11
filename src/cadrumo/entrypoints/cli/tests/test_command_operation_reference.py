"""The reference an agent reads says, command for command, what the recorded join and the counterparts say.

The reference is a rendering of the recorded join and of the declared
counterparts, shipped with the agent's operating data. It is compared with a
fresh rendering, so a join that moved without it fails here, and it is read
back row by row and compared with the join and the counterparts themselves, so
a rendering that dropped or merged a row fails too.

No count is a pass condition. A command, an operation or a route added to the
join or the counterparts changes the reference and the comparison together.
"""

from __future__ import annotations

import pytest

from ....application.operator_surface.command_operations import join_command_operations
from ..command_specs import COMMAND_GRAPH
from ..operator_surface_reconciliation import recorded_command_operation_join
from .command_frontend_counterparts import CommandReach, ToolRoute, command_reach, other_frontend_routes
from .command_operation_reference import (
    NO_OPERATION,
    REFERENCE_PATH,
    read_command_operation_reference,
    read_command_tool_routes,
    render_command_operation_reference,
    spelled_command,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REGENERATE = "write it again with: python -m cadrumo.entrypoints.cli.tests.command_operation_reference"


def _shipped() -> str:
    return REFERENCE_PATH.read_text(encoding="utf-8")


def test_the_shipped_reference_is_the_rendered_join() -> None:
    """The document in the agent's data is what the recorded join renders to today."""
    assert _shipped() == render_command_operation_reference(recorded_command_operation_join()), (
        f"the shipped reference no longer matches the recorded join; {_REGENERATE}"
    )


def test_each_command_row_lists_exactly_the_operations_the_join_records() -> None:
    """Read back, the reference has one row for every executable command, with that command's operations."""
    join = recorded_command_operation_join()
    commands, unsubmitted = read_command_operation_reference(_shipped())
    recorded = {spelled_command(row.cli_path): row.operation_ids for row in join.commands}
    assert recorded, "the recorded join names no command; the denominator is empty"
    assert commands == recorded, _REGENERATE
    assert unsubmitted == tuple(row.operation_id for row in join.operations if not row.cli_paths), _REGENERATE


def test_each_command_row_lists_exactly_the_other_routes_to_its_work() -> None:
    """Read back, every row names the installation acts, session tools and counterparts of its command."""
    join = recorded_command_operation_join()
    routes = read_command_tool_routes(_shipped())
    expected = {spelled_command(row.cli_path): other_frontend_routes(row) for row in join.commands}
    assert any(expected.values()), "no command has a route besides its operations; the denominator is empty"
    assert routes == expected, _REGENERATE


def test_every_command_with_work_to_share_has_a_tool_named_in_its_row() -> None:
    """An agent finds a tool for every command except the ones that have no work to do for it."""
    join = recorded_command_operation_join()
    commands, _unsubmitted = read_command_operation_reference(_shipped())
    routes = read_command_tool_routes(_shipped())
    without_work = {
        spelled_command(row.cli_path) for row in join.commands if command_reach(row) is CommandReach.NO_WORK_TO_SHARE
    }
    without_a_tool = {command for command in commands if not commands[command] and not routes[command]}
    assert without_a_tool == without_work


def test_a_route_is_read_back_as_its_tool_and_what_the_tool_is_given() -> None:
    """A tool alone, a tool with its selector, and several routes in one row are each read back whole."""
    document = (
        "| `aeat one` | none | `installation` `storage_check` |\n"
        "| `aeat two` | `ledger.list` | `authorization_prepare`; `session` `lock` |\n"
        "| `aeat three` | none | none |\n"
    )

    routes = read_command_tool_routes(document)

    assert routes == {
        "aeat one": (ToolRoute("installation", "storage_check"),),
        "aeat two": (ToolRoute("authorization_prepare"), ToolRoute("session", "lock")),
        "aeat three": (),
    }
    with pytest.raises(ValueError, match="a route names one tool"):
        read_command_tool_routes("| `aeat four` | none | `session` `lock` `again` |\n")


def test_the_reference_names_every_executable_command_of_the_live_graph() -> None:
    """A command a skill can name is a command the reference has a row for."""
    commands, _unsubmitted = read_command_operation_reference(_shipped())
    executable = {spelled_command(node.path[1:]) for node in COMMAND_GRAPH.nodes() if node.spec.handler is not None}
    assert executable, "the live command graph declares no executable command"
    assert set(commands) == executable


def test_a_join_that_moves_changes_the_reference_and_its_reading() -> None:
    """One operation added to one command, and one command gone silent, are both visible in the document."""
    recorded = recorded_command_operation_join()
    busiest = max(recorded.commands, key=lambda row: len(row.operation_ids))
    assert busiest.operation_ids, "no recorded command submits an operation; nothing can go silent"
    silenced = spelled_command(busiest.cli_path)
    rows = [
        (row.cli_path, operation_id)
        for row in recorded.commands
        if row.cli_path != busiest.cli_path
        for operation_id in row.operation_ids or (None,)
    ]
    rows.append((busiest.cli_path, None))
    still_submitted = {operation_id for _cli_path, operation_id in rows if operation_id is not None}
    moved = join_command_operations(
        rows,
        operations_without_command=sorted({row.operation_id for row in recorded.operations} - still_submitted),
    )

    rendered = render_command_operation_reference(moved)

    assert rendered != _shipped()
    commands, unsubmitted = read_command_operation_reference(rendered)
    assert commands[silenced] == ()
    assert f"| `{silenced}` | {NO_OPERATION} | " in rendered
    orphaned = set(busiest.operation_ids) - still_submitted
    assert orphaned <= set(unsubmitted)


def test_a_command_with_two_rows_is_refused_when_the_reference_is_read() -> None:
    """A hand edit that gives one command a second row cannot be read as either."""
    doubled = _shipped() + "| `aeat app ledger add` | `ledger.remove` | none |\n"
    with pytest.raises(ValueError, match="more than one row"):
        read_command_operation_reference(doubled)
