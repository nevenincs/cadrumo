"""Focused contracts for workbench-search and command-palette projection."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.command import DiscoveryHit, Hit
from textual.screen import Screen
from textual.widgets import Static

from ....application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchModeloAddress,
    WorkbenchSearchDocument,
    WorkbenchSearchKind,
    WorkbenchSearchLabelKey,
    WorkbenchSearchService,
    WorkbenchSearchSource,
    WorkbenchSearchStatus,
)
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiActionCandidateV1,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from ..search import WorkbenchCommandProviderV1, WorkbenchSearchProviderV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class MarkerScreen(Screen[None]):
    """A screen returned by the injected destination-factory seam."""


def _factory(_context: TuiScreenContextV1) -> Screen[None]:
    """Return a screen without consulting application state."""
    return MarkerScreen()


def _catalogue(*, actions: tuple[TuiActionCandidateV1, ...] = ()) -> TuiDestinationCatalogueV1:
    """Build the complete admitted catalogue used by the real provider tests."""
    admissions: dict[str, TuiDestinationAdmissionV1 | WorkbenchDestinationAdmission] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: _factory for descriptor in TUI_DESTINATION_CATALOGUE
    }
    return build_destination_catalogue(admissions=admissions, factories=factories, action_candidates=actions)


def _document(
    *,
    admission: WorkbenchDestinationAdmission | None = None,
    action_candidate_id: str | None = None,
) -> WorkbenchSearchDocument:
    """Return an application search projection with a canonical natural address."""
    return WorkbenchSearchDocument(
        kind=WorkbenchSearchKind.DECLARATION,
        source=WorkbenchSearchSource.DECLARATION,
        status=WorkbenchSearchStatus.DECLARATION_READY,
        label_key=WorkbenchSearchLabelKey.DECLARATION,
        address=WorkbenchModeloAddress(
            modelo=ModeloCode("303"),
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        ),
        admission=admission
        or WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        ),
        action_candidate_id=action_candidate_id,
    )


class SearchHostApp(App[None]):
    """Minimal root seam that receives palette targets for assertion."""

    def __init__(self, *, service: WorkbenchSearchService, catalogue: TuiDestinationCatalogueV1) -> None:
        """Bind the real application search service and current catalogue."""
        super().__init__()
        self._service = service
        self._catalogue = catalogue
        self.targets: list[TuiNavigationTargetV1] = []

    @property
    def workbench_search_service(self) -> WorkbenchSearchService:
        """Return the application-owned service without wrapping its result."""
        return self._service

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        """Return the already-admitted route catalogue."""
        return self._catalogue

    def navigate_to(self, target: TuiNavigationTargetV1) -> None:
        """Record the target instead of invoking an action or mounting a screen."""
        self.targets.append(target)

    @override
    def compose(self) -> ComposeResult:
        """Mount a concrete root screen so Textual can initialize providers."""
        yield Static("workbench")


async def _hits(provider: WorkbenchSearchProviderV1 | WorkbenchCommandProviderV1, query: str) -> list[Hit]:
    """Collect a provider's conventional query hits."""
    hits: list[Hit] = []
    async for hit in provider.search(query):
        if isinstance(hit, Hit):
            hits.append(hit)
    return hits


async def _discover(provider: WorkbenchCommandProviderV1) -> list[DiscoveryHit]:
    """Collect a command provider's empty-query discovery hits."""
    hits: list[DiscoveryHit] = []
    async for hit in provider.discover():
        if isinstance(hit, DiscoveryHit):
            hits.append(hit)
    return hits


@pytest.mark.asyncio
async def test_search_provider_preserves_application_stable_identity_and_admitted_action() -> None:
    """A search choice routes the authoritative result identity, never a row index."""
    action = TuiActionCandidateV1(action_candidate_id="operator.declaration.open", destination="workbench.declarations")
    service = WorkbenchSearchService([_document(action_candidate_id=action.action_candidate_id)])
    app = SearchHostApp(service=service, catalogue=_catalogue(actions=(action,)))

    async with app.run_test() as pilot:
        provider = WorkbenchSearchProviderV1(app.screen)
        hits = await _hits(provider, "declaration")
        assert len(hits) == 1
        hit = hits[0]
        assert hit.help is not None and len(hit.help) == 64
        hit.command()
        await pilot.pause()

    assert len(app.targets) == 1
    target = app.targets[0]
    assert target.destination == "workbench.declarations"
    assert target.focus.semantic_key == "search.declaration"
    assert target.focus.restore_token == hit.help
    assert target.action_candidate_id == action.action_candidate_id


@pytest.mark.asyncio
async def test_search_provider_skips_nonadmitted_and_unresolved_result_routes() -> None:
    """The palette does not turn stale search data into a reachable route."""
    action = TuiActionCandidateV1(action_candidate_id="operator.declaration.open", destination="workbench.declarations")
    service = WorkbenchSearchService(
        [
            _document(action_candidate_id="operator.declaration.missing"),
        ]
    )
    app = SearchHostApp(service=service, catalogue=_catalogue(actions=(action,)))

    async with app.run_test():
        provider = WorkbenchSearchProviderV1(app.screen)
        assert await _hits(provider, "declaration") == []


@pytest.mark.asyncio
async def test_command_provider_discovers_admitted_destinations_and_action_identity() -> None:
    """Discovery exposes only catalogue-admitted routes and action IDs."""
    action = TuiActionCandidateV1(action_candidate_id="operator.declaration.open", destination="workbench.declarations")
    app = SearchHostApp(service=WorkbenchSearchService([_document()]), catalogue=_catalogue(actions=(action,)))

    async with app.run_test() as pilot:
        provider = WorkbenchCommandProviderV1(app.screen)
        discovery = await _discover(provider)
        action_hit = next(hit for hit in discovery if hit.help == action.action_candidate_id)
        assert any(hit.help == "workbench.home" for hit in discovery)
        action_hit.command()
        await pilot.pause()

    assert app.targets == [
        TuiNavigationTargetV1(
            destination="workbench.declarations",
            focus={"destination": "workbench.declarations", "semantic_key": "action.operator.declaration.open"},
            action_candidate_id=action.action_candidate_id,
        )
    ]


def test_search_provider_has_no_network_or_application_search_reimplementation() -> None:
    """The TUI projects injected authorities and does not become a second search owner."""
    source = ast.parse((Path(__file__).parent.parent / "search.py").read_text(encoding="utf-8"))
    imported = {
        module for node in ast.walk(source) if isinstance(node, ast.ImportFrom) for module in ((node.module or ""),)
    }
    imported.update(alias.name for node in ast.walk(source) if isinstance(node, ast.Import) for alias in node.names)
    forbidden = {"httpx", "requests", "socket", "urllib", "pathlib", "sqlite3"}
    assert all(not any(part in forbidden for part in module.split(".")) for module in imported)
    assert "WorkbenchSearchService" not in imported
