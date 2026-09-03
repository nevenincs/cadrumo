"""Command-palette projections over admitted workbench search and navigation.

The application search service owns the safe snapshot, matching, ranking, and
stable result identity.  The navigation catalogue owns destination and action
admission.  This module only adapts those already-authoritative answers to
Textual command-palette hits; selecting a hit asks the injected root host to
navigate and cannot invoke a business action.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final, Protocol, override, runtime_checkable

from textual.command import DiscoveryHit, Hit, Hits, Provider

from ...application.search.workbench import (
    WorkbenchSearchLabelKey,
    WorkbenchSearchRequest,
    WorkbenchSearchResponse,
    WorkbenchSearchResult,
    WorkbenchSearchSource,
    WorkbenchSearchStatus,
)
from ...core.i18n.render import tr
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


_RESULT_LABEL_LOCALE_KEYS: Final[Mapping[WorkbenchSearchLabelKey, str]] = {
    WorkbenchSearchLabelKey.LEDGER_ENTRY: "tui.search.result.label.ledger_entry",
    WorkbenchSearchLabelKey.LEDGER_EVIDENCE: "tui.search.result.label.ledger_evidence",
    WorkbenchSearchLabelKey.DECLARATION: "tui.search.result.label.declaration",
    WorkbenchSearchLabelKey.MODELO: "tui.search.result.label.modelo",
    WorkbenchSearchLabelKey.REVISION: "tui.search.result.label.revision",
    WorkbenchSearchLabelKey.FILING: "tui.search.result.label.filing",
    WorkbenchSearchLabelKey.HISTORY: "tui.search.result.label.history",
    WorkbenchSearchLabelKey.RECONCILIATION: "tui.search.result.label.reconciliation",
    WorkbenchSearchLabelKey.NOTIFICATION: "tui.search.result.label.notification",
}
_RESULT_SOURCE_LOCALE_KEYS: Final[Mapping[WorkbenchSearchSource, str]] = {
    WorkbenchSearchSource.LEDGER_ENTRY: "tui.search.result.source.ledger_entry",
    WorkbenchSearchSource.LEDGER_EVIDENCE: "tui.search.result.source.ledger_evidence",
    WorkbenchSearchSource.DECLARATION: "tui.search.result.source.declaration",
    WorkbenchSearchSource.MODELO: "tui.search.result.source.modelo",
    WorkbenchSearchSource.REVISION: "tui.search.result.source.revision",
    WorkbenchSearchSource.FILING: "tui.search.result.source.filing",
    WorkbenchSearchSource.HISTORY: "tui.search.result.source.history",
    WorkbenchSearchSource.RECONCILIATION: "tui.search.result.source.reconciliation",
    WorkbenchSearchSource.NOTIFICATION: "tui.search.result.source.notification",
}
_RESULT_STATUS_LOCALE_KEYS: Final[Mapping[WorkbenchSearchStatus, str]] = {
    WorkbenchSearchStatus.LEDGER_ENTRY_READY: "tui.search.result.status.ledger_entry_ready",
    WorkbenchSearchStatus.LEDGER_ENTRY_NEEDS_REVIEW: "tui.search.result.status.ledger_entry_needs_review",
    WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED: "tui.search.result.status.ledger_entry_classified",
    WorkbenchSearchStatus.LEDGER_EVIDENCE_CAPTURED: "tui.search.result.status.ledger_evidence_captured",
    WorkbenchSearchStatus.LEDGER_EVIDENCE_MISSING: "tui.search.result.status.ledger_evidence_missing",
    WorkbenchSearchStatus.LEDGER_EVIDENCE_STALE: "tui.search.result.status.ledger_evidence_stale",
    WorkbenchSearchStatus.DECLARATION_DRAFT: "tui.search.result.status.declaration_draft",
    WorkbenchSearchStatus.DECLARATION_IN_PROGRESS: "tui.search.result.status.declaration_in_progress",
    WorkbenchSearchStatus.DECLARATION_NEEDS_ATTENTION: "tui.search.result.status.declaration_needs_attention",
    WorkbenchSearchStatus.DECLARATION_READY: "tui.search.result.status.declaration_ready",
    WorkbenchSearchStatus.DECLARATION_FILED: "tui.search.result.status.declaration_filed",
    WorkbenchSearchStatus.MODELO_AVAILABLE: "tui.search.result.status.modelo_available",
    WorkbenchSearchStatus.MODELO_UNAVAILABLE: "tui.search.result.status.modelo_unavailable",
    WorkbenchSearchStatus.REVISION_CURRENT: "tui.search.result.status.revision_current",
    WorkbenchSearchStatus.REVISION_SUPERSEDED: "tui.search.result.status.revision_superseded",
    WorkbenchSearchStatus.FILING_SUBMITTED: "tui.search.result.status.filing_submitted",
    WorkbenchSearchStatus.FILING_ACCEPTED: "tui.search.result.status.filing_accepted",
    WorkbenchSearchStatus.FILING_REJECTED: "tui.search.result.status.filing_rejected",
    WorkbenchSearchStatus.HISTORY_OBSERVED: "tui.search.result.status.history_observed",
    WorkbenchSearchStatus.HISTORY_NOT_OBSERVED: "tui.search.result.status.history_not_observed",
    WorkbenchSearchStatus.RECONCILIATION_OPEN: "tui.search.result.status.reconciliation_open",
    WorkbenchSearchStatus.RECONCILIATION_RESOLVED: "tui.search.result.status.reconciliation_resolved",
    WorkbenchSearchStatus.NOTIFICATION_UNREAD: "tui.search.result.status.notification_unread",
    WorkbenchSearchStatus.NOTIFICATION_READ: "tui.search.result.status.notification_read",
}
_DESTINATION_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "workbench.home": "tui.search.destination.home",
    "workbench.ledger": "tui.search.destination.ledger",
    "workbench.declarations": "tui.search.destination.declarations",
    "workbench.aeat_sync": "tui.search.destination.aeat_sync",
    "workbench.profile": "tui.search.destination.profile",
}
_ACTION_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "operator.declaration.open": "tui.search.action.open_declaration",
    "operator.ledger.open": "tui.search.action.open_ledger",
    "operator.not_declared.open": "tui.search.action.review_undeclared",
    "operator.profile.edit": "tui.search.action.edit_profile",
    "operator.ledger.review": "tui.search.action.review_ledger",
    "operator.ledger.classify": "tui.search.action.classify_ledger",
    "operator.ledger.evidence.review.list": "tui.search.action.review_ledger_evidence",
    "operator.ledger.link": "tui.search.action.link_ledger",
    "operator.ledger.preflight": "tui.search.action.validate_ledger",
    "operator.live.filed.pull": "tui.aeat_sync.action.pull_filed",
    "operator.live.filed.pull_all": "tui.aeat_sync.action.pull_filed_all",
    "operator.live.notifications.list": "tui.search.action.list_notifications",
    "operator.overview.explain": "tui.search.action.explain_overview",
    "operator.modelo.filing_record.list": "tui.search.action.list_filing_records",
}
_SEARCH_LOCALE_KEYS: Final[tuple[str, ...]] = (
    *_RESULT_LABEL_LOCALE_KEYS.values(),
    *_RESULT_SOURCE_LOCALE_KEYS.values(),
    *_RESULT_STATUS_LOCALE_KEYS.values(),
    *_DESTINATION_LOCALE_KEYS.values(),
    *_ACTION_LOCALE_KEYS.values(),
    "tui.search.result.address",
    "tui.search.destination.unknown",
    "tui.search.action.available",
)


def _render_locale(key: str, locale: str | None, **values: object) -> str:
    """Render one palette label, optionally under a test-selected locale."""
    if locale is None:
        return tr(key, **values)
    return tr(key, locale=locale, **values)


def _result_text(result: WorkbenchSearchResult, *, locale: str | None = None) -> str:
    """Render safe search metadata through localized human-facing labels."""
    label = _render_locale(_RESULT_LABEL_LOCALE_KEYS[result.label_key], locale)
    source = _render_locale(_RESULT_SOURCE_LOCALE_KEYS[result.source], locale)
    status = _render_locale(_RESULT_STATUS_LOCALE_KEYS[result.status], locale)
    parts = [label, source, status]
    if result.address is not None:
        parts.append(
            _render_locale(
                "tui.search.result.address",
                locale,
                modelo=result.address.modelo,
                filing_year=result.address.filing_year,
                period=result.address.period.registry_token,
            )
        )
    return " · ".join(parts)


def _destination_text(destination: str, *, locale: str | None = None) -> str:
    """Produce localized wording for one admitted destination."""
    key = _DESTINATION_LOCALE_KEYS.get(destination, "tui.search.destination.unknown")
    return _render_locale(key, locale)


def _action_text(action_candidate_id: str, *, locale: str | None = None) -> str:
    """Render an admitted action without exposing its internal identifier."""
    key = _ACTION_LOCALE_KEYS.get(action_candidate_id, "tui.search.action.available")
    return _render_locale(key, locale)


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
                help=_destination_text(result.admission.destination),
            )


class WorkbenchCommandProviderV1(Provider):
    """Expose admitted destinations and registered action identities as commands."""

    @override
    async def search(self, query: str) -> Hits:
        """Fuzzy-match the current catalogue's admitted routes and actions."""
        matcher = self.matcher(query)
        for text, target, _identity in _command_entries(_require_host(self.app).destination_catalogue):
            if (score := matcher.match(text)) > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(text),
                    command=_navigation_command(_require_host(self.app).navigate_to, target),
                    text=text,
                    help=_destination_text(target.destination),
                )

    @override
    async def discover(self) -> Hits:
        """List the current admitted destinations and actions before typing."""
        host = _require_host(self.app)
        for text, target, _identity in _command_entries(host.destination_catalogue):
            yield DiscoveryHit(
                display=text,
                command=_navigation_command(host.navigate_to, target),
                text=text,
                help=_destination_text(target.destination),
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
            entries.append((_action_text(candidate.action_candidate_id), action_target, candidate.action_candidate_id))
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
