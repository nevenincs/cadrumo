"""Navigation refuses a route whose admission does not describe its destination.

``DestinationAdmissionError`` guards five places where two halves of a routing
decision must name the same destination. No test anywhere in the tree named it,
so every one of those refusals was assertion-shaped rather than proven: a guard
that had quietly stopped firing would have looked exactly like this.

What they protect is not cosmetic. An admission belonging to another
destination decides whether a workspace is reachable at all; an action
candidate belonging elsewhere would offer the operator a task the destination
cannot perform; and a route that admits candidates while unavailable offers
work behind a door it has already refused to open.

Every case pairs with a control that the same construction succeeds when the
halves DO agree, because a guard that rejected everything would satisfy the
refusals alone.
"""

from __future__ import annotations

import pytest
from textual.screen import Screen

from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    DestinationAdmissionError,
    TuiActionCandidateV1,
    TuiDestinationAdmissionV1,
    TuiDestinationIdV1,
    TuiDestinationRouteV1,
    TuiScreenContextV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_HOME = TUI_DESTINATION_CATALOGUE[0]
_OTHER = TUI_DESTINATION_CATALOGUE[1]
_CANDIDATE_ID = "operator.navigation.open"


def _admission(
    destination: TuiDestinationIdV1,
    *,
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
    reason_code: str | None = None,
) -> TuiDestinationAdmissionV1:
    """Build an admission, supplying the reason a non-available state requires."""
    return TuiDestinationAdmissionV1(destination=destination, state=state, reason_code=reason_code)


def _never_built(context: TuiScreenContextV1, /) -> Screen[None]:
    """A factory the route only has to hold, never call.

    Typed to the real protocol -- one positional context, returning a
    ``Screen`` -- because the route validates the factory it is given, so a
    loosely-typed stand-in would be checking a different contract.
    """
    raise AssertionError("no screen is constructed by these contract tests")


def _candidate(destination: TuiDestinationIdV1) -> TuiActionCandidateV1:
    return TuiActionCandidateV1(action_candidate_id=_CANDIDATE_ID, destination=destination)


def test_a_route_whose_admission_names_another_destination_is_refused() -> None:
    """The admission decides reachability, so it must be about this destination."""
    with pytest.raises(DestinationAdmissionError):
        TuiDestinationRouteV1(
            descriptor=_HOME,
            admission=_admission(_OTHER.destination),
            factory=_never_built,
        )


def test_an_unavailable_destination_cannot_admit_action_candidates() -> None:
    """Offering work behind a door already refused is worse than offering none."""
    with pytest.raises(DestinationAdmissionError):
        TuiDestinationRouteV1(
            descriptor=_HOME,
            admission=_admission(
                _HOME.destination,
                state=WorkbenchDestinationAdmissionState.LOCKED,
                reason_code="navigation.locked",
            ),
            action_candidates=(_candidate(_HOME.destination),),
        )


def test_an_action_candidate_belonging_elsewhere_is_refused() -> None:
    """A candidate names a task; the wrong destination cannot perform it."""
    with pytest.raises(DestinationAdmissionError):
        TuiDestinationRouteV1(
            descriptor=_HOME,
            admission=_admission(_HOME.destination),
            factory=_never_built,
            action_candidates=(_candidate(_OTHER.destination),),
        )


def test_an_agreeing_route_is_accepted() -> None:
    """The control every refusal above needs.

    Without it, a constructor that rejected every route would satisfy all three
    while making the workbench unreachable.
    """
    route = TuiDestinationRouteV1(
        descriptor=_HOME,
        admission=_admission(_HOME.destination),
        factory=_never_built,
        action_candidates=(_candidate(_HOME.destination),),
    )

    assert route.admission.destination == _HOME.destination
    assert route.action_candidate(_CANDIDATE_ID).destination == _HOME.destination


def test_an_unavailable_destination_with_no_candidates_is_accepted() -> None:
    """Unavailability alone is not a defect; only unavailability WITH work is.

    Separating the two keeps the refusal above from being read as "a locked
    destination cannot be routed at all", which would hide every unavailable
    workspace instead of showing it as refused.
    """
    route = TuiDestinationRouteV1(
        descriptor=_HOME,
        admission=_admission(
            _HOME.destination,
            state=WorkbenchDestinationAdmissionState.LOCKED,
            reason_code="navigation.locked",
        ),
    )

    assert route.admission.state is WorkbenchDestinationAdmissionState.LOCKED
    assert route.action_candidates == ()
