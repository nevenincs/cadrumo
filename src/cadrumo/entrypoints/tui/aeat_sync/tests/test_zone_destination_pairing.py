"""The routes and the controller address the same destination for a zone.

The pairing was declared twice: once in the controller, to build a route target
from a zone, and once in the route table, to resolve a destination to a screen.
The module gate beside the routes checked that every zone appears exactly once
and IN ORDER, and that the destinations cover the closed literal type -- all of
which two swapped rows satisfy perfectly. Nothing checked that a route's
destination was the one the controller sends for that zone, so the halves could
disagree and land the operator on the wrong screen with every gate green.

There is now one declaration, in ``models`` beside the destination type,
because neither reader can own it: ``routes`` imports ``controller`` for its
resolver signature, so the controller cannot import ``routes`` back. These
tests hold the remaining risk -- that the route table drifts from the pairing
it is supposed to realise.
"""

from __future__ import annotations

import pytest

from .....application.aeat_sync.workspace import AeatSyncWorkspaceZone
from ..models import AEAT_SYNC_DESTINATION_BY_ZONE
from ..routes import AEAT_SYNC_ROUTES, declared_aeat_sync_destination_ids

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_each_route_addresses_the_destination_the_controller_sends() -> None:
    """The check the coverage-and-order gate cannot make.

    Two routes carrying each other's destination keep every zone present, in
    order, over the same destination set -- and send the operator to the wrong
    screen. Only comparing the pairs catches it.
    """
    assert {route.zone: route.destination for route in AEAT_SYNC_ROUTES} == dict(AEAT_SYNC_DESTINATION_BY_ZONE)


def test_the_pairing_names_every_zone_exactly_once() -> None:
    """A zone with no destination has no reachable body at all."""
    assert set(AEAT_SYNC_DESTINATION_BY_ZONE) == set(AeatSyncWorkspaceZone)
    assert len(AEAT_SYNC_DESTINATION_BY_ZONE) == len(tuple(AeatSyncWorkspaceZone))


def test_no_two_zones_share_a_destination() -> None:
    """Two zones on one destination would silently collapse a body.

    The dict cannot express a duplicated KEY, so only the values need this;
    without it a copy-paste in the pairing would send two zones to one screen
    while every coverage count still balanced.
    """
    destinations = list(AEAT_SYNC_DESTINATION_BY_ZONE.values())

    assert len(set(destinations)) == len(destinations)


def test_every_paired_destination_is_one_the_closed_type_declares() -> None:
    """The pairing cannot invent a destination the route table cannot resolve."""
    assert set(AEAT_SYNC_DESTINATION_BY_ZONE.values()) <= declared_aeat_sync_destination_ids()


def test_the_controller_builds_its_target_from_the_shared_pairing() -> None:
    """Proved through the controller's own method, not by re-reading the map.

    A test that only compared the two constants would still pass if the
    controller went back to a private copy, so this drives the real
    ``target`` call for every zone.
    """
    from ....tui.navigation import TuiScreenContextV1
    from ..tests.test_aeat_sync_workspace import _projection

    controller_type = _controller_type()
    controller = controller_type(TuiScreenContextV1(destination="workbench.aeat_sync"), _projection())

    for zone in AeatSyncWorkspaceZone:
        target = controller.target(zone)
        assert target.destination == AEAT_SYNC_DESTINATION_BY_ZONE[zone]
        assert target.zone is zone


def _controller_type():
    from ..controller import AeatSyncWorkspaceController

    return AeatSyncWorkspaceController
