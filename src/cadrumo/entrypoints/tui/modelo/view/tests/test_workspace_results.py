"""Real Textual-pilot proof for the modelo.workspace.results destination.

The property under test is the one the ruling turns on: under an admission
that cannot separate computed results from operator inputs, this
destination REFUSES rather than rendering the same content the inputs
destination shows at a different address.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceCapabilityDisposition
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ..controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..results import ModeloWorkspaceResultsScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


def test_a_static_inspection_cannot_partition_results_from_inputs(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The precondition for the refusal, asserted against the real projection.

    The work-review facet is unavailable under this admission, so the
    partition has no source at all. Asserted on the projection itself
    rather than through the screen's own helper: checking the helper would
    prove only that it agrees with itself, whereas the refusal's real
    precondition is a fact about what the admission carries.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)

    assert session.projection.work_review.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE
    assert session.projection.work_review.review is None


@pytest.mark.asyncio
async def test_the_destination_refuses_rather_than_showing_the_inputs_content(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A typed not-applicable, never the whole facet under a results heading.

    Rendering the unpartitioned facet here would assert a partition the
    admission did not make, and would put identical content at two
    addresses -- which is what teaches an operator to distrust addresses.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceResultsScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-results-not-applicable", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_results.not_applicable")


@pytest.mark.asyncio
async def test_a_refusing_destination_mounts_no_results_table_at_all(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Refusal means no table, not an empty one.

    An empty results table would read as "this calculation produced no
    results", which is a claim about the calculation. The truth is a claim
    about the admission.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceResultsScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#workspace-results-table")
        assert not app.screen.query("#workspace-results-empty")
        assert not app.screen.query("#workspace-results-boundedness")


@pytest.mark.asyncio
async def test_the_destination_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Results is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceResultsScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )
