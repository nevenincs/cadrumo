"""The named MCP surfaces a client can pin, and what each one admits.

A surface is what one MCP connection is served. Its name fixes what a client
pins: the tools the server advertises, and two declared properties, whether
anything on the surface can change the profile's records and whether anything
on it reaches the network. A surface whose tools or properties change takes a
new name. Its operation list may grow between releases, and only within those
properties.

A surface narrows what the registry opens to the MCP frontend and never widens
it: the frontend list of a definition is still applied first, wherever a
surface is applied. The runtime applies the surface a connection named at
login to every operation access on that connection. What a server lists or
describes under a surface is a convenience and enforces nothing.

Operations are named by definition id text and tools by their protocol name.
This package owns neither the feature packages' constants nor the tool
catalogue, and importing them would invert the dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .mcp_admission import MCP_ADMISSION_DECISIONS, McpRuling, mcp_admission_decision


class McpSurfaceName(StrEnum):
    """The stable names a client pins."""

    FULL = "full"
    """Everything the registry opens to the MCP frontend."""
    READ_ONLY_LOCAL = "read-only-local"
    """Reads that change no record and contact no host other than this machine."""


@dataclass(frozen=True, slots=True)
class McpSurface:
    """One named surface: its tools, its two declared properties and its operations."""

    name: McpSurfaceName
    tools: frozenset[str]
    """The protocol tools a server advertises under this name."""
    changes_records: bool
    """Something on the surface can commit a change to the profile's records."""
    reaches_network: bool
    """Something on the surface can contact a host other than this machine."""
    operations: frozenset[str] | None
    """The definition ids the surface keeps; ``None`` keeps whatever the registry opens to MCP."""

    def __post_init__(self) -> None:
        """Refuse a surface whose operation list breaks one of its declared properties."""
        if not self.tools:
            raise ValueError(f"{self.name}: a surface advertises at least one tool")
        for definition_id in sorted(self.operations or ()):
            if not self._within_properties(definition_id):
                raise ValueError(f"{self.name}: {definition_id} is outside the surface's declared properties")

    @property
    def narrows(self) -> bool:
        """Whether the surface keeps anything the registry opens to MCP off a connection."""
        return self.operations is not None or not (self.changes_records and self.reaches_network)

    def admits(self, definition_id: str) -> bool:
        """Tell whether the surface keeps one operation the registry opens to MCP.

        An operation outside the list is refused, and so is one whose recorded
        decision says it can do what the surface declares nothing on it does.
        An operation with no recorded decision is refused by every surface
        that narrows.
        """
        if not self.narrows:
            return True
        if self.operations is not None and definition_id not in self.operations:
            return False
        return self._within_properties(definition_id)

    def _within_properties(self, definition_id: str) -> bool:
        try:
            decision = mcp_admission_decision(definition_id)
        except KeyError:
            return False
        return (self.changes_records or not decision.changes_records) and (
            self.reaches_network or not decision.reaches_network
        )


_EVERY_TOOL: Final = frozenset(
    {
        "status",
        "authorization_prepare",
        "authorization_request",
        "authorization_poll",
        "authenticate",
        "authority",
        "corpus_search",
        "search",
        "describe",
        "execute",
        "observe",
        "result",
        "result_page",
        "review",
        "respond",
        "control",
    }
)

# A review is the step a person takes before an operation commits. No read
# declares one, so the two tools that serve reviews have nothing to act on.
_REVIEW_TOOLS: Final = frozenset({"review", "respond"})


def _open_local_reads() -> frozenset[str]:
    """Name every operation open to MCP that changes no record and contacts no other host.

    An admitted decision with nothing outstanding is what lists the MCP
    frontend, so this is the part of the registry's MCP listing the two facts
    allow. A decision that waits for approval is a sensitive act and stays out.
    """
    return frozenset(
        decision.definition_id
        for decision in MCP_ADMISSION_DECISIONS
        if decision.ruling is McpRuling.ADMITTED
        and not decision.prerequisites
        and not decision.changes_records
        and not decision.reaches_network
    )


MCP_SURFACES: Final[Mapping[McpSurfaceName, McpSurface]] = MappingProxyType(
    {
        surface.name: surface
        for surface in (
            McpSurface(
                name=McpSurfaceName.FULL,
                tools=_EVERY_TOOL,
                changes_records=True,
                reaches_network=True,
                operations=None,
            ),
            McpSurface(
                name=McpSurfaceName.READ_ONLY_LOCAL,
                tools=_EVERY_TOOL - _REVIEW_TOOLS,
                changes_records=False,
                reaches_network=False,
                operations=_open_local_reads(),
            ),
        )
    }
)
"""Every surface a connection can name, by name."""

DEFAULT_MCP_SURFACE: Final = McpSurfaceName.FULL
"""The surface served when none is named. It narrows nothing."""


def mcp_surface(name: str) -> McpSurface:
    """Return the surface with this name, or fail closed."""
    try:
        return MCP_SURFACES[McpSurfaceName(name)]
    except ValueError:
        raise KeyError(f"unknown MCP surface: {name!r}") from None


__all__ = [
    "DEFAULT_MCP_SURFACE",
    "MCP_SURFACES",
    "McpSurface",
    "McpSurfaceName",
    "mcp_surface",
]
