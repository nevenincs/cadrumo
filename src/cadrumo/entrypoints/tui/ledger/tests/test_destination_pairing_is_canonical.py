"""One declaration decides where a Ledger area leads, and it is checked.

The controller used to hold its own area-to-destination map beside the route
catalogue's, and the two were joined by a ``cast``. That is the worst of both:
a ``cast`` asserts rather than validates, so the type checker believed
whatever the controller claimed, and the route catalogue's own totality gate
never read the controller's copy. A destination misspelled there was invisible
to everything until an operator selected that area and the route lookup raised
``KeyError``; one swapped between two areas surfaced instead as a
disagreement refusal at the same moment.

The pairing is declared once now, typed as the destination alias so a
misspelling is a type error at the declaration, and the route catalogue reads
its destinations from it rather than repeating them. What the catalogue still
declares on its own is the read body each area opens, which is genuinely its
own fact.

These tests hold the properties that make the single declaration safe --
totality, canonical order, one destination per area -- and then walk every
area through the REAL route resolution to show that none of them lands on
another area's body. They do not pin the destination spellings: with the
catalogue deriving those from the pairing, renaming one renames both sides at
once and misroutes nothing. ``test_ledger_workspace`` spells the expected
tuple out positionally, and that is where a rename is answered.
"""

from __future__ import annotations

import pytest

from .....application.ledger.workspace import LedgerWorkspaceArea
from ..models import (
    LEDGER_DESTINATION_BY_AREA,
    declared_ledger_destination_ids,
)
from ..routes import _SCREEN_BY_AREA, LEDGER_ROUTES, LedgerUnavailableScreen, resolve_ledger_screen
from .test_ledger_workspace import _controller, _projection

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_workspace_area_has_a_destination() -> None:
    """An unmapped area is not a blank cell; the lookup raises on it.

    ``route_target`` indexes the pairing directly, so an area added to the
    enum without an entry here takes navigation down rather than degrading.
    """
    assert frozenset(LEDGER_DESTINATION_BY_AREA) == frozenset(LedgerWorkspaceArea)


def test_the_pairing_follows_the_enum_order_the_navigation_presents() -> None:
    """Order is meaning here: the workspace lists areas in this sequence.

    Checked as a sequence rather than a set because a pairing that held every
    area in a different order would still satisfy the totality test above
    while reordering what the operator sees.
    """
    assert tuple(LEDGER_DESTINATION_BY_AREA) == tuple(LedgerWorkspaceArea)


def test_no_two_areas_resolve_to_one_destination() -> None:
    """Two areas sharing a destination would collapse two screens into one."""
    destinations = tuple(LEDGER_DESTINATION_BY_AREA.values())

    assert len(frozenset(destinations)) == len(destinations)


def test_the_destinations_are_exactly_the_declared_catalogue() -> None:
    """Neither a destination nobody declared nor a declared one nobody reaches.

    The alias is the closed set; a value outside it would be unroutable, and
    one inside it that no area names would be a screen with no way in.
    """
    assert frozenset(LEDGER_DESTINATION_BY_AREA.values()) == declared_ledger_destination_ids()


def test_the_route_catalogue_carries_the_same_destination_for_every_area() -> None:
    """The agreement that nothing checked while the pairing was written twice.

    This is the regression this file exists for: the two surfaces are one
    declaration now, and this states the property that makes that true rather
    than asserting how it was achieved.
    """
    catalogue = {route.area: route.destination for route in LEDGER_ROUTES}

    assert catalogue == dict(LEDGER_DESTINATION_BY_AREA)


@pytest.mark.parametrize("area", tuple(LedgerWorkspaceArea), ids=lambda area: area.value)
def test_no_area_resolves_into_another_areas_screen(area: LedgerWorkspaceArea) -> None:
    """The end-to-end walk: an area lands on the body it asked for.

    Deliberately NOT a swap detector. Now that the route catalogue derives its
    destinations from the pairing, exchanging two destination tokens renames
    both sides together and routes nothing anywhere new -- the screen is keyed
    by area throughout. What still pins the tokens themselves is the
    positional assertion in ``test_ledger_workspace``, which spells the
    expected tuple out; that is the test a rename has to answer to.

    What this proves instead is that resolution never crosses areas: the
    resolver raises when a target's destination and area disagree, and the
    body it returns is the one its own route names. Both outcomes are
    accepted because both are correct -- whether an area opens its body or a
    typed placeholder depends on the doors the host injected, which is the
    caller's business.
    """
    controller = _controller(_projection())
    route = next(candidate for candidate in LEDGER_ROUTES if candidate.area is area)

    screen = resolve_ledger_screen(controller, controller.route_target(area))

    if isinstance(screen, LedgerUnavailableScreen):
        assert screen.refusal is not None
        assert screen.refusal.target.area is area
    else:
        assert type(screen) is route.factory
    assert screen.controller is controller


def test_the_walk_reaches_real_bodies_and_placeholders_alike() -> None:
    """The control the walk needs: neither branch above may be the only one taken.

    If every area refused, the type assertion would never run; if none did,
    the refusal assertion would never run. Both arms carry a real check, so a
    run that exercised only one would leave half the invariant unproven and
    look exactly like a passing test.
    """
    controller = _controller(_projection())

    resolved = [resolve_ledger_screen(controller, controller.route_target(area)) for area in LedgerWorkspaceArea]

    assert any(isinstance(screen, LedgerUnavailableScreen) for screen in resolved)
    assert any(not isinstance(screen, LedgerUnavailableScreen) for screen in resolved)


def test_an_area_the_application_marks_unavailable_reaches_the_placeholder() -> None:
    """An application refusal must render, not raise.

    Distinct from a missing door: this one comes from the projection itself,
    and it is the state that would otherwise reach the operator as a crash.
    """
    unavailable = LedgerWorkspaceArea.RECONCILIATION
    controller = _controller(_projection(unavailable=unavailable))

    screen = resolve_ledger_screen(controller, controller.route_target(unavailable))

    assert isinstance(screen, LedgerUnavailableScreen)
    assert screen.refusal is not None
    assert screen.refusal.target.area is unavailable


def test_the_controller_reads_the_canonical_pairing_rather_than_a_copy() -> None:
    """A second map would reintroduce exactly the drift this replaced.

    Stated as an identity between what the controller produces and the one
    declaration, for every area at once, so a copy that happened to agree
    today would still have to be kept in step to keep passing.
    """
    controller = _controller(_projection())

    produced = {area: controller.route_target(area).destination for area in LedgerWorkspaceArea}

    assert produced == dict(LEDGER_DESTINATION_BY_AREA)


def test_every_area_has_exactly_one_callable_body() -> None:
    """The executable catalogue itself proves body coverage without a status list."""
    assert frozenset(_SCREEN_BY_AREA) == frozenset(LedgerWorkspaceArea)
    assert all(callable(route.factory) for route in LEDGER_ROUTES)
