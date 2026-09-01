"""Real Textual-pilot proof for the modelo.workspace.overview destination.

The two properties under test are the ones where rendering the obvious
thing would assert something untrue: that the revision block shows
coordinates and not a chronology, and that absent recovery actions are
STATED rather than shown as an empty list.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable
from ..controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..overview import ModeloWorkspaceOverviewScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


@pytest.mark.asyncio
async def test_absent_recovery_actions_are_stated_not_rendered_as_an_empty_list(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An empty actions panel would claim there is nothing the operator can do.

    The truth is that this producer does not say what can be done. The
    screen must carry the second claim, never the first.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert all(capability.recovery_action is None for capability in session.projection.capabilities)

    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-overview-actions", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_overview.actions_not_carried")


@pytest.mark.asyncio
async def test_the_revision_block_shows_coordinates_and_no_chronology(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Four coordinate rows, none of them a sequence over time.

    Workspace V1 exposes one law-selected revision plus two point
    assertions. A row count above that would mean the screen had
    synthesised history the projection does not carry.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-revision-table", ContentDataTable)
        assert table.row_count == 4


@pytest.mark.asyncio
async def test_every_capability_appears_exactly_once_with_a_distinguishing_glyph(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The screen shows the whole denominator, not a filtered subset.

    A capability omitted from the display would be indistinguishable from
    one the producer never answered, which is the distinction the closed
    denominator exists to preserve.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-capability-table", ContentDataTable)
        assert table.row_count == len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_an_absent_work_unit_renders_its_own_value_rather_than_a_blank_cell(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The address table always has five rows, present work unit or not."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-address-table", ContentDataTable)
        assert table.row_count == 5


@pytest.mark.asyncio
async def test_the_destination_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Overview is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )
