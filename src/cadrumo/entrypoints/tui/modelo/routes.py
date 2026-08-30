"""The closed route table for the Modelo workspace read destinations.

This is a FIRST CONSTRUCTION, not a migration. No route registry existed
before it: the TUI had no route ids, no destination table and no factory
map, and destinations were reached by a CLI handler importing a screen
directly. So the census this module supports is derived from what it
BUILDS -- every declared destination resolves to exactly one factory, and
every factory answers exactly one declared destination -- and never
asserted as "zero remaining" over a structure that never had entries to
remove.

The destination identities come from
:data:`ModeloWorkspaceDestinationIdV1` rather than being restated here.
That alias is the single definition of the closed set, so a destination
cannot be routed that no view model can address, and the completeness
check below compares this table against the alias rather than against a
copy of it. A hand-listed census would agree with itself.

Factories take an admitted :class:`ModeloWorkspaceReadSession` and return
a screen. They resolve nothing: admission has already happened by the time
a route is taken, and a factory that re-resolved would give a destination
a different read from the one the operator navigated within.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, get_args

from textual.screen import Screen

from .view.controller import ModeloWorkspaceReadSession
from .view.filing import ModeloWorkspaceFilingScreen
from .view.inputs import ModeloWorkspaceInputsScreen
from .view.models import ModeloWorkspaceDestinationIdV1
from .view.overview import ModeloWorkspaceOverviewScreen
from .view.provenance import ModeloWorkspaceProvenanceScreen
from .view.results import ModeloWorkspaceResultsScreen
from .view.verification import ModeloWorkspaceVerificationScreen

type ModeloWorkspaceDestinationFactoryV1 = Callable[[ModeloWorkspaceReadSession], Screen[None]]
"""Builds one destination's screen from an already-admitted session."""

MODELO_WORKSPACE_DESTINATIONS: Final[dict[ModeloWorkspaceDestinationIdV1, ModeloWorkspaceDestinationFactoryV1]] = {
    "modelo.workspace.overview": ModeloWorkspaceOverviewScreen,
    "modelo.workspace.inputs": ModeloWorkspaceInputsScreen,
    "modelo.workspace.results": ModeloWorkspaceResultsScreen,
    "modelo.workspace.provenance": ModeloWorkspaceProvenanceScreen,
    "modelo.workspace.verification": ModeloWorkspaceVerificationScreen,
    "modelo.workspace.filing": ModeloWorkspaceFilingScreen,
}
"""Every read destination, keyed by its route identity.

The C1 selection outcome is ``modelo.workspace.overview``: a picker that
has resolved a work unit hands the operator the workspace frame, not the
bounded review screen it used to reach.
"""

WORKSPACE_SELECTION_OUTCOME: Final[ModeloWorkspaceDestinationIdV1] = "modelo.workspace.overview"
"""The destination a completed work-unit selection lands on.

Named rather than inlined at the call site so the selection outcome has
one definition. A launcher that hardcoded a screen class would make the
outcome a property of whichever CLI module happened to import it.
"""


def declared_destination_ids() -> frozenset[str]:
    """Return the closed destination set, read from its own type alias.

    Read from ``get_args`` rather than restated, so this cannot drift from
    the alias the view models address. A literal copy here would be a
    second definition that agrees with the first only until someone edits
    one of them.
    """
    return frozenset(get_args(ModeloWorkspaceDestinationIdV1.__value__))


def _require_total_destination_table() -> None:
    """Refuse a table that does not answer every declared destination exactly once."""
    routed = frozenset(MODELO_WORKSPACE_DESTINATIONS)
    declared = declared_destination_ids()
    if routed != declared:
        missing = sorted(declared - routed)
        extra = sorted(routed - declared)
        raise ValueError(f"workspace destination table must cover each declared id exactly once: {missing=} {extra=}")
    if len(set(MODELO_WORKSPACE_DESTINATIONS.values())) != len(MODELO_WORKSPACE_DESTINATIONS):
        raise ValueError("each workspace destination must resolve to its own factory")


_require_total_destination_table()


def resolve_destination(destination: ModeloWorkspaceDestinationIdV1) -> ModeloWorkspaceDestinationFactoryV1:
    """Return the one factory registered for this destination identity."""
    return MODELO_WORKSPACE_DESTINATIONS[destination]


__all__ = [
    "MODELO_WORKSPACE_DESTINATIONS",
    "WORKSPACE_SELECTION_OUTCOME",
    "ModeloWorkspaceDestinationFactoryV1",
    "declared_destination_ids",
    "resolve_destination",
]
