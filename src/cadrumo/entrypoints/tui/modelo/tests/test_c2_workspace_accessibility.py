"""Availability proof for the C2 workspace read cohort.

Every destination in the closed route table is driven under a real Textual
pilot across four locales, three geometries and both themes, plus the
census, capability, refusal and keyboard properties the cohort depends on.

The matrix is DERIVED from the route table rather than listing destinations
again: a destination added without a proof would otherwise pass by being
absent from a hand-written list, which is the failure the derived census
exists to prevent one layer down.

On "route replacement": there was no route registry before this cohort, so
nothing was replaced. The census proves what the table BUILDS -- every
declared id resolves to exactly one factory and every factory answers one
declared id -- rather than asserting "zero remaining" over a structure that
never had entries to remove. An assertion of absence over an empty history
would hold vacuously forever.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from .....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from .....application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n._render import SUPPORTED_OUTPUT_LANGUAGES
from .....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..routes import (
    MODELO_WORKSPACE_DESTINATIONS,
    WORKSPACE_SELECTION_OUTCOME,
    declared_destination_ids,
    resolve_destination,
)
from ..view.controller import ModeloWorkspaceReadSession, admit_workspace_session

# The real-projection fixture lives beside the view tests. Sibling test
# packages do not share a conftest, so it is re-exposed here by name rather
# than duplicated -- one fixture, one definition, both packages.
from ..view.tests.conftest import bucket_and_repository, resolve_real_result

__all__ = ["bucket_and_repository"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The three landscape grids the shipped appearance gate renders at
#: (``test_visual_verification._SIZES``): 80x24 is the floor a real terminal
#: can be and where an overflowing layout starts hiding controls rather than
#: merely looking cramped, 120x40 an ordinary window, 200x50 a wide one.
#:
#: Restated rather than imported because that constant is private to a
#: different test package, and reaching for it would be the cross-package
#: private import this cohort has removed twice. The obligation that comes
#: with restating it is the same one ``dev/tui/_viewports.py`` carries: WHEN
#: THAT GATE'S MATRIX MOVES, THIS ONE FOLLOWS. Two accessibility matrices
#: asserting different definitions of "wide" would let a layout pass one and
#: fail the other with nothing to say which is authoritative.
_GEOMETRIES = SUPPORTED_TERMINAL_SIZES
_DESTINATION_IDS = sorted(MODELO_WORKSPACE_DESTINATIONS)


def _host_for(destination: str, session: ModeloWorkspaceReadSession) -> ScreenHostApp[None]:
    """Host one destination exactly as the production launcher does.

    Composes the shared :class:`ScreenHostApp` rather than defining a local
    host, so the matrix proves what an operator will actually see. A
    test-only host would omit the tokenised base CSS and the awaited push
    that the shared one carries, and would then be proving a rendering
    production never performs.
    """
    return ScreenHostApp(resolve_destination(destination)(session))


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


def test_the_destination_census_is_closed_and_one_to_one() -> None:
    """Every declared id routes, every route is declared, no factory is shared."""
    assert frozenset(MODELO_WORKSPACE_DESTINATIONS) == declared_destination_ids()
    assert len(set(MODELO_WORKSPACE_DESTINATIONS.values())) == len(MODELO_WORKSPACE_DESTINATIONS)
    assert len(MODELO_WORKSPACE_DESTINATIONS) == 6


def test_the_selection_outcome_names_a_routed_destination() -> None:
    """The C1 picker's landing destination must be one this table can build."""
    assert WORKSPACE_SELECTION_OUTCOME in MODELO_WORKSPACE_DESTINATIONS
    assert WORKSPACE_SELECTION_OUTCOME == "modelo.workspace.overview"


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", _DESTINATION_IDS)
async def test_every_destination_mounts_and_leaves_without_deciding_anything(
    destination: str,
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Each route builds a reachable read screen that returns no value."""
    bucket_id, repository = bucket_and_repository
    app = _host_for(destination, _session(bucket_id, repository))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is not None
        await pilot.press("q")
        await pilot.pause()

    assert app.return_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", _DESTINATION_IDS)
async def test_no_destination_offers_an_editing_affordance_before_c3(
    destination: str,
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The whole cohort is read-only, proven per destination rather than per file.

    Checked by widget type on the running screen: a screen could acquire an
    edit control through a composed widget without importing one, so what
    the module imports is not the property that matters.
    """
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = _host_for(destination, _session(bucket_id, repository))

    async with app.run_test() as pilot:
        await pilot.pause()
        for widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(widget), f"{destination} mounted {widget.__name__}"


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", _DESTINATION_IDS)
async def test_every_destination_mounts_in_all_four_locales(
    destination: str,
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Four locales, six destinations, no missing key and no crash.

    A missing catalogue entry raises at render rather than degrading, so
    mounting under every supported language is what proves the six
    namespaces are complete for every screen that reads them.
    """
    bucket_id, repository = bucket_and_repository
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            app = _host_for(destination, _session(bucket_id, repository))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                header = app.screen.query(Static)
                assert header, f"{destination} rendered nothing under {language}"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _GEOMETRIES, ids=SUPPORTED_TERMINAL_SIZE_IDS)
@pytest.mark.parametrize("destination", _DESTINATION_IDS)
async def test_every_destination_survives_three_geometries(
    destination: str,
    size: tuple[int, int],
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A narrow terminal must not drop content or crash the mount."""
    bucket_id, repository = bucket_and_repository
    app = _host_for(destination, _session(bucket_id, repository))

    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.screen.query(Static), f"{destination} rendered nothing at {size}"


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", _DESTINATION_IDS)
async def test_every_destination_toggles_between_both_shipped_themes(
    destination: str,
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The shared appearance toggle reaches every destination."""
    bucket_id, repository = bucket_and_repository
    app = _host_for(destination, _session(bucket_id, repository))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        first = app.theme
        await pilot.press("f3")
        await pilot.pause()
        assert app.theme != first
        assert {first, app.theme} == {CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME}


@pytest.mark.asyncio
async def test_the_overview_carries_the_complete_capability_denominator(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Capabilities are shown whole, never filtered to the interesting rows."""
    from ...components.widgets import ContentDataTable

    bucket_id, repository = bucket_and_repository
    app = _host_for("modelo.workspace.overview", _session(bucket_id, repository))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-capability-table", ContentDataTable)
        assert table.row_count == len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_the_admission_scoped_refusals_are_stated_on_both_refusing_destinations(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Results and provenance both refuse under a static inspection, and say so.

    Neither renders an empty table: an empty table would be a claim about
    the calculation, where the truth is a claim about the admission.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.projection.materialization_facet is None
    assert session.projection.provenance_facet is None

    for destination, notice_id, table_id in (
        ("modelo.workspace.results", "#workspace-results-not-applicable", "#workspace-results-table"),
        ("modelo.workspace.provenance", "#workspace-provenance-not-applicable", "#workspace-provenance-table"),
    ):
        app = _host_for(destination, session)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.screen.query(notice_id), f"{destination} did not state its refusal"
            assert not app.screen.query(table_id), f"{destination} mounted a table while refusing"
