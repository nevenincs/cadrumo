"""The join between executable commands and the registered operations they submit.

A command reaches the runtime by submitting registered operations, and nothing
in a command's declaration says which. This record carries that relation in
both directions for a consumer in another composition root: for each command,
the operations its handler can submit, and for each registered operation, the
commands that submit it. Both directions keep their empty cases. A command that
submits nothing and an operation no command submits are recorded facts, not
absences.

The relation is an upper bound on one handler's own code. It lists every
operation any mode of the command can reach, and a group's row describes the
group's own callback, not the commands below it. Whether an operation is then
admitted is the runtime's decision, made at submission, and this record says
nothing about it.
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


class OperationCommands(BaseModel):
    """The executable commands that can submit one registered operation."""

    model_config = _FROZEN

    operation_id: str = Field(min_length=1)
    cli_paths: tuple[tuple[str, ...], ...] = ()


class CommandOperationJoin(BaseModel):
    """Every executable command with its operations, and every registered operation with its commands."""

    model_config = _FROZEN

    commands: tuple[CommandOperations, ...]
    operations: tuple[OperationCommands, ...]


def join_command_operations(
    rows: Iterable[tuple[tuple[str, ...], str | None]],
    *,
    operations_without_command: Iterable[str],
) -> CommandOperationJoin:
    """Build both directions of the join from its recorded rows.

    Args:
        rows: One row for each command and operation it can submit. A command
            that submits nothing has exactly one row, whose operation is
            ``None``.
        operations_without_command: Every registered operation no command
            submits.

    Returns:
        The join, with commands ordered by path and operations by id.

    Raises:
        OperatorSurfaceContractError: A row repeats, a path or an id is blank,
            a command is recorded both as submitting nothing and as submitting
            an operation, or an operation is recorded both ways.
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

    if diagnostics:
        raise OperatorSurfaceContractError(_SURFACE, reason="; ".join(diagnostics))
    return CommandOperationJoin(
        commands=tuple(
            CommandOperations(cli_path=cli_path, operation_ids=tuple(sorted(by_command[cli_path])))
            for cli_path in sorted(by_command)
        ),
        operations=tuple(
            OperationCommands(operation_id=operation_id, cli_paths=tuple(by_operation[operation_id]))
            for operation_id in sorted(by_operation)
        ),
    )


__all__ = ["CommandOperationJoin", "CommandOperations", "OperationCommands", "join_command_operations"]
