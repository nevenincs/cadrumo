"""The join between executable commands, registered operations, and connection actions.

A command may submit registered operations, but its declaration does not name
which ones. The join records that relation in both directions, preserving the
empty case for commands that submit nothing and operations no command submits.

A command may also send a connection request or installation act without an
operation. Those actions are recorded by command and in reverse, so a command
that sends none is not confused with one whose behavior is unknown.

The relation is an upper bound on one handler’s reachable code. It lists every
operation and connection action any mode can send; a group row describes its
own callback. Admission remains the connected service’s decision.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from .errors import OperatorSurfaceContractError

_SURFACE = "command_operations"

#: ``defer_build`` keeps these records out of the import cost every process
#: pays: only the surface manifest validates them, on its first use.
_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid", defer_build=True)


class CommandOperations(BaseModel):
    """The registered operations one executable command can submit.

    ``cli_path`` is the command's operator path without the executable's own
    name, so the root callback has the empty path.
    """

    model_config = _FROZEN

    cli_path: tuple[str, ...]
    operation_ids: tuple[str, ...] = ()
    connection_requests: tuple[str, ...] = ()
    """The actions of the connection requests and installation acts the command can send."""


class OperationCommands(BaseModel):
    """The executable commands that can submit one registered operation."""

    model_config = _FROZEN

    operation_id: str = Field(min_length=1)
    cli_paths: tuple[tuple[str, ...], ...] = ()


class ConnectionRequestCommands(BaseModel):
    """The executable commands that can send one connection request or installation act."""

    model_config = _FROZEN

    action: str = Field(min_length=1)
    cli_paths: tuple[tuple[str, ...], ...] = ()


class CommandOperationJoin(BaseModel):
    """Every executable command with what it sends, and every operation and request with its commands."""

    model_config = _FROZEN

    commands: tuple[CommandOperations, ...]
    operations: tuple[OperationCommands, ...]
    connection_requests: tuple[ConnectionRequestCommands, ...] = ()


def join_command_operations(
    rows: Iterable[tuple[tuple[str, ...], str | None]],
    *,
    operations_without_command: Iterable[str],
    connection_request_rows: Iterable[tuple[tuple[str, ...], str]] = (),
) -> CommandOperationJoin:
    """Build both directions of the join from its recorded rows.

    Args:
        rows: One row for each command and operation it can submit. A command
            that submits nothing has exactly one row, whose operation is
            ``None``.
        operations_without_command: Every registered operation no command
            submits.
        connection_request_rows: One row for each command and connection request or
            installation act it can send, named by the request's action. A
            command that sends none has no row here.

    Returns:
        The join, with commands ordered by path, operations by id and connection
        connection requests by action.

    Raises:
        OperatorSurfaceContractError: A row repeats, a path, an id or an action
            is blank, a command is recorded both as submitting nothing and as
            submitting an operation, an operation is recorded both ways, or a
            connection request names a command ``rows`` does not.
    """
    diagnostics: list[str] = []
    by_command: dict[tuple[str, ...], set[str]] = {}
    silent: set[tuple[str, ...]] = set()
    seen: set[tuple[tuple[str, ...], str | None]] = set()
    for row in rows:
        cli_path, operation_id = row
        spelled = " ".join(cli_path)
        if row in seen:
            diagnostics.append(f"row repeats: {spelled!r} -> {operation_id!r}")
        seen.add(row)
        if any(not token.strip() for token in cli_path):
            diagnostics.append(f"command path has a blank token: {cli_path!r}")
        submitted = by_command.setdefault(cli_path, set())
        if operation_id is None:
            silent.add(cli_path)
        elif not operation_id.strip():
            diagnostics.append(f"command names a blank operation: {spelled!r}")
        else:
            submitted.add(operation_id)
    diagnostics.extend(
        f"command is recorded both as submitting nothing and as submitting an operation: {' '.join(cli_path)!r}"
        for cli_path in sorted(silent)
        if by_command[cli_path]
    )

    by_operation: dict[str, list[tuple[str, ...]]] = {}
    for cli_path in sorted(by_command):
        for operation_id in by_command[cli_path]:
            by_operation.setdefault(operation_id, []).append(cli_path)
    submitted_operations = frozenset(by_operation)
    for operation_id in operations_without_command:
        if not operation_id.strip():
            diagnostics.append("an operation without a command has a blank id")
        elif operation_id in submitted_operations:
            diagnostics.append(f"operation is recorded both with and without a command: {operation_id!r}")
        elif operation_id in by_operation:
            diagnostics.append(f"operation without a command repeats: {operation_id!r}")
        else:
            by_operation[operation_id] = []

    connection_requests_by_command: dict[tuple[str, ...], set[str]] = {}
    seen_connection_requests: set[tuple[tuple[str, ...], str]] = set()
    for connection_request_row in connection_request_rows:
        cli_path, action = connection_request_row
        spelled = " ".join(cli_path)
        if connection_request_row in seen_connection_requests:
            diagnostics.append(f"connection request row repeats: {spelled!r} -> {action!r}")
        seen_connection_requests.add(connection_request_row)
        if not action.strip():
            diagnostics.append(f"command names a blank connection request: {spelled!r}")
        elif cli_path not in by_command:
            diagnostics.append(f"connection request names a command with no operation row: {spelled!r} -> {action!r}")
        else:
            connection_requests_by_command.setdefault(cli_path, set()).add(action)
    by_connection_request: dict[str, list[tuple[str, ...]]] = {}
    for cli_path in sorted(connection_requests_by_command):
        for action in connection_requests_by_command[cli_path]:
            by_connection_request.setdefault(action, []).append(cli_path)

    if diagnostics:
        raise OperatorSurfaceContractError(_SURFACE, reason="; ".join(diagnostics))
    return CommandOperationJoin(
        commands=tuple(
            CommandOperations(
                cli_path=cli_path,
                operation_ids=tuple(sorted(by_command[cli_path])),
                connection_requests=tuple(sorted(connection_requests_by_command.get(cli_path, ()))),
            )
            for cli_path in sorted(by_command)
        ),
        operations=tuple(
            OperationCommands(operation_id=operation_id, cli_paths=tuple(by_operation[operation_id]))
            for operation_id in sorted(by_operation)
        ),
        connection_requests=tuple(
            ConnectionRequestCommands(action=action, cli_paths=tuple(by_connection_request[action]))
            for action in sorted(by_connection_request)
        ),
    )


__all__ = [
    "CommandOperationJoin",
    "CommandOperations",
    "ConnectionRequestCommands",
    "OperationCommands",
    "join_command_operations",
]
