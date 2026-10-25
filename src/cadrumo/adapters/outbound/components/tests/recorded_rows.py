"""Setup status rows as the components role reports them, for tests of the surfaces that render them.

A surface reads every row through the client's protocol decoder. These rows
come the same way: decoded from the recorded output of the real role, or built
by the client for a build without the role, so a surface test reads exactly
what the surface would.
"""

from __future__ import annotations

from cadrumo.tests.components_role_replay import transcript_lines

from .....application.dependency_contracts import DependencyStatusRow
from ..client import ComponentsRequest, not_in_this_build_result
from ..protocol import ComponentsCommand, ComponentsResultLine, decode_components_line

__all__ = ["not_in_this_build_row", "recorded_absent_row"]


def recorded_absent_row(item_id: str) -> DependencyStatusRow:
    """The quick-status row the real role reported for ``item_id`` on a root without it, with its setup button."""
    (result,) = (
        line
        for line in map(decode_components_line, transcript_lines("status_quick"))
        if isinstance(line, ComponentsResultLine)
    )
    return next(row.status_row() for row in result.rows if row.item_id == item_id)


def not_in_this_build_row(item_id: str) -> DependencyStatusRow:
    """The quick-status row every Python surface reads for ``item_id`` in a build without the role."""
    result = not_in_this_build_result(ComponentsRequest(ComponentsCommand.STATUS))
    return next(row.status_row() for row in result.rows if row.item_id == item_id)
