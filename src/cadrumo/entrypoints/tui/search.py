"""Command-palette projections over admitted workbench search and navigation.

The application search service owns the safe snapshot, matching, ranking, and
stable result identity.  The navigation catalogue owns destination and action
admission.  This module only adapts those already-authoritative answers to
Textual command-palette hits; selecting a hit asks the injected root host to
navigate and cannot invoke a business action.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, override, runtime_checkable

from textual.command import DiscoveryHit, Hit, Hits, Provider

from ...application.search.workbench import (
    WorkbenchSearchRequest,
    WorkbenchSearchResponse,
    WorkbenchSearchResult,
)
from .navigation import (
    DestinationUnavailableError,
    NavigationContractError,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
)


@runtime_checkable
class WorkbenchSearchDoorV1(Protocol):
    """The application-owned search door consumed by the palette."""

    def search(self, request: WorkbenchSearchRequest, /) -> WorkbenchSearchResponse:
        """Return the authoritative bounded result page for a transient query."""
        ...


@runtime_checkable
class TuiSearchHostV1(Protocol):
    """The root seam through which palette hits request navigation."""

    @property
    def workbench_search_service(self) -> WorkbenchSearchDoorV1:
        """Return the already-composed application search service."""
        ...

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        """Return the already-admitted destination catalogue."""
        ...

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        """Navigate to an already-admitted semantic target."""
        ...


class TuiSearchHostError(RuntimeError):
    """Raised when a palette provider is mounted outside the workbench root."""


def _require_host(app: object) -> TuiSearchHostV1:
    """Return the root host or fail before reading search state."""
    if not isinstance(app, TuiSearchHostV1):
        raise TuiSearchHostError("the workbench palette requires a TuiSearchHostV1 root")
    return app


def _result_text(result: WorkbenchSearchResult) -> str:
    """Render closed search metadata without inventing a business label."""
    address = ""
    if result.address is not None:
        address = (
            f" · Modelo {result.address.modelo} · {result.address.filing_year} · {result.address.period.registry_token}"
        )
    return f"{result.label_key.value} · {result.source.value} · {result.status.value}{address}"


def _destination_text(destination: str) -> str:
    """Produce the fixed palette wording for one admitted destination."""
    return f"Open {destination.removeprefix('workbench.').replace('_', ' ')}"


class WorkbenchSearchProviderV1(Provider):
    """Expose application-ranked workbench results in the command palette."""

    @override
    async def search(self, query: str) -> Hits:
        """Yield only results that still resolve through the current catalogue."""
        try:
            request = WorkbenchSearchRequest(query=query)
        except ValueError:
            return
        host = _require_host(self.app)
        response = host.workbench_search_service.search(request)
        for result in response.results:
            try:
                target = host.destination_catalogue.target_for_search_result(result)
            except (DestinationUnavailableError, NavigationContractError):
                continue
            text = _result_text(result)
            yield Hit(
                score=1.0 / (result.rank + 1),
                match_display=text,
                command=_navigation_command(host.navigate_to, target),
                text=text,
                help=result.stable_id,
            )


class WorkbenchCommandProviderV1(Provider):
    """Expose admitted destinations and registered action identities as commands."""

    @override
    async def search(self, query: str) -> Hits:
        """Fuzzy-match the current catalogue's admitted routes and actions."""
        matcher = self.matcher(query)
        for text, target, identity in _command_entries(_require_host(self.app).destination_catalogue):
            if (score := matcher.match(text)) > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(text),
                    command=_navigation_command(_require_host(self.app).navigate_to, target),
                    text=text,
                    help=identity,
                )

    @override
    async def discover(self) -> Hits:
        """List the current admitted destinations and actions before typing."""
        host = _require_host(self.app)
        for text, target, identity in _command_entries(host.destination_catalogue):
            yield DiscoveryHit(
                display=text,
                command=_navigation_command(host.navigate_to, target),
                text=text,
                help=identity,
            )


def _command_entries(
    catalogue: TuiDestinationCatalogueV1,
) -> tuple[tuple[str, TuiNavigationTargetV1, str], ...]:
    """Project every currently admitted destination and registered action once."""
    entries: list[tuple[str, TuiNavigationTargetV1, str]] = []
    for route in catalogue.routes:
        if route.admission.state.value != "available":
            continue
        destination = route.descriptor.destination
        destination_target = TuiNavigationTargetV1(
            destination=destination,
            focus=TuiFocusIdentityV1(
                destination=destination,
                semantic_key=f"navigation.{destination.removeprefix('workbench.')}",
            ),
        )
        entries.append((_destination_text(destination), destination_target, destination))
        for candidate in route.action_candidates:
            action_target = TuiNavigationTargetV1(
                destination=destination,
                focus=TuiFocusIdentityV1(
                    destination=destination,
                    semantic_key=f"action.{candidate.action_candidate_id}",
                ),
                action_candidate_id=candidate.action_candidate_id,
            )
            entries.append((candidate.action_candidate_id, action_target, candidate.action_candidate_id))
    return tuple(entries)


def _navigation_command(
    navigate_to: Callable[[TuiNavigationTargetV1], None], target: TuiNavigationTargetV1
) -> Callable[[], None]:
    """Bind a validated target without turning a palette choice into an action."""

    def navigate() -> None:
        """Ask the root to mount the admitted destination."""
        navigate_to(target)

    return navigate


__all__ = [
    "TuiSearchHostError",
    "TuiSearchHostV1",
    "WorkbenchCommandProviderV1",
    "WorkbenchSearchDoorV1",
    "WorkbenchSearchProviderV1",
]
