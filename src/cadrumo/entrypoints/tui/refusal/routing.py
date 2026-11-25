"""Route a served way out of a refusal to the TUI destination that hosts it.

The router keeps no table of its own. The destination comes from the
registries the TUI already enforces: a destination that admits the action as
one of its action candidates, else the Operations destination when the
operation registry publishes one of the target operations the verdict served
for the action, in the order served. An action
neither admits is unroutable, and the panel shows it disabled rather than
dropping it or printing a command line.

Nothing here submits. Every intent opens a destination; one served as needing
arguments opens it on the form for them.
"""

from __future__ import annotations

import asyncio
from functools import partial

from ....application.operator_actions.catalogue import lookup_action
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ..navigation import TuiDestinationCatalogueV1, TuiFocusIdentityV1, TuiNavigationTargetV1
from ..operations.catalogue import OperationCatalogueV1
from ..operations.destination import OPERATIONS_DESTINATION
from ..operations.palette import offered_operation_source, operation_navigation_target
from ..search import TuiSearchHostV1
from .intent import RefusalIntentV1, RefusalRouterV1
from .served import RefusalWayV1, ServedRefusalV1, refusal_ways


def _candidate_target(destinations: TuiDestinationCatalogueV1, action_id: str) -> TuiNavigationTargetV1 | None:
    """Return the available destination that admits ``action_id`` as an action candidate."""
    for route in destinations.routes:
        if route.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            continue
        if any(candidate.action_candidate_id == action_id for candidate in route.action_candidates):
            destination = route.descriptor.destination
            return TuiNavigationTargetV1(
                destination=destination,
                focus=TuiFocusIdentityV1(destination=destination, semantic_key=f"action.{action_id}"),
                action_candidate_id=action_id,
            )
    return None


def _operation_target(
    destinations: TuiDestinationCatalogueV1,
    operations: OperationCatalogueV1 | None,
    target_operation_ids: tuple[str, ...],
) -> TuiNavigationTargetV1 | None:
    """Return the Operations form of the first served target operation the catalogue holds, when admitted."""
    if operations is None:
        return None
    route = destinations.resolve(OPERATIONS_DESTINATION)
    if route.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
        return None
    for operation_id in target_operation_ids:
        entry = operations.entry(operation_id)
        if entry is not None:
            return operation_navigation_target(entry)
    return None


def route_refusal_way(
    way: RefusalWayV1,
    *,
    destinations: TuiDestinationCatalogueV1,
    operations: OperationCatalogueV1 | None,
) -> RefusalIntentV1 | None:
    """Return where ``way`` leads in the TUI, or ``None`` when no admitted destination hosts it.

    ``operations`` is the already-loaded operation catalogue of the Operations
    destination, or ``None`` when it is not loaded; loading it reads the
    registry and belongs to the caller.
    """
    try:
        target_command_key = lookup_action(way.action_id).target_command_key
    except KeyError:
        return None
    target = _candidate_target(destinations, way.action_id) or _operation_target(
        destinations, operations, way.target_operation_ids
    )
    if target is None:
        return None
    return RefusalIntentV1(
        kind="form" if way.conditional else "follow",
        action_id=way.action_id,
        target_command_key=target_command_key,
        target=target,
        argument_bindings=way.argument_bindings,
        missing_argument_names=way.missing_argument_names,
    )


async def host_refusal_router(host: TuiSearchHostV1, refusal: ServedRefusalV1) -> RefusalRouterV1:
    """Return the router of ``host``'s admitted destinations for the ways out ``refusal`` serves.

    The Operations catalogue is read, off the event loop, only when a way out
    has served words and so can become a control; a catalogue that cannot be
    composed leaves every way it would have hosted unroutable.
    """
    destinations = host.destination_catalogue
    operations: OperationCatalogueV1 | None = None
    source = offered_operation_source(host)
    if source is not None and any(way.words is not None for way in refusal_ways(refusal)):
        try:
            operations = await asyncio.to_thread(source.load)
        except Exception:  # a registry that cannot compose must not end the session
            operations = None
    return partial(route_refusal_way, destinations=destinations, operations=operations)


__all__ = ["host_refusal_router", "route_refusal_way"]
