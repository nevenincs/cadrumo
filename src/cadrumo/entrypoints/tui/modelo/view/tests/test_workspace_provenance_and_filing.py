"""Real Textual-pilot proofs for the provenance and filing read destinations.

Both destinations exist to report narrow or absent content honestly, so the
properties under test are what they REFUSE to imply: provenance must not
arrange flat attribution rows into a causal shape, and filing must not
render two structurally different unknowns as one.
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
from ..filing import ModeloWorkspaceFilingScreen
from ..provenance import ModeloWorkspaceProvenanceScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


@pytest.mark.asyncio
async def test_provenance_refuses_when_the_admission_carries_no_facet(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A static inspection has no provenance facet, and the screen says so."""
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.projection.provenance_facet is None

    app = ScreenHostApp(ModeloWorkspaceProvenanceScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-provenance-not-applicable", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_provenance.not_applicable")
        assert not app.screen.query("#workspace-provenance-table")
        assert not app.screen.query("#workspace-provenance-boundedness")


@pytest.mark.asyncio
async def test_filing_distinguishes_a_permanent_unknown_from_a_pending_one(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Two capabilities, one disposition, TWO different reasons.

    Draft readiness is unmeasurable by design; export readiness is merely
    unbuilt. Rendering both as one uniform "unmeasured" would give an
    operator one remedy where there are two -- and one of them does not
    exist.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)

    app = ScreenHostApp(ModeloWorkspaceFilingScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-filing-table", ContentDataTable)
        assert table.row_count == 2

    structural = tr("flows.modelo_workspace_filing.why.draft_structural")
    pending = tr("flows.modelo_workspace_filing.why.export_pending_port")
    assert structural != pending, "the two filing unknowns must not share one explanation"


@pytest.mark.asyncio
async def test_filing_shows_only_its_own_two_capabilities(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Two of the five, selected by identity from the closed denominator."""
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert len(session.projection.capabilities) == len(ModeloWorkspaceCapabilityName)

    app = ScreenHostApp(ModeloWorkspaceFilingScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-filing-table", ContentDataTable)
        assert table.row_count == 2
        assert table.row_count < len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_filing_states_that_state_and_history_are_not_carried(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Absent filing state is disclosed, never implied by an empty panel."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceFilingScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-filing-state-not-carried", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_filing.state_not_carried")


@pytest.mark.asyncio
async def test_filing_offers_no_submission_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Live AEAT submission is prohibited, so no control may offer it."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceFilingScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(widget), f"the filing destination mounted {widget.__name__}"


@pytest.mark.asyncio
async def test_provenance_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Provenance is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceProvenanceScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(widget), f"the provenance destination mounted {widget.__name__}"
