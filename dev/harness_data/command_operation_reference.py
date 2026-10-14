"""Render, read and publish the agent's reference to the current tax CLI.

Run the owning publisher after the recorded join or declared routes change::

    python -m dev.harness_data.command_operation_reference

The pure readers describe the generated document; they do not scan source or
create a validation gate. MCP-aware rendering belongs to this developer host.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.application.operator_surface.command_operations import CommandOperationJoin
from cadrumo.entrypoints.cli.operator_surface_reconciliation import recorded_command_operation_join
from dev._paths import REPO_ROOT

from .command_frontend_counterparts import ToolRoute, is_person_act, other_frontend_routes

REFERENCE_PATH: Final[Path] = (
    REPO_ROOT / "src" / "cadrumo_harness" / "_data" / "agent" / "reference" / "command-operations.md"
)

EXECUTABLE_NAME: Final[str] = "aeat"
"""The executable's own name, which the skills write before every command path."""

NO_OPERATION: Final[str] = "none"
"""What the operations column says for a command that submits nothing."""

NO_ROUTE: Final[str] = "none"
"""What the routes column says for a command whose work no other tool does."""

PERSON_ROUTE: Final[str] = "the person's act"
"""What the routes column says for a command whose work is the person's own act, which no tool does for you."""

_ROUTE_SEPARATOR: Final[str] = "; "

_HEADER: Final[str] = """# Commands and the tools that do their work

Generated from the record the command line publishes of its own commands, the
registered operations each one can submit, the connection requests each one
sends, and what serves the work a command does in its own process. Do not edit
it by hand.

A workflow skill names commands. Through MCP you do a command's work with the
tools its row names, so look the command up here as the skill spells it,
without its options and arguments.

- The second column lists every operation any mode of the command can submit,
  and you run one with `execute`. A command with one operation runs that
  operation. A command with several runs the one whose contract fits the step,
  and often a read first: the operation that resolves the identifier the write
  then takes.
- The third column lists every other route to the command's work: a tool, and
  after it the operation or query the tool is given. `execute` with an
  operation there means the command does that work in its own process and the
  operation does the same work for you. `authority` takes the name shown as its
  `query`. A tool shown alone takes no such name.
- `the person's act` in the third column means the command's work is the
  person's own: signing in or out, profile creation, locking, sessions, keys, passwords and other
  secrets, recovery, and work outside this profile such as the profile list,
  storage, repair and resetting every profile. You cannot do it. Ask the person
  to do it in Cadrumo. An operation listed beside it that needs a secret, or
  that administers keys, is refused to you as the person's act too. For a command
  with both a registered-operation mode and a sessionless file mode, this label
  covers the latter; the operation's own contract decides its admission.
- `none` in both columns means the command has no work to do for you: it
  prints help. A missing declaration is not rendered as an empty route.
- A command's options are not the operation's fields. Read the operation's
  input schema with `describe` and fill it from the same facts the options
  carry.

## Commands

| Command | Operations it can submit | Other routes to its work |
| --- | --- | --- |
"""

_UNSUBMITTED_HEADER: Final[str] = """
## Operations no command submits

These are registered operations too, and `search` finds them. No command
submits them. One that does the work a command does in its own process is
named in that command's row above.

"""

_COMMAND_ROW: Final[re.Pattern[str]] = re.compile(
    r"^\| `(?P<command>[^`]+)` \| (?P<operations>[^|]+) \| (?P<routes>[^|]+) \|$"
)
_UNSUBMITTED_ROW: Final[re.Pattern[str]] = re.compile(r"^- `(?P<operation>[^`]+)`$")
_OPERATION: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")


def spelled_command(cli_path: tuple[str, ...]) -> str:
    """Spell one command the way a skill writes it: the executable's name, then the path."""
    return " ".join((EXECUTABLE_NAME, *cli_path))


def spelled_route(route: ToolRoute) -> str:
    """Spell one route as its tool and, when the tool is given one, what it is given."""
    return f"`{route.tool}`" if route.selector is None else f"`{route.tool}` `{route.selector}`"


def render_command_operation_reference(join: CommandOperationJoin) -> str:
    """Render the join as the reference document, one row for every executable command."""
    contracts = load_operation_contract_manifest().contract_set.definitions
    secret_operations = frozenset(
        contract.definition_id for contract in contracts if contract.ephemeral_secret_required
    )
    lines = [_HEADER]
    for row in join.commands:
        operations = ", ".join(f"`{operation_id}`" for operation_id in row.operation_ids) or NO_OPERATION
        routes = (
            PERSON_ROUTE
            if is_person_act(row, secret_operations=secret_operations)
            else _ROUTE_SEPARATOR.join(spelled_route(route) for route in other_frontend_routes(row)) or NO_ROUTE
        )
        lines.append(f"| `{spelled_command(row.cli_path)}` | {operations} | {routes} |\n")
    lines.append(_UNSUBMITTED_HEADER)
    lines.extend(f"- `{row.operation_id}`\n" for row in join.operations if not row.cli_paths)
    return "".join(lines)


def _read_route(spelled: str) -> ToolRoute:
    named = _OPERATION.findall(spelled)
    if not named or len(named) > 2:
        raise ValueError(f"a route names one tool and at most one thing it is given: {spelled!r}")
    return ToolRoute(named[0], named[1] if len(named) == 2 else None)


def read_command_operation_reference(text: str) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    """Read a reference document back as its rows.

    Returns:
        Each spelled command with the operations its row lists, and the
        operations listed as submitted by no command.

    Raises:
        ValueError: A command has more than one row.
    """
    commands: dict[str, tuple[str, ...]] = {}
    unsubmitted: list[str] = []
    for line in text.splitlines():
        command_row = _COMMAND_ROW.match(line)
        if command_row is not None:
            command = command_row["command"]
            if command in commands:
                raise ValueError(f"command has more than one row: {command!r}")
            listed = command_row["operations"]
            commands[command] = () if listed == NO_OPERATION else tuple(_OPERATION.findall(listed))
            continue
        unsubmitted_row = _UNSUBMITTED_ROW.match(line)
        if unsubmitted_row is not None:
            unsubmitted.append(unsubmitted_row["operation"])
    return commands, tuple(unsubmitted)


def read_command_tool_routes(text: str) -> dict[str, tuple[ToolRoute, ...]]:
    """Read back, for each spelled command of a reference document, the other routes its row lists.

    Raises:
        ValueError: A command has more than one row, or a route cannot be read.
    """
    routes: dict[str, tuple[ToolRoute, ...]] = {}
    for line in text.splitlines():
        command_row = _COMMAND_ROW.match(line)
        if command_row is None:
            continue
        command = command_row["command"]
        if command in routes:
            raise ValueError(f"command has more than one row: {command!r}")
        routed = command_row["routes"]
        routes[command] = (
            ()
            if routed in {NO_ROUTE, PERSON_ROUTE}
            else tuple(_read_route(item) for item in routed.split(_ROUTE_SEPARATOR))
        )
    return routes


def read_person_act_commands(text: str) -> frozenset[str]:
    """Read back the spelled commands whose row says their work is the person's own act."""
    commands: set[str] = set()
    for line in text.splitlines():
        command_row = _COMMAND_ROW.match(line)
        if command_row is not None and command_row["routes"] == PERSON_ROUTE:
            commands.add(str(command_row["command"]))
    return frozenset(commands)


def main() -> int:
    """Publish the reference from the current tax join and declared MCP counterparts."""
    join = recorded_command_operation_join()
    text = render_command_operation_reference(join)
    REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_PATH.write_text(text, encoding="utf-8", newline="\n")
    routes = read_command_tool_routes(text)
    authority = sum(any(route.tool == "authority" for route in row) for row in routes.values())
    in_process = sum(any(route.tool == "execute" for route in row) for row in routes.values())
    person = len(read_person_act_commands(text))
    submitted = sum(bool(row.operation_ids) for row in join.commands)
    print(
        f"wrote {REFERENCE_PATH} ({len(join.commands)} commands; {submitted} submitted-operation rows; "
        f"{authority} authority counterparts; {in_process} in-process execute counterparts; {person} person commands)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
