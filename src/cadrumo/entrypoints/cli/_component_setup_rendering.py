"""CLI text line for a refusal recovered by setting up a missing component.

A refused feature that needs the browser or the local AI carries a verdict
naming that item's setup action. Text output shows the person what the item's
current row allows, instead of the action's condition and evidence fields: the
exact command the live command tree resolved for the action when the row's
button sets the item up now, or the row's own sentence when it reads blocked.
The row comes from the quick setup status the invocation binds; without a
readable row nothing is offered. JSON output keeps the typed action record.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from ...core.i18n.render import tr
from ...core.json_contract import ResolvedPreconditionAction
from ...core.logging import get_logger

if TYPE_CHECKING:
    from ...application.dependency_contracts import DependencyStatusRow

__all__ = ["SetupStatusRowsReader", "component_setup_lines", "setup_status_source"]

type SetupStatusRowsReader = Callable[[], Sequence[DependencyStatusRow]]
"""Reads every setup item's quick-status row; raises when the status cannot be read."""

_log = get_logger(__name__)


class _OnceReader:
    """One invocation's status, read at most once and only when a setup line needs it."""

    def __init__(self, read: SetupStatusRowsReader) -> None:
        self._read = read
        self._asked = False
        self._rows: tuple[DependencyStatusRow, ...] | None = None

    def rows(self) -> tuple[DependencyStatusRow, ...] | None:
        if not self._asked:
            self._asked = True
            try:
                self._rows = tuple(self._read())
            except Exception:  # an unreadable status offers nothing; it must never break error emit
                _log.debug("cli setup line: setup status could not be read")
        return self._rows


_SETUP_STATUS: ContextVar[_OnceReader | None] = ContextVar("cadrumo_cli_setup_status", default=None)


@contextmanager
def setup_status_source(read: SetupStatusRowsReader) -> Generator[None]:
    """Bind the quick setup status read for the rest of this invocation, unless one is already bound."""
    if _SETUP_STATUS.get() is not None:
        yield
        return
    token = _SETUP_STATUS.set(_OnceReader(read))
    try:
        yield
    finally:
        _SETUP_STATUS.reset(token)


def _setup_target(action: ResolvedPreconditionAction | None) -> tuple[str, str] | None:
    """Return the item and exact command of an action that sets up a missing component.

    Only the recovery action a setup item declares qualifies, and only once the
    live command tree resolved its full path with nothing left to supply, so the
    printed command is the one that runs.
    """
    if action is None or action.action is None or action.action.cli_path is None:
        return None
    arguments = action.action.arguments
    if action.argument_bindings or (arguments is not None and len(arguments) > 0):
        return None
    from ...application.dependency_registry import dependency_item_declarations

    item_id = next(
        (
            declaration.item_id
            for declaration in dependency_item_declarations()
            if declaration.recovery_action_id == action.action.action_id
        ),
        None,
    )
    return None if item_id is None else (item_id, " ".join(action.action.cli_path))


def component_setup_lines(action: ResolvedPreconditionAction | None) -> tuple[str, ...] | None:
    """Return the localized lines for a component setup action, or ``None`` for any other action.

    The setup command is printed only while the item's current row can set it
    up; a blocked row prints its own sentence instead, and an unreadable status
    prints nothing.
    """
    target = _setup_target(action)
    if target is None:
        return None
    item_id, command = target
    reader = _SETUP_STATUS.get()
    rows = None if reader is None else reader.rows()
    row = None if rows is None else next((row for row in rows if row.item_id == item_id), None)
    if row is None:
        return ()
    from ...application.dependency_contracts import DEPENDENCY_SETUP_RECOVERIES

    if row.recovery in DEPENDENCY_SETUP_RECOVERIES:
        return (tr("cli.config.provision.fix", command=command),)
    from ...application.dependency_registry import dependency_item_declarations
    from ...application.dependency_wording import dependency_held_sentence

    declaration = next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)
    return (dependency_held_sentence(row, declaration),)
