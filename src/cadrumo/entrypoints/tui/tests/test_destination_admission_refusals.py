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

from ....application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    DestinationAdmissionError,
    TuiActionCandidateV1,
    TuiDestinationAdmissionV1,
    TuiDestinationIdV1,
    TuiDestinationRouteV1,
    TuiScreenContextV1,
    build_destination_catalogue,
)
from .test_navigation import _admissions, _catalogue, _factories, _search_result

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


def _workbench_admission(
    destination: TuiDestinationIdV1,
    *,
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
    reason_code: str | None = None,
) -> WorkbenchDestinationAdmission:
    """The application-side admission a search result carries."""
    return WorkbenchDestinationAdmission(destination=destination, state=state, reason_code=reason_code)


def test_a_search_result_carrying_a_stale_admission_is_refused() -> None:
    """A result records reachability as it was WHEN THE SEARCH RAN.

    If the route's admission has moved since, navigating on the result would
    act on a judgement the workbench has already revised -- opening a
    destination that is now locked, or refusing one that has since opened.
    Comparing the two is what keeps a stale result from deciding.
    """
    catalogue = _catalogue()
    stale = _workbench_admission(
        _HOME.destination,
        state=WorkbenchDestinationAdmissionState.LOCKED,
        reason_code="search.stale",
    )

    with pytest.raises(DestinationAdmissionError, match="does not match the current route admission"):
        catalogue.target_for_search_result(_search_result(admission=stale))


def test_a_search_result_agreeing_with_the_route_navigates() -> None:
    """The control: the comparison must not refuse every search result."""
    catalogue = _catalogue()

    target = catalogue.target_for_search_result(_search_result(admission=_workbench_admission(_HOME.destination)))

    assert target.destination == _HOME.destination


def test_an_admissions_mapping_whose_key_and_value_disagree_is_refused() -> None:
    """The key is how the catalogue addresses it; the value is what it says.

    A caller that files one destination's admission under another's key would
    build a catalogue whose every lookup returned a judgement about a
    different workspace, and the destination set would still be complete.
    """
    admissions = dict(_admissions())
    admissions[_HOME.destination] = admissions[_OTHER.destination]

    with pytest.raises(DestinationAdmissionError, match="key and value must name the same destination"):
        build_destination_catalogue(admissions=admissions)


def test_a_consistent_admissions_mapping_builds_the_catalogue() -> None:
    """The control: the key/value check must not reject an ordinary mapping.

    Factories are supplied because an AVAILABLE destination requires one --
    a separate refusal that fires AFTER the key/value check, so the test
    above passes without them while this one would not.
    """
    catalogue = build_destination_catalogue(admissions=_admissions(), factories=_factories())

    assert catalogue.resolve(_HOME.destination).admission.destination == _HOME.destination
