"""Warn, in text and JSON alike, of every statement a calculation left out of the earlier head.

A calculation that carries its own inputs stands in place of what the person
had entered in the earlier head. The served result names each statement it did
not carry; this module turns that list into warning notices and the matching
text lines, built from the same notices so the two cannot drift. The words of
each statement are served by the backend; only the sentence around them is the
CLI's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity

if TYPE_CHECKING:
    from ...application.modelo.work_calculation_contracts import (
        ModeloUnusedHeadStatement,
        ModeloWorkCalculateReplacedHead,
    )


def replaced_head_statement_output(
    replaced_head: ModeloWorkCalculateReplacedHead | None, *, command: str
) -> tuple[list[Notice], list[str]]:
    """Project the statements the calculation did not carry into warning notices and text lines.

    One summary notice names the earlier calculation, which still holds every
    statement, and one notice per statement follows it. Nothing is emitted when
    the calculation replaced no head or left nothing out.
    """
    if replaced_head is None or (not replaced_head.unused_statements and replaced_head.unused_statements_complete):
        return ([], [])
    earlier = replaced_head.calculation_revision_id
    notices: list[Notice] = []
    if replaced_head.unused_statements:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"{command}.statements_not_carried",
                message=tr(
                    "cli.app.modelo.work.statements_not_carried",
                    count=len(replaced_head.unused_statements),
                    revision_id=earlier,
                ),
                context={
                    "replaced_calculation_revision_id": earlier,
                    "count": str(len(replaced_head.unused_statements)),
                },
            )
        )
    if not replaced_head.unused_statements_complete:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"{command}.statements_not_recorded",
                message=tr("cli.app.modelo.work.statements_not_carried_incomplete", revision_id=earlier),
                context={"replaced_calculation_revision_id": earlier},
            )
        )
    notices.extend(_statement_notice(statement, command=command) for statement in replaced_head.unused_statements)
    return (notices, [f"warning\t{notice.message}" for notice in notices])


def _statement_notice(statement: ModeloUnusedHeadStatement, *, command: str) -> Notice:
    """Word one statement the calculation did not carry, naming its box when the form prints one."""
    target = _target_words(statement)
    if target is not None and statement.value is not None:
        message = tr(
            "cli.app.modelo.work.statement_not_carried", words=statement.words, target=target, value=statement.value
        )
    elif target is not None:
        message = tr("cli.app.modelo.work.statement_not_carried_without_value", words=statement.words, target=target)
    else:
        message = tr("cli.app.modelo.work.statement_not_carried_whole", words=statement.words)
    context = {
        "kind": statement.kind.value,
        **({"subject": statement.subject} if statement.subject is not None else {}),
        **({"row_identity": statement.row_identity} if statement.row_identity is not None else {}),
        **({"box": statement.box} if statement.box is not None else {}),
        **({"value": statement.value} if statement.value is not None else {}),
    }
    return Notice(
        severity=NoticeSeverity.WARNING, code=f"{command}.statement_not_carried", message=message, context=context
    )


def _target_words(statement: ModeloUnusedHeadStatement) -> str | None:
    """Name what the statement speaks of: its printed box and label, its label, or its identifier."""
    if statement.box is not None and statement.label is not None:
        return tr("cli.app.modelo.work.statement_target_box", box=statement.box, label=statement.label)
    if statement.label is not None:
        return statement.label
    return statement.subject


__all__ = ["replaced_head_statement_output"]
