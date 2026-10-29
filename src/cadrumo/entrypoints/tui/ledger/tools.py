"""Screens a Ledger area offers beyond its own body, attached as named tools.

An area body shows the area's main work; a tool is a further screen reached
from it, such as account setup from the overview or a rule editor from
classification. Tools are given to the workspace from outside, so a domain can
add one without editing the area screens or the workspace's injection.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ....application.ledger.workspace import LedgerWorkspaceArea

if TYPE_CHECKING:
    from .controller import LedgerWorkspaceController
    from .workspace_screen import LedgerWorkspaceScreen

_KEY_PATTERN: Final = re.compile(r"ledger\.tool\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


@dataclass(frozen=True, slots=True)
class LedgerToolV1:
    """One further screen an area offers, named in the operator's language."""

    key: str
    """Stable identity, ``ledger.tool.<domain>.<name>``; unique within one workspace."""
    label_key: str
    """Locale key of the name the area lists the tool under."""
    area: LedgerWorkspaceArea
    """The area that lists the tool and that Back returns to."""
    build: Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]
    """Build the tool's screen over the workspace as it stands when chosen."""

    def __post_init__(self) -> None:
        """Refuse a key outside the tool namespace or an empty label key."""
        if _KEY_PATTERN.fullmatch(self.key) is None:
            raise ValueError("a Ledger tool key must read ledger.tool.<domain>.<name>")
        if not self.label_key:
            raise ValueError("a Ledger tool needs a label key")


def require_unique_tool_keys(tools: tuple[LedgerToolV1, ...]) -> None:
    """Refuse two tools that share a key, which would make a selection ambiguous."""
    keys = [tool.key for tool in tools]
    if len(set(keys)) != len(keys):
        raise ValueError("Ledger tool keys must be unique within one workspace")


__all__ = ["LedgerToolV1", "require_unique_tool_keys"]
