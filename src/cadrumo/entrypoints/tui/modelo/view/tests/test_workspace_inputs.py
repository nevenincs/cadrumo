"""Real Textual-pilot proof for the modelo.workspace.inputs destination.

Drives the screen against a real admitted session and asserts the two
properties the row exists to guarantee: that no editing affordance is
offered before C3, and that an unmeasured axis is DISCLOSED rather than
rendered as a zero, a blank, or an absent column.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList, Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......core import OutputLanguage
from ......core.i18n import tr
from ....components.theme import install_cadrumo_themes
from ..controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..inputs import ModeloWorkspaceInputsScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _InputsHost(App[None]):
    """Minimal host so the destination runs under a real Textual pilot."""

    def __init__(self, session: ModeloWorkspaceReadSession) -> None:
        super().__init__()
        self._session = session

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.push_screen(ModeloWorkspaceInputsScreen(self._session))

    def compose(self) -> ComposeResult:
        return iter(())


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


@pytest.mark.asyncio
async def test_the_inputs_destination_offers_no_editing_affordance_before_c3(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The core C2 constraint: a read destination mounts no edit control.

    Checked by widget type rather than by reading the source, because the
    property that matters is what the operator can reach on the running
    screen, not what the module appears to import.
    """
    bucket_id, repository = bucket_and_repository
    app = _InputsHost(_session(bucket_id, repository))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )


@pytest.mark.asyncio
async def test_a_static_inspection_discloses_that_no_values_were_measured(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Absence is stated, never rendered as an empty table or a zero."""
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.projection.materialization_facet is None

    app = _InputsHost(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = app.screen.query_one("#workspace-inputs-values-disposition", Static)
        assert str(banner.content) == tr("flows.modelo_workspace_inputs.values_unmeasured")


@pytest.mark.asyncio
async def test_a_complete_page_shows_no_boundedness_notice_rather_than_an_empty_one(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An empty bordered notice reads as a rendering defect, so it is removed."""
    bucket_id, repository = bucket_and_repository
    app = _InputsHost(_session(bucket_id, repository))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#workspace-inputs-boundedness")


@pytest.mark.asyncio
async def test_the_destination_is_reachable_and_leaves_without_deciding_anything(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A read destination returns no value: it renders and exits, deciding nothing."""
    bucket_id, repository = bucket_and_repository
    app = _InputsHost(_session(bucket_id, repository))

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

    assert app.return_value is None
