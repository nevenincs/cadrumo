"""Closed, frontend-only navigation contracts for the TUI root.

The root owns route composition.  It receives truthful admission outcomes and
screen factories from its caller; this module does not read application state,
perform I/O, translate labels, or import a concrete destination screen.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, Protocol, Self, get_args, runtime_checkable

from pydantic import BaseModel, model_validator
from textual.screen import Screen

from ...application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchSearchResult,
)
from ...core.hex import Hex64Str
from ...core.identifier_grammar import NamespacedId
from ...core.models import STRICT_FROZEN_CONFIG

type TuiDestinationIdV1 = Literal[
    "workbench.home",
    "workbench.ledger",
    "workbench.declarations",
    "workbench.aeat_sync",
    "workbench.profile",
]
"""The closed route identities admitted by the TUI shell."""

type TuiDestinationLabelKeyV1 = Literal[
    "tui.destination.home",
    "tui.destination.ledger",
    "tui.destination.declarations",
    "tui.destination.aeat_sync",
    "tui.destination.profile",
]
"""Stable locale keys, not display strings."""

type TuiDestinationZoneV1 = Literal["primary", "account"]


class NavigationContractError(ValueError):
    """Base error for an invalid or non-admittable navigation contract."""


class UnknownDestinationError(NavigationContractError):
    """Raised when a destination is outside the closed catalogue."""


class DestinationAdmissionError(NavigationContractError):
    """Raised when an admission does not match the route it claims."""


class DestinationUnavailableError(NavigationContractError):
    """Raised when navigation tries to open a non-available route."""


class UnresolvedActionCandidateError(NavigationContractError):
    """Raised when a search action candidate has no catalogue declaration."""


class DestinationFactoryError(NavigationContractError):
    """Raised when a route cannot produce a valid Textual screen."""


class TuiDestinationDescriptorV1(BaseModel):
    """Static metadata for one shell destination."""

    model_config = STRICT_FROZEN_CONFIG

    destination: TuiDestinationIdV1
    label_key: TuiDestinationLabelKeyV1
    zone: TuiDestinationZoneV1


class TuiDestinationAdmissionV1(BaseModel):
    """Truthful, explicit admission for one closed destination.

    The state enum is owned by the S368 workbench projection.  Reusing it
    keeps search results and shell routing on one vocabulary for unavailable,
    stale, locked, and never-captured destinations.
    """

    model_config = STRICT_FROZEN_CONFIG

    destination: TuiDestinationIdV1
    state: WorkbenchDestinationAdmissionState
    reason_code: NamespacedId | None = None

    @model_validator(mode="after")
    def _reason_matches_state(self) -> Self:
        if self.state is WorkbenchDestinationAdmissionState.AVAILABLE:
            if self.reason_code is not None:
                raise ValueError("an available destination cannot carry an admission reason")
        elif self.reason_code is None:
            raise ValueError("a non-available destination requires an admission reason")
        return self

    @classmethod
    def from_workbench(cls, admission: WorkbenchDestinationAdmission) -> Self:
        """Adapt the S368 search admission without widening its state set."""
        return cls(
            destination=admission.destination,
            state=admission.state,
            reason_code=admission.reason_code,
        )


class TuiFocusIdentityV1(BaseModel):
    """A stable semantic focus address independent of rendered row position."""

    model_config = STRICT_FROZEN_CONFIG

    destination: TuiDestinationIdV1
    semantic_key: NamespacedId
    restore_token: Hex64Str | None = None


class TuiNavigationTargetV1(BaseModel):
    """A destination plus the semantic focus to restore after mounting it."""

    model_config = STRICT_FROZEN_CONFIG

    destination: TuiDestinationIdV1
    focus: TuiFocusIdentityV1
    action_candidate_id: NamespacedId | None = None

    @model_validator(mode="after")
    def _focus_belongs_to_destination(self) -> Self:
        if self.focus.destination != self.destination:
            raise ValueError("navigation target focus must belong to its destination")
        return self


class TuiScreenContextV1(BaseModel):
    """Immutable context handed to an injected destination screen factory."""

    model_config = STRICT_FROZEN_CONFIG

    destination: TuiDestinationIdV1
    focus: TuiFocusIdentityV1 | None = None
    action_candidate_id: NamespacedId | None = None

    @model_validator(mode="after")
    def _focus_belongs_to_destination(self) -> Self:
        if self.focus is not None and self.focus.destination != self.destination:
            raise ValueError("screen context focus must belong to its destination")
        return self


@runtime_checkable
class TuiScreenFactoryV1(Protocol):
    """Build one host-agnostic Textual screen from an admitted context."""

    def __call__(self, context: TuiScreenContextV1, /) -> Screen[None]:
        """Return the screen for the already-admitted route."""


class TuiActionCandidateV1(BaseModel):
    """A declared action candidate that a result may refer to."""

    model_config = STRICT_FROZEN_CONFIG

    action_candidate_id: NamespacedId
    destination: TuiDestinationIdV1


@dataclass(frozen=True, slots=True)
class TuiDestinationRouteV1:
    """One descriptor, admission, optional factory, and admitted actions."""

    descriptor: TuiDestinationDescriptorV1
    admission: TuiDestinationAdmissionV1
    factory: TuiScreenFactoryV1 | None = None
    action_candidates: tuple[TuiActionCandidateV1, ...] = ()

    def __post_init__(self) -> None:
        if self.descriptor.destination != self.admission.destination:
            raise DestinationAdmissionError("route descriptor and admission must name the same destination")
        if self.admission.state is WorkbenchDestinationAdmissionState.AVAILABLE and self.factory is None:
            raise DestinationFactoryError("an available destination requires an injected screen factory")
        if self.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            if self.factory is not None:
                raise DestinationFactoryError("a non-available destination cannot carry a screen factory")
            if self.action_candidates:
                raise DestinationAdmissionError("a non-available destination cannot admit action candidates")
        action_ids = tuple(item.action_candidate_id for item in self.action_candidates)
        if len(set(action_ids)) != len(action_ids):
            raise NavigationContractError("action candidate IDs must be unique within a destination")
        if any(item.destination != self.descriptor.destination for item in self.action_candidates):
            raise DestinationAdmissionError("an action candidate must belong to its destination")

    def action_candidate(self, action_candidate_id: str) -> TuiActionCandidateV1:
        """Resolve one action candidate declared by this route."""
        for candidate in self.action_candidates:
            if candidate.action_candidate_id == action_candidate_id:
                return candidate
        raise UnresolvedActionCandidateError(f"unknown action candidate: {action_candidate_id!r}")


def declared_destination_ids() -> frozenset[str]:
    """Return the destination set from the closed type alias."""
    return frozenset(
        argument
        for argument in get_args(TuiDestinationIdV1.__value__)
        if isinstance(argument, str)
    )


TUI_DESTINATION_CATALOGUE: Final[tuple[TuiDestinationDescriptorV1, ...]] = (
    TuiDestinationDescriptorV1(destination="workbench.home", label_key="tui.destination.home", zone="primary"),
    TuiDestinationDescriptorV1(destination="workbench.ledger", label_key="tui.destination.ledger", zone="primary"),
    TuiDestinationDescriptorV1(
        destination="workbench.declarations",
        label_key="tui.destination.declarations",
        zone="primary",
    ),
    TuiDestinationDescriptorV1(destination="workbench.aeat_sync", label_key="tui.destination.aeat_sync", zone="primary"),
    TuiDestinationDescriptorV1(destination="workbench.profile", label_key="tui.destination.profile", zone="account"),
)
"""The static, localized-key-only destination catalogue."""


_DESCRIPTORS_BY_ID: Mapping[str, TuiDestinationDescriptorV1] = MappingProxyType(
    {descriptor.destination: descriptor for descriptor in TUI_DESTINATION_CATALOGUE}
)


def _require_closed_destination_keys(values: Mapping[str, object], *, field_name: str) -> None:
    declared = declared_destination_ids()
    actual = frozenset(values)
    if not actual <= declared:
        raise NavigationContractError(f"{field_name} contains unknown destination IDs: {sorted(actual - declared)!r}")


class TuiDestinationCatalogueV1:
    """Immutable runtime catalogue assembled from explicit admissions/factories."""

    __slots__ = ("_routes", "_routes_by_id")

    def __init__(self, routes: Iterable[TuiDestinationRouteV1]) -> None:
        ordered_routes = tuple(routes)
        expected = declared_destination_ids()
        actual = frozenset(route.descriptor.destination for route in ordered_routes)
        if actual != expected:
            raise NavigationContractError(
                f"destination routes must cover the closed catalogue exactly: missing={sorted(expected - actual)!r}, "
                f"extra={sorted(actual - expected)!r}"
            )
        if len(actual) != len(ordered_routes):
            raise NavigationContractError("destination route IDs must be unique")
        self._routes = ordered_routes
        self._routes_by_id = MappingProxyType(
            {route.descriptor.destination: route for route in ordered_routes}
        )

    @property
    def routes(self) -> tuple[TuiDestinationRouteV1, ...]:
        """Return the immutable route sequence."""
        return self._routes

    def resolve(self, destination: str) -> TuiDestinationRouteV1:
        """Resolve one closed destination identity or fail closed."""
        try:
            return self._routes_by_id[destination]
        except KeyError as error:
            raise UnknownDestinationError(f"unknown TUI destination: {destination!r}") from error

    def target_for_search_result(self, result: WorkbenchSearchResult) -> TuiNavigationTargetV1:
        """Turn an S368 result into an admitted semantic navigation target."""
        route = self.resolve(result.admission.destination)
        result_admission = TuiDestinationAdmissionV1.from_workbench(result.admission)
        if result_admission != route.admission:
            raise DestinationAdmissionError("search result admission does not match the current route admission")
        if route.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            raise DestinationUnavailableError(
                f"destination {route.descriptor.destination!r} is {route.admission.state.value!r}"
            )
        action_candidate_id = result.action_candidate_id
        if action_candidate_id is not None:
            route.action_candidate(action_candidate_id)
        focus = TuiFocusIdentityV1(
            destination=route.descriptor.destination,
            semantic_key=f"search.{result.kind.value}",
            restore_token=result.stable_id,
        )
        return TuiNavigationTargetV1(
            destination=route.descriptor.destination,
            focus=focus,
            action_candidate_id=action_candidate_id,
        )

    def create_screen(self, target: TuiNavigationTargetV1) -> Screen[None]:
        """Invoke the injected factory for an admitted target."""
        route = self.resolve(target.destination)
        if route.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE:
            raise DestinationUnavailableError(
                f"destination {route.descriptor.destination!r} is {route.admission.state.value!r}"
            )
        factory = route.factory
        if factory is None:  # pragma: no cover - route construction prevents this
            raise DestinationFactoryError("available destination has no screen factory")
        context = TuiScreenContextV1(
            destination=target.destination,
            focus=target.focus,
            action_candidate_id=target.action_candidate_id,
        )
        screen = factory(context)
        if not isinstance(screen, Screen):
            raise DestinationFactoryError("screen factory must return a Textual Screen")
        return screen


def build_destination_catalogue(
    *,
    admissions: Mapping[str, TuiDestinationAdmissionV1 | WorkbenchDestinationAdmission],
    factories: Mapping[str, TuiScreenFactoryV1] | None = None,
    action_candidates: Iterable[TuiActionCandidateV1] = (),
) -> TuiDestinationCatalogueV1:
    """Compose the closed catalogue from caller-supplied boundary values."""
    _require_closed_destination_keys(admissions, field_name="admissions")
    if frozenset(admissions) != declared_destination_ids():
        raise NavigationContractError("admissions must state every destination exactly once")
    if factories is not None:
        _require_closed_destination_keys(factories, field_name="factories")

    candidates_by_destination: dict[str, list[TuiActionCandidateV1]] = {}
    seen_action_ids: set[str] = set()
    for candidate in action_candidates:
        if candidate.action_candidate_id in seen_action_ids:
            raise NavigationContractError("action candidate IDs must be globally unique")
        seen_action_ids.add(candidate.action_candidate_id)
        candidates_by_destination.setdefault(candidate.destination, []).append(candidate)

    routes: list[TuiDestinationRouteV1] = []
    for descriptor in TUI_DESTINATION_CATALOGUE:
        raw_admission = admissions[descriptor.destination]
        admission = (
            TuiDestinationAdmissionV1.from_workbench(raw_admission)
            if isinstance(raw_admission, WorkbenchDestinationAdmission)
            else raw_admission
        )
        if admission.destination != descriptor.destination:
            raise DestinationAdmissionError("admission key and value must name the same destination")
        factory = factories.get(descriptor.destination) if factories is not None else None
        routes.append(
            TuiDestinationRouteV1(
                descriptor=descriptor,
                admission=admission,
                factory=factory,
                action_candidates=tuple(candidates_by_destination.get(descriptor.destination, ())),
            )
        )
    return TuiDestinationCatalogueV1(routes)


__all__ = [
    "DestinationAdmissionError",
    "DestinationFactoryError",
    "DestinationUnavailableError",
    "NavigationContractError",
    "TUI_DESTINATION_CATALOGUE",
    "TuiActionCandidateV1",
    "TuiDestinationAdmissionV1",
    "TuiDestinationDescriptorV1",
    "TuiDestinationIdV1",
    "TuiDestinationLabelKeyV1",
    "TuiDestinationCatalogueV1",
    "TuiDestinationRouteV1",
    "TuiDestinationZoneV1",
    "TuiFocusIdentityV1",
    "TuiNavigationTargetV1",
    "TuiScreenContextV1",
    "TuiScreenFactoryV1",
    "UnknownDestinationError",
    "UnresolvedActionCandidateError",
    "WorkbenchDestinationAdmissionState",
    "build_destination_catalogue",
    "declared_destination_ids",
]
