"""The command lines that say, through the installed CLI, what the table states about a return.

The table states a return's facts by submitting registered operations in process (the declaration's form read, the
edit check and the guarded edit). Each statement has a command that submits those same operations, so the CLI column
states the same facts through that command. This module is the whole mapping and is pure: it builds the arguments of
one command from one statement, reads no product code and sends nothing. A statement the table makes that no command
says the same way is named here, so the return is reported as not driven rather than seeded behind the CLI.

No statement carries a secret: every operand is a binding, a casilla, a family token or an amount, and the profile
passphrase travels only on the runner's standard input.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .world_report import Statement, StatementKind

FORM_OPERATION: Final = "modelo.work.form"
PREFLIGHT_OPERATION: Final = "modelo.edit.preflight"
EFFECT_OPERATION: Final = "modelo.edit.apply"
"""The registered operation that records a statement; the one a missing command is reported by."""
_ENTRY_LANGUAGE: Final = ("--output-language", "en")
"""A value is read through the declaration's own grammar in the language named, so amounts are written as English."""
_WORK: Final = ("app", "modelo", "work")

TABLE_OPERATIONS: Final[Mapping[StatementKind, tuple[str, ...]]] = {
    StatementKind.PRIOR_CARRIES: (FORM_OPERATION, PREFLIGHT_OPERATION, EFFECT_OPERATION),
    StatementKind.PRIOR_VALUE: (FORM_OPERATION, EFFECT_OPERATION),
    StatementKind.WORK_INPUT: (FORM_OPERATION, EFFECT_OPERATION),
    StatementKind.WORK_INCOME_NONE: (FORM_OPERATION, EFFECT_OPERATION),
    StatementKind.RENTAL_CARRY: (FORM_OPERATION, PREFLIGHT_OPERATION, EFFECT_OPERATION),
}
"""The registered operations the table submits to make each kind of statement."""


@dataclass(frozen=True, slots=True)
class Door:
    """The command that makes one kind of statement."""

    path: tuple[str, ...]
    required: bool
    """Whether the application's refusal ends the return, as the table lets it; else the statement is optional.

    The table makes an optional statement only where the form offers it (a figure whose earlier return the profile
    holds is left to that return, a carry nothing is open for, a work-income statement the return does not rest on).
    The command asks the application to check the same offer, and its refusal is that same absence of the offer.
    """


DOORS: Final[Mapping[StatementKind, Door]] = {
    StatementKind.PRIOR_CARRIES: Door((*_WORK, "attest-prior-carries"), required=False),
    StatementKind.PRIOR_VALUE: Door((*_WORK, "attest-prior-value"), required=False),
    StatementKind.WORK_INPUT: Door((*_WORK, "set-value"), required=True),
    StatementKind.WORK_INCOME_NONE: Door((*_WORK, "attest-work-income"), required=False),
    StatementKind.RENTAL_CARRY: Door((*_WORK, "attest-no-amount"), required=True),
}


def _carries(statement: Statement, work_unit_id: str) -> tuple[list[str], list[str]]:
    options = [token for family in statement.families for token in ("--family", family)]
    options += [token for box, amount in statement.amounts for token in ("--amount", f"{box}={amount}")]
    return options, [work_unit_id]


def _on_target(statement: Statement, work_unit_id: str) -> tuple[list[str], list[str]]:
    row = [] if statement.row is None else ["--row", statement.row]
    return row, [work_unit_id, statement.target]


def _with_value(statement: Statement, work_unit_id: str) -> tuple[list[str], list[str]]:
    options, operands = _on_target(statement, work_unit_id)
    return options, [*operands, statement.value]


def _alone(_statement: Statement, work_unit_id: str) -> tuple[list[str], list[str]]:
    return [], [work_unit_id]


_OPERANDS: Final[Mapping[StatementKind, Callable[[Statement, str], tuple[list[str], list[str]]]]] = {
    StatementKind.PRIOR_CARRIES: _carries,
    StatementKind.PRIOR_VALUE: _with_value,
    StatementKind.WORK_INPUT: _with_value,
    StatementKind.WORK_INCOME_NONE: _alone,
    StatementKind.RENTAL_CARRY: _on_target,
}


def statement_args(statement: Statement, work_unit_id: str, doors: Mapping[StatementKind, Door] = DOORS) -> list[str]:
    """The ``aeat`` arguments that make ``statement`` on the work unit ``work_unit_id``, confirmed with ``--yes``.

    A negative amount is a positive operand only after ``--``, so the operands follow it then.
    """
    options, operands = _OPERANDS[statement.kind](statement, work_unit_id)
    separator = ["--"] if any(operand.startswith("-") for operand in operands) else []
    return [*doors[statement.kind].path, "--yes", *_ENTRY_LANGUAGE, *options, *separator, *operands]


def statement_gap(statements: Sequence[Statement], doors: Mapping[StatementKind, Door] = DOORS) -> str | None:
    """Why the statements cannot all be made through the CLI, or ``None`` when every one has a command that says it."""
    for statement in statements:
        if statement.kind not in doors:
            return f"no CLI door for {EFFECT_OPERATION} ({statement.kind.value})"
        if statement.gap is not None:
            return f"no CLI door for {EFFECT_OPERATION} ({statement.kind.value}: {statement.gap})"
    return None
